"""AC-14 + AC-15 (SPEC.md, требование 13 «Изоляция пула от ролей»):
общая песочница doctor (не `_sandbox.CanarySandbox` — эти два критерия
не про сам прогон канарейки, а про курируемый слой роли/`doctor`,
песочница ближе к `tests/test_doctor.py::_DoctorTmpRootTest`, тот же
приём воспроизведён здесь напрямую, поскольку исходный класс локален
для `tests/test_doctor.py` и не экспортируется).

AC-14. Курируемый слой роли содержит запрещающие правила CLI на чтение
путей под каталогом пула и на команды клонирования/подключения
репозитория пула; тест: роль с этими правилами получает отказ CLI на
такой вызов до исполнения.

Проверяется СТАТИЧЕСКОЕ содержимое развёрнутого `.claude/settings.json`
(`permissions.deny`, документированный формат самого Claude Code CLI:
https://docs.claude.com/... permissions.deny — массив правил вида
`Read(...)`/`Bash(...)`), не живой запуск настоящего `claude`: раз
правило присутствует в `permissions.deny`, отказ CLI ДО исполнения —
задокументированный контракт самого инструмента (тот же класс доверия,
что мы не перепроверяем «git commit -m текст действительно попадает в
сообщение коммита» отдельным тестом на сам git). Живой прогон реального
`claude` с реальной моделью против этого файла — недетерминированный
и небесплатный (требует сети/токена/решения модели действительно
попытаться вызвать инструмент) вне охвата offline unittest; это не
«лень», а тот же класс зависимости, что уже принят AC-7 этой задачи
(markers.py) — внешний инструмент, не код этого репозитория.

AC-15. После прогона канарейки и при `doctor` логи шагов ролей
проверяются на упоминание каталога пула, имени его репозитория и GUID
любого шаблона; тест: лог с таким упоминанием поднимает алерт
`kind=incident`, лог без него — не поднимает.

Наблюдается через ОДИН из трёх сигналов требования 13б — упоминание
каталога пула (`~/.artel-canary`, ЛИТЕРАЛЬНО зафиксировано требованием
1 SPEC, не implementation-деталь) — двух других (имя репозитория пула,
GUID шаблона) SPEC явно относит к «Не входит» (инициализация и
содержимое пула — ручная настройка Оператора), стабильного значения
для теста тут взять неоткуда. Точка наблюдения — `doctor.cmd_doctor()`,
единственный из двух триггеров требования 13б, доступный СНАРУЖИ
настоящего прогона канарейки (второй — «после каждого прогона
канарейки» — часть механики `canary`, покрытой отдельными AC-1..12).

Красен до реализации:
- AC-14: `docs/reference/role-home/claude/` сегодня несёт только
  `CLAUDE.md` — файла `settings.json` там ещё нет,
  `_deploy_role_home_reference` копирует дерево референса как есть, так
  что `config.ROLE_CONFIG_DIR/settings.json` не появляется вовсе после
  `cmd_init`; `assertTrue(settings_path.exists())` красный по этой
  причине, не по опечатке песочницы.
- AC-15: `doctor.cmd_doctor()` сегодня не читает `config.LOGS` вовсе
  (нет такого шага в `all_checks`/нигде в `doctor.py`) — первая
  проверка (чистый лог не поднимает инцидент) проходит уже сегодня
  ТРИВИАЛЬНО (аудита ещё нет, поднять алерт нечему), но вторая
  (лог с упоминанием `.artel-canary` обязан поднять `kind=incident`)
  красна по факту отсутствия самой проверки — `open_alerts` после
  прогона с «утёкшим» логом пуст, тест падает на `assertTrue`.
"""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import agent_log, alerts, catalog, config, doctor, store  # noqa: E402
from tests.sandbox import TmpRootTest, claude_only_popen, claude_only_run  # noqa: E402

# Тот же литерал, что называет требование 1 SPEC (каталог пула вне
# корня пульта) — не имя реализации, а буквальная строка из SPEC.
POOL_DIR_MARKER = ".artel-canary"


