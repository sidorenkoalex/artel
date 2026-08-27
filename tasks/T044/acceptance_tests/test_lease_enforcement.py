"""Приёмочные тесты T044 — advisory-lease задачи: AC-1..AC-4 (SPEC.md).

## Допущения интерфейса, которые вводит этот файл

SPEC требование 9 сознательно НЕ фиксирует, откуда конкретный вызов CLI
берёт свой `session_id` — это решение разработчика. Но тест обязан
СИМУЛИРОВАТЬ две разные сессии, зовущие одну и ту же команду, а значит
кому-то нужно завести управляемый шов ДО того, как разработчик это
решение примет. Решения теста:

- Семь мутирующих команд (`runner.cmd_run`, `auto.cmd_auto`,
  `fsm.cmd_advance`, `fsm.cmd_approve`, `fsm.cmd_reject`,
  `cleanup.cmd_kill`, `budget.cmd_budget`) получают НОВЫЙ необязательный
  именованный параметр `session_id: str | None = None`. Это тестовый шов
  для подмены identity ЭТОГО вызова, а не источник session_id для
  настоящего `artel.py <cmd>` — что подставляется вместо `None` в
  реальном CLI, здесь не решается (требование 9 остаётся открытым).
  Дефолт `None` не трогает поведение уже существующих десятков мест,
  зовущих эти функции без session_id (например
  `tests/test_invariants.py::FsmTest.commands()`) — сигнатуры
  расширяются, не переопределяются, поэтому AC-7 (существующий набор
  тестов зелёный) этим допущением не подрывается.
- Новая константа порога свежести heartbeat (требование 6,
  `orchestrator/config.py`) названа `LEASE_STALE_AFTER_SEC` — по
  аналогии с `BACKUP_MAX_AGE_DAYS`/`DOCTOR_MIN_FREE_MB`.
- Таблица `leases` — ровно пять колонок требования 1
  (`task_id, session_id, pid, hostname, heartbeat_ts`), `task_id`
  уникален (одна активная запись на задачу — «lease ЗАДАЧИ», не лога
  захватов).

Эти допущения — часть замка теста, а не факт уже существующего кода:
`leases`, параметр `session_id` и `LEASE_STALE_AFTER_SEC` ещё не
существуют. Прогон ДО реализации падает по этой причине
(`sqlite3.OperationalError: no such table: leases` /
`TypeError: cmd_run() got an unexpected keyword argument 'session_id'` /
`AttributeError: module 'orchestrator.config' has no attribute
'LEASE_STALE_AFTER_SEC'`) — ожидаемо (скил test-authoring: «падать на
отсутствующей пока реализации — нормально»), не брак теста.

Песочница — `tests.test_invariants.FsmTest` (T001, git и preflight
заглушены, `spawn_agent` подменяется по месту вызова тем же приёмом,
что и `FsmTest.run_command`) — переиспользуется, а не копируется
(skills/test-authoring, conventions-core).

AC-5, AC-6 — в `test_lease_readonly_and_doctor.py` (другая, более лёгкая
песочница: читающим командам и `doctor` не нужны git-заглушка и
агентский фреймворк). AC-7 размечен там же.
"""
import io
import os
import socket
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto, budget, cleanup, config, fsm, runner, store  # noqa: E402
from tests.test_invariants import FakeProc, FsmTest  # noqa: E402


