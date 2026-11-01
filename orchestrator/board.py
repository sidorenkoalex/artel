"""Модель доски: одна проекция БД и журнала проекта, из которой строятся
виды `status` и `epic show` (SPEC 01M5TBBDFS6DWQY6MS263T1KPY, требования
8-11; ADR-0028 п. 12), команда `board` и доска `report` (SPEC
01M5TBFH5VZ7GSRXX7VNKHFCCQ, требования 1-4, 8).

Модель — словарь, построенный только чтением БД и `.git` корня пульта:
без хостинга, сети и записи в БД. Порядок карточек, эпиков и рёбер
детерминирован — два построения без изменений БД равны (кроме
`generated_at`)."""
import heapq
import html
import json
import sys

from . import config, merge_after, store, targets, zone_lock

SCHEMA_VERSION = 1
# Состояния, которым `status` ставит отметку «ЖДЁТ ОПЕРАТОРА» (требование 11).
OPERATOR_STATES = ("spec_gate", "acceptance", "merge_gate", "escalated")
CI_STATES = ("verifying",)
# MR вливают люди проекта (SPEC 01M5XZ9Z68V75VXF5Z66C708T4, требование 6).
HUMAN_STATES = ("awaiting_human",)
EDGE_MERGE_AFTER = "merge_after"
EDGE_PARENT = "parent"


def waiting_on(conn, t, terminal_states) -> str | None:
    """Кто держит задачу: первое сработавшее правило operator → ci → human
    → dependency → role; у окончательного состояния — `None`. Зависимость —
    ожидание зоны (`zone_lock.queue_wait`, в том числе «ради зависимости»)
    либо незакрытые `start_after` задачи без первого шага роли (SPEC
    01M5TBCY7WTN121S136XP2C6SR, требование 19): незакрытые `merge_after`
    держат задачу только на гейте мержа, где раньше срабатывает operator."""
    state = t["state"]
    if state in terminal_states:
        return None
    if state in OPERATOR_STATES:
        return "operator"
    if state in CI_STATES:
        return "ci"
    if state in HUMAN_STATES:
        return "human"
    if zone_lock.queue_wait(conn, t["id"], t) is not None:
        return "dependency"
    if merge_after.start_after_blocks(conn, t):
        return "dependency"
    return "role"


def _ref_item(row) -> dict:
    """Элемент `refs` (SPEC 01M5TBFH5VZ7GSRXX7VNKHFCCQ, требование 8): без
    id строки и владельца — копия ссылки у части деления равна ссылке
    родителя поэлементно."""
    return {"system": row["system"], "key": row["key"], "url": row["url"],
            "by": row["created_by"], "at": row["created_at"]}


def _refs_by_owner(conn, kind: str, project: str) -> dict:
    """{id объекта: [элементы refs]} проекта — один запрос на вид объекта."""
    found: dict = {}
    for row in store.project_external_refs(conn, kind, project):
        found.setdefault(row["object_id"], []).append(_ref_item(row))
    return found


def _card(conn, t, last_events: dict, terminal_states, refs: dict,
          with_waiting: bool) -> dict:
    return {
        "task": t["id"],
        "title": t["title"],
        "epic": t["epic_id"],
        "state": t["state"],
        "closed_as": t["closed_as"],
        # Без расчёта (`report`, SPEC 01M5TBFH5VZ7GSRXX7VNKHFCCQ, требование
        # 3) `zone_lock.queue_wait` не зовётся: он читает журнал на карточку.
        "waiting_on": (waiting_on(conn, t, terminal_states) if with_waiting
                       else None),
        "depends_on": merge_after.stored(t["merge_after"]),
        "parent": t["parent_task_id"],
        "spent_usd": t["spent_usd"] or 0.0,
        "budget_usd": t["budget_usd"],
        "branch": t["branch"],
        "last_event_at": last_events.get(t["id"]),
        # Поля плитки `report` (требование 4).
        "review_iters": t["review_iters"],
        "escalated_from": t["escalated_from"],
        "project": t["target"] or config.DEFAULT_TARGET,
        "refs": refs.get(t["id"], []),
        # Ссылка на MR задачи (SPEC 01M5XZ9Z68V75VXF5Z66C708T4, требование 16).
        "mr_iid": store.mr_link(t)[0],
        "mr_url": store.mr_link(t)[1],
        # Последний итог `mr-sync` задачи в `awaiting_human` (SPEC
        # 01M6AB4VE2R0Q2V5D4MMJGNGH7, требование 7); иначе `None`.
        "mr_sync": mr_sync_shown(t),
    }


def mr_sync_shown(t) -> dict | None:
    """{итог, время сверки} последнего `mr-sync` задачи в `awaiting_human`;
    `None` — задача не ждёт людей проекта или сверки не было."""
    if (t["state"] not in HUMAN_STATES or "mr_sync_outcome" not in t.keys()
            or not t["mr_sync_outcome"]):
        return None
    return {"outcome": t["mr_sync_outcome"], "at": t["mr_sync_at"]}


