"""Общие помощники приёмочной планки «мьютекс merge держит процесс, не
сессия» (задача 01M2XFSE8G3MBRHHQR38H53J1M).

Тонкая надстройка НАД `tests.sandbox.TmpRootTest` (не копия её патчей —
`disk_backed_show`/`ls_tree_files`/`advance_from_in_dev` здесь не нужны
вовсе: ни один тест этой планки не проходит переходов FSM, все зовут
`merge_lock`/`merge_queue`/`fsm_merge_gate` напрямую на уже заведённых
задачах в состоянии `merge_gate` — тем же приёмом, что
`tests/test_merge_lock.py` и `tests/test_merge_queue.py`).

Два процесса «одной сессии» разыгрываются без второго интерпретатора:
держатель мьютекса/записи очереди — строка БД, а признак «процесс жив»
читается из `pid`/`hostname` этой строки (`merge_lock._holder_is_dead`).
Поэтому «другой ЖИВОЙ процесс той же сессии» — это `_alive_foreign_pid`
(настоящий живой дочерний процесс, гарантированно отличный от
`os.getpid()`) на СВОЁМ host, а «этот процесс» — `os.getpid()`; оба
варианта наблюдаются из одного тестового процесса честно, потому что
проверку живости делает `orchestrator/liveness.py`, а не сам тест.
"""
import time
from unittest import mock

from orchestrator import catalog, config, store
from tests.sandbox import (TmpRootTest, _alive_foreign_pid,  # noqa: F401
                           _dead_pid, _ts_ago, capture)


class FakeClock:
    """`sleep(s)` продвигает `monotonic()` на `s` вместо настоящего
    ожидания — тот же приём, что `tests/test_merge_gate_ci_wait.py::
    FakeClock` (цикл опроса очереди/CI обязан проходить потолки без
    минут реального времени)."""

    def __init__(self, start: float = 0.0):
        self.value = start
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.value += seconds


class MergeOwnerSandbox(TmpRootTest):
    """Две задачи на `merge_gate` (A — «наша», B — «чужого процесса») и
    точечные помощники доступа к строке мьютекса/записям очереди."""

    TASK_A = "T001"
    TASK_B = "T002"
    BRANCH = {"T001": "task/t001-a", "T002": "task/t002-b"}

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        for tid in (self.TASK_A, self.TASK_B):
            store.insert_task(store.db(), tid, tid, "merge_gate",
                              self.BRANCH[tid], config.DEFAULT_TARGET, 25.0)

    def lock_row(self):
        return store.merge_lock_row(store.db())

    def seed_lock(self, task_id: str, session_id: str, pid: int,
                  hostname: str, heartbeat_ts: str | None = None) -> None:
        store.set_merge_lock(store.db(), task_id, session_id, pid, hostname,
                             heartbeat_ts or store.now())

    def enqueue(self, task_id: str, session_id: str, pid: int,
                hostname: str, ts: str) -> None:
        store.enqueue_merge_wait(store.db(), task_id, session_id, pid,
                                 hostname, ts)

    def queue_rows(self) -> list:
        return store.merge_queue_rows(store.db())

    def journal_records(self, task_id: str) -> list:
        """«действие | детали» каждой записи журнала задачи — pid держателя
        может стоять в любом из двух полей, тесты проверяют пару целиком."""
        return [f"{s['action']} | {s['detail']}"
                for s in store.task_steps(store.db(), task_id)]

    def fake_clock(self) -> FakeClock:
        """Подменяет `time.monotonic`/`time.sleep` на весь тест и отдаёт
        часы вызывающему (снятие патчей — штатным `addCleanup`)."""
        clock = FakeClock()
        for name in ("monotonic", "sleep"):
            patcher = mock.patch.object(time, name, getattr(clock, name))
            patcher.start()
            self.addCleanup(patcher.stop)
        return clock
