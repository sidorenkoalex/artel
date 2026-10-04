"""Зависимости мержа `merge_after`: проверка на гейте SPEC и в каналах переписывания, отказ на гейте мержа.

SPEC 01M44EP0D47F498TEE08MNGBYT. Порядок «эта задача — только после той»
до этой задачи жил текстом ТЗ, и пульт его не исполнял: очередь
`merge_queue` — FIFO по времени прихода на гейт (прецедент 13.09:
инвариант приложения попал в main раньше мержа фикса).

Поле SPEC `merge_after` — список id задач (полных или префиксов) через
запятую. Форму поля без БД проверяет guard (`scripts/guard.py::
merge_after_form_errors`); здесь — проверка по БД (`check`): задача
есть, префикс однозначен (`store.task_id_matches` — узел
`store.resolve_task_id`), не `killed`, тот же target, не сама задача, нет
цикла в графе `merge_after` всех задач с учётом нового значения.

Значение в колонке `tasks.merge_after` — полные id через запятую в порядке
записи — пишет `approve` гейта SPEC (`spec_gate_value`) и переписывают три
канала, каждый с записью журнала «было → стало» (`rewrite`): PLAN на
переходе `in_dev -> verifying` (`apply_plan`), мандат Оператора
«Зависимости мержа: …» в ANSWER-n.md (`mandate_value`, проверку строки
зовёт `advance_gates/mandate.refusals`), эскалация роли — только через
перенос её строки Оператором в ANSWER, отдельного кода у неё нет.

Исполняет значение `approve` на `merge_gate` (`merge_gate_refuses`) — до
мьютекса merge-окна и до очереди: незавершённая зависимость — отказ с
подсказкой повтора, убитая — отдельный отказ с каналом снятия `answer`.
`status`/`show` печатают зависимости заново из БД на каждый вызов
(`status_suffix`, `show_line`).
"""
from scripts import guard

from . import store
from .advance_gates.mandate import MERGE_AFTER_MANDATE_MARKER

FIELD = guard.MERGE_AFTER_FIELD

# Слово строки мандата, снимающее все зависимости: «Зависимости мержа: нет».
NONE_WORD = "нет"

# Состояния задачи, в которых `status` печатает ожидание зависимостей:
# задача уже готова к мержу или вот-вот будет (требование 5).
STATUS_WAIT_STATES = ("acceptance", "merge_gate")

# Состояние зависимости, которой нет в БД (строку убрали мимо пульта):
# печатается вместо состояния и на гейте мержа читается как убитая — ждать
# её завершения бессмысленно, нужен канал снятия.
MISSING_STATE = "нет в БД"

CHANGED_ACTION = "merge_after изменён"
PLAN_REJECTED_ACTION = "merge_after из PLAN отклонён"
MERGE_GATE_WAIT_ACTION = "approve отклонён: зависимости мержа не в done"
MERGE_GATE_KILLED_ACTION = "approve отклонён: зависимость мержа убита"

IMPACT_SECTION = "Влияние на систему"


def stored(value) -> list[str]:
    """Перечень id значения колонки (`None` — пустой)."""
    return guard.merge_after_items(value)


def column(ids: list[str]) -> str | None:
    """Значение колонки для перечня полных id; пустой перечень — NULL."""
    return ", ".join(ids) if ids else None


def _text(ids: list[str]) -> str:
    return ", ".join(ids) if ids else "—"


def _reason(item: str, why: str) -> str:
    return f"{FIELD}: элемент «{item}» — {why}"


def _cycle_path(graph: dict[str, list[str]], start: str,
                goal: str) -> list[str] | None:
    """Путь по рёбрам `graph` от `start` до `goal` (оба конца включены);
    `None` — пути нет. Обход в глубину с множеством посещённых: граф БД
    может уже нести чужие циклы, обход на них не зацикливается."""
    stack = [(start, [start])]
    seen = set()
    while stack:
        node, path = stack.pop()
        if node == goal:
            return path
        if node in seen:
            continue
        seen.add(node)
        for nxt in graph.get(node, []):
            stack.append((nxt, path + [nxt]))
    return None


