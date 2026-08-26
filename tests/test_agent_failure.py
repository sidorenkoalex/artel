"""Тесты провала шага по коду возврата агента (см. tasks/T006/SPEC.md).

Реального `claude` CLI тут нет: `subprocess.Popen` подменяется списком
фейковых процессов — по одному на попытку, — поэтому сценарий «упал, упал,
поднялся» проверяется целиком, включая журнал и состояние задачи. Паузы
бэкоффа не спим, а записываем.

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002, принцип целостности): кодируют инварианты
«у каждого цикла числовой лимит, после лимита — Оператор, не ретрай» и
«транзиентные ретраи не считаются итерацией ревью» (README «Инварианты»
3, docs/design.md §6). Ослабить, заскипать или удалить их может только
Оператор отдельным ADR; перечень «инвариант → тест → откуда» —
docs/invariants.md.
"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (agent_log, catalog, config, fsm, gitcmd,  # noqa: E402
                          runner, store)
from tests.sandbox import TmpRootTest, fake_git  # noqa: E402


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


class _AgentFailureTmpRootTest(TmpRootTest):
    """Общая песочница: DB, TASKS и LOGS уводятся во временный каталог."""

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR")


TmpRootTest = _AgentFailureTmpRootTest


class LogTailTest(TmpRootTest):
    """Хвост лога прогона — то, по чему Оператор видит причину падения."""

    def log_with(self, text: str) -> Path:
        path = agent_log.new_agent_log("T006", "developer")
        path.write_text(text, encoding="utf-8")
        return path

    def test_only_last_lines_are_taken(self):
        path = self.log_with("".join(f"строка {i}\n" for i in range(1, 51)))

        tail = agent_log.log_tail(path)

        self.assertTrue(tail.startswith(f"строка {50 - config.LOG_TAIL_LINES + 1}\n"))
        self.assertTrue(tail.endswith("строка 50"))
        self.assertEqual(len(tail.splitlines()), config.LOG_TAIL_LINES)

    def test_short_log_is_taken_whole(self):
        path = self.log_with("API Error: 401 Unauthorized\n")

        self.assertEqual(agent_log.log_tail(path), "API Error: 401 Unauthorized")

    def test_empty_log_is_reported_as_empty(self):
        self.assertEqual(agent_log.log_tail(self.log_with("")), "лог пуст")

    def test_long_line_is_cut_to_the_end(self):
        path = self.log_with("ш" * 5000 + "причина в конце\n")

        tail = agent_log.log_tail(path)

        self.assertEqual(len(tail), config.LOG_TAIL_CHARS)
        self.assertTrue(tail.endswith("причина в конце"))

    def test_unreadable_log_does_not_raise(self):
        missing = config.LOGS / "нет-такого-каталога" / "шаг.log"

        self.assertIn("лог не прочитан", agent_log.log_tail(missing))


class CmdRunFailureTest(TmpRootTest):
    """`run` с падающим агентом: журнал, ретраи, эскалация."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Код возврата агента")
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()

        self.pauses = []
        patcher = mock.patch.object(runner.time, "sleep", self.pauses.append)
        patcher.start()
        self.addCleanup(patcher.stop)

        # Шаг ревью собирает пакет настоящим git (T011); в песочнице
        # репозитория нет, а этому модулю важен исход попыток агента, не diff.
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def run_agent(self, *attempts) -> str:
        """attempts: (rc, строки вывода) — по одной паре на попытку."""
        procs = [FakeProc(lines, rc) for rc, lines in attempts]
        with mock.patch.object(runner, "spawn_agent", side_effect=procs) as popen:
            out = self.capture(runner.cmd_run, self.TASK)
        self.popen = popen
        return out

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def test_successful_run_behaves_as_before(self):
        out = self.run_agent((0, ["готово\n"]))

        self.assertIn("developer завершил (rc=0)", out)
        self.assertIn(f"дальше: artel.py advance {self.TASK}", out)
        self.assertEqual(self.journal_details("agent run FAILED"), [])
        self.assertEqual(self.task_row()["state"], "in_dev")
        self.assertEqual(self.pauses, [], "успех не ретраится")

    def test_failure_is_journaled_with_rc_and_log_tail(self):
        # Попытки говорят разное: хвост в записи должен быть от своего прогона,
        # а не от первого — по нему разбирают, чем кончилась именно эта попытка.
        self.run_agent(*[(1, [f"API Error: 401 на попытке {n}\n"])
                         for n in range(1, config.AGENT_ATTEMPTS + 1)])

        details = self.journal_details("agent run FAILED")
        self.assertEqual(len(details), config.AGENT_ATTEMPTS)
        self.assertIn("rc=1", details[0])
        self.assertIn("401 на попытке 1", details[0], "в хвосте лога — причина")
        self.assertIn(f"401 на попытке {config.AGENT_ATTEMPTS}", details[-1],
                      "хвост берётся из лога своей попытки")
        self.assertEqual(self.journal_details("agent run finished"), [],
                         "провал не пишется как нормальное завершение")

    def test_console_does_not_repeat_log_tail_on_every_attempt(self):
        out = self.run_agent(*[(1, ["API Error: 401 Unauthorized\n"])]
                             * config.AGENT_ATTEMPTS)

        # По разу на попытку — живой вывод перекачки; плюс один раз в причине
        # эскалации, которая печатается последней, когда живые строки уже
        # уехали с экрана. Каждый провал свой хвост в консоли не повторяет.
        self.assertEqual(out.count("401 Unauthorized"), config.AGENT_ATTEMPTS + 1,
                         "строки лога Оператор уже видел вживую — не дублируем")
        self.assertIn("причина в", out, "путь к логу в консоли остаётся")

    def test_failure_prints_no_advance_hint(self):
        out = self.run_agent(*[(1, ["упал\n"])] * config.AGENT_ATTEMPTS)

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
        self.run_agent(*[(1, ["упал\n"])] * config.AGENT_ATTEMPTS)

        self.assertEqual(self.pauses, [config.RETRY_BACKOFF_SEC,
                                       config.RETRY_BACKOFF_SEC * 2])
        self.assertEqual(len(self.journal_details("agent run retry")),
                         config.AGENT_RETRIES)

    def test_attempt_counter_is_journaled(self):
        self.run_agent(*[(1, ["упал\n"])] * config.AGENT_ATTEMPTS)

        started = self.journal_details("agent run started")
        self.assertEqual([f"попытка {n}/{config.AGENT_ATTEMPTS}"
                          for n in (1, 2, 3)],
                         [d.split(",")[0] for d in started])

    def test_escalates_after_retries_exhausted(self):
        out = self.run_agent(*[(1, ["API Error: 401 Unauthorized\n"])]
                             * config.AGENT_ATTEMPTS)

        self.assertEqual(self.popen.call_count, config.AGENT_ATTEMPTS)
        self.assertEqual(self.task_row()["state"], "escalated")
        self.assertIn("escalated", out)
        detail = self.journal_details("state -> escalated")[0]
        self.assertIn("rc=1", detail)
        self.assertIn("401 Unauthorized", detail)

    def test_escalated_task_waits_for_operator_in_status(self):
        self.run_agent(*[(1, ["упал\n"])] * config.AGENT_ATTEMPTS)

        self.assertIn("ЖДЁТ ОПЕРАТОРА", self.capture(catalog.cmd_status))

    def test_retries_are_not_review_iterations(self):
        conn = store.db()
        conn.execute("UPDATE tasks SET state='review', review_iters=1 WHERE id=?",
                     (self.TASK,))
        conn.commit()

        self.run_agent(*[(1, ["упал\n"])] * config.AGENT_ATTEMPTS)

        row = self.task_row()
        self.assertEqual(row["review_iters"], 1, "ретраи не считаются итерациями")
        self.assertEqual(row["state"], "escalated")

    def test_approve_returns_failed_dev_step_to_in_dev(self):
        out = self.run_agent(*[(1, ["упал\n"])] * config.AGENT_ATTEMPTS)
        self.assertIn("вернёт в in_dev", out)

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.task_row()["state"], "in_dev")

    def test_approve_returns_failed_review_step_to_review(self):
        """Упало ревью — чинить надо ревью, а не откатывать готовый код в разработку."""
        conn = store.db()
        conn.execute("UPDATE tasks SET state='review' WHERE id=?", (self.TASK,))
        conn.commit()

        out = self.run_agent(*[(1, ["упал\n"])] * config.AGENT_ATTEMPTS)
        self.assertIn("вернёт в review", out)

        self.capture(fsm.cmd_approve, self.TASK)

        row = self.task_row()
        self.assertEqual(row["state"], "review")
        self.assertIsNone(row["escalated_from"], "точка возврата одноразовая")

    def test_approve_after_other_escalation_still_goes_to_in_dev(self):
        """Эскалации по вердикту и по лимитам точку возврата не пишут."""
        conn = store.db()
        conn.execute("UPDATE tasks SET state='escalated' WHERE id=?", (self.TASK,))
        conn.commit()

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.task_row()["state"], "in_dev")

    def test_every_attempt_writes_its_own_log(self):
        self.run_agent((1, ["первый упал\n"]), (1, ["второй упал\n"]),
                       (0, ["третий дошёл\n"]))

        logs = sorted(config.LOGS.glob(f"{self.TASK}-developer-*.log"))
        self.assertEqual([p.name for p in logs],
                         [f"{self.TASK}-developer-{n}.log" for n in (1, 2, 3)])
        self.assertEqual(logs[0].read_text(encoding="utf-8"), "первый упал\n")
        self.assertEqual(logs[2].read_text(encoding="utf-8"), "третий дошёл\n")

    def test_timeout_is_not_retried(self):
        proc = mock.Mock(stdout=FakeStream([]))
        proc.wait.side_effect = [
            runner.subprocess.TimeoutExpired(cmd="claude",
                                            timeout=config.AGENT_TIMEOUT_SEC),
            -9,
        ]
        with mock.patch.object(runner, "spawn_agent", return_value=proc) as popen:
            out = self.capture(runner.cmd_run, self.TASK)

        self.assertEqual(popen.call_count, 1, "три таймаута — полтора часа ожидания")
        self.assertEqual(self.pauses, [])
        self.assertEqual(self.task_row()["state"], "in_dev")
        self.assertIn("таймаут шага", out)

    def test_missing_cli_is_not_retried(self):
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=FileNotFoundError) as popen:
            out = self.capture(runner.cmd_run, self.TASK)

        self.assertEqual(popen.call_count, 1, "повтор не создаст CLI")
        self.assertEqual(self.pauses, [])
        self.assertEqual(self.task_row()["state"], "in_dev")
        # Промпт для ручного прогона теперь в файле рядом с логом шага (T011).
        saved = list(config.LOGS.glob("*.prompt.txt"))
        self.assertEqual(len(saved), 1)
        self.assertIn(str(saved[0]), out)
        self.assertIn("Роль: разработчик", saved[0].read_text(encoding="utf-8"))


class MigrationTest(TmpRootTest):
    """БД прошлой версии догоняется на лету: `init` заново Оператор не делает."""

    def test_return_point_column_is_added_to_old_db(self):
        config.DB.parent.mkdir(parents=True, exist_ok=True)
        old = sqlite3.connect(config.DB)
        old.executescript("CREATE TABLE tasks (id TEXT PRIMARY KEY, state TEXT);")
        old.commit()
        old.close()

        conn = store.db()
        self.addCleanup(conn.close)

        cols = {r["name"] for r in conn.execute("PRAGMA table_info(tasks)")}
        self.assertIn("escalated_from", cols)
        self.assertIn("reviewed_iter", cols, "прежняя миграция не потерялась")


if __name__ == "__main__":
    unittest.main()