def _invoke(call) -> str:
    """Стдаут вызова + текст SystemExit (если он был): отказ мог уйти любым
    из двух путей, для теста это один и тот же наблюдаемый текст."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        return buf.getvalue() + str(exc)
    return buf.getvalue()


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%SZ")


def _ts_ago(seconds: float) -> str:
    return _ts(datetime.now(timezone.utc) - timedelta(seconds=seconds))


def _parse_ts(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%SZ").replace(
        tzinfo=timezone.utc)


class LeaseSandbox(FsmTest):
    """`FsmTest` (T001, git/агент заглушены) + прямые операции над `leases`."""

    HOLDER_SESSION = "session-holder"
    HOLDER_PID = 424242
    HOLDER_HOST = "holder-host"
    CALLER_SESSION = "session-caller"

    def seed_lease(self, session_id: str, pid: int, hostname: str,
                   heartbeat_ts: str) -> None:
        conn = store.db()
        conn.execute("DELETE FROM leases WHERE task_id=?", (self.TASK,))
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    def lease_row(self):
        row = store.db().execute(
            "SELECT * FROM leases WHERE task_id=?", (self.TASK,)).fetchone()
        return dict(row) if row is not None else None

    def commands(self, session_id: str) -> list:
        return [
            ("run", lambda: runner.cmd_run(self.TASK, session_id=session_id)),
            ("auto", lambda: auto.cmd_auto(self.TASK, session_id=session_id)),
            ("advance",
             lambda: fsm.cmd_advance(self.TASK, session_id=session_id)),
            ("approve",
             lambda: fsm.cmd_approve(self.TASK, session_id=session_id)),
            ("reject", lambda: fsm.cmd_reject(self.TASK, "причина",
                                              session_id=session_id)),
            ("kill",
             lambda: cleanup.cmd_kill(self.TASK, session_id=session_id)),
            ("budget", lambda: budget.cmd_budget(self.TASK, "40",
                                                 session_id=session_id)),
        ]

    def reset_task(self) -> None:
        """Возвращает T001 к нейтральному in_dev перед очередным подшагом
        свипа — предыдущая (неотказанная, пока замок не реализован)
        команда могла сдвинуть состояние/бюджет/счётчики."""
        self.set_state("in_dev", budget_usd=config.DEFAULT_BUDGET_USD,
                       spent_usd=0.0, review_iters=0, accept_rejects=0,
                       escalated_from=None)


class Ac1ForeignFreshLeaseRefusesAllMutatingCommandsTest(LeaseSandbox):
    """AC-1: чужой свежий lease — именованный отказ у каждой из семи команд,
    состояние задачи (и сам чужой lease) не меняются."""

    def test_ac1_each_mutating_command_is_refused_by_name(self):
        for name, call in self.commands(self.CALLER_SESSION):
            with self.subTest(команда=name):
                self.reset_task()
                self.seed_lease(self.HOLDER_SESSION, self.HOLDER_PID,
                                self.HOLDER_HOST, store.now())
                before_task = dict(self.task_row())
                before_lease = self.lease_row()

                with mock.patch.object(
                        runner, "spawn_agent",
                        return_value=FakeProc(["готово\n"])):
                    output = _invoke(call)

                self.assertIn(
                    self.HOLDER_SESSION, output,
                    f"{name}: отказ не назвал session_id держателя lease")
                self.assertIn(
                    self.HOLDER_HOST, output,
                    f"{name}: отказ не назвал hostname держателя lease")
                self.assertRegex(
                    output, r"\d+",
                    f"{name}: отказ не назвал возраст heartbeat в секундах")

                self.assertEqual(
                    dict(self.task_row()), before_task,
                    f"{name}: состояние задачи изменилось при живом "
                    f"чужом lease (tasks.state/budget_usd/... должны "
                    f"остаться как до вызова)")
                self.assertEqual(
                    self.lease_row(), before_lease,
                    f"{name}: отказанный вызов изменил чужой lease")


class Ac2SameSessionRenewsWithoutRefusalTest(LeaseSandbox):
    """AC-2: повторный вызов ТОЙ ЖЕ сессии — без отказа, heartbeat продлён."""

    def test_ac2_same_session_id_renews_heartbeat_without_refusal(self):
        self.reset_task()
        self.seed_lease(self.CALLER_SESSION, 111111, "stale-host-name",
                        _ts_ago(30))
        before_call = datetime.now(timezone.utc) - timedelta(seconds=1)

        output = _invoke(lambda: budget.cmd_budget(
            self.TASK, "42", session_id=self.CALLER_SESSION))

        self.assertEqual(
            self.task_row()["budget_usd"], 42.0,
            f"budget не выполнился при собственном (совпадающем) lease: "
            f"{output!r}")
        row = self.lease_row()
        self.assertIsNotNone(row, "собственный lease пропал после продления")
        self.assertEqual(row["session_id"], self.CALLER_SESSION)
        self.assertGreaterEqual(
            _parse_ts(row["heartbeat_ts"]), before_call,
            "heartbeat_ts не продлён на текущий момент")


class Ac3StaleForeignLeaseIsTakenOverTest(LeaseSandbox):
    """AC-3: протухший чужой lease — перехват вызывающей сессией, факт
    перехвата — отдельной записью в журнале задачи."""

    def test_ac3_stale_lease_is_taken_over_and_journalled(self):
        self.reset_task()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 5)
        self.seed_lease(self.HOLDER_SESSION, self.HOLDER_PID,
                        self.HOLDER_HOST, stale_ts)
        journalled_before = len(store.task_steps(store.db(), self.TASK))
        before_call = datetime.now(timezone.utc) - timedelta(seconds=1)

        output = _invoke(lambda: budget.cmd_budget(
            self.TASK, "42", session_id=self.CALLER_SESSION))

        self.assertEqual(
            self.task_row()["budget_usd"], 42.0,
            f"budget не выполнился после протухания чужого lease: "
            f"{output!r}")
        row = self.lease_row()
        self.assertIsNotNone(row, "lease пропал вместо перехвата")
        self.assertEqual(row["session_id"], self.CALLER_SESSION)
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(row["hostname"], socket.gethostname())
        self.assertGreaterEqual(_parse_ts(row["heartbeat_ts"]), before_call)

        journal_text = "\n".join(
            f"{s['action']} {s['detail']}" for s in
            store.task_steps(store.db(), self.TASK)[journalled_before:]
        ).lower()
        self.assertTrue(
            any(k in journal_text for k in ("перехват", "lease")),
            f"перехват протухшего lease не отражён отдельной записью "
            f"журнала: {journal_text!r}")


class Ac4LeaseReleasedAfterSuccessfulCommandTest(LeaseSandbox):
    """AC-4: успешное завершение мутирующей команды освобождает lease —
    следующий вызов от ДРУГОЙ сессии не встречает живой lease."""

    SECOND_CALLER = "session-second-caller"

    def test_ac4_lease_freed_after_success_next_session_not_blocked(self):
        self.reset_task()

        first = _invoke(lambda: budget.cmd_budget(
            self.TASK, "41", session_id=self.CALLER_SESSION))
        after_first = self.task_row()["budget_usd"]

        second = _invoke(lambda: budget.cmd_budget(
            self.TASK, "43", session_id=self.SECOND_CALLER))
        after_second = self.task_row()["budget_usd"]

        self.assertEqual(after_first, 41.0,
                         f"первый вызов не выполнился: {first!r}")
        self.assertEqual(
            after_second, 43.0,
            f"второй вызов ДРУГОЙ сессии не выполнился — lease первой "
            f"сессии не был освобождён по завершении: {second!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
