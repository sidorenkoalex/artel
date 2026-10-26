"""Модель доски: одна проекция БД и журнала проекта, из которой строятся
виды `status` и `epic show` (SPEC 01M5TBBDFS6DWQY6MS263T1KPY, требования
8-11; ADR-0028 п. 12).

Модель — словарь, построенный только чтением БД и `.git` корня пульта:
без хостинга, сети и записи в БД. Порядок карточек, эпиков и рёбер
детерминирован — два построения без изменений БД равны (кроме
`generated_at`)."""
import heapq

from . import merge_after, store, zone_lock

SCHEMA_VERSION = 1
# Состояния, которым `status` ставит отметку «ЖДЁТ ОПЕРАТОРА» (требование 11).
OPERATOR_STATES = ("spec_gate", "acceptance", "merge_gate", "escalated")
CI_STATES = ("verifying",)
EDGE_MERGE_AFTER = "merge_after"
EDGE_PARENT = "parent"


def waiting_on(conn, t, terminal_states) -> str | None:
    """Кто держит задачу: первое сработавшее правило operator → ci →
    dependency → role; у окончательного состояния — `None`. Зависимость —
    ожидание зоны (`zone_lock.queue_wait`, в том числе «ради зависимости»):
    незакрытые `merge_after` держат задачу только на гейте мержа, где раньше
    срабатывает operator."""
    state = t["state"]
    if state in terminal_states:
        return None
    if state in OPERATOR_STATES:
        return "operator"
    if state in CI_STATES:
        return "ci"
    if zone_lock.queue_wait(conn, t["id"], t) is not None:
        return "dependency"
    return "role"


def _card(conn, t, last_events: dict, terminal_states) -> dict:
    return {
        "task": t["id"],
        "title": t["title"],
        "epic": t["epic_id"],
        "state": t["state"],
        "closed_as": t["closed_as"],
        "waiting_on": waiting_on(conn, t, terminal_states),
        "depends_on": merge_after.stored(t["merge_after"]),
        "parent": t["parent_task_id"],
        "spent_usd": t["spent_usd"] or 0.0,
        "budget_usd": t["budget_usd"],
        "branch": t["branch"],
        "last_event_at": last_events.get(t["id"]),
    }


def _ordered(nodes: list[str], edges: list[dict]) -> list[str]:
    """Порядок задач эпика (требование 8): задача после всех задач эпика,
    от которых зависит по `merge_after`; без взаимной зависимости — по
    возрастанию id. Цикл (данные БД его могут нести) не теряет задач: их
    остаток идёт по id."""
    members = set(nodes)
    pending = {n: set() for n in members}
    for edge in edges:
        if (edge["kind"] == EDGE_MERGE_AFTER and edge["from"] in members
                and edge["to"] in members and edge["from"] != edge["to"]):
            pending[edge["from"]].add(edge["to"])
    ready = [n for n in members if not pending[n]]
    heapq.heapify(ready)
    order = []
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for other in sorted(members):
            if node in pending[other]:
                pending[other].discard(node)
                if not pending[other]:
                    heapq.heappush(ready, other)
    order += sorted(members - set(order))
    return order


def _epic_item(epic, tasks: list, cards: dict, terminal_states,
               states) -> dict:
    members = [t for t in tasks if t["epic_id"] == epic["id"]]
    member_ids = {t["id"] for t in members}
    edges = [{"from": t["parent_task_id"], "to": t["id"], "kind": EDGE_PARENT}
             for t in tasks if t["parent_task_id"]
             and (t["parent_task_id"] in member_ids or t["id"] in member_ids)]
    edges += [{"from": t["id"], "to": dep, "kind": EDGE_MERGE_AFTER}
              for t in members for dep in merge_after.stored(t["merge_after"])]
    edges.sort(key=lambda e: (e["kind"], e["from"], e["to"]))
    counts = {state: sum(1 for t in members if t["state"] == state)
              for state in states}
    counts = {state: n for state, n in counts.items() if n}
    divisions = []
    for t in members:
        if t["closed_as"] != store.CLOSED_AS_DIVIDED:
            continue
        parts = [e["to"] for e in edges
                 if e["kind"] == EDGE_PARENT and e["from"] == t["id"]]
        merged = sum(1 for p in parts if p in cards and cards[p]["state"] == "done")
        divisions.append({"task": t["id"], "merged": merged, "total": len(parts)})
    return {
        "id": epic["id"],
        "title": epic["title"],
        "goal": epic["goal"],
        "envelope_usd": epic["envelope_usd"],
        "spent_usd": sum(t["spent_usd"] or 0.0 for t in members),
        "counts": counts,
        "nodes": _ordered(sorted(member_ids), edges),
        "edges": edges,
        "state": epic["state"],
        "outcome": epic["outcome"],
        "divisions": divisions,
        # Эпик без задач готовым не считается (требование 9); сам эпик
        # пульт не закрывает — только показывает.
        "ready_to_close": (epic["state"] == "open" and bool(members)
                           and all(t["state"] in terminal_states
                                   for t in members)),
    }


def build_model(conn, project: str) -> dict:
    """Модель доски проекта `project` (требование 10)."""
    # Отложенно: `fsm` и `watch` тянут граф модулей, импортирующий
    # `catalog`, а `catalog` строит `status` из этой модели.
    from . import fsm, watch
    terminal = fsm.TERMINAL_STATES
    tasks = store.project_tasks(conn, project)
    last_events = store.last_step_times(conn, project)
    cards = [_card(conn, t, last_events, terminal) for t in tasks]
    by_id = {c["task"]: c for c in cards}
    epics = [_epic_item(e, tasks, by_id, terminal, fsm.STATES)
             for e in store.project_epics(conn, project)]
    return {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "generated_at": store.now(),
        "pin": watch._pin_head(),
        "columns": fsm.STATES,
        "epics": epics,
        "cards": cards,
    }
