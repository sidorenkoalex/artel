"""Запись строки «оборвана сигналом» дочерним `canary run-task` (AC-2, AC-3,
AC-8, AC-9): повторы при `sqlite3.OperationalError`, `store.db()` в каждой
попытке, отчёт в stderr и код `128 + сигнал` при неудаче, без `sleep`.

Группа: разовый
Красен до реализации: ветка `except CanaryInterrupted` в `cmd_canary_run_task` пишет строку одним вызовом без повторов и без перехвата — исключение записи всплывает из функции вместо `SystemExit(128 + SIGTERM)`, строки нет, сообщения «строка прогона не записана» нет.

Разовый, хотя проверяет свойство кода: критерии предписывают подмены
закрытых имён `canary` (`_set_plan`, `_mark_owned_by_parent`,
`_run_one_task`), которые правила долгоживущего файла запрещают;
долгоживущее покрытие того же свойства — `tests/test_canary_child_row_write.py`
разработчика (требование 6 SPEC).

Сценарий внутри процесса: `cmd_canary_run_task` в песочнице
`InitializedTmpRootTest`; ведение задачи бросает `CanaryInterrupted(SIGTERM)`,
план набора и сверка метки подменены; `store.insert_canary_run` и/или
`store.db` — шпионы с заданными сбоями; `time.sleep` модуля
`orchestrator.canary` — шпион.
"""
import contextlib
import io
import signal
import sqlite3
from unittest import mock

from orchestrator import canary, store
from tests.sandbox import InitializedTmpRootTest

FULL_SHA = "3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93"
STAMP = "20261023T120000Z"
SET_NAME = "nabor-kedr"
SUMMARY = "developer → model-pihta; источник: набор"
TITLE = "alfa"
NOTE = "оборвана сигналом SIGTERM"
EXIT_CODE = 128 + signal.SIGTERM
SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)


class _Outcome:
    def __init__(self, exc, stderr: str, sleep, insert, db):
        self.exc = exc
        self.stderr = stderr
        self.sleep = sleep
        self.insert = insert
        self.db = db

    def code(self):
        return self.exc.code if isinstance(self.exc, SystemExit) else None

    def describe(self) -> str:
        return f"исход: {self.exc!r}\nstderr:\n{self.stderr}"