class _FakeLiveSmokeProc:
    """Замена `subprocess.Popen` для `doctor.live_smoke` — тот же приём,
    что `tests/test_doctor.py::FakeLiveSmokeProc` (не импортируется
    оттуда напрямую: тот класс локален для соседнего файла тестов, не
    часть переиспользуемой `tests.sandbox`)."""

    def __init__(self, output: str, returncode: int = 0):
        self.output = output
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self.output, None

    def kill(self) -> None:
        pass

    def wait(self, timeout=None) -> int:
        return self.returncode


def _result_event(usd: float) -> str:
    return f'{{"type":"result","total_cost_usd":{usd},"usage":{{}}}}\n'


class RolePoolIsolationSandbox(TmpRootTest):
    """Песочница doctor: та же, что `tests/test_doctor.py::
    _DoctorTmpRootTest` (skills/templates + docs/codebase-map.md +
    CLAUDE.md, keychain-заглушка, ambient-токен сброшен) — без неё
    `isolation_smoke()`/`check_token` роняют `doctor.cmd_doctor()`
    ещё до интересующей нас части (ENOENT на skills роли, отсутствие
    токена)."""

    def setUp(self):
        super().setUp()
        import shutil
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: " + "0" * 40 + "\n---\n\n# Карта\n",
            encoding="utf-8")
        # `_deploy_role_home_reference` читает референс от `config.ROOT`
        # (патченного на `self.root` этой песочницей), не от настоящего
        # корня репозитория — без этой копии AC-14 краснел бы по ложной
        # причине («пусто, потому что песочница не завела референс»), не
        # по отсутствию `settings.json` в реализации.
        shutil.copytree(REPO_ROOT / "docs" / "reference",
                        self.root / "docs" / "reference")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")

        from orchestrator import runner
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        env_patcher = mock.patch.dict(
            "os.environ",
            {"CLAUDE_CODE_OAUTH_TOKEN": "", "ANTHROPIC_API_KEY": ""})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        self.capture(catalog.cmd_init)

    @staticmethod
    def _which(name):
        return "/usr/bin/claude" if name == "claude" else None

    def run_doctor_healthy(self) -> str:
        """`doctor.cmd_doctor()` под теми же подменами, что уже
        доказанно дают «здоровый» прогон без посторонних инцидентов
        (`tests/test_doctor.py::DoctorCommandTest.
        test_healthy_repo_prints_ok_and_does_not_exit`, тот же набор
        трёх патчей) — `SystemExit` (код ≠0 по НЕсвязанной с этим
        тестом причине, например отсутствию `targets.yaml`) допустим и
        проглатывается: этот тест смотрит только на `alerts`, не на код
        выхода `doctor`."""
        buf = io.StringIO()
        with mock.patch.object(doctor.shutil, "which", side_effect=self._which), \
                mock.patch.object(doctor.subprocess, "run", side_effect=claude_only_run(
                    f"{config.CLI_VERSION_PIN} (Claude Code)\n")), \
                mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                    _FakeLiveSmokeProc(_result_event(0.01)))):
            try:
                with redirect_stdout(buf):
                    doctor.cmd_doctor()
            except SystemExit:
                pass
        return buf.getvalue()


