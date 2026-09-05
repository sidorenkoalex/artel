"""Общая песочница приёмочных тестов задачи 01M1NSR5M5THYRC0RFWPMVE2DW
(«Пул канарейки в репозитории в зашифрованном виде: seal, restore,
манифест GUID»).

Не тестовый файл сам по себе (`unittest discover` его не подхватывает —
имя не начинается с `test_`), только общая инфраструктура для соседних
`test_*.py` этого каталога: тот же приём, что и `_sandbox.py` части 1
(01M1NEEWH5K1XPFRDGRMPYSBXJ) — общий код не копируется в каждый файл
планки заново.

`PoolBaseSandbox` — минимальная песочница: временный `config.ROOT`
(`tests.sandbox.TmpRootTest`) + отдельный от него фейковый `HOME` вне
корня пульта (`Path.home()` подменена, требование 1 SPEC) с каталогом
пула `~/.artel-canary` + подмена `orchestrator.keychain.token` на
детерминированный ключ (AC-2: ключ добывается ТЕМ ЖЕ механизмом, что
токены ролей, — тем же `keychain.token`, реального macOS keychain в
песочнице нет и не нужно). Каталог пула ПУСТ по умолчанию — наполняет
его сам тест через `write_pool_templates`.

`PoolDoctorSandbox` — то же плюс `skills/`, `templates/`, `docs/
codebase-map.md`, `CLAUDE.md`, `targets.yaml` (тот же набор, что
`tests/test_doctor.py::_DoctorTmpRootTest`) — без него `doctor.
cmd_doctor()` падает на ENOENT/ambient-токене ещё до сценария пула,
который проверяет тест; нужна только двум файлам планки, которым
интересен именно `doctor` (`--restore`/предупреждение о незапечатанных
правках), не всем.

Команда пульта («канарейка pool-seal», «init», «doctor --restore») —
единственный контракт, который называет сама SPEC (требования 2-3);
имя внутреннего Python-модуля/функции, которая её реализует, — решение
разработчика. Тесты поэтому идут через настоящий CLI-диспетчер
(`orchestrator/artel.py::main`), не через прямой импорт ещё
не существующей функции: `run_cli` — тот же приём, что `run_cli` в
`_sandbox.py` части 1. Команды может не быть в таблице до реализации
задачи — `SystemExit` («Неизвестная команда …») перехватывается и
попадает в возвращаемый текст вместо падения всего прогона `discover`.
"""
import hashlib
import io
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artel, catalog, config, keychain, roles  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

# Литералы самой SPEC (не деталь реализации): требование 1 — каталог
# пула вне корня пульта; требования 2/4 — пути файлов в репозитории.
POOL_DIR_NAME = ".artel-canary"
SEALED_REL_PATH = ("canary", "pool.sealed")
GUIDS_REL_PATH = ("canary", "guids.txt")

# Ключ-заглушка песочницы (AC-2): значение не имеет значения само по
# себе, важно только что seal/restore используют ОДНО и то же значение,
# добытое ОДНИМ и тем же вызовом `keychain.token` — тем самым
# перепроверяется общий по коду canary-задаче механизм с токенами
# ролей, не конкретный slot (тот SPEC не называет, имя слота — решение
# разработчика).
FAKE_POOL_KEY = "unit-test-pool-key-0123456789abcdef"


def _known_role_token_slots() -> set:
    """Все слоты keychain, которые сегодня заняты токенами РОЛЕЙ
    (`roles.yaml`, реальный файл пульта — не патчен ни в одном
    `config`-атрибуте песочницы) — нужно отличать их от слота ключа
    пула в моке `keychain.token` ниже: без этого один и тот же мок
    «любой слот -> ключ пула» подставил бы ключ пула ТУДА, где
    `runner.role_env()` на самом деле спрашивает токен подписки роли
    (`CLAUDE_CODE_OAUTH_TOKEN`), и AC-17 (`test_pool_key_not_leaked.py`)
    ложно решил бы, что ключ пула утёк в окружение роли — артефакт
    самого мока, не проверяемое им свойство."""
    try:
        role_names = list(roles.load().keys())
    except roles.RolesError:
        role_names = []
    slots = set(roles.token_slots(None))
    for name in role_names:
        try:
            slots.update(roles.token_slots(name))
        except roles.RolesError:
            continue
    return slots


