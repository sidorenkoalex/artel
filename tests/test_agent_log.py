"""Тесты лога агента по ходу шага (см. tasks/T005/SPEC.md).

Процесс агента в основном фейковый: `subprocess.Popen` подменяется объектом
с итератором строк вместо stdout — так проверяется и построчность записи, и
то, что `cmd_run` не теряет вывод. Связка «настоящий пайп + поток» отдельно
проверена на реальном подпроцессе (RealSubprocessPumpTest).

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002, принцип целостности): кодируют инвариант
«журнал шагов пишется всегда» — запуск, исход, лог и сбой перекачки
попадают в журнал, а не в тишину (README «Инварианты» 5,
docs/design.md §6, §7). Ослабить, заскипать или удалить их может только
Оператор отдельным ADR; перечень «инвариант → тест → откуда» —
docs/invariants.md.
"""
import io
import json
import shutil
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

from orchestrator import (agent_log, catalog, config, gitcmd,  # noqa: E402
                          runner, store)
from tests.sandbox import (FakeProc, FakeStream, TmpRootTest,  # noqa: E402
                           capture_new_task_id, fake_git,
                           seed_developer_brief_fixtures, sync_spec_from_worktree)

REPO_ROOT = Path(__file__).resolve().parent.parent


def event(**fields) -> str:
    """Строка потока `--output-format stream-json`."""
    return json.dumps(fields, ensure_ascii=False) + "\n"


def assistant_event(*blocks) -> str:
    return event(type="assistant", message={"role": "assistant", "content": list(blocks)})


class BlockingStream(FakeStream):
    """Пайп, из которого EOF не приходит: его write-конец держит чужой процесс."""

    def __init__(self):
        super().__init__([])
        self.released = threading.Event()

    def __next__(self) -> str:
        self.released.wait(timeout=30)
        raise StopIteration


class BrokenPipeStream(FakeStream):
    """Пайп, обрывающийся посреди чтения: после заготовленных строк — `OSError`
    вместо чистого `StopIteration` (tasks/T040, AC-2)."""

    def __next__(self) -> str:
        try:
            return next(self.lines)
        except StopIteration:
            raise OSError("обрыв stdout-пайпа шага") from None


class _AgentLogTmpRootTest(TmpRootTest):
    """Общая песочница: DB, TASKS и LOGS уводятся во временный каталог.

    `ROOT` тоже уводится (SPEC T049: холодный старт сканирует его для
    посева счётчика — непропатченный ROOT читал бы реальное дерево
    пульта) — `templates/` копируется рядом, `cmd_new` продолжает читать
    настоящий `templates/SPEC.md`, только уже из песочницы.
    """

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR",
                     "WORKTREES", "ROOT")

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        seed_developer_brief_fixtures(self.root)


TmpRootTest = _AgentLogTmpRootTest