def _mr_cell(c: dict) -> str | None:
    synced = c.get("mr_sync")
    if synced is None:
        return c.get("mr_url")
    text = f"mr-sync {synced['at']}: {synced['outcome']}"
    return f"{c['mr_url']} · {text}" if c.get("mr_url") else text


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


def _epic_item(conn, epic, tasks: list, cards: dict, terminal_states,
               states, refs: dict) -> dict:
    from . import budget  # отложенно — см. `build_model`
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
    spent = budget.epic_spent(conn, epic["id"])
    return {
        "id": epic["id"],
        "title": epic["title"],
        "goal": epic["goal"],
        "envelope_usd": epic["envelope_usd"],
        "spent_usd": spent,
        "envelope_warning": budget.epic_envelope_warning(spent,
                                                         epic["envelope_usd"]),
        "counts": counts,
        "nodes": _ordered(sorted(member_ids), edges),
        "edges": edges,
        "state": epic["state"],
        "outcome": epic["outcome"],
        "divisions": divisions,
        # Эпик без задач готовым не считается (требование 9); сам эпик
        # пульт не закрывает — только показывает. Черновик в `draft` —
        # будущая задача эпика: с ним эпик не готов (SPEC
        # 01M5TBFCVFNN95BHH0E9C6KBKB, требование 17).
        "ready_to_close": (epic["state"] == "open" and bool(members)
                           and all(t["state"] in terminal_states
                                   for t in members)
                           and not any(d["state"] == "draft" for d in
                                       store.epic_drafts(conn, epic["id"]))),
        "refs": refs.get(epic["id"], []),
    }


