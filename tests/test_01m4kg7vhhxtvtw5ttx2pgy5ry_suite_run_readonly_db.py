"""`suite-run` из процесса роли без права записи в БД пульта: итог, отчёт,
дослав журнала, замок, пределы и место логов прогона.

Группа: долгоживущий

Красен до реализации: запись журнала задачи, не удавшаяся в процессе без права записи в БД (сигнал «длительность близка к пределу»), сегодня теряется — процесс пульта её не досылает (AC-5); логи прогона `suite-run` (основной и `-base`) пишутся прямо в `config.LOGS`, а не внутрь `config.LOGS / "suite-run"`, и отчёт называет путь вне него (AC-9); AC-4, AC-6 и AC-8 держат свойства, которые прежний код соблюдает и в процессе без записи в БД, и зелены с рождения.

Стенд — настоящий git-репозиторий песочницы (`RealGitSandbox`): закоммиченный
набор `tests/` — зелёная база ветки задачи, рабочее дерево несёт набор
сценария (зелёный, красный, висящий дольше предела). Рабочая копия задачи
подменена корнем песочницы (`workspace.path`), дерево приложений PLAN —
тем же корнем (`appendix_tree.suite_tree`); база ветки считается
настоящим git, прогон базы идёт во временной рабочей копии, прогоны —
настоящим pytest командой профиля тестов артели.

Процесс роли: в окружении признак роли (`config.ARTEL_ROLE_ENV`,
`config.ARTEL_TASK_ENV`), а открытие БД пульта (`store.db`) отдаёт
соединение только на чтение (`mode=ro`) — запись в нём отказывает
`sqlite3.OperationalError`, как отказывает открытию на запись песочница
Codex. Процесс пульта — без признака роли и с обычным `store.db`.

Фоновый процесс команды (`subprocess.Popen` интерпретатора пульта с
номером задачи в argv) исполняется в процессе теста тем же кодом
(`python -c <код>` либо `python -m <модуль>`), в окружении, которое
команда ему передала, и под тем же запретом записи в БД: песочница роли
распространяется и на её потомков. Прочие запуски процессов — настоящие.

Часы подменены (`time.monotonic`, `time.perf_counter`, `time.time`):
каждый тест набора сценария, исполняясь, дописывает строку в файл
отметок, и каждая новая строка сдвигает часы процесса на заданную долю
предела. Так прогон, длящийся секунды, «длится» 85% предела и оставляет
сигнал «длительность близка к пределу» — запись журнала задачи. Пределы,
доли, роль процесса и состав набора — от зерна; зерно печатается и входит
в текст провала.
"""
import contextlib
import io
import os
import random
import re
import runpy
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, appendix_tree, config, project_profile,
                          store, suite_lock, suite_run, workspace)
from tests.sandbox import RealGitSandbox, _alive_foreign_pid, _dead_pid

TASK = "T001"
OTHER = "T002"
BRANCH = "task/t001-suite-run"
OTHER_BRANCH = "task/t002-gate"
ROLES = ("test_author", "reviewer")
PROBE = Path("tests") / "test_probe.py"
PROFILE_HEAD = "    test_profile:\n"
LIMIT_FIELD = re.compile(r"^ *full_suite_timeout_sec:.*\n", re.MULTILINE)
LOG_PATH = re.compile(r"(/[^\s;«»]+?\.log)(?![\w.-])")

REAL_MONOTONIC = time.monotonic
REAL_PERF_COUNTER = time.perf_counter
REAL_TIME = time.time


def real(path) -> str:
    return os.path.realpath(str(path))


def is_within(path: str, ancestor: str) -> bool:
    """`path` совпадает с `ancestor` или лежит под ним (оба — realpath)."""
    return path == ancestor or path.startswith(ancestor.rstrip(os.sep) + os.sep)


