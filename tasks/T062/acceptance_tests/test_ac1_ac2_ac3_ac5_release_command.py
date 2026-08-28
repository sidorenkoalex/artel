"""Приёмочные тесты T062 — команда `release`: AC-1, AC-2, AC-3, AC-5 (SPEC.md).

AC-4 (снятие чужого lease освобождает слот лимитера MAX_PARALLEL_TASKS) —
в отдельном файле `test_ac4_release_frees_limiter_slot.py`: там нужна
тяжёлая песочница `tests.test_invariants.FsmTest` (git/агент заглушены,
`FakeProc`), а этим четырём критериям — нет: `release` не берёт lease
задачи сама и не спавнит агента (SPEC, требование 4), достаточно
`tests.sandbox.TmpRootTest` с задачей, заведённой напрямую в БД (тот же
приём, что и `tasks/T044/acceptance_tests/test_lease_readonly_and_doctor.py`).

## Допущения интерфейса, которые вводит этот файл

SPEC называет только внешнюю форму команды (`artel.py release <task_id>`,
требование 1) и явно НЕ фиксирует модуль/имя функции, которая её
реализует — тем же приёмом, что и остальные однопредметные CLI-команды
пульта (`orchestrator/cleanup.py::cmd_kill`, `orchestrator/budget.py::
cmd_budget`), это допущение теста, а не факт уже существующего кода:

- Новый модуль `orchestrator/release.py` с функцией
  `cmd_release(task_id: str) -> None`. Без `session_id`: `release` не
  берёт lease задачи сама (требование 4) и не удостоверяет СВОЮ identity
  вызывающей сессии — в отличие от мутирующих команд T044/T057, ей нечего
  продлевать или перехватывать, только снять чужую строку.
- Прогон ДО реализации падает `ModuleNotFoundError: No module named
  'orchestrator.release'` — ожидаемо (skills/test-authoring: «падать на
  отсутствующей пока реализации — нормально»), не брак теста.
"""
import io
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, lease, parallel_limit, release, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

HOLDER_SESSION = "session-holder"
HOLDER_PID = 424242
HOLDER_HOST = "holder-host"


def _invoke(call) -> tuple[str, object]:
    """(стдаут, код_выхода). `код_выхода` — `None`, если вызов не звал
    `sys.exit` (обычный `return`) — по коду процесса CLI оба исхода
    неотличимы (успешное завершение), но AC-3 явно требует именно код 0,
    поэтому тест смотрит на код отдельно, а не только на текст."""
    buf = io.StringIO()
    code = None
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        code = exc.code
    return buf.getvalue(), code


def _ts_ago(seconds: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%d %H:%M:%SZ")


class ReleaseSandbox(TmpRootTest):
    """Задача T001 заведена напрямую в БД (без git/веток/worktree) —
    `release` их не касается."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def insert_lease(self, session_id: str, pid: int, hostname: str,
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

    def journal_len(self) -> int:
        return len(store.task_steps(store.db(), self.TASK))

    def journal_tail(self, since: int) -> str:
        rows = store.task_steps(store.db(), self.TASK)[since:]
        return "\n".join(f"{r['actor']} {r['action']} {r['detail']}"
                         for r in rows)


class Ac1ExistingLeaseRemovedAndJournalledTest(ReleaseSandbox):
    """AC-1: `release <id>` для задачи с существующим lease удаляет
    строку этой задачи из `leases` и добавляет в журнал задачи запись с
    данными бывшего держателя (`session_id`, `pid`, `hostname`, возраст
    heartbeat)."""

    def test_ac1_release_deletes_lease_row_and_journals_former_holder(self):
        self.insert_lease(HOLDER_SESSION, HOLDER_PID, HOLDER_HOST,
                          store.now())
        journalled_before = self.journal_len()

        output, code = _invoke(lambda: release.cmd_release(self.TASK))

        self.assertIsNone(
            self.lease_row(),
            f"release не удалил строку leases задачи {self.TASK}: {output!r}")

        journal = self.journal_tail(journalled_before)
        self.assertTrue(
            journal.strip(),
            f"release не добавил запись в журнал задачи: {output!r}")
        self.assertIn(HOLDER_SESSION, journal,
                     "запись журнала не назвала session_id бывшего держателя")
        self.assertIn(str(HOLDER_PID), journal,
                     "запись журнала не назвала pid бывшего держателя")
        self.assertIn(HOLDER_HOST, journal,
                     "запись журнала не назвала hostname бывшего держателя")
        self.assertRegex(
            journal, r"\d+",
            "запись журнала не назвала возраст heartbeat в секундах")


class Ac2FreshAndStaleLeaseBothRemovedTest(ReleaseSandbox):
    """AC-2: `release <id>` снимает как свежий (heartbeat моложе
    `LEASE_STALE_AFTER_SEC`), так и протухший lease — без разбора
    свежести."""

    def test_ac2_release_removes_fresh_heartbeat_lease(self):
        self.insert_lease(HOLDER_SESSION, HOLDER_PID, HOLDER_HOST,
                          store.now())

        output, _ = _invoke(lambda: release.cmd_release(self.TASK))

        self.assertIsNone(
            self.lease_row(),
            f"release не снял свежий (heartbeat только что) lease: {output!r}")

    def test_ac2_release_removes_stale_heartbeat_lease(self):
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 5)
        self.insert_lease(HOLDER_SESSION, HOLDER_PID, HOLDER_HOST, stale_ts)

        output, _ = _invoke(lambda: release.cmd_release(self.TASK))

        self.assertIsNone(
            self.lease_row(),
            f"release не снял протухший lease: {output!r}")


class Ac3NoLeaseExitsZeroWithFriendlyMessageTest(ReleaseSandbox):
    """AC-3: `release <id>` для задачи без lease завершается кодом
    возврата 0 и печатает дружелюбное сообщение о том, что снимать
    нечего."""

    def test_ac3_release_without_lease_exits_zero_and_prints_message(self):
        self.assertIsNone(self.lease_row(), "предусловие: lease не заведён")

        output, code = _invoke(lambda: release.cmd_release(self.TASK))

        self.assertIn(
            code, (0, None),
            f"release без lease обязан завершиться кодом возврата 0, "
            f"получено {code!r} (вывод: {output!r})")
        self.assertTrue(
            output.strip(),
            "release без lease обязан напечатать сообщение о том, что "
            "снимать нечего")
        self.assertIsNone(
            self.lease_row(),
            "release без lease не должен заводить строку leases")


class Ac5ReleaseBypassesLeaseAndLimiterTest(ReleaseSandbox):
    """AC-5: `release` не берёт lease задачи сама и не проходит проверку
    лимитера `MAX_PARALLEL_TASKS` — вызывается без входа через
    `lease.run_locked`/`parallel_limit`."""

    def test_ac5_release_does_not_call_run_locked_acquire_or_parallel_limit(self):
        self.insert_lease(HOLDER_SESSION, HOLDER_PID, HOLDER_HOST,
                          store.now())

        with mock.patch.object(lease, "run_locked") as run_locked_mock, \
             mock.patch.object(lease, "acquire") as acquire_mock, \
             mock.patch.object(parallel_limit, "refusal") as refusal_mock:
            output, _ = _invoke(lambda: release.cmd_release(self.TASK))

        run_locked_mock.assert_not_called()
        acquire_mock.assert_not_called()
        refusal_mock.assert_not_called()
        self.assertIsNone(
            self.lease_row(),
            f"release обязан снять lease без входа через "
            f"lease.run_locked/lease.acquire/parallel_limit.refusal: "
            f"{output!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
