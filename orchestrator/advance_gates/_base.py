"""Каркас гейтов `_run_gates` и общий тип исхода `GateRefusal` (SPEC R2
01M1TKNXX5YN5KT4WHG4T44JWV, требование 1) — перенесено дословно из
`orchestrator/fsm_advance.py` разрезом задачи 01M2CYQR0357VAQFZ5VACJD9TD.
"""
from typing import NamedTuple

from .. import store


class GateRefusal(NamedTuple):
    """Единый неизменяемый исход гейта (SPEC R2 01M1TKNXX5YN5KT4WHG4T44JWV,
    требование 1): `action` — второй позиционный аргумент store.journal
    (текст "переход отклонён: ..."), `detail` — третий, `hint` — строка для
    "  дальше: {hint}" (пустая — подсказка не печатается). Гейт пройден —
    `None`, не экземпляр этого типа."""
    action: str
    detail: str
    hint: str


def _run_gates(conn, task_id: str, gates) -> bool:
    """Каркас гейтов (требования 2-4): `gates` — список вызываемых без
    аргументов предикатов `() -> GateRefusal | None`, применяется по
    порядку, останавливаясь на первом отказе — последующие гейты списка
    не вызываются (AC-3). Отказ — ровно один `store.journal` под
    действием `refusal.action`, печать `[{task_id}] переход отклонён:
    {detail}` и (если есть) подсказки; переход не происходит (`True`,
    AC-4). Все гейты списка пройдены — `False`, без единой записи в
    журнал и без печати (AC-4)."""
    for gate in gates:
        refusal = gate()
        if refusal is None:
            continue
        store.journal(conn, task_id, "fsm", refusal.action, refusal.detail)
        print(f"[{task_id}] переход отклонён: {refusal.detail}")
        if refusal.hint:
            print(f"  дальше: {refusal.hint}")
        return True
    return False
