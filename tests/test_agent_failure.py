"""Тесты провала шага по коду возврата агента (см. tasks/T006/SPEC.md).

Реального `claude` CLI тут нет: `subprocess.Popen` подменяется списком
фейковых процессов — по одному на попытку, — поэтому сценарий «упал, упал,
поднялся» проверяется целиком, включая журнал и состояние задачи. Паузы
бэкоффа не спим, а записываем.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel  # noqa: E402


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class TmpRootTest(unittest.TestCase):
    """Общая песочница: DB, TASKS и LOGS уводятся во временный каталог."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs")):
            patcher = mock.patch.object(artel, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()


class LogTailTest(TmpRootTest):
    """Хвост лога прогона — то, по чему Оператор видит причину падения."""

    def log_with(self, text: str) -> Path:
        path = artel.new_agent_log("T006", "developer")
        path.write_text(text, encoding="utf-8")
        return path

    def test_only_last_lines_are_taken(self):
        path = self.log_with("".join(f"строка {i}\n" for i in range(1, 51)))

        tail = artel.log_tail(path)

        self.assertTrue(tail.startswith(f"строка {50 - artel.LOG_TAIL_LINES + 1}\n"))
        self.assertTrue(tail.endswith("строка 50"))
        self.assertEqual(len(tail.splitlines()), artel.LOG_TAIL_LINES)

    def test_short_log_is_taken_whole(self):
        path = self.log_with("API Error: 401 Unauthorized\n")

        self.assertEqual(artel.log_tail(path), "API Error: 401 Unauthorized")

    def test_empty_log_is_reported_as_empty(self):
        self.assertEqual(artel.log_tail(self.log_with("")), "лог пуст")

    def test_long_line_is_cut_to_the_end(self):
        path = self.log_with("ш" * 5000 + "причина в конце\n")

        tail = artel.log_tail(path)

        self.assertEqual(len(tail), artel.LOG_TAIL_CHARS)
        self.assertTrue(tail.endswith("причина в конце"))

    def test_unreadable_log_does_not_raise(self):
        missing = artel.LOGS / "нет-такого-каталога" / "шаг.log"

        self.assertIn("лог не прочитан", artel.log_tail(missing))


class CmdRunFailureTest(TmpRootTest):
    """`run` с падающим агентом: журнал, ретраи, эскалация."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.capture(artel.cmd_init)
        self.capture(artel.cmd_new, "Код возврата агента")
        conn = artel.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()

        self.pauses = []
        patcher = mock.patch.object(artel.time, "sleep", self.pauses.append)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_agent(self, *attempts) -> str:
        """attempts: (rc, строки вывода) — по одной паре на попытку."""
        procs = [FakeProc(lines, rc) for rc, lines in attempts]
        with mock.patch.object(artel.subprocess, "Popen", side_effect=procs) as popen:
            out = self.capture(artel.cmd_run, self.TASK)
        self.popen = popen
        return out

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in artel.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def task_row(self):
        return artel.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def test_successful_run_behaves_as_before(self):
        out = self.run_agent((0, ["готово\n"]))

        self.assertIn("developer завершил (rc=0)", out)
        self.assertIn(f"дальше: artel.py advance {self.TASK}", out)
        self.assertEqual(self.journal_details("agent run FAILED"), [])
        self.assertEqual(self.task_row()["state"], "in_dev")
        self.assertEqual(self.pauses, [], "успех не ретраится")

    def test_failure_is_journaled_with_rc_and_log_tail(self):
        self.run_agent(*[(1, ["API Error: 401 Unauthorized\n"])] * artel.AGENT_ATTEMPTS)

        details = self.journal_details("agent run FAILED")
        self.assertEqual(len(details), artel.AGENT_ATTEMPTS)
        self.assertIn("rc=1", details[0])
        self.assertIn("401 Unauthorized", details[0], "в хвосте лога — причина")
        self.assertEqual(self.journal_details("agent run finished"), [],
                         "провал не пишется как нормальное завершение")

    def test_failure_prints_no_advance_hint(self):
        out = self.run_agent(*[(1, ["упал\n"])] * artel.AGENT_ATTEMPTS)

        self.assertNotIn("advance", out, "подсказка advance — только при успехе")
        self.assertIn("агент упал", out)

    def test_retry_succeeds_on_second_attempt(self):
        out = self.run_agent((1, ["упал\n"]), (0, ["поднялся\n"]))

        self.assertEqual(self.popen.call_count, 2, "третья попытка не нужна")
        self.assertEqual(len(self.journal_details("agent run FAILED")), 1)
        self.assertEqual(len(self.journal_details("agent run finished")), 1)
        self.assertEqual(self.task_row()["state"], "in_dev", "успех не эскалирует")
        self.assertIn(f"дальше: artel.py advance {self.TASK}", out)

    def test_backoff_pauses_grow_between_attempts(self):
        self.run_agent(*[(1, ["упал\n"])] * artel.AGENT_ATTEMPTS)

        self.assertEqual(self.pauses, [artel.RETRY_BACKOFF_SEC,
                                       artel.RETRY_BACKOFF_SEC * 2])
        self.assertEqual(len(self.journal_details("agent run retry")),
                         artel.AGENT_RETRIES)

    def test_attempt_counter_is_journaled(self):
        self.run_agent(*[(1, ["упал\n"])] * artel.AGENT_ATTEMPTS)

        started = self.journal_details("agent run started")
        self.assertEqual([f"попытка {n}/{artel.AGENT_ATTEMPTS}"
                          for n in (1, 2, 3)],
                         [d.split(",")[0] for d in started])

    def test_escalates_after_retries_exhausted(self):
        out = self.run_agent(*[(1, ["API Error: 401 Unauthorized\n"])]
                             * artel.AGENT_ATTEMPTS)

        self.assertEqual(self.popen.call_count, artel.AGENT_ATTEMPTS)
        self.assertEqual(self.task_row()["state"], "escalated")
        self.assertIn("escalated", out)
        detail = self.journal_details("state -> escalated")[0]
        self.assertIn("rc=1", detail)
        self.assertIn("401 Unauthorized", detail)

    def test_escalated_task_waits_for_operator_in_status(self):
        self.run_agent(*[(1, ["упал\n"])] * artel.AGENT_ATTEMPTS)

        self.assertIn("ЖДЁТ ОПЕРАТОРА", self.capture(artel.cmd_status))

    def test_retries_are_not_review_iterations(self):
        conn = artel.db()
        conn.execute("UPDATE tasks SET state='review', review_iters=1 WHERE id=?",
                     (self.TASK,))
        conn.commit()

        self.run_agent(*[(1, ["упал\n"])] * artel.AGENT_ATTEMPTS)

        row = self.task_row()
        self.assertEqual(row["review_iters"], 1, "ретраи не считаются итерациями")
        self.assertEqual(row["state"], "escalated")

    def test_every_attempt_writes_its_own_log(self):
        self.run_agent((1, ["первый упал\n"]), (1, ["второй упал\n"]),
                       (0, ["третий дошёл\n"]))

        logs = sorted(artel.LOGS.glob(f"{self.TASK}-developer-*.log"))
        self.assertEqual([p.name for p in logs],
                         [f"{self.TASK}-developer-{n}.log" for n in (1, 2, 3)])
        self.assertEqual(logs[0].read_text(encoding="utf-8"), "первый упал\n")
        self.assertEqual(logs[2].read_text(encoding="utf-8"), "третий дошёл\n")

    def test_timeout_is_not_retried(self):
        proc = mock.Mock(stdout=FakeStream([]))
        proc.wait.side_effect = [
            artel.subprocess.TimeoutExpired(cmd="claude",
                                            timeout=artel.AGENT_TIMEOUT_SEC),
            -9,
        ]
        with mock.patch.object(artel.subprocess, "Popen", return_value=proc) as popen:
            out = self.capture(artel.cmd_run, self.TASK)

        self.assertEqual(popen.call_count, 1, "три таймаута — полтора часа ожидания")
        self.assertEqual(self.pauses, [])
        self.assertEqual(self.task_row()["state"], "in_dev")
        self.assertIn("таймаут шага", out)

    def test_missing_cli_is_not_retried(self):
        with mock.patch.object(artel.subprocess, "Popen",
                               side_effect=FileNotFoundError) as popen:
            out = self.capture(artel.cmd_run, self.TASK)

        self.assertEqual(popen.call_count, 1, "повтор не создаст CLI")
        self.assertEqual(self.pauses, [])
        self.assertEqual(self.task_row()["state"], "in_dev")
        self.assertIn("Роль: разработчик", out)


if __name__ == "__main__":
    unittest.main()