class _ChildRowSandbox(InitializedTmpRootTest):
    def setUp(self):
        super().setUp()
        before = {s: signal.getsignal(s) for s in SIGNALS}
        self.addCleanup(lambda: [signal.signal(s, h) for s, h in before.items()])
        self.real_insert = store.insert_canary_run
        self.real_db = store.db
        self.template = self.root / "pool" / f"{TITLE}.md"
        self.template.parent.mkdir(parents=True, exist_ok=True)
        self.template.write_text("# учебная задача\n", encoding="utf-8")

    def run_task(self, insert=None, db=None) -> _Outcome:
        """`cmd_canary_run_task` с подменами; `insert`/`db` — `side_effect`
        шпионов `store.insert_canary_run`/`store.db` (None — шпион поверх
        настоящей функции)."""
        plan = canary.CanarySetPlan(SET_NAME, {}, None, SUMMARY, ())
        sleep = mock.Mock(name="time.sleep")
        insert_spy = mock.Mock(name="store.insert_canary_run",
                               side_effect=insert or self.real_insert)
        db_spy = mock.Mock(name="store.db", side_effect=db or self.real_db)
        stderr = io.StringIO()
        exc = None
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(
                canary, "_set_plan", return_value=plan))
            stack.enter_context(mock.patch.object(
                canary, "_mark_owned_by_parent", return_value=True))
            stack.enter_context(mock.patch.object(
                canary, "_run_one_task",
                side_effect=canary.CanaryInterrupted(signal.SIGTERM)))
            stack.enter_context(mock.patch.object(
                canary, "_ephemeral_clone",
                side_effect=AssertionError("клон в тесте запрещён")))
            stack.enter_context(mock.patch.object(canary.time, "sleep", sleep))
            stack.enter_context(mock.patch.object(
                store, "insert_canary_run", insert_spy))
            stack.enter_context(mock.patch.object(store, "db", db_spy))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            try:
                canary.cmd_canary_run_task(
                    run_stamp=STAMP, template_path=self.template,
                    target_sha=FULL_SHA, set_name=SET_NAME, summary=SUMMARY)
            except BaseException as caught:  # noqa: BLE001 — исход сценария
                exc = caught
        return _Outcome(exc, stderr.getvalue(), sleep, insert_spy, db_spy)

    def rows(self) -> list:
        return [(r["run_stamp"], r["title"], r["outcome"], r["main_sha"],
                 r["verdict"], r["set_name"])
                for r in store.all_canary_runs(store.db())
                if r["title"] == TITLE]

    def fail_first(self, error, then):
        """`side_effect`: первый вызов бросает `error`, далее — `then`."""
        calls = []

        def effect(*args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                raise error
            return then(*args, **kwargs)
        return effect

    @staticmethod
    def always(error):
        def effect(*args, **kwargs):
            raise error
        return effect

    def assert_reported(self, outcome: _Outcome, error_name: str) -> None:
        self.assertEqual(outcome.code(), EXIT_CODE, outcome.describe())
        self.assertIn("строка прогона не записана", outcome.stderr,
                      outcome.describe())
        self.assertIn("Traceback (most recent call last)", outcome.stderr,
                      outcome.describe())
        self.assertIn(error_name, outcome.stderr, outcome.describe())


class ChildRowWriteTest(_ChildRowSandbox):
    def test_ac2_locked_first_write_is_retried_and_row_written(self):
        """Первая запись строки — «database is locked», вторая настоящая.

        Сценарий: ведение оборвано SIGTERM; `store.insert_canary_run` на
        первом вызове бросает `sqlite3.OperationalError("database is
        locked")`, затем пишет по-настоящему. Исход — `SystemExit(128 +
        SIGTERM)`, в БД ровно одна строка шаблона «оборвана сигналом
        SIGTERM» с sha и набором прогона; вызовов записи — два; `time.sleep`
        модуля `canary` не вызван.

        Ловит мутацию: запись без повтора (как сейчас) — всплывает
        `OperationalError`, строки нет; либо повтор при сбое глотает ошибку
        и выходит без второй попытки — строки нет.
        """
        outcome = self.run_task(insert=self.fail_first(
            sqlite3.OperationalError("database is locked"), self.real_insert))
        self.assertEqual(outcome.code(), EXIT_CODE, outcome.describe())
        self.assertEqual(self.rows(),
                         [(STAMP, TITLE, NOTE, FULL_SHA, "red", SET_NAME)],
                         outcome.describe())
        self.assertEqual(outcome.insert.call_count, 2, outcome.describe())
        outcome.sleep.assert_not_called()

    def test_ac3_persistent_failure_reported_with_stack_and_signal_code(self):
        """Сбой записи не преодолён — отчёт в stderr со стеком, код 128 + SIGTERM.

        Сценарий 1: `store.insert_canary_run` всегда бросает
        `sqlite3.OperationalError` — попыток записи ровно 3, исход
        `SystemExit(128 + SIGTERM)`, в stderr «строка прогона не записана»,
        «Traceback (most recent call last)» и имя исключения. Сценарий 2:
        запись бросает `sqlite3.IntegrityError` — ровно одна попытка, тот же
        код и то же сообщение со стеком. В обоих `time.sleep` модуля
        `canary` не вызван.

        Ловит мутацию: после исчерпания попыток исключение всплывает (код 1
        процесса, сообщения нет); либо повторяется любое исключение —
        `IntegrityError` записывается трижды; либо попыток 2 или 4
        (перепутана граница цикла); либо в stderr только текст ошибки без
        стека (`str(exc)` вместо `traceback.format_exc()`).
        """
        cases = ((sqlite3.OperationalError("database is locked"),
                  "OperationalError", 3),
                 (sqlite3.IntegrityError("UNIQUE constraint failed"),
                  "IntegrityError", 1))
        for error, name, attempts in cases:
            with self.subTest(error=name):
                outcome = self.run_task(insert=self.always(error))
                self.assert_reported(outcome, name)
                self.assertEqual(outcome.insert.call_count, attempts,
                                 outcome.describe())
                outcome.sleep.assert_not_called()

    def test_ac8_db_connection_opened_inside_each_attempt(self):
        """`store.db()` открывается в каждой попытке и внутри её перехвата.

        Сценарий 1: запись всегда бросает `OperationalError`, `store.db` —
        шпион поверх настоящего: вызовов `store.db` ровно 3 (по одному на
        попытку). Сценарий 2: запись настоящая, `store.db` на первом вызове
        бросает `sqlite3.OperationalError("database is locked")`, затем
        отдаёт настоящее соединение — строка «оборвана сигналом SIGTERM» в
        БД, исход `SystemExit(128 + SIGTERM)`.

        Ловит мутацию: соединение открыто один раз до цикла повторов —
        вызов `store.db` один (сценарий 1); либо `store.db()` в цикле, но
        вне `try` — сбой открытия соединения всплывает `OperationalError`,
        строки нет (сценарий 2).
        """
        with self.subTest(scenario="запись всегда падает"):
            outcome = self.run_task(insert=self.always(
                sqlite3.OperationalError("database is locked")))
            self.assertEqual(outcome.code(), EXIT_CODE, outcome.describe())
            self.assertEqual(outcome.db.call_count, 3, outcome.describe())
        with self.subTest(scenario="открытие соединения падает первым"):
            outcome = self.run_task(db=self.fail_first(
                sqlite3.OperationalError("database is locked"), self.real_db))
            self.assertEqual(outcome.code(), EXIT_CODE, outcome.describe())
            self.assertEqual(self.rows(),
                             [(STAMP, TITLE, NOTE, FULL_SHA, "red", SET_NAME)],
                             outcome.describe())

    def test_ac9_no_sleep_between_attempts(self):
        """Между попытками записи нет `time.sleep`.

        Сценарии AC-2 (первая запись — «database is locked») и AC-3 (всегда
        `OperationalError`, всегда `IntegrityError`) с шпионом `time.sleep`
        модуля `orchestrator.canary`: ни в одном шпион не вызван, а попыток
        записи в сценариях с `OperationalError` больше одной — повторы
        действительно шли.

        Ловит мутацию: `time.sleep(…)` между попытками записи — шпион видит
        вызов.
        """
        locked = sqlite3.OperationalError("database is locked")
        cases = (("AC-2", self.fail_first(locked, self.real_insert), 2),
                 ("AC-3 OperationalError", self.always(locked), 3),
                 ("AC-3 IntegrityError",
                  self.always(sqlite3.IntegrityError("UNIQUE")), 1))
        for name, insert, attempts in cases:
            with self.subTest(scenario=name):
                outcome = self.run_task(insert=insert)
                self.assertEqual(outcome.insert.call_count, attempts,
                                 outcome.describe())
                self.assertEqual(outcome.sleep.call_args_list, [],
                                 outcome.describe())
