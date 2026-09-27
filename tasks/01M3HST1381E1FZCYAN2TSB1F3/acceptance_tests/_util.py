"""Общие помощники планки 01M3HST1381E1FZCYAN2TSB1F3 (клон канарейки
находит вход Codex: указатель связки ключей в доме роли клона).

Пять предметов, нужные больше чем одному файлу планки:

1. **Указатель связки ключей** (`POINTER_REL`, `POINTER_BYTES`) —
   относительный путь из формулировки AC-1 и байты фикстуры. Байты
   заведомо не текст референса дома роли: AC-1 требует равенства
   байт-в-байт, и на пустом файле такое равенство держалось бы само.
2. **Наборы-фикстуры** — набор с ролью на провайдере `codex`
   (`SET_NAME`) и набор, ни одна роль которого на Codex не идёт
   (`CLAUDE_SET_NAME`). Второй нужен AC-2: «набор, ни одна роль которого
   не идёт провайдером codex» — это не то же самое, что набор по
   умолчанию, и оба случая критерий называет отдельно.
3. **Песочница прогона** (`CodexClonePlankSandbox`) — НАСТОЯЩИЙ git-корень
   пульта с `roles.yaml`/`models.yaml`/`docs/reference/role-home/` в
   коммите (чтобы холодный старт клона реально разворачивал дом роли),
   засеянный дом роли ПУЛЬТА с указателем и посторонними файлами, пул из
   одного шаблона. Один приём прогона — `run()`: возвращает `Outcome` со
   всем, что критерии наблюдают (текст отчёта, вызовы `subprocess`,
   вызовы узла проверки входа, временные каталоги клона, факт вождения).
4. **Перехват процессов** (`RunSpy`) — подмена `subprocess.run` САМОГО
   модуля `subprocess` (не атрибута одного пакета): критерии AC-4/AC-7
   говорят «ни одного `git clone`» и «`security` не зовётся» о прогоне
   ЦЕЛИКОМ, а каждый модуль пульта зовёт `subprocess.run` через своё
   `import subprocess` — патч одного `doctor.subprocess` оставил бы
   `canary.subprocess` невидимым. `codex … login status` перехватывается
   ответом фикстуры, остальное проходит к настоящему `subprocess.run`:
   живой Codex CLI не запускается ни разу.
5. **Чтение main** (`main_source`, `main_tree_files`,
   `unittest_method_names`) — исходники коммита main читаются `git show`/
   `git ls-tree` в репозитории рабочей копии, а не с диска ветки (AC-10).

Артефакты задачи (SPEC.md/PLAN.md/REVIEW.md) планка не читает вовсе: её
предмет — код, документация и наблюдаемое поведение команды.

Имя файла с ведущим подчёркиванием — единственная форма общего кода
планки, которую checkpoint не отбрасывает (skills/test-authoring.md).
Лёгкую песочницу переходов FSM этот файл не переопределяет и не копирует:
`RealGitSandbox` импортируется из `tests/sandbox.py`.
"""
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import namedtuple
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (canary, config, doctor, models,  # noqa: E402
                          pool_seal, providers, roles, runner, store,
                          workspace)
from orchestrator.providers import codex as codex_provider  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK_ID = "01M3HST1381E1FZCYAN2TSB1F3"

#: Коммит main, с которым планка сверяет состав тестов (голова main на
#: момент заведения задачи).
MAIN_SHA = "b21f01e6"

TESTS_DIR = REPO_ROOT / "tests"
STACK_MD = REPO_ROOT / "docs" / "stack.md"

# --- указатель связки ключей --------------------------------------------

#: Относительный путь указателя внутри дома роли — РОВНО тот, что называет
#: формулировка AC-1/AC-3.
POINTER_REL = "Library/Preferences/com.apple.security.plist"

#: Байты указателя-фикстуры: непустые и заведомо уникальные, чтобы
#: равенство байт-в-байт (AC-1) нельзя было получить пустым файлом или
#: файлом, собранным заново.
POINTER_BYTES = (b"bplist00\xd1\x01\x02"
                 b"plank-01M3HST1381E1FZCYAN2TSB1F3-keychain-pointer\n")