def check(conn, task_id: str, items: list[str]) -> tuple[list[str], list[str]]:
    """(полные id в порядке `items`, причины отказа) — проверка значения
    `merge_after` задачи `task_id` правилами требований 1-2. Причины не
    пусты — перечень id не годен и не возвращается.

    Сначала форма (тот же узел, что у guard), затем каждый элемент по БД,
    затем цикл — только для значения, чьи элементы все годны: граф с
    несуществующим или неоднозначным узлом не строится."""
    reasons = guard.merge_after_form_errors(items, task_id)
    if reasons:
        return [], reasons
    own_target = store.task_target(conn, task_id)
    resolved: list[tuple[str, str]] = []
    for item in items:
        matches = store.task_id_matches(conn, item)
        if not matches:
            reasons.append(_reason(item, "нет такой задачи"))
            continue
        if len(matches) > 1:
            reasons.append(_reason(
                item, f"префикс неоднозначен — совпадает с {len(matches)} "
                      f"задачами: {', '.join(sorted(matches))}"))
            continue
        dep = matches[0]
        if dep == task_id:
            reasons.append(_reason(item, f"ссылается на саму задачу {task_id}"))
            continue
        if store.task_state(conn, dep) == "killed":
            reasons.append(_reason(item, f"задача {dep} убита (killed)"))
            continue
        dep_target = store.task_target(conn, dep)
        if dep_target != own_target:
            reasons.append(_reason(
                item, f"задача {dep} другого target ({dep_target}), у задачи "
                      f"— {own_target}"))
            continue
        if dep in [d for _, d in resolved]:
            reasons.append(_reason(item, f"повтор: задача {dep} уже названа"))
            continue
        resolved.append((item, dep))
    if reasons:
        return [], reasons
    graph = {r["id"]: stored(r["merge_after"]) for r in store.all_tasks(conn)}
    graph[task_id] = [dep for _, dep in resolved]
    for item, dep in resolved:
        path = _cycle_path(graph, dep, task_id)
        if path is not None:
            reasons.append(_reason(
                item, f"цикл: {' → '.join([task_id] + path)}"))
    if reasons:
        return [], reasons
    return [dep for _, dep in resolved], []


def spec_gate_value(conn, task_id: str,
                    meta: dict) -> tuple[str | None, str | None]:
    """(значение колонки, причина отказа) для `approve` гейта SPEC
    (требование 2). Поля в SPEC нет — (`None`, `None`): колонка пуста."""
    if FIELD not in meta:
        return None, None
    ids, reasons = check(conn, task_id, guard.merge_after_items(meta[FIELD]))
    if reasons:
        return None, "; ".join(reasons)
    return column(ids), None


def rewrite(conn, task_id: str, new_ids: list[str], channel: str,
            actor: str) -> None:
    """Записывает уже проверенное значение и строку журнала «было →
    стало» с названием канала (требование 3)."""
    old = stored(store.get_task(conn, task_id)["merge_after"])
    store.update_task(conn, task_id, merge_after=column(new_ids))
    detail = f"{_text(old)} → {_text(new_ids)} (канал: {channel})"
    store.journal(conn, task_id, actor, CHANGED_ACTION, detail)
    print(f"[{task_id}] {CHANGED_ACTION}: {detail}")


def apply_plan(conn, task_id: str, t, meta: dict, plan_text: str) -> None:
    """Канал PLAN на переходе `in_dev -> verifying` (требование 3) — по
    образцу `fsm_advance._apply_plan_budget`: отказ значения переход не
    останавливает, только пишется в журнал. Поля в PLAN нет — молча.

    Значение, совпавшее с БД после разрешения, не меняет ничего и
    обоснования не требует. Отличное — применяется, только если раздел
    «Влияние на систему» упоминает `merge_after` (обоснование смены) и
    значение прошло те же проверки, что на гейте SPEC."""
    if FIELD not in meta:
        return
    old = stored(t["merge_after"])
    ids, reasons = check(conn, task_id, guard.merge_after_items(meta[FIELD]))
    if not reasons and ids == old:
        return
    if not reasons and FIELD not in guard.section_body(plan_text,
                                                       IMPACT_SECTION):
        reasons = [f"смена {FIELD} не обоснована: раздел «{IMPACT_SECTION}» "
                   f"PLAN.md не упоминает {FIELD}"]
    if reasons:
        detail = f"{'; '.join(reasons)}; остаётся {_text(old)}"
        store.journal(conn, task_id, "fsm", PLAN_REJECTED_ACTION, detail)
        print(f"[{task_id}] ВНИМАНИЕ: {PLAN_REJECTED_ACTION}: {detail}")
        return
    rewrite(conn, task_id, ids, "PLAN", "fsm")


def _mandate_items(raw: str) -> list[list[str]]:
    """Элементы каждой строки мандата зависимостей в тексте ответа."""
    from .advance_gates import mandate
    found = []
    for line in raw.splitlines():
        parsed = mandate.elements(line, MERGE_AFTER_MANDATE_MARKER)
        if parsed is not None:
            found.append(parsed)
    return found


