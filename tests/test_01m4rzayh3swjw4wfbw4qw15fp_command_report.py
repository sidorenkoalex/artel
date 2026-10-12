"""Команда `explore-stats` и блок «Разведка ролей» отчёта `report`.

Команда вызывается через диспетчер `artel.main` с подменённым `sys.argv` в
окружении Оператора (без `ARTEL_ROLE`, `HOME` чужой); отчёт — через
`report.cmd_report`. Журнал и задачи — в БД песочницы (`tests/sandbox.py`),
логи шагов — синтетические файлы в `config.LOGS` песочницы; настоящие
`.artel/logs` и `state.db` не читаются. Метки времени записей ставятся от
текущих часов с запасом в часы, так что команде и отчёту не нужна подмена
часов. Номера задач и часть чисел случайные; зерно печатается и входит в
текст провала.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/explore_metric.py ещё нет — имя explore_metric равно None и заглушка сводки не ставится; команды explore-stats нет в таблице artel.main, блока «Разведка ролей» в отчёте нет.
"""
import contextlib
import hashlib
import html as html_lib
import io
import os
import random
import re
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, report, retro, store
from orchestrator.providers import claude

try:
    from orchestrator import explore_metric
except ImportError:  # модуля ещё нет: тесты красны, сбор файла цел
    explore_metric = None
from tests.sandbox import SchemaConnTmpRootTest

PREFIX = claude.TOOL_CALL_LINE_PREFIX
STARTED = "agent run started"
KNOWN = retro.TOKEN_JOURNAL_ACTIONS[0]
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
DEFAULT_ROLES = ("developer", "test_author", "reviewer", "analyst")
BLOCK_TITLE = "Разведка ролей (последние 7 дней)"
NOT_AVAILABLE = "н/д"
LABELS = (
    "шагов:", "медиана вызовов:", "медиана до первой правки кода:",
    "правка кода не наступила:", "медиана до первой записи:",
    "запись не наступила:", "доля разведки:", "шагов без правки:",
    "правок не распознано:", "записей вне рабочей копии:",
    "логов не найдено:", "топ-10 файлов:", "путь обрезан:",
    "топ-10 искомых строк:",
)
CODE_EDIT = ("Edit", "wt:orchestrator/x.py")


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%SZ")


def reads(count: int, tag: str) -> list:
    return [("Read", f"wt:src/{tag}_{i}.py") for i in range(count)]


def number(text: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}\s*(\d+(?:[.,]\d+)?)", text)
    return match.group(1) if match else None


def explore_block_text(page: str) -> str:
    """Текст блока «Разведка ролей»: от заголовка до следующего блока."""
    start = page.find("Разведка ролей")
    if start < 0:
        return ""
    ends = [i for i in (page.find("<section", start), page.find("</main>", start))
            if i >= 0]
    fragment = page[start:min(ends) if ends else len(page)]
    return html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))


class SharedConnection:
    """Подмена `store.db`: одно соединение на весь прогон и счёт открытий."""

    def __init__(self, conn):
        self.conn = conn
        self.opened = 0

    def __call__(self):
        self.opened += 1
        return Borrowed(self.conn)


class Borrowed:
    """Соединение, которое вызывающий не может закрыть."""

    def __init__(self, conn):
        self.conn = conn

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def close(self) -> None:
        return None

    def __enter__(self):
        return self.conn.__enter__()

    def __exit__(self, *exc_info):
        return self.conn.__exit__(*exc_info)


class StepsTrace:
    """Счётчик SQL-запросов соединения к таблице `steps`."""

    def __init__(self, conn):
        self.conn = conn
        self.count = 0

    def __enter__(self):
        self.conn.set_trace_callback(self.trace)
        return self

    def __exit__(self, *exc_info):
        self.conn.set_trace_callback(None)
        return False

    def trace(self, statement) -> None:
        if statement and re.search(r"\bfrom\s+steps\b", str(statement), re.I):
            self.count += 1