#: Посторонние файлы дома роли ПУЛЬТА: ни один из них в дом клона попасть
#: не должен (AC-3). Два из них лежат под `Library/` — рядом с указателем и
#: в соседнем каталоге связок: «скопировали весь `Library/`» и
#: «скопировали весь `Preferences/`» обязаны быть различимы от «скопировали
#: ровно указатель».
PULT_ONLY_FILES = {
    "Library/Preferences/com.apple.other.plist": b"postoronnij plist\n",
    "Library/Keychains/login.keychain-db": b"soderzhimoe svyazki klyuchej\n",
    ".claude/plank-marker.txt": b"marker doma roli pulta\n",
    "plank-secret.txt": b"sekret pulta\n",
}

# --- наборы-фикстуры ----------------------------------------------------

#: Набор с ролью на провайдере `codex`. Обе роли — одного яруса на ОДНОЙ
#: модели (разные модели одного яруса — отказ `_set_tiers_or_exit`).
SET_NAME = "codex-strong"
SET_MODEL = "gpt-5.6-terra"
SET_ROLES = ("developer", "reviewer")

#: Набор, ни одна роль которого не идёт провайдером `codex` (AC-2): та же
#: роль, но модель провайдера по умолчанию.
CLAUDE_SET_NAME = "claude-only"
CLAUDE_SET_MODEL = "claude-opus-5"

#: Имя провайдера Codex — из реестра, не литералом: реестр провайдеров
#: крутилка пульта, а не константа планки.
CODEX_PROVIDER = codex_provider.CLI_NAME

GOOD_SETS = {
    SET_NAME: {role: {"provider": CODEX_PROVIDER, "model": SET_MODEL}
               for role in SET_ROLES},
    CLAUDE_SET_NAME: {role: {"provider": providers.DEFAULT_PROVIDER,
                             "model": CLAUDE_SET_MODEL}
                      for role in SET_ROLES},
}

#: Часовой «параметр `set_name` не передан вовсе» — прогон без `--set`.
OMIT = object()

#: Тело шаблона пула: маркер «эскалация не ожидается» держит исход прогона
#: без расхождения.
POOL_TEMPLATE_TITLE = "vkhod-codex-v-klone"
POOL_TEMPLATE_TEXT = (
    "# Синтетическое ТЗ планки указателя связки ключей\n\n"
    f"{canary.MARK_EXPECT_ESCALATION_NO}\n\n"
    "Поправь одну строку и остановись.\n")

# --- перехват процессов -------------------------------------------------

#: Каталог-заглушка объявленных инструментов манифеста: `argv[0]` вызова
#: `codex login status` собирается из `runner.declared_tool_path`, и без
#: подмены он либо указал бы на живой CLI машины Оператора, либо отказал
#: бы `OSError` на машине без Codex.
STUB_BIN = "/plank-01M3HST-stub/bin"

#: Ответ `codex login status` для дома роли, вход которого подтверждён, и
#: для дома, который не вошёл. Оба — в том потоке, в который печатает
#: настоящий 0.155.1 (`stderr`), и оба сверяются регуляркой самого
#: провайдера, а не литералом планки.
LOGGED_IN_CHATGPT = "Logged in using ChatGPT"
NOT_LOGGED_IN = "Not logged in"

#: Префикс временных каталогов эфемерного клона (`_ephemeral_clone`).
CLONE_TMP_PREFIX = "artel-canary-"

_REAL_RUN = subprocess.run

#: Команда, меняющая связку ключей по умолчанию, и вообще единственный CLI,
#: которым пульт способен и прочитать связку, и переписать указатель
#: (`orchestrator/keychain.py`, рецепт `doctor.CODEX_AUTH_RECIPE`): AC-7
#: требует, чтобы прогон не звал её ни разу.
KEYCHAIN_CLI = "security"


def is_login_status(argv: list) -> bool:
    """Вызов `codex … login status`: имя CLI нулевым элементом и обе
    подкоманды. Не по полному равенству argv: пары авторизации между
    `argv[0]` и подкомандой — предмет отдельной сверки, не признак."""
    return (bool(argv) and Path(argv[0]).name == codex_provider.CLI_NAME
            and "login" in argv and "status" in argv)