def value_refusals(conn, task_id: str | None, elements: list[str]) -> list[str]:
    """Причины отказа элементов ОДНОЙ строки мандата «Зависимости мержа:»
    (требование 3). `["нет"]` — снятие всех зависимостей, годно всегда.
    Без `conn` — только форма: проверка по БД нужна задаче, для которой
    пишется ответ."""
    if elements == [NONE_WORD]:
        return []
    if NONE_WORD in elements:
        return [f"слово «{NONE_WORD}» снимает все зависимости и стоит в "
                f"строке одно, без id"]
    if conn is None or task_id is None:
        return guard.merge_after_form_errors(elements, task_id)
    return check(conn, task_id, elements)[1]


def lines_refusal(raw: str) -> str | None:
    """Отказ файла с несколькими строками мандата зависимостей: строка
    задаёт значение целиком, двух значений у одного ответа быть не может."""
    if len(_mandate_items(raw)) > 1:
        return (f"строка «{MERGE_AFTER_MANDATE_MARKER}» повторена — новое "
                f"значение задаёт одна строка")
    return None


def mandate_value(conn, task_id: str, raw: str) -> list[str] | None:
    """Новое значение (полные id) из строки мандата текста ответа, уже
    прошедшего `mandate.refusals`; `None` — строки мандата зависимостей в
    тексте нет."""
    found = _mandate_items(raw)
    if not found:
        return None
    elements = found[0]
    if elements == [NONE_WORD]:
        return []
    return check(conn, task_id, elements)[0]


def has_mandate_line(raw: str) -> bool:
    return bool(_mandate_items(raw))


def _dependency_states(conn, t) -> list[tuple[str, str]]:
    """(id, текущее состояние) каждой зависимости задачи — из БД на каждый
    вызов, без кэша."""
    return [(dep, store.task_state(conn, dep) or MISSING_STATE)
            for dep in stored(t["merge_after"])]


def _listing(pairs: list[tuple[str, str]]) -> str:
    return ", ".join(f"{dep} ({state})" for dep, state in pairs)


def merge_gate_refuses(conn, task_id: str, t) -> bool:
    """Отказ `approve` на `merge_gate` по зависимостям (требование 4) —
    до `merge_lock.acquire` и до `merge_queue`: задача остаётся на гейте,
    окно и очередь не трогаются. `True` — отказано (печать и журнал
    сделаны).

    Убитая (или пропавшая из БД) зависимость не завершится никогда —
    отдельный именованный отказ с каналом снятия, а не подсказка повтора:
    иначе Оператор повторял бы `approve` без конца."""
    states = _dependency_states(conn, t)
    dead = [(d, s) for d, s in states if s in ("killed", MISSING_STATE)]
    if dead:
        reason = (f"зависимость мержа не завершится: {_listing(dead)} — сними "
                  f"или замени её ответом Оператора: artel.py answer "
                  f"{task_id} <файл> со строкой «{MERGE_AFTER_MANDATE_MARKER} "
                  f"<id>, …» (или «{MERGE_AFTER_MANDATE_MARKER} {NONE_WORD}»)")
        store.journal(conn, task_id, "operator", MERGE_GATE_KILLED_ACTION,
                      reason)
        print(f"[{task_id}] {MERGE_GATE_KILLED_ACTION}: {reason}")
        return True
    pending = [(d, s) for d, s in states if s != "done"]
    if pending:
        reason = (f"ждёт мержа зависимостей: {_listing(pending)} — повтори, "
                  f"когда они будут в done: artel.py approve {task_id}")
        store.journal(conn, task_id, "operator", MERGE_GATE_WAIT_ACTION, reason)
        print(f"[{task_id}] {MERGE_GATE_WAIT_ACTION}: {reason}")
        return True
    return False


def status_suffix(conn, t) -> str:
    """Добавка строки `status` (требование 5) — только в `acceptance`/
    `merge_gate` и только пока есть зависимости не в `done`; тем же
    приёмом, что `catalog._zone_wait_suffix`."""
    if t["state"] not in STATUS_WAIT_STATES:
        return ""
    pending = [(d, s) for d, s in _dependency_states(conn, t) if s != "done"]
    if not pending:
        return ""
    return f"  [ждёт мержа: {_listing(pending)}]"


def show_line(conn, t) -> str | None:
    """Строка `show` со всеми зависимостями, включая завершённые;
    `None` — зависимостей нет."""
    states = _dependency_states(conn, t)
    if not states:
        return None
    return f"  зависимости мержа: {_listing(states)}"