class NewAgentLogTest(TmpRootTest):
    def test_first_run_gets_number_one(self):
        path = agent_log.new_agent_log("T005", "developer")

        self.assertEqual(path.name, "T005-developer-1.log")
        self.assertTrue(path.exists(), "файл создаётся сразу — для tail -f")

    def test_second_run_increments_and_keeps_old(self):
        first = agent_log.new_agent_log("T005", "developer")
        first.write_text("прогон 1\n", encoding="utf-8")

        second = agent_log.new_agent_log("T005", "developer")

        self.assertEqual(second.name, "T005-developer-2.log")
        self.assertEqual(first.read_text(encoding="utf-8"), "прогон 1\n")

    def test_numbering_is_per_role_and_task(self):
        agent_log.new_agent_log("T005", "developer")

        self.assertEqual(agent_log.new_agent_log("T005", "reviewer").name,
                         "T005-reviewer-1.log")
        self.assertEqual(agent_log.new_agent_log("T006", "developer").name,
                         "T006-developer-1.log")

    def test_alien_files_do_not_break_numbering(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T005-developer-хвост.log").touch()

        self.assertEqual(agent_log.new_agent_log("T005", "developer").name,
                         "T005-developer-1.log")


class RenderAgentLineTest(unittest.TestCase):
    """Событие stream-json → строка Оператору: видно, что агент делает."""

    def test_assistant_text_is_shown_as_is(self):
        line = agent_log.render_agent_line(
            assistant_event({"type": "text", "text": "Начинаю с SPEC."}))

        self.assertEqual(line, "Начинаю с SPEC.\n")

    def test_tool_use_shows_tool_and_command(self):
        line = agent_log.render_agent_line(assistant_event(
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "python3 -m unittest discover -s tests"}}))

        self.assertEqual(line, "· Bash python3 -m unittest discover -s tests\n")

    def test_tool_use_shows_file_path_when_there_is_no_command(self):
        line = agent_log.render_agent_line(assistant_event(
            {"type": "tool_use", "name": "Edit",
             "input": {"file_path": "orchestrator/artel.py"}}))

        self.assertEqual(line, "· Edit orchestrator/artel.py\n")

    def test_multiline_command_stays_one_line(self):
        line = agent_log.render_agent_line(assistant_event(
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
                self.assertEqual(agent_log.render_agent_line(raw), "")

    def test_failed_result_is_shown(self):
        line = agent_log.render_agent_line(
            event(type="result", subtype="error_during_execution",
                  is_error=True, result="лимит контекста"))

        self.assertIn("лимит контекста", line)
        self.assertTrue(line.endswith("\n"))

    def test_non_json_passes_through_unchanged(self):
        for raw in ("Traceback (most recent call last):\n", "  простой stderr\n"):
            with self.subTest(raw=raw):
                self.assertEqual(agent_log.render_agent_line(raw), raw)

    def test_broken_json_passes_through_unchanged(self):
        raw = '{"type":"assistant","message":\n'

        self.assertEqual(agent_log.render_agent_line(raw), raw)


class StreamToLogTest(TmpRootTest):
    def setUp(self):
        super().setUp()
        self.log = agent_log.new_agent_log("T005", "developer")

    def test_line_is_written_before_stream_ends(self):
        seen = []

        def agent_output():
            yield "первая\n"
            # процесс ещё жив — строка уже обязана быть в файле
            seen.append(self.log.read_text(encoding="utf-8"))
            yield "вторая\n"

        self.capture(agent_log.stream_to_log, agent_output(), self.log)

        self.assertEqual(seen, ["первая\n"])
        self.assertEqual(self.log.read_text(encoding="utf-8"),
                         "первая\nвторая\n")

    def test_output_also_goes_to_console(self):
        out = self.capture(agent_log.stream_to_log, iter(["раз\n", "два\n"]), self.log)

        self.assertEqual(out, "раз\nдва\n")

    def test_appends_to_existing_file(self):
        self.log.write_text("хвост прошлого чтения\n", encoding="utf-8")

        self.capture(agent_log.stream_to_log, iter(["новая\n"]), self.log)

        self.assertEqual(self.log.read_text(encoding="utf-8"),
                         "хвост прошлого чтения\nновая\n")

    def test_stream_json_events_land_rendered(self):
        stream = iter([
            event(type="system", subtype="init"),
            assistant_event({"type": "text", "text": "Читаю SPEC."}),
            assistant_event({"type": "tool_use", "name": "Read",
                             "input": {"file_path": "tasks/T005/SPEC.md"}}),
        ])

        out = self.capture(agent_log.stream_to_log, stream, self.log)

        self.assertEqual(out, "Читаю SPEC.\n· Read tasks/T005/SPEC.md\n")
        self.assertEqual(self.log.read_text(encoding="utf-8"), out)


class OutputPumpTest(TmpRootTest):
    def test_pump_is_daemon(self):
        """Не-демон не дал бы интерпретатору выйти, если EOF не пришёл."""
        pump = agent_log.OutputPump(iter([]), agent_log.new_agent_log("T005", "developer"))

        self.assertTrue(pump.daemon)

    def test_log_failure_is_kept_and_console_survives(self):
        unreachable = config.LOGS / "нет-такого-каталога" / "шаг.log"
        pump = agent_log.OutputPump(iter(["агент жив\n"]), unreachable)

        buf = io.StringIO()
        with redirect_stdout(buf):
            pump.start()
            pump.join(5)

        self.assertIsInstance(pump.error, OSError)
        self.assertEqual(buf.getvalue(), "агент жив\n",
                         "пайп дочитывается в консоль даже без лога")

    def test_clean_run_leaves_no_error(self):
        log = agent_log.new_agent_log("T005", "developer")
        pump = agent_log.OutputPump(iter(["готово\n"]), log)

        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)

        self.assertIsNone(pump.error)
        self.assertEqual(log.read_text(encoding="utf-8"), "готово\n")

    def test_partial_tokens_survive_a_broken_pipe(self):
        """tasks/T040, AC-2: usage-события до обрыва пайпа не теряются —
        читать их после обрыва больше неоткуда."""
        log = agent_log.new_agent_log("T005", "developer")
        stream = BrokenPipeStream([
            event(type="assistant",
                 message={"role": "assistant", "content": [],
                         "usage": {"input_tokens": 30, "output_tokens": 12}}),
        ])
        pump = agent_log.OutputPump(stream, log)

        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)

        self.assertIsInstance(pump.error, OSError)
        self.assertEqual(pump.partial_tokens, 42)
        self.assertTrue(pump.saw_usage_event)

    def test_no_usage_events_leaves_partial_tokens_at_zero(self):
        pump = agent_log.OutputPump(iter(["просто вывод\n"]),
                                    agent_log.new_agent_log("T005", "developer"))

        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)

        self.assertEqual(pump.partial_tokens, 0)
        self.assertFalse(pump.saw_usage_event)

    def test_friction_is_computed_from_the_raw_stream_not_the_rendered_log(self):
        """Ответ Оператора 01.09 (tasks/T095/ANSWER-1.md): персистентный
        лог несёт только рендер (`render_agent_line`) — сигналов ТЗ в нём
        нет. `pump.friction` обязана увидеть повторный `Read` по сырому
        потоку живьём, даже когда пост-фактум разбор того же файла лога
        честно даёт 0.0 (тот самый дефект, который чинит T095)."""
        log = agent_log.new_agent_log("T005", "developer")
        stream = iter([
            assistant_event({"type": "tool_use", "id": "t1", "name": "Read",
                            "input": {"file_path": "a.py"}}),
            assistant_event({"type": "tool_use", "id": "t2", "name": "Read",
                            "input": {"file_path": "a.py"}}),
        ])
        pump = agent_log.OutputPump(stream, log)

        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)

        self.assertEqual(agent_log.step_friction(log), 0.0,
                         "лог на диске — рендер, а не сырой поток")
        self.assertEqual(pump.friction, 0.5,
                         "трение вживую обязано увидеть повтор Read")

    def test_friction_defaults_to_zero_without_a_single_tool_call(self):
        pump = agent_log.OutputPump(iter(["просто вывод\n"]),
                                    agent_log.new_agent_log("T005", "developer"))

        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)

        self.assertEqual(pump.friction, 0.0)


