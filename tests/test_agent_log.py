"""Тесты лога агента по ходу шага (см. tasks/T005/SPEC.md).

Процесс агента в основном фейковый: `subprocess.Popen` подменяется объектом
с итератором строк вместо stdout — так проверяется и построчность записи, и
то, что `cmd_run` не теряет вывод. Связка «настоящий пайп + поток» отдельно
проверена на реальном подпроцессе (RealSubprocessPumpTest).
"""
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel  # noqa: E402


def event(**fields) -> str:
    """Строка потока `--output-format stream-json`."""
    return json.dumps(fields, ensure_ascii=False) + "\n"


def assistant_event(*blocks) -> str:
    return event(type="assistant", message={"role": "assistant", "content": list(blocks)})


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


class BlockingStream(FakeStream):
    """Пайп, из которого EOF не приходит: его write-конец держит чужой процесс."""

    def __init__(self):
        super().__init__([])
        self.released = threading.Event()

    def __next__(self) -> str:
        self.released.wait(timeout=30)
        raise StopIteration


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
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


class RenderAgentLineTest(unittest.TestCase):
    """Событие stream-json → строка Оператору: видно, что агент делает."""

    def test_assistant_text_is_shown_as_is(self):
        line = artel.render_agent_line(
            assistant_event({"type": "text", "text": "Начинаю с SPEC."}))

        self.assertEqual(line, "Начинаю с SPEC.\n")

    def test_tool_use_shows_tool_and_command(self):
        line = artel.render_agent_line(assistant_event(
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "python3 -m unittest discover -s tests"}}))

        self.assertEqual(line, "· Bash python3 -m unittest discover -s tests\n")

    def test_tool_use_shows_file_path_when_there_is_no_command(self):
        line = artel.render_agent_line(assistant_event(
            {"type": "tool_use", "name": "Edit",
             "input": {"file_path": "orchestrator/artel.py"}}))

        self.assertEqual(line, "· Edit orchestrator/artel.py\n")

    def test_multiline_command_stays_one_line(self):
        line = artel.render_agent_line(assistant_event(
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "git add -A\ngit commit -m 'T005'"}}))

        self.assertEqual(line, "· Bash git add -A git commit -m 'T005'\n")
        self.assertEqual(line.count("\n"), 1)

    def test_service_events_are_dropped(self):
        for raw in (event(type="system", subtype="init", cwd="/tmp"),
                    event(type="system", subtype="hook_started"),
                    event(type="rate_limit_event", rate_limit_info={}),
                    event(type="user", message={"role": "user", "content": [
                        {"type": "tool_result", "content": "простыня вывода"}]}),
                    event(type="result", subtype="success", is_error=False,
                          result="готово", total_cost_usd=0.42)):
            with self.subTest(raw=raw[:40]):
                self.assertEqual(artel.render_agent_line(raw), "")

    def test_failed_result_is_shown(self):
        line = artel.render_agent_line(
            event(type="result", subtype="error_during_execution",
                  is_error=True, result="лимит контекста"))

        self.assertIn("лимит контекста", line)
        self.assertTrue(line.endswith("\n"))

    def test_non_json_passes_through_unchanged(self):
        for raw in ("Traceback (most recent call last):\n", "  простой stderr\n"):
            with self.subTest(raw=raw):
                self.assertEqual(artel.render_agent_line(raw), raw)

    def test_broken_json_passes_through_unchanged(self):
        raw = '{"type":"assistant","message":\n'

        self.assertEqual(artel.render_agent_line(raw), raw)


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

    def test_stream_json_events_land_rendered(self):
        stream = iter([
            event(type="system", subtype="init"),
            assistant_event({"type": "text", "text": "Читаю SPEC."}),
            assistant_event({"type": "tool_use", "name": "Read",
                             "input": {"file_path": "tasks/T005/SPEC.md"}}),
        ])

        out = self.capture(artel.stream_to_log, stream, self.log)

        self.assertEqual(out, "Читаю SPEC.\n· Read tasks/T005/SPEC.md\n")
        self.assertEqual(self.log.read_text(encoding="utf-8"), out)


class OutputPumpTest(TmpRootTest):
    def test_pump_is_daemon(self):
        """Не-демон не дал бы интерпретатору выйти, если EOF не пришёл."""
        pump = artel.OutputPump(iter([]), artel.new_agent_log("T005", "developer"))

        self.assertTrue(pump.daemon)

    def test_log_failure_is_kept_and_console_survives(self):
        unreachable = artel.LOGS / "нет-такого-каталога" / "шаг.log"
        pump = artel.OutputPump(iter(["агент жив\n"]), unreachable)

        buf = io.StringIO()
        with redirect_stdout(buf):
            pump.start()
            pump.join(5)

        self.assertIsInstance(pump.error, OSError)
        self.assertEqual(buf.getvalue(), "агент жив\n",
                         "пайп дочитывается в консоль даже без лога")

    def test_clean_run_leaves_no_error(self):
        log = artel.new_agent_log("T005", "developer")
        pump = artel.OutputPump(iter(["готово\n"]), log)

        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)

        self.assertIsNone(pump.error)
        self.assertEqual(log.read_text(encoding="utf-8"), "готово\n")


