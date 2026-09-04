"""Общая песочница приёмочных тестов 01M1NEEYSP0QWPMXHG0BK591M7 (SPEC:
предупреждение при чужом живом lease для `pause`/`release`).

Способ хранения `session_id` предупреждающего события журнала (отдельная
колонка либо часть `detail`) — решение разработчика, тем же приёмом, что
уже применил `tasks/01M1GCHKG8DDK4DCZWCE3DYKWC/acceptance_tests/_sandbox.py`:
`row_carries`/`any_step_carries` ищут искомую строку среди ВСЕХ полей
записи, не в конкретной колонке.
"""
# AC-8: skip — критерий агрегирует сценарии, уже покрытые по отдельности тестами AC-1..AC-7 в этом каталоге (предупреждение для pause/release, отсутствие предупреждения при своём/мёртвом/протухшем lease и у read-only команд, запись в журнал), плюс требование «существующие тесты остаются зелёными», проверяемое прогоном полного набора tests/+acceptance_tests, а не отдельным новым тестом-дублёром.
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, _ts_ago, capture  # noqa: E402,F401

TASK = "T001"


def dead_pid() -> int:
    """Гарантированно мёртвый pid: дочерний процесс, дождавшийся своего
    завершения (тот же приём, что и `tests/sandbox.py::_dead_pid`)."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
    return proc.pid


def row_carries(row, token: str) -> bool:
    """True, если `token` встречается среди полей строки БД — целиком в
    колонке или подстрокой текстового поля. Формат хранения session_id
    в предупреждающей записи журнала — решение разработчика, проверка
    от него не зависит (см. докстринг модуля)."""
    for value in dict(row).values():
        if value is None:
            continue
        if str(value) == token:
            return True
        if isinstance(value, str) and token in value:
            return True
    return False


def any_step_carries(steps, token: str) -> bool:
    return any(row_carries(s, token) for s in steps)


class LeaseTaskTest(TmpRootTest):
    """Задача TASK в свежей БД (без git) — таблиц tasks/steps/leases
    достаточно для команд pause/release/status/log/show и
    `doctor.check_leases`."""

    TASK = TASK

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          f"task/{self.TASK.lower()}-zadacha",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def task_row(self, task_id: str = None):
        return store.get_task(store.db(), task_id or self.TASK)

    def lease_row(self, task_id: str = None):
        return store.lease_row(store.db(), task_id or self.TASK)

    def steps(self, task_id: str = None):
        return store.task_steps(store.db(), task_id or self.TASK)

    def insert_lease(self, task_id: str, session_id: str, pid: int,
                     hostname: str, heartbeat_ts: str) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (task_id, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    def insert_step(self, task_id: str, actor: str, action: str,
                    detail: str = "", ts: str = None) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (task_id, config.DEFAULT_TARGET, ts or store.now(), actor,
             action, detail))
        conn.commit()