class ExploreSandbox(SchemaConnTmpRootTest):
    """БД и логи песочницы; журнал пишется с явной меткой времени."""

    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.now = datetime.now(timezone.utc)
        Path(config.LOGS).mkdir(parents=True, exist_ok=True)

    def msg(self, extra: str = "") -> str:
        return f"зерно: {self.seed}; {extra}"

    def tid(self) -> str:
        return "01M9" + "".join(self.rng.choice(ALPHABET) for _ in range(22))

    def task(self, known: bool = True) -> str:
        tid = self.tid()
        if known:
            store.insert_task(self.conn, tid, f"Задача {tid}", "in_dev",
                              f"task/{tid.lower()}", config.DEFAULT_TARGET, 25.0)
        return tid

    def add_row(self, tid: str, actor: str, action: str, detail: str,
                ago: timedelta) -> None:
        self.conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail,"
            " session_id) VALUES (?,?,?,?,?,?,?)",
            (tid, config.DEFAULT_TARGET, stamp(self.now - ago), actor, action,
             detail, "fixture-session"))
        self.conn.commit()

    def started_detail(self, log) -> str:
        log_part = f"лог: {log}, " if log is not None else ""
        return (f"попытка 1/1, model=fixture-model, {log_part}"
                f"промпт: {Path(config.LOGS) / 'prompt.md'}, окружение: fixture")

    def step(self, tid: str, role: str, calls, *, n: int = 1,
             ago: timedelta = timedelta(hours=1),
             provider: str | None = claude.CLI_NAME) -> Path:
        path = Path(config.LOGS) / f"{tid}-{role}-{n}.log"
        lines = ["старт шага роли"]
        for name, arg in calls:
            lines += [f"{PREFIX}{name} {arg}", "  вывод инструмента"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.add_row(tid, role, STARTED, self.started_detail(path), ago)
        if provider is not None:
            self.add_row(tid, role, KNOWN,
                         f"попытка 1/1, model=fixture-model, provider={provider}: "
                         f"стоимость $0.0100", ago)
        return path

    def operator_env(self) -> dict:
        return {"HOME": f"/tmp/operator_{self.rng.randrange(1 << 30):x}",
                "PATH": os.environ.get("PATH", "")}

    def dispatch(self, argv, env=None) -> tuple:
        """(код выхода или None, вывод stdout+stderr) вызова `artel.py`."""
        out, err = io.StringIO(), io.StringIO()
        code = None
        with mock.patch.dict(os.environ, env or self.operator_env(), clear=True), \
                mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue() + err.getvalue()

    def explore(self, *args) -> str:
        code, output = self.dispatch(["explore-stats", *args])
        self.assertIn(code, (None, 0), self.msg(f"{args}: отказ {code!r}; {output}"))
        return output

    def run_report(self, shared: SharedConnection | None = None) -> tuple:
        """(HTML отчёта, запросов к `steps`) прогона `cmd_report` на одном
        соединении песочницы."""
        shared = shared or SharedConnection(self.conn)
        with mock.patch.object(store, "db", shared), StepsTrace(self.conn) as trace, \
                contextlib.redirect_stdout(io.StringIO()):
            report.cmd_report()
        page = (Path(config.ROOT) / ".artel" / "report.html").read_text(
            encoding="utf-8")
        return page, trace.count


class CommandTableTest(ExploreSandbox):
    """AC-13: команда в таблице, справке и вне белого списка роли."""

    def test_ac13_command_is_dispatched_and_listed_in_help(self):
        """Пустой журнал: команда исполняется, справка её называет.

        `explore-stats` без данных печатает «шагов за 7 суток нет» с кодом
        0, а не «Неизвестная команда»; раздел «Команды:» справки называет
        `explore-stats`.

        Ловит мутацию: строка команды не добавлена в таблицу `artel.main`
        — диспетчер ответит «Неизвестная команда» с ненулевым кодом; не
        добавлена в справку — раздел «Команды:» её не назовёт.
        """
        code, output = self.dispatch(["explore-stats"])
        self.assertIn(code, (None, 0), self.msg(output))
        self.assertNotIn("Неизвестная команда", output)
        self.assertIn("шагов за 7 суток нет", output, self.msg(output))

        _code, help_text = self.dispatch(["--help"])
        start = help_text.find("Команды:")
        self.assertGreaterEqual(start, 0, "в справке нет раздела «Команды:»")
        end = help_text.find("\n\n", start)
        section = help_text[start:end if end >= 0 else len(help_text)]
        self.assertIn("explore-stats", section)

    def test_ac13_command_is_refused_to_role_process(self):
        """Вызов из окружения роли (`ARTEL_ROLE` выставлен).

        Команда не исполняется: отказ с ненулевым кодом, текст называет
        `explore-stats`, сводки в выводе нет.

        Ловит мутацию: `explore-stats` добавлена в белый список команд роли
        — под ролью команда исполнится и напечатает «шагов за 7 суток
        нет» с кодом 0.
        """
        env = {**self.operator_env(), config.ARTEL_ROLE_ENV: "developer"}
        code, output = self.dispatch(["explore-stats"], env=env)
        self.assertNotIn(code, (None, 0), self.msg(output))
        self.assertIn("explore-stats", str(code) + output)
        self.assertNotIn("суток нет", output)


class CommandOptionsTest(ExploreSandbox):
    """AC-13: параметры по умолчанию, `--role`, `--days`, подписи вывода."""

    def test_ac13_default_days_and_roles(self):
        """По шагу каждой из пяти ролей час назад и два шага developer у
        границы семи суток (6 сут 23 ч и 7 сут 1 ч назад).

        По умолчанию вывод называет developer, test_author, reviewer и
        analyst, но не spec_auditor; у developer шагов 2. С `--days 8` у
        developer шагов 3. `--role spec_auditor` — только spec_auditor.

        Ловит мутацию: окно по умолчанию не 7 суток (14 — шагов developer
        3); spec_auditor включён в роли по умолчанию; `--role` не применён
        (вывод назовёт developer); `--days` не применён (шагов останется 2).
        """
        for role in DEFAULT_ROLES + ("spec_auditor",):
            self.step(self.task(), role, reads(1, role) + [CODE_EDIT])
        self.step(self.task(), "developer", [CODE_EDIT],
                  ago=timedelta(days=6, hours=23))
        self.step(self.task(), "developer", [CODE_EDIT],
                  ago=timedelta(days=7, hours=1))

        output = self.explore()
        for role in DEFAULT_ROLES:
            self.assertIn(role, output, self.msg(output))
        self.assertNotIn("spec_auditor", output, self.msg(output))
        self.assertEqual("2", number(self.explore("--role", "developer"),
                                     "шагов:"), self.msg())
        self.assertEqual("3", number(self.explore("--role", "developer",
                                                  "--days", "8"), "шагов:"),
                         self.msg())

        narrowed = self.explore("--role", "spec_auditor")
        self.assertIn("spec_auditor", narrowed)
        for role in DEFAULT_ROLES:
            self.assertNotIn(role, narrowed, self.msg(narrowed))

    def test_ac13_labels_in_order_and_undefined_values(self):
        """Шаг developer без правки кода и без записи (только чтения).

        Вывод `--role developer` несёт все подписи в порядке требования;
        «первых прогонов:» и «Codex:» — в строке «шагов:»; строка «путь
        обрезан: K из M чтений»; неопределённые медианы «до границы» и доля
        — «н/д».

        Ловит мутацию: подписи переставлены или одна потеряна (например,
        «запись не наступила:») — порядок не сойдётся; `None` напечатан
        как «None» или 0 вместо «н/д».
        """
        self.step(self.task(), "developer", reads(self.rng.randint(1, 5), "v"))

        output = self.explore("--role", "developer")

        position = 0
        for label in LABELS:
            found = output.find(label, position)
            self.assertGreaterEqual(found, 0, self.msg(f"{label!r} после "
                                                       f"{position}: {output}"))
            position = found + len(label)
        steps_line = next(line for line in output.splitlines() if "шагов:" in line)
        self.assertIn("первых прогонов:", steps_line)
        self.assertIn("Codex:", steps_line)
        self.assertRegex(output, r"путь обрезан: \d+ из \d+ чтений")
        for label in ("медиана до первой правки кода:", "медиана до первой записи:",
                      "доля разведки:"):
            line = next(x for x in output.splitlines() if label in x)
            self.assertIn(NOT_AVAILABLE, line, self.msg(line))
        self.assertNotIn("None", output)

    def test_ac13_empty_period_and_named_refusals(self):
        """Пустой журнал и ошибочные параметры.

        Пустой период — «шагов за N суток нет», код 0 (N по умолчанию 7 и
        переданное `--days`). `--days 0`, `--days -1`, `--days abc`,
        `--days` без значения — отказ, называющий `--days`; неизвестная
        роль — отказ, называющий роль.

        Ловит мутацию: проверка «больше нуля» пропущена (`--days 0` даст
        «шагов за 0 суток нет» с кодом 0); `int()` без перехвата (`--days
        abc` — `ValueError` вместо именованного отказа); неизвестная роль
        молча даёт пустой вывод.
        """
        days = self.rng.randint(2, 40)
        self.assertIn("шагов за 7 суток нет", self.explore())
        self.assertIn(f"шагов за {days} суток нет",
                      self.explore("--days", str(days)))
        unknown = f"janitor_{self.rng.randrange(1 << 20):x}"
        for argv, named in ((["--days", "0"], "--days"),
                            (["--days", "-1"], "--days"),
                            (["--days", "abc"], "--days"),
                            (["--days"], "--days"),
                            (["--role", unknown], unknown)):
            with self.subTest(argv=argv):
                code, output = self.dispatch(["explore-stats", *argv])
                self.assertNotIn(code, (None, 0), self.msg(f"{argv}: {output}"))
                self.assertIn(named, str(code) + output, self.msg(output))


class CommandJournalTest(ExploreSandbox):
    """AC-3, AC-4: состав журнала команды и отсутствующие логи."""

    def test_ac3_records_of_tasks_outside_tasks_table_are_skipped(self):
        """Шаг developer задачи из таблицы `tasks` и шаг задачи, строки
        которой в `tasks` нет (псевдозадача журнала).

        И команда, и блок отчёта считают только первый шаг: у команды
        шагов 1, чтение первого шага есть, второго — нет; в блоке отчёта
        так же.

        Ловит мутацию: отбор «только задачи из `tasks`» снят у команды (три
        выборки журнала отданы сводке как есть) — шагов станет 2 и чтение
        псевдозадачи попадёт в топ; снят у блока отчёта — то же в HTML.
        """
        self.step(self.task(), "developer",
                  [("Read", "wt:orchestrator/known_task.py"), CODE_EDIT])
        self.step(self.task(known=False), "developer",
                  [("Read", "wt:orchestrator/pseudo_task.py"), CODE_EDIT])

        output = self.explore("--role", "developer")
        self.assertEqual("1", number(output, "шагов:"), self.msg(output))
        self.assertIn("orchestrator/known_task.py", output)
        self.assertNotIn("orchestrator/pseudo_task.py", output)

        block = explore_block_text(self.run_report()[0])
        self.assertIn("orchestrator/known_task.py", block, self.msg(block))
        self.assertNotIn("orchestrator/pseudo_task.py", block, self.msg(block))

    def test_ac4_command_survives_missing_logs(self):
        """Три записи developer: без пути лога, путь к отсутствующему файлу,
        каталог на месте файла — и обычный шаг рядом.

        Команда завершается с кодом 0 и печатает «логов не найдено: 3».

        Ловит мутацию: `OSError` чтения каталога не перехвачен — команда
        упадёт `IsADirectoryError`; запись без пути не учтена — счётчик 2.
        """
        tid = self.task()
        self.add_row(tid, "developer", STARTED, self.started_detail(None),
                     timedelta(hours=1))
        self.add_row(self.task(), "developer", STARTED,
                     self.started_detail(Path(config.LOGS) / "gone-developer-1.log"),
                     timedelta(hours=1))
        folder = Path(config.LOGS) / "folder-developer-1.log"
        folder.mkdir()
        self.add_row(self.task(), "developer", STARTED,
                     self.started_detail(folder), timedelta(hours=1))
        self.step(self.task(), "developer", [("Read", "wt:src/ok.py"), CODE_EDIT])

        output = self.explore("--role", "developer")

        self.assertEqual("3", number(output, "логов не найдено:"), self.msg(output))


class CommandReadOnlyTest(ExploreSandbox):
    """AC-14: команда только читает."""

    def test_ac14_command_changes_neither_db_nor_logs_nor_calls_git(self):
        """Журнал с шагами нескольких ролей; команда по умолчанию на одном
        соединении песочницы.

        `total_changes` соединения после прогона равен отсчёту, взятому
        после `migrate`/`seed_task_counters` и засева; содержимое логов не
        изменилось; ни `subprocess.run`, ни `subprocess.Popen` не вызваны
        с git.

        Ловит мутацию: команда пишет запись журнала о своём прогоне
        (`store.journal`) — `total_changes` вырастет; лог дописан или
        переписан — его сумма изменится; команда зовёт `git` (например,
        для корня рабочей копии) — вызов появится в перехвате.
        """
        for role in DEFAULT_ROLES:
            for _ in range(self.rng.randint(1, 3)):
                self.step(self.task(), role,
                          reads(self.rng.randint(1, 6), role) + [CODE_EDIT])
        store.seed_task_counters(self.conn)
        self.conn.commit()
        logs = sorted(Path(config.LOGS).glob("*.log"))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in logs}
        baseline = self.conn.total_changes
        git_runs = len(self.git_spy.git_subcommands())
        popen_calls = []
        real_popen = subprocess.Popen

        def popen(cmd, *args, **kwargs):
            popen_calls.append(cmd)
            return real_popen(cmd, *args, **kwargs)

        shared = SharedConnection(self.conn)
        with mock.patch.object(store, "db", shared), \
                mock.patch.object(subprocess, "Popen", popen):
            output = self.explore()

        self.assertIn("developer", output)
        self.assertEqual(baseline, self.conn.total_changes, "запись в state.db")
        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in logs}
        self.assertEqual(before, after, "лог изменён")
        self.assertEqual(git_runs, len(self.git_spy.git_subcommands()),
                         f"git вызван: {self.git_spy.git_subcommands()[git_runs:]}")
        git_popen = [c for c in popen_calls
                     if "git" in (str(c[0]) if isinstance(c, (list, tuple)) else str(c))]
        self.assertEqual([], git_popen)