class RunSpy:
    """Подмена `subprocess.run` модуля `subprocess`: отвечает фикстурой на
    `codex … login status`, всё остальное отдаёт настоящему `subprocess.
    run`, запоминая КАЖДЫЙ вызов.

    Настоящий Codex CLI не запускается ни разу: единственный вызов, за
    который планка отвечает сама, — проверка входа.
    """

    def __init__(self, status: str = LOGGED_IN_CHATGPT, returncode: int = 0):
        self.status, self.returncode = status, returncode
        self.calls = []
        self.login_calls = []

    def __call__(self, args, *rest, **kwargs):
        argv = ([args] if isinstance(args, (str, Path))
                else [str(item) for item in args])
        self.calls.append(argv)
        if is_login_status(argv):
            self.login_calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, self.returncode, "",
                                               f"{self.status}\n")
        return _REAL_RUN(args, *rest, **kwargs)

    def git_subcommands(self) -> list:
        """Подкоманды git всех перехваченных вызовов — вход проверки «ни
        одного `git clone`» (AC-4)."""
        return [argv[1] for argv in self.calls
                if len(argv) > 1 and Path(argv[0]).name == "git"]

    def keychain_calls(self) -> list:
        """Вызовы CLI связки ключей (AC-7)."""
        return [argv for argv in self.calls
                if argv and Path(argv[0]).name == KEYCHAIN_CLI]


# --- наблюдение за узлом проверки входа ---------------------------------

#: Один вызов узла проверки входа: роль-аргумент, `config.ROOT` в момент
#: вызова (у вызова изнутри клона это каталог клона) и вернувшаяся строка.
AuthCall = namedtuple("AuthCall", "role root check")


def auth_check_targets() -> tuple:
    """(настоящая `doctor.check_codex_chatgpt_auth`, места её подмены).

    Мест два рода: атрибут пакета `doctor` (вызов `doctor.check_codex_
    chatgpt_auth(...)`, как его зовёт `providers/codex.py:501`) и ЛЮБОЕ имя
    модуля `canary`, значение которого — та же самая функция (импорт
    `from .doctor import check_codex_chatgpt_auth`, в том числе под
    псевдонимом). Так наблюдение «зовётся тот же узел, что у doctor»
    (AC-6) не зависит от того, каким из двух законных способов
    реализация до узла добралась.
    """
    real = doctor.check_codex_chatgpt_auth
    targets = [(doctor, "check_codex_chatgpt_auth")]
    targets += [(canary, name) for name, value in vars(canary).items()
                if value is real]
    return real, targets


# --- исход прогона ------------------------------------------------------

#: `text` — вывод прогона (stdout, stderr и сообщение `SystemExit` одним
#: текстом: критерий AC-5 говорит «напечатана причина», не фиксируя поток);
#: `exited` — сообщение `SystemExit`, если команда отказала, иначе `None`;
#: `spy` — перехват процессов; `auth_calls` — вызовы узла проверки входа;
#: `clone_dirs` — временные каталоги эфемерного клона; `drive_calls` —
#: вызовы вождения задачи (каждый шаг роли идёт только оттуда);
#: `task_ids` — задачи, заведённые прогоном; `probe` — снимок, сделанный
#: ВНУТРИ клона.
Outcome = namedtuple(
    "Outcome",
    "text exited spy auth_calls clone_dirs drive_calls task_ids probe")


class _ProbeStop(Exception):
    """Прерывает прогон сразу после снятия наблюдения внутри клона."""


def normalized(text: str) -> str:
    """Текст, сведённый к одному пробелу между словами — сверка длинного
    `detail` (рецепт `doctor.CODEX_AUTH_RECIPE`) не должна зависеть от
    того, как отчёт разложил его по строкам."""
    return " ".join(text.split())


def files_under(base: Path) -> set:
    """Относительные пути ФАЙЛОВ дерева `base` (`set()` — каталога нет)."""
    if not base.is_dir():
        return set()
    return {str(path.relative_to(base)) for path in base.rglob("*")
            if path.is_file()}


def snapshot(base: Path) -> dict:
    """{относительный путь -> байты} дерева `base` — вход сверки «дом роли
    пульта до и после команды совпадает» (AC-7)."""
    return {rel: (base / rel).read_bytes() for rel in files_under(base)}


