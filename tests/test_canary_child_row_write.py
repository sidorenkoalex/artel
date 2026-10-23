"""Запись строки «оборвана сигналом» дочерним `canary run-task` и её отчёт
родителем (SPEC 01M5MVG2B1YGVPTZWKB18EVGHZ, требования 2-3, 6).

Сценарии внутри процесса: `cmd_canary_run_task` в песочнице, ведение задачи
бросает `CanaryInterrupted(SIGTERM)`; план набора и сверка метки подменены,
`store.insert_canary_run`/`store.db` — шпионы с заданными сбоями, `time.sleep`
модуля `canary` — шпион. Нагрузки и серий повторных прогонов нет.
"""
import contextlib
import io
import signal
import sqlite3
from unittest import mock

from orchestrator import canary, store
from tests.sandbox import InitializedTmpRootTest, patch_sleep

FULL_SHA = "3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93"
STAMP = "20261023T130000Z"
SET_NAME = "nabor-kedr"
SUMMARY = "developer → model-pihta; источник: набор"
TITLE = "alfa"
NOTE = "оборвана сигналом SIGTERM"
EXIT_CODE = 128 + signal.SIGTERM
SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
LOCKED = sqlite3.OperationalError("database is locked")


def _fail_first(error, then):
    calls = []

    def effect(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise error
        return then(*args, **kwargs)
    return effect


def _always(error):
    def effect(*args, **kwargs):
        raise error
    return effect


class _RunTaskSandbox(InitializedTmpRootTest):
    def setUp(self):
        super().setUp()
        before = {s: signal.getsignal(s) for s in SIGNALS}
        self.addCleanup(lambda: [signal.signal(s, h) for s, h in before.items()])
        self.real_insert = store.insert_canary_run
        self.real_db = store.db
        self.template = self.root / "pool" / f"{TITLE}.md"
        self.template.parent.mkdir(parents=True, exist_ok=True)
        self.template.write_text("# учебная задача\n", encoding="utf-8")

    def run_task(self, insert=None, db=None):
        """(исключение выхода, stderr, шпион sleep, шпион записи, шпион db)."""
        plan = canary.CanarySetPlan(SET_NAME, {}, None, SUMMARY, ())
        sleep = mock.Mock(name="canary_sleep")
        insert_spy = mock.Mock(side_effect=insert or self.real_insert)
        db_spy = mock.Mock(side_effect=db or self.real_db)
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
            # Только паузы модуля `canary`: глобальная подмена ловила бы и
            # опрос `subprocess.run(timeout=…)` в `process_start_time`.
            stack.enter_context(patch_sleep(canary, sleep))
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
        return exc, stderr.getvalue(), sleep, insert_spy, db_spy

    def rows(self) -> list:
        return [(r["title"], r["outcome"], r["main_sha"], r["verdict"])
                for r in store.all_canary_runs(store.db())]


class InterruptedRowRetryTest(_RunTaskSandbox):
    def test_locked_write_is_retried_without_sleep_and_row_written(self):
        """Первая вставка — «database is locked», вторая настоящая.

        Исход — `SystemExit(128 + SIGTERM)`, строка «оборвана сигналом
        SIGTERM» в БД, вставок две, `time.sleep` не вызван, stderr пуст.

        Ловит мутацию: вставка без повтора — всплывает `OperationalError`,
        строки нет; либо `time.sleep` между попытками — шпион видит вызов.
        """
        exc, err, sleep, insert, _db = self.run_task(
            insert=_fail_first(LOCKED, self.real_insert))
        self.assertIsInstance(exc, SystemExit, err)
        self.assertEqual(exc.code, EXIT_CODE, err)
        self.assertEqual(self.rows(), [(TITLE, NOTE, FULL_SHA, "red")], err)
        self.assertEqual(insert.call_count, 2)
        sleep.assert_not_called()
        self.assertEqual(err, "")

    def test_failed_connection_open_is_retried(self):
        """Открытие соединения (`store.db()`) первым падает «database is locked».

        Исход — строка записана, код `128 + SIGTERM`.

        Ловит мутацию: `store.db()` вне цикла попыток или в цикле, но вне
        перехвата `OperationalError` — сбой открытия всплывает, строки нет.
        """
        exc, err, _sleep, _insert, _db = self.run_task(
            db=_fail_first(LOCKED, self.real_db))
        self.assertIsInstance(exc, SystemExit, err)
        self.assertEqual(exc.code, EXIT_CODE, err)
        self.assertEqual(self.rows(), [(TITLE, NOTE, FULL_SHA, "red")], err)

    def test_persistent_lock_exhausts_attempts_and_reports_stack(self):
        """Вставка всегда «database is locked» — попыток ровно
        `CHILD_ROW_WRITE_ATTEMPTS`, соединение открыто в каждой.

        Исход — код `128 + SIGTERM`, в stderr «строка прогона не записана»
        и стек с `OperationalError`, `time.sleep` не вызван, строки нет.

        Ловит мутацию: после исчерпания попыток исключение всплывает (код 1,
        сообщения нет); либо граница цикла смещена (2 или 4 попытки); либо
        соединение открыто один раз до цикла; либо в stderr нет стека.
        """
        exc, err, sleep, insert, db = self.run_task(insert=_always(LOCKED))
        self.assertIsInstance(exc, SystemExit, err)
        self.assertEqual(exc.code, EXIT_CODE, err)
        self.assertEqual(canary.CHILD_ROW_WRITE_ATTEMPTS, 3)
        self.assertEqual(insert.call_count, 3, err)
        self.assertEqual(db.call_count, 3, err)
        self.assertIn("строка прогона не записана", err)
        self.assertIn("Traceback (most recent call last)", err)
        self.assertIn("OperationalError", err)
        sleep.assert_not_called()
        self.assertEqual(self.rows(), [])

    def test_other_error_is_not_retried_and_reported(self):
        """Вставка бросает `sqlite3.IntegrityError` — одна попытка, отчёт со
        стеком, код `128 + SIGTERM`.

        Ловит мутацию: повтор любого исключения (`except Exception` в цикле)
        — попыток три; либо не `OperationalError` всплывает без отчёта.
        """
        exc, err, sleep, insert, _db = self.run_task(
            insert=_always(sqlite3.IntegrityError("UNIQUE constraint failed")))
        self.assertIsInstance(exc, SystemExit, err)
        self.assertEqual(exc.code, EXIT_CODE, err)
        self.assertEqual(insert.call_count, 1, err)
        self.assertIn("строка прогона не записана", err)
        self.assertIn("Traceback (most recent call last)", err)
        self.assertIn("IntegrityError", err)
        sleep.assert_not_called()


class ParentReportsUnwrittenRowTest(InitializedTmpRootTest):
    def test_finish_child_prints_child_report_and_writes_drive_failed(self):
        """Дочерний с кодом 143 без строки, в журнале — «строка прогона не
        записана: …»: родитель печатает журнал и пишет `drive_failed`.

        Ловит мутацию: `_finish_child` не печатает журнал дочернего — отчёта
        о несостоявшейся записи нет в выводе родителя; либо родитель
        пропускает красную строку для шаблона без своей строки.
        """
        plan = canary.CanarySetPlan(SET_NAME, {}, None, SUMMARY, ())
        log_path = self.root / "child.log"
        report = ("[canary] alfa: строка прогона не записана: "
                  "OperationalError('database is locked')\n")
        log_path.write_text(report, encoding="utf-8")
        proc = mock.Mock(pid=424242, returncode=143)
        child = canary._Child(self.root / "pool" / f"{TITLE}.md", proc, log_path)
        live_dir = self.root / "live"
        live_dir.mkdir()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            passed = canary._finish_child(child, STAMP, plan, live_dir)
        self.assertFalse(passed)
        self.assertIn(report, out.getvalue())
        self.assertEqual(self.rows(), [(TITLE, canary._DRIVE_FAILED_OUTCOME)])

    def rows(self) -> list:
        return [(r["title"], r["outcome"])
                for r in store.all_canary_runs(store.db())]