class RoleCliDenyRulesTest(RolePoolIsolationSandbox):

    def test_ac14_role_curated_layer_denies_pool_reads_and_clone_commands(self):
        """Развёрнутый курируемый слой роли (`.artel/home/.claude/
        settings.json`, из референса `docs/reference/role-home/claude/`)
        несёт правила `permissions.deny`, покрывающие ОБЕ половины
        требования 13а: чтение путей под каталогом пула (упоминание
        `.artel-canary`) и команды клонирования/подключения репозитория
        (`git clone`, `gh repo clone`, `git remote add`) — раз правило
        лежит в `permissions.deny`, отказ CLI до исполнения гарантирован
        самим Claude Code (см. докстринг модуля), отдельно проверять
        живым прогоном не нужно.

        Ловит мутацию: разработчик добавляет `settings.json` только с
        частью правил (например, только запрет чтения пула, забыв про
        `git clone`/`gh repo clone`/`git remote add`, или наоборот) —
        соответствующий `assertIn` по недостающей подстроке падает,
        отличая «частично реализовано» от «реализовано полностью».
        """
        settings_path = config.ROLE_CONFIG_DIR / "settings.json"
        self.assertTrue(
            settings_path.exists(),
            f"курируемый слой роли не несёт settings.json после `init`: "
            f"{settings_path} — добавь `docs/reference/role-home/claude/"
            f"settings.json`, `_deploy_role_home_reference` разворачивает "
            f"дерево референса как есть")

        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self.fail(f"settings.json курируемого слоя роли — "
                     f"невалидный JSON: {exc}")

        deny = (data.get("permissions") or {}).get("deny")
        self.assertIsInstance(
            deny, list,
            f"settings.json: нет списка permissions.deny (документированный "
            f"формат Claude Code) — {data}")
        combined = "\n".join(str(rule) for rule in deny)

        self.assertIn(
            POOL_DIR_MARKER, combined,
            f"permissions.deny не запрещает чтение путей под каталогом "
            f"пула ({POOL_DIR_MARKER}): {deny}")
        for needle in ("git clone", "gh repo clone", "git remote add"):
            self.assertIn(
                needle, combined,
                f"permissions.deny не запрещает команду {needle!r} "
                f"клонирования/подключения репозитория пула: {deny}")


class RoleLogPoolLeakAlertTest(RolePoolIsolationSandbox):

    def test_ac15_log_mentioning_pool_dir_raises_incident_clean_log_does_not(self):
        """Два прогона `doctor.cmd_doctor()` на одном и том же (иначе
        здоровом) пульте: (1) с ОБЫЧНЫМ логом шага роли (без единого
        упоминания пула) в `config.LOGS` — открытых `kind=incident`
        алертов после прогона быть не должно; (2) следом — ещё один
        лог, в котором роль по ошибке напечатала путь каталога пула
        (`~/.artel-canary/...`) — после этого прогона обязан появиться
        хотя бы один открытый `kind=incident` алерт (требование 13б).

        Ловит мутацию: разработчик реализует аудит логов, но не
        подключает его к `alerts.raise_alert(..., kind="incident", ...)`
        (например, только печатает предупреждение в stdout `doctor`,
        тем же классом ошибки, что уже описан у AC-12 этой же SPEC) —
        тогда `store.open_alerts(conn, "incident")` после второго
        прогона останется таким же пустым, каким было после первого,
        и `assertTrue` по нему падает.
        """
        conn = store.db()

        clean_log = agent_log.new_agent_log("00000000000000000000000000", "developer")
        clean_log.write_text(
            "Обычный шаг роли developer: правка кода, коммит, готово.\n",
            encoding="utf-8")

        self.run_doctor_healthy()
        baseline = alerts.open_alerts(conn, "incident")
        self.assertEqual(
            baseline, [],
            f"обычный лог без упоминания пула уже поднял incident-алерт(ы), "
            f"проверка слишком широкая: {baseline}")

        leaking_log = agent_log.new_agent_log("00000000000000000000000000", "developer")
        leaking_log.write_text(
            f"Шаг роли по ошибке прочитал файл пула: "
            f"~/{POOL_DIR_MARKER}/shablon-3.md — вывод команды ниже.\n",
            encoding="utf-8")

        self.run_doctor_healthy()
        after = alerts.open_alerts(conn, "incident")
        self.assertTrue(
            after,
            f"лог с упоминанием каталога пула ({POOL_DIR_MARKER}) не "
            f"поднял ни одного incident-алерта после `doctor`: {after}")


if __name__ == "__main__":
    unittest.main()