def cold_start_role_home_files() -> set:
    """Относительные пути файлов, которые кладёт в дом роли ХОЛОДНЫЙ СТАРТ
    (`catalog._deploy_role_home_reference`): референс каждого провайдера
    реестра под своим развёрнутым именем.

    Считается от `providers.home_references()` в момент вызова, то есть от
    `config.ROOT` песочницы, а не перечислением имён: состав референса —
    крутилка Оператора, и его правка не должна красить планку.
    """
    expected = set()
    for reference in providers.home_references():
        if not reference.reference.is_dir():
            continue
        expected |= {f"{reference.deployed_name}/{rel}"
                     for rel in files_under(reference.reference)}
    return expected


def codex_roles_of_set(set_name: str) -> list:
    """Роли, идущие провайдером Codex на наборе `set_name` — те же ВСЕ роли
    сдвинутого яруса, которые считает сам прогон (`canary._roles_of_tiers`).

    Нужна там, где критерий говорит «набор, где хотя бы одна роль идёт
    провайдером codex» / «ни одна роль»: состав ярусов живёт в
    `roles.yaml`, и перечислять его литералом планка не вправе.
    """
    entries = GOOD_SETS[set_name]
    tiers = {roles.model_tier(role): entry["provider"]
             for role, entry in entries.items()}
    affected = []
    for role, entry in roles.load().items():
        if not isinstance(entry, dict) or entry.get("executor") != "agent":
            continue
        if tiers.get(roles.model_tier(role)) == CODEX_PROVIDER:
            affected.append(role)
    return sorted(affected)


# --- песочница прогона --------------------------------------------------