class RealSubprocessPumpTest(TmpRootTest):
    """Настоящий пайп и настоящий поток: фейки эту связку не проверяют."""

    def test_first_line_lands_in_log_while_process_is_alive(self):
        log = agent_log.new_agent_log("T005", "developer")
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
            pump = agent_log.OutputPump(proc.stdout, log)
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

    def setUp(self):
        super().setUp()
        # ДО `cmd_new` (SPEC T048) — сам заводит ветку/worktree через
        # `gitcmd`, без фейка ушёл бы в реальный репозиторий пульта.
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.capture(catalog.cmd_init)
        # `cmd_new` возвращает id ULID (SPEC T094, требование 2), больше не
        # предсказуемый "T001" — забираем реальный через
        # `capture_new_task_id`, а не `self.capture` (та отбрасывает возврат).
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Лог агента")
        sync_spec_from_worktree(self.TASK)
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def run_agent(self, lines, returncode: int = 0):
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(lines, returncode)
            return self.capture(runner.cmd_run, self.TASK)

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def log_file(self, n: int) -> Path:
        return config.LOGS / f"{self.TASK}-developer-{n}.log"

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
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc([])
            self.capture(runner.cmd_run, self.TASK)

        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["stdout"], runner.subprocess.PIPE)
        self.assertEqual(kwargs["stderr"], runner.subprocess.STDOUT)

    def test_agent_started_in_streaming_mode(self):
        """Без stream-json строки приходят одним куском в конце — см. PLAN.md."""
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc([])
            self.capture(runner.cmd_run, self.TASK)

        argv = popen.call_args.args[0]
        self.assertIn("--output-format", argv)
        self.assertEqual(argv[argv.index("--output-format") + 1], "stream-json")
        self.assertIn("--verbose", argv, "без него CLI выходит с rc=1")

    def test_pipe_closed_after_pump_finished(self):
        with mock.patch.object(runner, "spawn_agent") as popen:
            proc = FakeProc(["шаг 1\n"])
            popen.return_value = proc
            self.capture(runner.cmd_run, self.TASK)

        self.assertTrue(proc.stdout.closed)

    def test_missing_cli_saves_prompt_to_a_file_and_journals_skip(self):
        """Ручной прогон роли: промпт в файле, путь — в выводе и в журнале."""
        with mock.patch.object(runner, "spawn_agent", side_effect=FileNotFoundError):
            out = self.capture(runner.cmd_run, self.TASK)

        saved = list(config.LOGS.glob("*.prompt.txt"))
        self.assertEqual(len(saved), 1)
        self.assertIn("Роль: разработчик", saved[0].read_text(encoding="utf-8"))
        self.assertIn(str(saved[0]), out, "Оператор видит, где взять промпт")
        self.assertNotIn("Роль: разработчик", out, "простыня не летит в терминал")
        self.assertEqual(self.journal_details("agent run SKIPPED"),
                         [f"claude CLI не найден, промпт: {saved[0]}"])

    def test_timeout_kills_process_and_journals(self):
        proc = mock.Mock(stdout=FakeStream([]))
        proc.wait.side_effect = [
            runner.subprocess.TimeoutExpired(cmd="claude", timeout=config.AGENT_TIMEOUT_SEC),
            -9,
        ]
        with mock.patch.object(runner, "spawn_agent", return_value=proc):
            out = self.capture(runner.cmd_run, self.TASK)

        proc.kill.assert_called_once()
        self.assertIn("таймаут шага", out)
        self.assertEqual(
            self.journal_details("agent run TIMEOUT"),
            [f"{config.AGENT_TIMEOUT_SEC // 60} мин, попытка 1/"
             f"{config.AGENT_ATTEMPTS} (без ретрая)"])
        self.assertEqual(self.journal_details("agent run finished"), [])

    def test_stuck_pump_does_not_hang_run(self):
        """EOF не пришёл (пайп держит чужой процесс) — run всё равно вернётся."""
        proc = FakeProc([])
        proc.stdout = BlockingStream()
        self.addCleanup(proc.stdout.released.set)

        with mock.patch.object(config, "PUMP_JOIN_TIMEOUT_SEC", 0.05), \
                mock.patch.object(runner, "spawn_agent", return_value=proc):
            out = self.capture(runner.cmd_run, self.TASK)

        self.assertIn("лог неполный", out)
        self.assertIn("developer завершил (rc=0)", out, "управление вернулось")
        self.assertFalse(proc.stdout.closed,
                         "пайп с живым читателем не закрываем — close() ждал бы лок")
        details = self.journal_details("agent log INCOMPLETE")
        self.assertEqual(len(details), 1)
        self.assertIn("лог неполный", details[0])

    def test_broken_log_is_journaled_not_silent(self):
        with mock.patch.object(agent_log, "stream_to_log",
                               side_effect=OSError("No space left on device")), \
                mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["шаг 1\n"])
            out = self.capture(runner.cmd_run, self.TASK)

        details = self.journal_details("agent log INCOMPLETE")
        self.assertEqual(len(details), 1)
        self.assertIn("No space left on device", details[0])
        self.assertIn("лог не записан", out)