def readonly_db() -> sqlite3.Connection:
    """БД пульта только на чтение: запись отказывает `OperationalError`."""
    conn = sqlite3.connect(f"{Path(config.DB).resolve().as_uri()}?mode=ro",
                           uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def probe_suite(marks: Path, kind: str, failing: int = 1,
                passing: int = 0) -> str:
    """Набор `tests/` сценария: зелёный и красный тест пишут отметку
    прогона; висящий тест держится дольше предела; `failing`/`passing`
    — состав красного набора без отметок."""
    mark = (f"    with open({str(marks)!r}, 'a', encoding='utf-8') as fh:\n"
            f"        fh.write('прогон\\n')\n")
    if kind == "green":
        return f"def test_probe():\n{mark}    assert True\n"
    if kind == "red":
        return f"def test_probe():\n{mark}    assert False, 'красный намеренно'\n"
    if kind == "timeout":
        return "import time\n\n\ndef test_probe():\n    time.sleep(60)\n"
    tests = [f"def test_red_{i}():\n    assert False, 'красный {i}'\n"
             for i in range(failing)]
    tests += [f"def test_green_{i}():\n    assert True\n"
              for i in range(passing)]
    return "\n\n".join(tests)


class ShiftedClock:
    """Часы процесса: каждая новая строка файла отметок сдвигает их вперёд
    на `shift` секунд — прогон «длится» столько, сколько задал сценарий."""

    def __init__(self, marks: Path):
        self.marks = marks
        self.shift = 0.0
        self.seen = 0
        self.offset = 0.0

    def current_offset(self) -> float:
        try:
            count = len(self.marks.read_text(encoding="utf-8").splitlines())
        except FileNotFoundError:
            count = 0
        if count > self.seen:
            self.offset += (count - self.seen) * self.shift
            self.seen = count
        return self.offset

    def monotonic(self) -> float:
        return REAL_MONOTONIC() + self.current_offset()

    def perf_counter(self) -> float:
        return REAL_PERF_COUNTER() + self.current_offset()

    def time(self) -> float:
        return REAL_TIME() + self.current_offset()


def passed_limit(call):
    """Предел, переданный в `acceptance.run_full_suite` вызовом `call`
    (именованный `limit` либо шестой позиционный)."""
    if "limit" in call.kwargs:
        return call.kwargs["limit"]
    return call.args[5] if len(call.args) > 5 else None


class SuiteRunStand(RealGitSandbox):
    """Задачи артели в БД, зелёная база ветки в git, набор сценария в
    рабочем дереве; процесс роли и процесс пульта — контексты теста."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.role = self.rng.choice(ROLES)
        self.dead_pid = _dead_pid()

        marks_dir = tempfile.mkdtemp(prefix="artel-marks-")
        self.addCleanup(shutil.rmtree, marks_dir, ignore_errors=True)
        self.marks = Path(marks_dir) / "marks.txt"
        self.clock = ShiftedClock(self.marks)
        for name in ("monotonic", "perf_counter", "time"):
            patcher = mock.patch(f"time.{name}", getattr(self.clock, name))
            patcher.start()
            self.addCleanup(patcher.stop)
        for target, attr, value in (
                (config, "FULL_SUITE_WORKERS", 1),
                (workspace, "path", lambda *a, **k: self.root),
                (appendix_tree, "suite_tree", lambda *a, **k:
                 contextlib.nullcontext(
                     appendix_tree.SuiteTree(self.root, "", "", "")))):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           config.ARTEL_TASK_ENV: ""})
        env.start()
        self.addCleanup(env.stop)

        # Пульт держит БД открытой — файлы WAL на месте, чтение только на
        # чтение их и находит.
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "suite-run роли", "in_dev",
                          BRANCH, config.DEFAULT_TARGET, 25.0)
        store.insert_task(self.conn, OTHER, "Гейт пульта", "in_dev",
                          OTHER_BRANCH, config.DEFAULT_TARGET, 25.0)
        (self.root / PROBE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / PROBE).write_text("def test_base():\n    assert True\n",
                                       encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база ветки")
        self.git("branch", BRANCH)
        self.git("branch", OTHER_BRANCH)

    def msg(self, text: str = "") -> str:
        return f"зерно {self.seed}, роль {self.role}: {text}"

    def random_limit(self) -> int:
        return self.rng.randint(1000, 3000)

    def set_profile_limit(self, limit: int) -> tuple[int, str]:
        """Поле `full_suite_timeout_sec` профиля артели; возвращает
        действующий предел и источник пульта."""
        text = LIMIT_FIELD.sub("", config.TARGETS.read_text(encoding="utf-8"))
        self.assertIn(PROFILE_HEAD, text, self.msg("нет профиля артели"))
        text = text.replace(
            PROFILE_HEAD,
            f"{PROFILE_HEAD}      full_suite_timeout_sec: {limit}\n", 1)
        config.TARGETS.write_text(text, encoding="utf-8")
        return project_profile.full_suite_limit(config.DEFAULT_TARGET)

    def write_suite(self, kind: str, **counts) -> None:
        (self.root / PROBE).write_text(probe_suite(self.marks, kind, **counts),
                                       encoding="utf-8")

    @contextlib.contextmanager
    def role_process(self):
        """Процесс роли: признак роли в окружении, БД только на чтение."""
        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: self.role,
                                          config.ARTEL_TASK_ENV: TASK}), \
                mock.patch.object(store, "db", readonly_db):
            yield

    def process(self, role: bool):
        return self.role_process() if role else contextlib.nullcontext()

    def run_child(self, tokens: list, env) -> None:
        """Фоновый процесс команды — в процессе теста, тем же кодом."""
        saved = sys.argv
        environ = (mock.patch.dict(os.environ, env, clear=True)
                   if env is not None else contextlib.nullcontext())
        try:
            with environ:
                if tokens[1] == "-c":
                    sys.argv = ["-c", *tokens[3:]]
                    exec(compile(tokens[2], "<suite-run child>", "exec"),
                         {"__name__": "__main__"})
                elif tokens[1] == "-m":
                    sys.argv = [tokens[2], *tokens[3:]]
                    runpy.run_module(tokens[2], run_name="__main__",
                                     alter_sys=True)
                else:
                    self.fail(self.msg(f"фоновый процесс неизвестной формы: "
                                       f"{tokens}"))
        finally:
            sys.argv = saved

    def child_popen(self, live_pid: int | None = None):
        """Подмена `subprocess.Popen`: запуск фонового процесса команды
        (интерпретатор пульта, номер задачи в argv) исполняется здесь же
        (`live_pid is None`) либо только отмечается живым чужим pid;
        прочие запуски — настоящие."""
        real_popen = subprocess.Popen
        launched = []

        def popen(argv, *args, **kwargs):
            tokens = ([str(t) for t in argv]
                      if isinstance(argv, (list, tuple)) else [])
            if tokens and tokens[0] == sys.executable and TASK in tokens:
                launched.append(tokens)
                if live_pid is not None:
                    return mock.Mock(pid=live_pid)
                self.run_child(tokens, kwargs.get("env"))
                return mock.Mock(pid=self.dead_pid)
            return real_popen(argv, *args, **kwargs)

        return popen, launched

    def start_run(self, role: bool = True, live_pid: int | None = None) -> str:
        """`suite-run <id>` процессом роли (или пульта); вывод команды."""
        popen, launched = self.child_popen(live_pid)
        buf = io.StringIO()
        with self.process(role), \
                mock.patch.object(subprocess, "Popen", popen), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                suite_run.cmd_suite_run([TASK])
            except SystemExit as exc:
                self.fail(self.msg(f"suite-run отказал: {exc.code}\n"
                                   f"{buf.getvalue()}"))
        self.assertTrue(launched, self.msg(
            f"фоновый процесс не запущен:\n{buf.getvalue()}"))
        return buf.getvalue()

    def wait_report(self, role: bool = True) -> tuple[str, object]:
        """`suite-run <id> --wait 0`: вывод и код выхода (`None` — 0)."""
        buf, code = io.StringIO(), None
        with self.process(role), contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            try:
                suite_run.cmd_suite_run([TASK, "--wait", "0"])
            except SystemExit as exc:
                code = exc.code
        return buf.getvalue(), code

    def near_records(self) -> list:
        return [dict(row) for row in store.task_steps(store.db(), TASK)
                if row["action"] == acceptance.SUITE_NEAR_LIMIT_ACTION]


class ReadonlyDbOutcomeTest(SuiteRunStand):

    def test_ac4_readonly_db_run_reaches_same_outcome_and_report(self):
        """Прогон без права записи в БД доходит до итога и отчёта; итог прежний.

        Сценарий: процесс роли (БД только на чтение) запускает
        `suite-run <id>` дважды, в случайном порядке — зелёный и красный
        набор, каждый «длится» 82–95% случайного предела профиля, так что
        прогон пытается записать сигнал в журнал задачи и получает отказ
        БД. `suite-run <id> --wait 0` того же процесса печатает отчёт
        прогона: у зелёного — «зелёный прогон» и код 0, у красного —
        «красный прогон» и код 1; обрыва исключением нет, запись в журнал
        задачи из процесса роли не попала.

        Ловит мутацию: сбой записи журнала из процесса роли не перехвачен
        (вынесен из `try` либо перехват сужен до `OSError`) — отчёт «прогон
        оборван исключением» вместо итога; сбой записи считается провалом
        прогона — зелёный набор отчитывается красным или кодом 1."""
        limit, _ = self.set_profile_limit(self.random_limit())
        order = ["green", "red"]
        self.rng.shuffle(order)
        for kind in order:
            with self.subTest(kind=kind):
                self.write_suite(kind)
                self.clock.shift = self.rng.uniform(0.82, 0.95) * limit
                started = self.start_run(role=True)
                report, code = self.wait_report(role=True)
                text = self.msg(f"{kind}:\n{started}\n{report}")
                self.assertNotIn("исключением", report, text)
                if kind == "green":
                    self.assertIn("зелёный прогон", report, text)
                    self.assertIn(code, (None, 0), text)
                else:
                    self.assertIn("красный прогон", report, text)
                    self.assertEqual(code, 1, text)
                self.assertEqual(self.near_records(), [], text)


class JournalRedeliveryTest(SuiteRunStand):

    def test_ac5_pult_process_delivers_journal_record(self):
        """Запись журнала, не удавшаяся процессу роли, досылается процессом пульта.

        Сценарий: процесс роли (БД только на чтение) гоняет `suite-run
        <id>` зелёным набором, «длящимся» 82–95% случайного предела, и
        забирает отчёт `--wait`; записи «длительность близка к пределу» в
        журнале задачи нет — БД отказала. Затем процесс пульта (обычная
        БД, без признака роли) делает штатные входы в хозяйство
        `suite-run`: Оператор забирает отчёт `suite-run <id> --wait 0`, а
        гейт гоняет полный набор задачи (`acceptance.full_suite`, часы
        больше не сдвигаются — свой сигнал гейт не пишет). После них в
        журнале задачи есть запись «длительность близка к пределу».

        Ловит мутацию: процесс роли откладывает несостоявшуюся запись, но
        процесс пульта её не читает (досыл не вызван ни командой, ни
        замком гейта) — запись теряется; отложенная запись пишется в
        журнал под чужой задачей либо удаляется до записи."""
        limit, _ = self.set_profile_limit(self.random_limit())
        self.write_suite("green")
        self.clock.shift = self.rng.uniform(0.82, 0.95) * limit
        started = self.start_run(role=True)
        report, code = self.wait_report(role=True)
        self.assertIn("зелёный прогон", report, self.msg(f"{started}\n{report}"))
        self.assertEqual(self.near_records(), [], self.msg(
            "процесс роли без права записи всё же записал журнал"))

        self.clock.shift = 0.0
        pult_report, _ = self.wait_report(role=False)
        gate = acceptance.full_suite(self.root, TASK, fresh=True)
        self.assertGreaterEqual(len(self.near_records()), 1, self.msg(
            f"запись не дослана; отчёт пульта:\n{pult_report}\n"
            f"гейт: {gate.outcome} {gate.detail}"))


class SharedLockTest(SuiteRunStand):

    def gate_holds_role_refused(self) -> None:
        """Замок держит гейт пульта — `suite-run` процесса роли не стартует."""
        self.assertIsNone(suite_lock.acquire(OTHER, kind=suite_lock.KIND_GATE),
                          self.msg("замок гейта не взят"))
        self.addCleanup(suite_lock.release)
        popen, launched = self.child_popen()
        buf = io.StringIO()
        with self.role_process(), \
                mock.patch.object(subprocess, "Popen", popen), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            with self.assertRaises(SystemExit, msg=self.msg(buf.getvalue())) \
                    as refused:
                suite_run.cmd_suite_run([TASK])
        self.assertEqual(launched, [], self.msg(
            f"прогон роли запущен при замке гейта:\n{buf.getvalue()}"))
        self.assertIn(OTHER, str(refused.exception.code), self.msg())
        suite_lock.release()

    def role_holds_gate_waits(self) -> None:
        """Замок держит `suite-run` процесса роли — гейт пульта не стартует."""
        self.write_suite("green")
        live = _alive_foreign_pid(self)
        self.start_run(role=True, live_pid=live)
        with mock.patch.object(config, "FULL_SUITE_LOCK_WAIT_SEC", 0):
            gate = acceptance.full_suite(self.root, OTHER, fresh=True)
        self.assertEqual(gate.outcome, acceptance.FULL_SUITE_NOT_STARTED,
                         self.msg(f"гейт: {gate.outcome} {gate.detail}"))
        self.assertFalse(self.marks.exists(), self.msg(
            "pytest гейта запущен при замке прогона роли"))

    def test_ac6_role_suite_run_and_gate_share_one_lock_file(self):
        """Прогон роли и гейт пульта — один файл замка: при одном держателе второй не стартует.

        Сценарий (в случайном порядке, каждый на свежем замке): (а) гейт
        пульта взял замок полных прогонов (`suite_lock`, вид «гейт»), и
        `suite-run <id>` процесса роли (БД только на чтение) отказывает,
        называя задачу гейта, — фоновый прогон не запускается; (б)
        `suite-run <id>` процесса роли запущен и передал замок живому
        фоновому процессу, и полный прогон гейта пульта
        (`acceptance.full_suite`, ожидание замка — 0 с) кончается исходом
        «прогон не начат», pytest гейта не запускался.

        Ловит мутацию: замок `suite-run` процесса роли перенесён в
        доступный ему каталог по признаку роли или песочницы (рабочая
        копия, отдельный файл) — прогон роли и гейт берут разные файлы и
        идут одновременно; при сбое записи замка процесс роли идёт без
        замка."""
        steps = [self.gate_holds_role_refused, self.role_holds_gate_waits]
        self.rng.shuffle(steps)
        for step in steps:
            with self.subTest(step=step.__name__):
                with contextlib.suppress(FileNotFoundError):
                    suite_lock.path().unlink()
                step()


class LimitUnchangedTest(SuiteRunStand):

    def test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome(self):
        """Без права записи в БД предел прогона — из профиля, превышение — тот же исход «предел».

        Сценарий: процесс роли (БД только на чтение); случайный предел
        профиля артели — каждый вызов `acceptance.run_full_suite` прогона
        `suite-run` (ветка и база) получает действующий предел пульта
        `project_profile.full_suite_limit` с его источником. Затем предел
        профиля 3 с и висящий набор: отчёт `--wait` называет исход «прогон
        не уложился в предел 3 с» с источником предела, код 1.

        Ловит мутацию: процесс без записи в БД не читает предел профиля
        (обход ради отказа БД) и гоняет с запасным
        `config.FULL_SUITE_TIMEOUT_SEC` либо без предела; превышение
        предела в таком процессе отчитывается иначе (красным, «не начат»,
        обрывом исключением)."""
        limit, source = self.set_profile_limit(self.random_limit())
        self.write_suite("green")
        with mock.patch.object(acceptance, "run_full_suite",
                               wraps=acceptance.run_full_suite) as spy:
            started = self.start_run(role=True)
            report, _ = self.wait_report(role=True)
        self.assertTrue(spy.call_args_list, self.msg(f"{started}\n{report}"))
        for call in spy.call_args_list:
            self.assertEqual(passed_limit(call), (limit, source),
                             self.msg(f"{call}\n{report}"))

        short, short_source = self.set_profile_limit(3)
        self.write_suite("timeout")
        self.start_run(role=True)
        report, code = self.wait_report(role=True)
        self.assertRegex(report, rf"не уложился в предел {short} с",
                         self.msg(report))
        self.assertIn(short_source, report, self.msg(report))
        self.assertEqual(code, 1, self.msg(report))


class LogPlacementTest(SuiteRunStand):

    def test_ac9_suite_run_logs_live_under_suite_run_dir(self):
        """Логи прогона `suite-run` (ветки и базы) — внутри `config.LOGS / "suite-run"`.

        Сценарий: процесс роли или пульта (случайно) запускает `suite-run
        <id>` красным набором случайного состава; база ветки не посчитана
        заранее, и прогон базы идёт тут же. После прогона ни одного нового
        файла `*.log` в `config.LOGS` вне `config.LOGS / "suite-run"` нет;
        среди новых — лог прогона базы (`-base`); каждый путь `*.log`,
        который называют вывод запуска и отчёт `--wait`, лежит под
        `config.LOGS / "suite-run"` и файл по нему есть; отчёт называет
        хотя бы один.

        Ловит мутацию: перенесён только основной лог, а лог базы
        (`-base`) остаётся в `config.LOGS`; номер прогона по-прежнему
        выдаёт `agent_log.new_agent_log`, создающий пустой файл в
        `config.LOGS`; отчёт называет прежний путь в `config.LOGS`, а
        пишется лог в другое место."""
        role = self.rng.choice((True, False))
        failing, passing = self.rng.randint(1, 3), self.rng.randint(0, 2)
        self.write_suite("mixed", failing=failing, passing=passing)
        logs = Path(config.LOGS)
        before = set(logs.rglob("*.log")) if logs.exists() else set()
        started = self.start_run(role=role)
        report, code = self.wait_report(role=role)
        text = self.msg(f"процесс роли: {role}\n{started}\n{report}")
        self.assertEqual(code, 1, text)
        suite_dir = real(logs / "suite-run")
        new = set(logs.rglob("*.log")) - before
        outside = sorted(str(p) for p in new
                         if not is_within(real(p), suite_dir))
        self.assertEqual(outside, [], text)
        self.assertTrue(any("-base" in p.name for p in new),
                        self.msg(f"лога базы нет среди {sorted(map(str, new))}"
                                 f"\n{report}"))
        named = LOG_PATH.findall(report)
        self.assertTrue(named, text)
        for path in LOG_PATH.findall(started) + named:
            with self.subTest(path=path):
                self.assertTrue(is_within(real(path), suite_dir), text)
                self.assertTrue(Path(path).is_file(), text)


if __name__ == "__main__":
    unittest.main()