class CodexClonePlankSandbox(RealGitSandbox):
    """Настоящий git-корень пульта (целевой sha прогона несёт `roles.yaml`,
    `models.yaml` и референс дома роли), засеянный дом роли ПУЛЬТА с
    указателем связки ключей и посторонними файлами, локальный слой с
    наборами, пул из одного шаблона.

    Ни один шаг роли и ни один живой CLI провайдера не исполняются: шаги
    подменены синтетическим вождением, `codex login status` — ответом
    фикстуры.
    """

    def setUp(self):
        super().setUp()
        for name in ("roles.yaml", "models.yaml"):
            shutil.copy2(REPO_ROOT / name, self.root / name)
        # Референс дома роли — в КОММИТ: без него холодный старт клона
        # (`catalog._deploy_role_home_reference`) не развернул бы дом роли
        # клона вовсе, и сверка «дом клона содержит ровно то, что кладёт
        # холодный старт» (AC-2) выродилась бы в сверку двух пустот.
        reference_rel = Path("docs") / "reference" / "role-home"
        shutil.copytree(REPO_ROOT / reference_rel, self.root / reference_rel)
        self.git("add", "-A")
        self.git("commit", "-q", "-m",
                 "карта исполнителей, каталог моделей и референс дома роли")
        self.head = self.git("rev-parse", "HEAD").strip()

        self.write_local_layer(GOOD_SETS)
        self.pult_home = config.ROLE_HOME
        self.pointer = self.pult_home / POINTER_REL
        self.seed_pult_role_home()

        pool = tempfile.mkdtemp(prefix="artel-plank-pool-")
        self.addCleanup(shutil.rmtree, pool, ignore_errors=True)
        self.pool_dir = Path(pool)
        (self.pool_dir / f"{POOL_TEMPLATE_TITLE}.md").write_text(
            POOL_TEMPLATE_TEXT, encoding="utf-8")

        for target, attr, value in (
                (canary, "_pool_dir", lambda: self.pool_dir),
                # Восстановление пула из `catalog.cmd_init` внутри клона
                # трогало бы РЕАЛЬНЫЙ `~/.artel-canary` Оператора — к
                # предмету планки отношения не имеет.
                (pool_seal, "restore_pool_if_missing", lambda conn: None),
                # `argv[0]` вызова `codex login status`: без подмены резолв
                # манифеста либо указал бы на живой CLI машины, либо
                # отказал бы `OSError` на машине без Codex.
                (runner, "declared_tool_path",
                 lambda name: f"{STUB_BIN}/{name}")):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.conn = store.db()
        self._task_counter = 0

    def write_local_layer(self, sets: dict) -> None:
        """Локальный слой ПУЛЬТА: текст шаблона плюс раздел наборов
        вложенными блочными отображениями (потоковых отображений
        `orchestrator/yamlmini.py` не читает вовсе)."""
        lines = [models.local_template_text(), f"{models.CANARY_SETS_KEY}:"]
        for name, entries in sets.items():
            lines.append(f"  {name}:")
            for role, entry in entries.items():
                lines.append(f"    {role}:")
                lines += [f"      {key}: {value}"
                          for key, value in entry.items()]
        config.MODELS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        config.MODELS_LOCAL.write_text("\n".join(lines) + "\n",
                                       encoding="utf-8")

    def seed_pult_role_home(self, with_pointer: bool = True) -> None:
        """Дом роли ПУЛЬТА: развёрнутый референс (как после `init`),
        указатель связки ключей и посторонние файлы.

        `with_pointer=False` — сценарий требования 3: указателя в доме роли
        пульта нет вовсе (AC-4).
        """
        shutil.rmtree(self.pult_home, ignore_errors=True)
        for reference in providers.home_references():
            if reference.reference.is_dir():
                shutil.copytree(reference.reference,
                                self.pult_home / reference.deployed_name)
        for rel, payload in PULT_ONLY_FILES.items():
            path = self.pult_home / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        if with_pointer:
            self.pointer.parent.mkdir(parents=True, exist_ok=True)
            self.pointer.write_bytes(POINTER_BYTES)

    # -- прогон -----------------------------------------------------------

    @contextmanager
    def _watched_tempdirs(self, clone_dirs: list):
        """Временные каталоги эфемерного клона по мере их создания:
        `tempfile.mkdtemp`/`shutil.rmtree` — единственный способ, которым
        `_ephemeral_clone` их заводит и убирает (его докстринг)."""
        real_mkdtemp = tempfile.mkdtemp

        def watched(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            if str(kwargs.get("prefix") or "").startswith(CLONE_TMP_PREFIX):
                clone_dirs.append(Path(path))
            return path

        with mock.patch.object(canary.tempfile, "mkdtemp", watched):
            yield

    def run_canary(self, set_name=OMIT, spy: RunSpy = None,
                   probe=None) -> Outcome:
        """Прогон одной канареечной задачи командой `canary.cmd_canary`.

        Имя метода — не `run`: `unittest.TestCase.run` перекрывать нельзя,
        песочница сама является тест-кейсом.

        Настоящее: разбор набора, отказы до клона, эфемерный клон целиком
        (включая холодный старт клона и его дом роли), проверка входа
        узлом `doctor` на ответе фикстуры, уборка клона.

        Синтетическое: заведение задачи (`catalog.cmd_new`), её worktree и
        вождение (`_drive_task`) — ни одного шага роли и ни одного вызова
        живого CLI.

        `probe` — снимок, снимаемый ВНУТРИ клона в момент, когда клон
        собран, но задача ещё не заведена; после снимка прогон прерывается
        исключением (проверка уборки клона на пути исключения, AC-8).
        """
        spy = spy or RunSpy()
        clone_dirs, drive_calls, task_ids = [], [], []
        probed = {}
        real_auth, targets = auth_check_targets()
        auth_calls = []

        def spy_auth(role):
            check = real_auth(role)
            auth_calls.append(AuthCall(role, Path(config.ROOT), check))
            return check

        def fake_cmd_new(title, tz_path=None, canary=False, **kwargs):
            if probe is not None:
                probed.update(probe())
                raise _ProbeStop
            self._task_counter += 1
            task_id = "01M3HSTPLANKA" + f"{self._task_counter:013d}"
            conn = store.db()
            store.insert_task(conn, task_id, title, "in_dev",
                              f"task/{task_id.lower()}-kanarejka",
                              config.DEFAULT_TARGET, 10.0, is_canary=True)
            task_ids.append(task_id)
            return task_id

        def fake_drive(conn, task_id):
            drive_calls.append(task_id)
            store.journal(conn, task_id, canary.CANARY_MARK_ACTOR,
                          canary._MERGE_GATE_KILL_ACTION,
                          "синтетический штатный исход планки")
            conn.execute("UPDATE tasks SET state='killed', spent_usd=1.0 "
                         "WHERE id=?", (task_id,))
            conn.commit()

        out, err = io.StringIO(), io.StringIO()
        exited = None
        patches = [mock.patch.object(target, attr, spy_auth)
                   for target, attr in targets]
        patches += [
            mock.patch.object(canary.catalog, "cmd_new", fake_cmd_new),
            mock.patch.object(canary, "_drive_task", fake_drive),
            mock.patch.object(workspace, "ensure",
                              lambda task_id, branch: (self.root, None)),
            # Патч САМОГО модуля `subprocess`, не атрибута одного пакета:
            # см. пункт 4 модульного докстринга.
            mock.patch.object(subprocess, "run", spy),
        ]
        kwargs = {"k": 1, "sha": self.head,
                  "templates": [POOL_TEMPLATE_TITLE]}
        if set_name is not OMIT:
            kwargs["set_name"] = set_name
        try:
            with self._watched_tempdirs(clone_dirs):
                for patcher in patches:
                    patcher.start()
                try:
                    with redirect_stdout(out), redirect_stderr(err):
                        canary.cmd_canary(**kwargs)
                finally:
                    for patcher in reversed(patches):
                        patcher.stop()
        except SystemExit as exc:
            exited = str(exc)
        except _ProbeStop:
            pass

        text = out.getvalue() + err.getvalue() + (exited or "")
        return Outcome(text, exited, spy, auth_calls, clone_dirs, drive_calls,
                       task_ids, probed)

    def clone_probe(self, set_name, probe, spy: RunSpy = None) -> Outcome:
        """`run_canary()` с наблюдением внутри клона (параметр `probe`)."""
        return self.run_canary(set_name=set_name, spy=spy, probe=probe)

    def clone_role_home_files(self, set_name) -> tuple:
        """(перечень файлов дома роли клона, каталог клона) — снимок,
        снятый ВНУТРИ клона после его подготовки."""
        outcome = self.clone_probe(
            set_name,
            lambda: {"files": files_under(config.ROLE_HOME),
                     "home": Path(config.ROLE_HOME),
                     "root": Path(config.ROOT)})
        self.assertTrue(outcome.probe, "наблюдение внутри клона не снято: "
                                      f"{outcome.text}")
        return outcome.probe["files"], outcome.probe["root"]


# --- чтение main --------------------------------------------------------

def _git(*args) -> tuple:
    """(код возврата, stdout) команды git в РЕПОЗИТОРИИ рабочей копии.

    Не `gitcmd` (он ходит в `config.ROOT`): песочница планки уводит
    `config.ROOT` во временный каталог, а исходники main лежат в
    репозитории.
    """
    result = _REAL_RUN(["git", *args], cwd=REPO_ROOT, capture_output=True,
                       text=True)
    return result.returncode, result.stdout


def main_source(rel_path: str) -> str:
    """Текст файла `rel_path` в коммите `MAIN_SHA` — только через git."""
    code, text = _git("show", f"{MAIN_SHA}:{rel_path}")
    if code != 0:
        raise AssertionError(f"{MAIN_SHA}:{rel_path} не прочитан")
    return text


def main_tree_files(rel_dir: str) -> list:
    """Пути файлов каталога `rel_dir` в дереве коммита `MAIN_SHA`."""
    code, text = _git("ls-tree", "-r", "--name-only", MAIN_SHA, rel_dir)
    if code != 0:
        raise AssertionError(f"дерево {MAIN_SHA} не прочитано")
    return [line for line in text.splitlines() if line]


TEST_METHOD_RE = re.compile(r"^\s*def (test_\w+)", re.M)
GUARD_FUNC_RE = re.compile(r"^def ((?:check|scan)_\w+)", re.M)


def unittest_method_names(source: str) -> set:
    return set(TEST_METHOD_RE.findall(source))


def guard_function_names(source: str) -> set:
    return set(GUARD_FUNC_RE.findall(source))


class DocsSectionTest(unittest.TestCase):
    """Разбор раздела `docs/stack.md` — без песочницы: предмет AC-9 текст
    документации, а не поведение команды."""

    SECTION_TITLE = "## Провайдер codex"

    def section_text(self) -> str:
        """Текст раздела «Провайдер codex» до следующего заголовка того же
        уровня: правило, дописанное в ДРУГОЙ раздел, критерия не
        закрывает."""
        lines = STACK_MD.read_text(encoding="utf-8").splitlines()
        starts = [index for index, line in enumerate(lines)
                  if line.strip() == self.SECTION_TITLE]
        self.assertTrue(starts, f"в docs/stack.md нет раздела "
                                f"«{self.SECTION_TITLE}»")
        start = starts[0] + 1
        end = next((index for index in range(start, len(lines))
                    if lines[index].startswith("## ")), len(lines))
        return "\n".join(lines[start:end]).lower()