class RealSubprocessPumpTest(TmpRootTest):
    """Настоящий пайп и настоящий поток: фейки эту связку не проверяют."""

    def test_first_line_lands_in_log_while_process_is_alive(self):
        log = artel.new_agent_log("T005", "developer")
        proc = subprocess.Popen(
            [sys.executable, "-c",
             "import time; print('step-1', flush=True); time.sleep(30)"],
            text=True, bufsize=1,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.addCleanup(proc.stdout.close)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)

        with redirect_stdout(io.StringIO()):
            pump = artel.OutputPump(proc.stdout, log)
            pump.start()
            deadline = time.monotonic() + 10
            while not log.read_text(encoding="utf-8").endswith("\n"):
                if time.monotonic() > deadline:
                    break
                time.sleep(0.02)
            written = log.read_text(encoding="utf-8")
            still_running = proc.poll() is None
            proc.kill()
            pump.join(5)

        self.assertEqual(written, "step-1\n")
        self.assertTrue(still_running,
                        "строка обязана лечь в файл, пока процесс ещё работает")


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

    def test_agent_started_in_streaming_mode(self):
        """Без stream-json строки приходят одним куском в конце — см. PLAN.md."""
        with mock.patch.object(artel.subprocess, "Popen") as popen:
            popen.return_value = FakeProc([])
            self.capture(artel.cmd_run, self.TASK)

        argv = popen.call_args.args[0]
        self.assertIn("--output-format", argv)
        self.assertEqual(argv[argv.index("--output-format") + 1], "stream-json")
        self.assertIn("--verbose", argv, "без него CLI выходит с rc=1")

    def test_pipe_closed_after_pump_finished(self):
        with mock.patch.object(artel.subprocess, "Popen") as popen:
            proc = FakeProc(["шаг 1\n"])
            popen.return_value = proc
            self.capture(artel.cmd_run, self.TASK)

        self.assertTrue(proc.stdout.closed)

    def test_missing_cli_prints_prompt_and_journals_skip(self):
        with mock.patch.object(artel.subprocess, "Popen", side_effect=FileNotFoundError):
            out = self.capture(artel.cmd_run, self.TASK)

        self.assertIn("Роль: разработчик", out)
        self.assertEqual(self.journal_details("agent run SKIPPED"),
                         ["claude CLI не найден"])

    def test_timeout_kills_process_and_journals(self):
        proc = mock.Mock(stdout=FakeStream([]))
        proc.wait.side_effect = [
            artel.subprocess.TimeoutExpired(cmd="claude", timeout=artel.AGENT_TIMEOUT_SEC),
            -9,
        ]
        with mock.patch.object(artel.subprocess, "Popen", return_value=proc):
            out = self.capture(artel.cmd_run, self.TASK)

        proc.kill.assert_called_once()
        self.assertIn("таймаут шага", out)
        self.assertEqual(self.journal_details("agent run TIMEOUT"),
                         [f"30 мин, попытка 1/{artel.AGENT_ATTEMPTS} (без ретрая)"])
        self.assertEqual(self.journal_details("agent run finished"), [])

    def test_stuck_pump_does_not_hang_run(self):
        """EOF не пришёл (пайп держит чужой процесс) — run всё равно вернётся."""
        proc = FakeProc([])
        proc.stdout = BlockingStream()
        self.addCleanup(proc.stdout.released.set)

        with mock.patch.object(artel, "PUMP_JOIN_TIMEOUT_SEC", 0.05), \
                mock.patch.object(artel.subprocess, "Popen", return_value=proc):
            out = self.capture(artel.cmd_run, self.TASK)

        self.assertIn("лог неполный", out)
        self.assertIn("developer завершил (rc=0)", out, "управление вернулось")
        self.assertFalse(proc.stdout.closed,
                         "пайп с живым читателем не закрываем — close() ждал бы лок")
        details = self.journal_details("agent log INCOMPLETE")
        self.assertEqual(len(details), 1)
        self.assertIn("лог неполный", details[0])

    def test_broken_log_is_journaled_not_silent(self):
        with mock.patch.object(artel, "stream_to_log",
                               side_effect=OSError("No space left on device")), \
                mock.patch.object(artel.subprocess, "Popen") as popen:
            popen.return_value = FakeProc(["шаг 1\n"])
            out = self.capture(artel.cmd_run, self.TASK)

        details = self.journal_details("agent log INCOMPLETE")
        self.assertEqual(len(details), 1)
        self.assertIn("No space left on device", details[0])
        self.assertIn("лог не записан", out)


if __name__ == "__main__":
    unittest.main()