def tool_use_call(call_id: str, name: str, **input_kwargs) -> dict:
    return {"type": "tool_use", "id": call_id, "name": name, "input": input_kwargs}


def tool_result_event(call_id: str, content: str, is_error: bool = False) -> str:
    return event(type="user", message={"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": call_id, "content": content,
         "is_error": is_error}]})


class StepFrictionTest(unittest.TestCase):
    """tasks/T095/SPEC.md, AC-1 — детали помимо направления/детерминизма,
    уже покрытых `tasks/T095/acceptance_tests/test_ac1_*.py`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp_dir = Path(tmp.name)
        self._n = 0

    def write(self, lines: list) -> Path:
        self._n += 1
        path = self.tmp_dir / f"step-{self._n}.log"
        path.write_text("".join(lines), encoding="utf-8")
        return path

    def test_empty_log_has_zero_friction(self):
        path = self.write([])

        self.assertEqual(agent_log.step_friction(path), 0.0)

    def test_log_without_a_single_tool_call_has_zero_friction(self):
        path = self.write([assistant_event({"type": "text", "text": "Читаю SPEC."})])

        self.assertEqual(agent_log.step_friction(path), 0.0)

    def test_non_json_lines_are_ignored_not_counted_as_calls(self):
        path = self.write([
            "Traceback (most recent call last):\n",
            assistant_event(tool_use_call("t1", "Read", file_path="a.py")),
        ])

        self.assertEqual(agent_log.step_friction(path), 0.0)

    def test_a_call_flagged_by_two_signals_is_not_counted_twice(self):
        """Повторный Read того же файла + ошибка на том же вызове — один
        и тот же вызов не должен удвоить непродуктивную долю."""
        path = self.write([
            assistant_event(tool_use_call("t1", "Read", file_path="a.py")),
            assistant_event(tool_use_call("t2", "Read", file_path="a.py")),
            tool_result_event("t2", "permission denied", is_error=True),
            assistant_event(tool_use_call("t3", "Bash", command="pytest")),
            assistant_event(tool_use_call("t4", "Edit", file_path="c.py")),
        ])

        self.assertEqual(agent_log.step_friction(path), 0.25)

    def test_different_files_read_once_each_are_not_repeats(self):
        path = self.write([
            assistant_event(tool_use_call("t1", "Read", file_path="a.py")),
            assistant_event(tool_use_call("t2", "Read", file_path="b.py")),
            assistant_event(tool_use_call("t3", "Read", file_path="c.py")),
        ])

        self.assertEqual(agent_log.step_friction(path), 0.0)

    def test_retry_of_a_different_command_after_an_error_is_not_flagged(self):
        """Ошибка одного вызова не обязана метить НЕ похожий на него
        следующий вызов — сигнал 2 ТЗ это «тот же вызов повторно», не
        «любой вызов после сбоя»."""
        path = self.write([
            assistant_event(tool_use_call("t1", "Bash", command="pytest")),
            tool_result_event("t1", "ModuleNotFoundError", is_error=True),
            assistant_event(tool_use_call("t2", "Read", file_path="a.py")),
        ])

        self.assertEqual(agent_log.step_friction(path), 0.5)

    def test_repeated_large_result_from_different_tools_is_flagged(self):
        """Сигнал 3 ТЗ не привязан к конкретному инструменту/файлу — тот
        же большой текст, полученный ЛЮБЫМ инструментом дважды, считается."""
        big = "y" * (agent_log.LARGE_TOOL_RESULT_CHARS + 1)
        path = self.write([
            assistant_event(tool_use_call("t1", "Bash", command="cat log")),
            tool_result_event("t1", big),
            assistant_event(tool_use_call("t2", "Read", file_path="other.log")),
            tool_result_event("t2", big),
        ])

        self.assertEqual(agent_log.step_friction(path), 0.5)


if __name__ == "__main__":
    unittest.main()
