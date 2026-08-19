"""Тесты лога агента по ходу шага (см. tasks/T005/SPEC.md).

Процесс агента фейковый: `subprocess.Popen` подменяется объектом с
итератором строк вместо stdout — так проверяется и построчность записи,
и то, что `cmd_run` не теряет вывод.
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


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = iter(lines)
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


class NewAgentLogTest(TmpRootTest):
    def test_first_run_gets_number_one(self):
        path = artel.new_agent_log("T005", "developer")

        self.assertEqual(path.name, "T005-developer-1.log")
        self.assertTrue(path.exists(), "файл создаётся сразу — для tail -f")

    def test_second_run_increments_and_keeps_old(self):
        first = artel.new_agent_log("T005", "developer")
        first.write_text("прогон 1\n", encoding="utf-8")

        second = artel.new_agent_log("T005", "developer")

        self.assertEqual(second.name, "T005-developer-2.log")
        self.assertEqual(first.read_text(encoding="utf-8"), "прогон 1\n")

    def test_numbering_is_per_role_and_task(self):
        artel.new_agent_log("T005", "developer")

        self.assertEqual(artel.new_agent_log("T005", "reviewer").name,
                         "T005-reviewer-1.log")
        self.assertEqual(artel.new_agent_log("T006", "developer").name,
                         "T006-developer-1.log")

    def test_alien_files_do_not_break_numbering(self):
        artel.LOGS.mkdir(parents=True)
        (artel.LOGS / "T005-developer-хвост.log").touch()

        self.assertEqual(artel.new_agent_log("T005", "developer").name,
                         "T005-developer-1.log")


class StreamToLogTest(TmpRootTest):
    def setUp(self):
        super().setUp()
        self.log = artel.new_agent_log("T005", "developer")

    def test_line_is_written_before_stream_ends(self):
        seen = []

        def agent_output():
            yield "первая\n"
            # процесс ещё жив — строка уже обязана быть в файле
            seen.append(self.log.read_text(encoding="utf-8"))
            yield "вторая\n"

        self.capture(artel.stream_to_log, agent_output(), self.log)

        self.assertEqual(seen, ["первая\n"])
        self.assertEqual(self.log.read_text(encoding="utf-8"),
                         "первая\nвторая\n")

    def test_output_also_goes_to_console(self):
        out = self.capture(artel.stream_to_log, iter(["раз\n", "два\n"]), self.log)

        self.assertEqual(out, "раз\nдва\n")

    def test_appends_to_existing_file(self):
        self.log.write_text("хвост прошлого чтения\n", encoding="utf-8")

        self.capture(artel.stream_to_log, iter(["новая\n"]), self.log)

        self.assertEqual(self.log.read_text(encoding="utf-8"),
                         "хвост прошлого чтения\nновая\n")


class CmdRunLoggingTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.capture(artel.cmd_init)
        self.capture(artel.cmd_new, "Лог агента")
        conn = artel.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()

    def run_agent(self, lines, returncode: int = 0):
        with mock.patch.object(artel.subprocess, "Popen") as popen:
            popen.return_value = FakeProc(lines, returncode)
            return self.capture(artel.cmd_run, self.TASK)

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in artel.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def log_file(self, n: int) -> Path:
        return artel.LOGS / f"{self.TASK}-developer-{n}.log"

    def test_agent_output_lands_in_log_file(self):
        self.run_agent(["шаг 1\n", "шаг 2\n"])

        self.assertEqual(self.log_file(1).read_text(encoding="utf-8"),
                         "шаг 1\nшаг 2\n")

    def test_agent_output_still_printed(self):
        out = self.run_agent(["шаг 1\n"])

        self.assertIn("шаг 1\n", out)
        self.assertIn("developer завершил (rc=0)", out)

    def test_log_path_printed_at_start(self):
        out = self.run_agent(["шаг 1\n"])

        self.assertIn(str(self.log_file(1)), out.splitlines()[0])

    def test_log_path_journaled_at_start(self):
        self.run_agent(["шаг 1\n"])

        details = self.journal_details("agent run started")
        self.assertEqual(len(details), 1)
        self.assertIn(str(self.log_file(1)), details[0])

    def test_second_run_writes_new_file(self):
        self.run_agent(["прогон 1\n"])
        self.run_agent(["прогон 2\n"])

        self.assertEqual(self.log_file(1).read_text(encoding="utf-8"), "прогон 1\n")
        self.assertEqual(self.log_file(2).read_text(encoding="utf-8"), "прогон 2\n")

    def test_stderr_merged_into_the_same_file(self):
        with mock.patch.object(artel.subprocess, "Popen") as popen:
            popen.return_value = FakeProc([])
            self.capture(artel.cmd_run, self.TASK)

        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["stdout"], artel.subprocess.PIPE)
        self.assertEqual(kwargs["stderr"], artel.subprocess.STDOUT)

    def test_missing_cli_prints_prompt_and_journals_skip(self):
        with mock.patch.object(artel.subprocess, "Popen", side_effect=FileNotFoundError):
            out = self.capture(artel.cmd_run, self.TASK)

        self.assertIn("Роль: разработчик", out)
        self.assertEqual(self.journal_details("agent run SKIPPED"),
                         ["claude CLI не найден"])

    def test_timeout_kills_process_and_journals(self):
        proc = mock.Mock(stdout=iter([]))
        proc.wait.side_effect = [
            artel.subprocess.TimeoutExpired(cmd="claude", timeout=artel.AGENT_TIMEOUT_SEC),
            -9,
        ]
        with mock.patch.object(artel.subprocess, "Popen", return_value=proc):
            out = self.capture(artel.cmd_run, self.TASK)

        proc.kill.assert_called_once()
        self.assertIn("таймаут шага", out)
        self.assertEqual(self.journal_details("agent run TIMEOUT"), ["30 мин"])
        self.assertEqual(self.journal_details("agent run finished"), [])


if __name__ == "__main__":
    unittest.main()