class ReportBlockTest(ExploreSandbox):
    """AC-15: блок «Разведка ролей» отчёта."""

    def seed_tasks(self, count: int) -> list:
        tids = [self.task() for _ in range(count)]
        self.seed_runs(tids, (1, 2))
        return tids

    def seed_runs(self, tids, numbers) -> None:
        for tid in tids:
            for n in numbers:
                self.step(tid, "developer", reads(self.rng.randint(1, 4), "w")
                          + [CODE_EDIT], n=n)

    def stubbed_report(self, shared: SharedConnection | None = None) -> tuple:
        """Отчёт с заглушкой функции сводки (пустой журнал на входе) и
        признак того, что заглушка вызвана."""
        original = explore_metric.summarize
        called = []

        def stub(*args, **kwargs):
            called.append(1)
            if "steps" in kwargs:
                kwargs["steps"] = []
            else:
                args = ([],) + args[1:]
            return original(*args, **kwargs)

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(explore_metric, "summarize", stub))
            if getattr(report, "summarize", None) is original:
                stack.enter_context(mock.patch.object(report, "summarize", stub))
            _page, count = self.run_report(shared)
        return count, bool(called)

    def test_ac15_block_is_rendered_with_own_window(self):
        """Шаги developer 3 и 10 суток назад; окно операторских блоков
        поднято до 30 суток.

        Отчёт несёт блок «Разведка ролей (последние 7 дней)»; чтение шага
        3 суток назад в блоке есть, 10 суток назад — нет.

        Ловит мутацию: окно блока взято `OPERATOR_WINDOW_DAYS` — шаг 10
        суток назад войдёт в блок, и его чтение появится в HTML блока.
        """
        self.step(self.task(), "developer",
                  [("Read", "wt:orchestrator/inside_window.py"), CODE_EDIT],
                  ago=timedelta(days=3))
        self.step(self.task(), "developer",
                  [("Read", "wt:orchestrator/outside_window.py"), CODE_EDIT],
                  ago=timedelta(days=10))

        with mock.patch.object(report, "OPERATOR_WINDOW_DAYS", 30):
            page, _count = self.run_report()

        self.assertIn(BLOCK_TITLE, page)
        block = explore_block_text(page)
        self.assertIn("orchestrator/inside_window.py", block, self.msg(block))
        self.assertNotIn("orchestrator/outside_window.py", block, self.msg(block))

    def test_ac15_steps_queries_do_not_grow_with_runs_and_db_opened_once(self):
        """Отчёт на случайном числе задач по два прогона, затем на тех же
        задачах с ещё тремя прогонами каждая.

        На одном подменённом соединении `store.db()` за прогон вызывается
        один раз, а число запросов к `steps` при двух и при пяти записях
        «agent run started» на задачу одно и то же (и больше нуля).

        Ловит мутацию: блок читает журнал или запись стоимости шага сам —
        запросом на каждую запись «agent run started» (число запросов
        вырастет с прогонами) либо через своё `store.db()` (открытий за
        прогон станет два).
        """
        tids = self.seed_tasks(self.rng.randint(2, 4))
        small = SharedConnection(self.conn)
        page, few = self.run_report(small)
        self.assertIn(BLOCK_TITLE, page)

        self.seed_runs(tids, (3, 4, 5))
        large = SharedConnection(self.conn)
        _page, many = self.run_report(large)

        self.assertGreater(few, 0, "счётчик не увидел ни одного запроса")
        self.assertEqual(few, many, self.msg(f"запросов к steps: {few} и {many}"))
        self.assertEqual((1, 1), (small.opened, large.opened))

    def test_ac15_block_adds_no_steps_query_at_any_task_count(self):
        """Отчёт с настоящей функцией сводки и с заглушкой — на наборе из
        двух задач и затем из семи.

        Заглушка сводит функцию сводки к пустому журналу и действительно
        вызвана; на каждом наборе `store.db()` за прогон вызывается один
        раз (и с блоком, и с заглушкой), а число запросов к `steps` с
        блоком равно числу с заглушкой — блок не добавляет ни одного
        запроса (ANSWER-1: рост существующих блоков с числом задач вне
        задачи).

        Ловит мутацию: блок (или функция сводки через переданное
        соединение) делает свой запрос журнала — один на прогон или по
        одному на задачу: с настоящей функцией запросов станет больше, чем
        с заглушкой; блок открывает своё `store.db()` — открытий за прогон
        станет два.
        """
        total = 0
        for size in (2, 7):
            self.seed_tasks(size - total)
            total = size
            real_db = SharedConnection(self.conn)
            _page, real = self.run_report(real_db)
            stub_db = SharedConnection(self.conn)
            stubbed, called = self.stubbed_report(stub_db)
            self.assertTrue(called, "заглушка функции сводки не вызвана")
            self.assertEqual((1, 1), (real_db.opened, stub_db.opened),
                             self.msg(f"{size} задач: открытий store.db()"))
            self.assertEqual(stubbed, real,
                             self.msg(f"{size} задач: с блоком {real}, "
                                      f"с заглушкой {stubbed}"))

    def test_ac15_block_numbers_match_default_command(self):
        """Три шага developer за 7 суток (до правки кода 5, 17, 19 из 9, 23,
        31 вызовов, в каждом читается `orchestrator/match_probe.py`) и шаг
        10 суток назад.

        Команда по умолчанию печатает шагов 3, медиану вызовов 23 и до
        правки кода 17, файл `orchestrator/match_probe.py` трижды; те же
        числа и путь — в блоке отчёта на тех же данных.

        Ловит мутацию: блок считает по своему окну иной длины или по иным
        ролям — медианы блока станут 27 и 18 (шаг 10 суток назад войдёт), и
        числа команды в блоке не найдутся.
        """
        probe = ("Read", "wt:orchestrator/match_probe.py")
        for k, (before, total) in enumerate(((5, 9), (17, 23), (19, 31))):
            calls = ([probe] + reads(before - 1, f"m{k}") + [CODE_EDIT]
                     + reads(total - before - 1, f"n{k}"))
            self.step(self.task(), "developer", calls)
        self.step(self.task(), "developer",
                  [probe] + reads(39, "old") + [CODE_EDIT] + reads(20, "late"),
                  ago=timedelta(days=10))

        output = self.explore()
        start = output.find("developer")
        ends = [output.find(r, start) for r in DEFAULT_ROLES if r != "developer"]
        ends = [e for e in ends if e > start]
        developer = output[start:min(ends) if ends else len(output)]
        values = {}
        for label in ("шагов:", "медиана вызовов:", "медиана до первой правки кода:"):
            text = number(developer, label)
            values[label] = None if text is None else float(text.replace(",", "."))
        self.assertEqual({"шагов:": 3, "медиана вызовов:": 23,
                          "медиана до первой правки кода:": 17},
                         values, self.msg(developer))
        self.assertRegex(developer, r"\b3\s+orchestrator/match_probe\.py")

        block = explore_block_text(self.run_report()[0])

        for label, value in values.items():
            self.assertRegex(block, rf"(?<![\d.,]){int(value)}(?:[.,]0+)?(?![\d.,]*\d)",
                             self.msg(f"{label} {value}: {block}"))
        self.assertIn("orchestrator/match_probe.py", block, self.msg(block))


if __name__ == "__main__":
    unittest.main()
