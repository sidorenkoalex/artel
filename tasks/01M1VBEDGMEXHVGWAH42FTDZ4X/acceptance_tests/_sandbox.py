"""Общие фикстуры приёмочных тестов 01M1VBEDGMEXHVGWAH42FTDZ4X (budget под
живым шагом и возврат из эскалации без холостого шага роли, см.
tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/SPEC.md).

Все сценарии этой планки используют ту же лёгкую песочницу цикла `auto`,
что и `tests/test_auto_cycle.py::AutoCycleTest` (fake git, диск как
источник артефактов, БД во временном каталоге) — предмет проверки этой
задачи читает журнал/`tasks.*`, не git, поэтому настоящий репозиторий не
нужен ни одному из требований 1-3 SPEC.
"""
import os
import socket
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import runner, store  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest, PLAN_MD, REVIEW_MD  # noqa: E402,F401

__all__ = ["AutoCycleTest", "PLAN_MD", "REVIEW_MD", "insert_lease",
          "journal_agent_run_finished", "agent_run_finished_actors"]


def insert_lease(conn, task_id: str, session_id: str, hostname: str,
                 pid: int | None = None) -> None:
    """Живой (heartbeat только что записан) lease задачи от указанной
    session_id/hostname — тот же приём, что `tests/test_invariants.py`
    использует для сценариев с чужим lease (прямая вставка строки
    `leases`, в обход `lease.acquire`, чтобы получить ИМЕННО чужой
    держатель, а не свой)."""
    conn.execute(
        "INSERT INTO leases (task_id, session_id, pid, hostname,"
        " heartbeat_ts) VALUES (?,?,?,?,?)",
        (task_id, session_id, pid if pid is not None else os.getpid() + 1000,
         hostname, store.now()))
    conn.commit()


def journal_agent_run_finished(conn, task_id: str) -> str:
    """Журналирует «agent run finished» под именем роли, активной для
    ТЕКУЩЕГО состояния задачи (`runner.step_role`) — тем же action/actor,
    что и настоящий `orchestrator/runner.py::_cmd_run` по завершении шага
    (см. докстринг `FakeRun`/`agent_step` в `tests/test_auto_cycle.py` и
    `tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests/_sandbox.py`, тот
    же общий узел, которым сверяется `auto._role_step_since_state_entry`).
    Возвращает имя роли — сценарии сверяют его с ожиданием."""
    role = runner.step_role(store.get_task(conn, task_id))
    store.journal(conn, task_id, role, "agent run finished",
                 "rc=0, тестовая заглушка приёмочного теста")
    return role


def agent_run_finished_actors(conn, task_id: str) -> list:
    """Роли (`actor`), под которыми журнал несёт «agent run finished» этой
    задачи, по порядку записи (см. одноимённый помощник в
    `tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests/_sandbox.py`)."""
    return [row["actor"] for row in store.task_steps(conn, task_id)
           if row["action"] == "agent run finished"]