def dir_fingerprint(path: Path) -> str:
    """Отпечаток НАБОРА файлов каталога (имя + содержимое каждого,
    отсортированные) — независимая от реализации проверка «тот же набор
    файлов пула» (AC-16): считается тестом заново, не читает никакой
    отпечаток, который мог бы напечатать сам `pool-seal`."""
    h = hashlib.sha256()
    files = sorted(p for p in path.iterdir() if p.is_file())
    for f in files:
        h.update(f.name.encode("utf-8"))
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


class PoolBaseSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()

        home_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(home_tmp.cleanup)
        self.fake_home = Path(home_tmp.name).resolve()
        self.pool_dir = self.fake_home / POOL_DIR_NAME
        home_patcher = mock.patch.object(Path, "home",
                                         return_value=self.fake_home)
        home_patcher.start()
        self.addCleanup(home_patcher.stop)
        env_patcher = mock.patch.dict("os.environ", {"HOME": str(self.fake_home)})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        self.pool_key = FAKE_POOL_KEY
        role_slots = _known_role_token_slots()

        def fake_token(slot):
            if slot in role_slots:
                return "test-role-subscription-token-unrelated-to-pool-key"
            return self.pool_key

        kc_patcher = mock.patch.object(keychain, "token", fake_token)
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)

    @property
    def sealed_path(self) -> Path:
        return config.ROOT.joinpath(*SEALED_REL_PATH)

    @property
    def guids_path(self) -> Path:
        return config.ROOT.joinpath(*GUIDS_REL_PATH)

    def write_pool_templates(self, texts: dict) -> Path:
        """`*.md` файлы открытого пула — В ФЕЙКОВОМ HOME (вне `self.root`,
        требование 1 SPEC: Оператор держит пул вне корня пульта)."""
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        for name, text in texts.items():
            (self.pool_dir / name).write_text(text, encoding="utf-8")
        return self.pool_dir

    def run_cli(self, *argv_tail: str) -> str:
        argv = ["artel.py", *argv_tail]
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv):
            with redirect_stdout(buf):
                try:
                    artel.main()
                except SystemExit as exc:
                    buf.write(f"\n[SystemExit] {exc}\n")
        return buf.getvalue()

    def seal(self) -> str:
        return self.run_cli("canary", "pool-seal")

    def restore_via_init(self) -> str:
        return self.run_cli("init")

    def restore_via_doctor(self) -> str:
        return self.run_cli("doctor", "--restore")


class PoolDoctorSandbox(PoolBaseSandbox):
    """`doctor.cmd_doctor()` живой (не мок) — нужен минимум окружения,
    без которого он падает по НЕсвязанным с пулом причинам (тот же
    набор, что `tests/test_doctor.py::_DoctorTmpRootTest`)."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: " + "0" * 40 + "\n---\n\n# Карта\n",
            encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        config.TARGETS.write_text(
            "targets:\n"
            "  artel:\n"
            "    forge: github\n"
            "    url: https://example.invalid/artel\n"
            "    base: main\n"
            "    token_slot: artel-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n",
            encoding="utf-8")

        env_patcher = mock.patch.dict(
            "os.environ",
            {"CLAUDE_CODE_OAUTH_TOKEN": "", "ANTHROPIC_API_KEY": ""})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        # Схема БД (`store.migrate()` без неё — no-op, T028) и курируемый
        # слой роли (`_deploy_role_home_reference`) — бутстрап через
        # ПРЯМОЙ вызов `cmd_init`, не через `self.run_cli("init")`: та же
        # команда — один из двух путей restore под тестом в соседних
        # файлах планки, здесь она только заводит песочницу до сценария
        # (пул ещё пуст — восстанавливать нечего, `init` не более чем
        # печатает "OK").
        self.capture(catalog.cmd_init)

    def run_doctor(self, *extra_args: str) -> str:
        return self.run_cli("doctor", *extra_args)
