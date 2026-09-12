"""Общий код приёмочной планки 01M2B6JWGS9HMR9XZJBASXVNSY (skills/
test-authoring: общий код планки — только в модулях `_*.py`, не
копипаста по каждому `test_ac*.py`).

`LeaseTmpRootTest` — общая заготовка: задача T001 заведена, `row()`
читает её строку lease. `insert_lease_row` — прямая вставка строки
lease с произвольными полями (сценарии SPEC требуют конкретных
комбинаций pid/hostname/heartbeat, которых `lease.acquire` сама не
заводит). `spawn_alive_pid` — pid, заведомо ЖИВОЙ на момент вызова и
ОТЛИЧНЫЙ от `os.getpid()` текущего процесса теста: `tests/sandbox.py`
несёт `_dead_pid()` (обратный случай), но не живой чужой pid, который
требуют AC-1/AC-2/AC-5/AC-6 этой планки («pid прежнего держателя жив и
не равен pid текущего процесса»).
"""
import subprocess
import sys

from orchestrator import catalog, config, store
from tests.sandbox import TmpRootTest, capture

TASK = "T001"


class LeaseTmpRootTest(TmpRootTest):

    TASK = TASK

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.lease_row(store.db(), self.TASK)


def insert_lease_row(conn, task_id: str, session_id: str, pid: int,
                     hostname: str, heartbeat_ts: str,
                     pgid: int | None = None) -> None:
    conn.execute(
        "INSERT INTO leases (task_id, session_id, pid, hostname,"
        " heartbeat_ts, pgid) VALUES (?,?,?,?,?,?)",
        (task_id, session_id, pid, hostname, heartbeat_ts, pgid))
    conn.commit()


def spawn_alive_pid(testcase) -> int:
    """pid дочернего процесса, дожидающегося `terminate()` в cleanup
    теста — живой на момент вызова `lease.acquire`/`_lease_holder_suffix`
    и гарантированно отличный от pid процесса, исполняющего тест."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])

    def _cleanup():
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    testcase.addCleanup(_cleanup)
    return proc.pid