def build_model(conn, project: str, with_waiting: bool = True) -> dict:
    """Модель доски проекта `project` (требование 10). `with_waiting=False`
    — без расчёта `waiting_on` (у карточек `None`): так её строит `report`
    (SPEC 01M5TBFH5VZ7GSRXX7VNKHFCCQ, требование 3)."""
    # Отложенно: `fsm` и `watch` тянут граф модулей, импортирующий
    # `catalog`, а `catalog` строит `status` из этой модели.
    # `budget` (в `_epic_item`) — тем же приёмом: потрачено по эпику
    # считает одна функция `budget.epic_spent` (SPEC
    # 01M5TBCY7WTN121S136XP2C6SR, требование 1).
    from . import fsm, watch
    terminal = fsm.TERMINAL_STATES
    tasks = store.project_tasks(conn, project)
    last_events = store.last_step_times(conn, project)
    task_refs = _refs_by_owner(conn, store.REF_KIND_TASK, project)
    cards = [_card(conn, t, last_events, terminal, task_refs, with_waiting)
             for t in tasks]
    by_id = {c["task"]: c for c in cards}
    epic_refs = _refs_by_owner(conn, store.REF_KIND_EPIC, project)
    epics = [_epic_item(conn, e, tasks, by_id, terminal, fsm.STATES, epic_refs)
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


# ===== Команда `board` (SPEC 01M5TBFH5VZ7GSRXX7VNKHFCCQ, требование 1) =====

BOARD_USAGE = "board --project <имя> [--json | --md | --html]"
VIEWS = ("--json", "--md", "--html")
DEFAULT_VIEW = "--md"


def _refs_text(refs: list) -> str:
    return ", ".join(f"{r['system']}:{r['key']}" for r in refs)


def _usd(value) -> str:
    return "—" if value is None else f"${value:.2f}"


def _md_cell(value) -> str:
    text = "—" if value is None or value == "" else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _md_row(values) -> str:
    return "| " + " | ".join(_md_cell(v) for v in values) + " |"


def render_md(model: dict) -> str:
    """Вид `--md`: таблицы эпиков и карточек модели."""
    lines = [f"# Доска проекта {model['project']}", "",
             f"Сгенерировано: {model['generated_at']} · пин: "
             f"{model['pin'] or '—'}", ""]
    if model["epics"]:
        lines += ["## Эпики", "",
                  _md_row(("Эпик", "Название", "Состояние", "Задачи",
                           "Потрачено", "Конверт", "Ссылки")),
                  _md_row(("---",) * 7)]
        lines += [_md_row((e["id"], e["title"], e["state"], len(e["nodes"]),
                           _usd(e["spent_usd"]), _usd(e["envelope_usd"]),
                           _refs_text(e["refs"])))
                  for e in model["epics"]]
        lines.append("")
    lines += ["## Карточки", ""]
    if not model["cards"]:
        lines.append("Задач нет.")
        return "\n".join(lines) + "\n"
    lines += [_md_row(("Задача", "Название", "Эпик", "Состояние", "Ждёт",
                       "Бюджет", "Расход", "Ссылки", "MR")),
              _md_row(("---",) * 9)]
    lines += [_md_row((c["task"], c["title"], c["epic"], c["state"],
                       c["waiting_on"], _usd(c["budget_usd"]),
                       _usd(c["spent_usd"]), _refs_text(c["refs"]),
                       _mr_cell(c)))
              for c in model["cards"]]
    return "\n".join(lines) + "\n"


def _html_refs(refs: list) -> str:
    items = []
    for r in refs:
        label = html.escape(f"{r['system']}:{r['key']}")
        if r["url"]:
            label = f'<a href="{html.escape(r["url"])}">{label}</a>'
        items.append(label)
    return ", ".join(items)


def _html_card(c: dict) -> str:
    refs = (f'<div class="card-refs">{_html_refs(c["refs"])}</div>'
            if c["refs"] else "")
    epic = (f'<div class="card-epic">эпик {html.escape(c["epic"])}</div>'
            if c["epic"] else "")
    mr = (f'<div class="card-mr"><a href="{html.escape(c["mr_url"])}">MR '
          f'{html.escape(c["mr_url"])}</a></div>' if c.get("mr_url") else "")
    synced = c.get("mr_sync")
    if synced is not None:
        mr += (f'<div class="card-mr-sync">mr-sync '
               f'{html.escape(synced["at"] or "")}: '
               f'{html.escape(synced["outcome"])}</div>')
    return (f'<div class="card"><span class="card-id">{html.escape(c["task"])}'
            f'</span> <span class="card-title">{html.escape(c["title"] or "")}'
            f'</span>{epic}<div class="card-wait">ждёт: '
            f'{html.escape(c["waiting_on"] or "—")}</div>{refs}{mr}</div>')


def _html_epic(e: dict) -> str:
    refs = f' ({_html_refs(e["refs"])})' if e["refs"] else ""
    return (f'<li>{html.escape(e["id"])} {html.escape(e["title"] or "")} — '
            f'{html.escape(e["state"])}{refs}</li>')


def render_html(model: dict) -> str:
    """Вид `--html`: страница с колонками состояний модели."""
    by_state: dict = {}
    for c in model["cards"]:
        by_state.setdefault(c["state"], []).append(c)
    states = [s for s in model["columns"] if s in by_state]
    states += sorted(s for s in by_state if s not in model["columns"])
    columns = "".join(
        f'<div class="col"><h3>{html.escape(s)}</h3>'
        f'{"".join(_html_card(c) for c in by_state[s])}</div>'
        for s in states) or '<p class="empty">Задач нет.</p>'
    epics = "".join(_html_epic(e) for e in model["epics"])
    epics_html = f"<h2>Эпики</h2><ul>{epics}</ul>\n" if epics else ""
    project = html.escape(model["project"])
    return ("<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n"
            "<meta charset=\"utf-8\">\n"
            f"<title>Доска проекта {project}</title>\n</head>\n<body>\n"
            f"<h1>Доска проекта {project}</h1>\n"
            f"<p>Сгенерировано: {html.escape(model['generated_at'])} · пин: "
            f"{html.escape(model['pin'] or '—')}</p>\n"
            f"{epics_html}<div class=\"board\">{columns}</div>\n"
            "</body>\n</html>\n")


def render_json(model: dict) -> str:
    return json.dumps(model, ensure_ascii=False, indent=2) + "\n"


RENDERERS = {"--json": render_json, "--md": render_md, "--html": render_html}


def _known_project(conn, project: str) -> bool:
    """Проект заявлен в `targets.yaml` либо у него есть задача или эпик в
    БД. Нечитаемый `targets.yaml` — сверка только с БД."""
    try:
        if project in targets.load():
            return True
    except targets.TargetsError:
        pass
    return bool(store.project_tasks(conn, project)
                or store.project_epics(conn, project))


def _parse_board_args(rest: list) -> tuple[str, str]:
    views = [arg for arg in rest if arg in VIEWS]
    if len(views) > 1:
        sys.exit(f"board: один вид из {' | '.join(VIEWS)}; использование: "
                 f"{BOARD_USAGE}")
    others = [arg for arg in rest if arg not in VIEWS]
    if (len(others) != 2 or others[0] != "--project"
            or others[1].startswith("-")):
        sys.exit(f"использование: {BOARD_USAGE}")
    return others[1], (views[0] if views else DEFAULT_VIEW)


def cmd_board(rest: list) -> None:
    """Печатает модель доски проекта видом `--json`/`--md`/`--html`; без
    флага вида — `--md`. Все виды — из одной модели; только чтение БД и
    `.git` пульта, без сети и записи в БД (требование 1)."""
    project, view = _parse_board_args(rest)
    conn = store.db()
    if not _known_project(conn, project):
        sys.exit(f"board: проект {project} неизвестен — нет записи в "
                 f"{config.TARGETS.name}, нет задач и эпиков в БД")
    sys.stdout.write(RENDERERS[view](build_model(conn, project)))
