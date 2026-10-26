"""Зависимости мержа `merge_after`: заявление при `new` строкой ТЗ «Порядок: после …» (заявленное значение — сразу в колонке `merge_after`), сверка SPEC с заявленным на гейте SPEC, добавка `status` «[мерж после: …]» до `acceptance`, проверка в каналах переписывания, отказ на гейте мержа.

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

SPEC 01M45D29BQJE8FJYJA4JQWSYFZ: зависимость, названная Оператором в ТЗ
строкой «Порядок: после …», не ждёт пересказа аналитиком. `new --tz`
разбирает строку (`declared_from_tz`) и проверяет её тем же `check` до
заведения задачи — target заводимой задачи передаётся явно, строки БД ещё
нет. Прошедшее значение пишется сразу в колонку `merge_after`: до первого
прохода гейта SPEC её пишут только `new` и мандат Оператора в `escalated`,
значит колонка и есть заявленное значение, и `approve` на `spec_gate`
сверяет с ней поле SPEC ДО перезаписи (`spec_gate_declared_refusal`):
потеря заявленной — отказ, добавка аналитика — только с обоснованием в
разделе «## Обоснование зависимостей мержа».
"""
import re
from typing import NamedTuple

from scripts import guard

from . import idgen, store
from .advance_gates.mandate import MERGE_AFTER_MANDATE_MARKER

FIELD = guard.MERGE_AFTER_FIELD

# Слово строки мандата, снимающее все зависимости: «Зависимости мержа: нет».
NONE_WORD = "нет"

# Состояния задачи, в которых `status` печатает ожидание зависимостей:
# задача уже готова к мержу или вот-вот будет (требование 5).
STATUS_WAIT_STATES = ("acceptance", "merge_gate")

# Состояния до гейта SPEC: колонка в них — заявленное Оператором значение,
# `status` печатает его своей добавкой, отличной от «[ждёт мержа:».
STATUS_DECLARED_STATES = ("spec_writing", "spec_audit", "spec_gate")

# Строка ТЗ, заявляющая зависимости: метка с первой позиции, затем слово
# «после». «Порядок: без зависимостей» под неё не подходит и ничего не
# заявляет. Перечень кончается на конце строки, «(» или «.» — дальше в
# исторических ТЗ идёт пояснение свободным текстом.
ORDER_LINE = "Порядок: после"
_ORDER_LINE_RE = re.compile(r"^Порядок:[ \t]+после(?!\w)(.*)$", re.M)
_ORDER_LIST_END = re.compile(r"[(.]")

# Поле «Порядок:» части деления (SPEC 01M5TB6VDVV6AM8DWPGVQE8CDW,
# требование 4): тот же перечень после слова «после», что у строки ТЗ, и
# элемент «части N» — ссылка на N-й подраздел того же деления.
_DIVISION_ORDER_RE = re.compile(r"^после(?!\w)(.*)$", re.S)
_PART_ITEM_RE = re.compile(r"^части[ \t]+(\d+)$")

DECLARED_ACTION = "merge_after заявлен Оператором"
ADDED_ACTION = "merge_after: добавлено аналитиком"
JUSTIFICATION_SECTION = "Обоснование зависимостей мержа"

# Переходы, после которых задача уже прошла гейт SPEC: дальше колонка —
# рабочее значение (PLAN, мандат), а не заявленное, и сверки с ним нет.
_PAST_SPEC_GATE_ACTIONS = ("state -> tests_writing", "state -> in_dev")

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


def check(conn, task_id: str | None, items: list[str], *,
          target: str | None = None) -> tuple[list[str], list[str]]:
    """(полные id в порядке `items`, причины отказа) — проверка значения
    `merge_after` задачи `task_id` правилами требований 1-2. Причины не
    пусты — перечень id не годен и не возвращается.

    Сначала форма (тот же узел, что у guard), затем каждый элемент по БД,
    затем цикл — только для значения, чьи элементы все годны: граф с
    несуществующим или неоднозначным узлом не строится.

    `task_id=None` с явным `target` — проверка для ещё не заведённой задачи
    (`new --tz`): строки БД нет, и `store.task_target` молча вернул бы
    target по умолчанию вместо target'а заводимой задачи."""
    reasons = guard.merge_after_form_errors(items, task_id)
    if reasons:
        return [], reasons
    own_target = target if target is not None else store.task_target(conn, task_id)
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


def declared_from_tz(conn, tz_raw: str,
                     target: str) -> tuple[list[str], list[str]]:
    """(заявленные полные id в порядке строки, причины отказа `new`) из
    строки ТЗ «Порядок: после …» (SPEC 01M45D29BQJE8FJYJA4JQWSYFZ,
    требования 1-2). Строки нет — ([], []). Элементы проверяет `check` для
    ещё не заведённой задачи target'а `target`."""
    items, reasons = _tz_order_items(tz_raw)
    if reasons or not items:
        return [], reasons
    return check(conn, None, items, target=target)


def _tz_order_items(tz_raw: str) -> tuple[list[str], list[str]]:
    """(элементы строки ТЗ «Порядок: после …» как написаны, причины отказа
    по форме строки). Строки нет — ([], [])."""
    tails = [m.group(1) for m in _ORDER_LINE_RE.finditer(tz_raw)]
    if not tails:
        return [], []
    if len(tails) > 1:
        return [], [f"строка «{ORDER_LINE}» повторена — значение задаёт "
                    f"одна строка"]
    tail = _ORDER_LIST_END.split(tails[0], maxsplit=1)[0]
    items = guard.merge_after_items(tail)
    if not items:
        return [], [f"в строке «{ORDER_LINE}» нет ни одного id задачи"]
    return items, []


def declared_for_new(conn, tz_raw: str | None, after: str | None,
                     target: str) -> tuple[list[str], list[str]]:
    """(полные id, причины отказа `new`) из строки ТЗ «Порядок: после …» и
    флага `--after` (SPEC 01M5TBBDFS6DWQY6MS263T1KPY, требование 5):
    объединение — сначала элементы ТЗ, затем элементы `--after`, чей полный
    id ещё не вошёл (префикс и полный id одной задачи — один элемент).
    Дедупликация — до `check`: `check` отказывает на повторе, а проверяет
    он уже объединённый перечень, так что непрошедший элемент любого
    источника отказывает всему."""
    items, reasons = _tz_order_items(tz_raw) if tz_raw is not None else ([], [])
    if reasons:
        return [], reasons

    def full_id(item: str) -> str:
        matches = store.task_id_matches(conn, item)
        return matches[0] if len(matches) == 1 else item

    # Повтор внутри самой строки ТЗ — по-прежнему отказ `check`: схлопываются
    # только элементы `--after`, уже вошедшие в перечень.
    merged = list(items)
    seen = {full_id(item) for item in items}
    for item in guard.merge_after_items(after):
        key = full_id(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    if not merged:
        return [], []
    return check(conn, None, merged, target=target)


def record_declared(conn, task_id: str, ids: list[str]) -> None:
    """Заявленное значение — в колонку при заведении, с записью журнала
    (требование 3); пустое — колонка и журнал не трогаются."""
    if not ids:
        return
    store.update_task(conn, task_id, merge_after=column(ids))
    store.journal(conn, task_id, "operator", DECLARED_ACTION, _text(ids))
    print(f"[{task_id}] {DECLARED_ACTION}: {_text(ids)}")


def _declared_in_force(conn, task_id: str) -> bool:
    """Колонка всё ещё заявленное значение — задача ни разу не проходила
    гейт SPEC (повторный приход на `spec_gate` после прохода сверяет уже
    рабочее значение не с чем)."""
    return not any(r["action"] in _PAST_SPEC_GATE_ACTIONS
                   for r in store.task_steps(conn, task_id))


def _justified(section: str, item: str, dep: str) -> bool:
    """Раздел обоснования называет зависимость полным id либо тем же
    элементом, что стоит в поле, — словом целиком: короткий префикс внутри
    чужого id обоснованием не считается."""
    words = set(re.findall(r"[0-9A-Za-z]+", section))
    return dep in words or item in words


def spec_gate_declared_refusal(conn, task_id: str, t, meta: dict,
                               new_value: str | None,
                               spec_text: str) -> tuple[list[str], str | None]:
    """(добавленные аналитиком полные id, причина отказа) — сверка уже
    проверенного значения поля SPEC `new_value` с заявленным Оператором
    (колонка до перезаписи, требования 5-6). Заявленного нет или гейт SPEC
    уже пройден — сверки нет: ([], None)."""
    declared = stored(t["merge_after"])
    if not declared or not _declared_in_force(conn, task_id):
        return [], None
    new_ids = stored(new_value)
    lost = [d for d in declared if d not in new_ids]
    if lost:
        return [], (f"{FIELD} SPEC теряет зависимости, заявленные Оператором "
                    f"строкой ТЗ «{ORDER_LINE}»: {_text(lost)} — верни SPEC "
                    f"аналитику: artel.py reject {task_id} \"аналитик, "
                    f"эскалируй вопрос о зависимости {_text(lost)}\"; после "
                    f"эскалации аналитика ответ в escalated — artel.py "
                    f"answer {task_id} <файл> со строкой "
                    f"«{MERGE_AFTER_MANDATE_MARKER} …», затем artel.py "
                    f"approve {task_id}")
    section = guard.section_body(spec_text, JUSTIFICATION_SECTION)
    # `new_value` — итог `check` по элементам поля: тот же порядок и длина.
    pairs = [(item, dep) for item, dep in
             zip(guard.merge_after_items(meta.get(FIELD)), new_ids)
             if dep not in declared]
    added = [dep for _, dep in pairs]
    unjustified = [dep for item, dep in pairs
                   if not _justified(section, item, dep)]
    if unjustified:
        return [], (f"{FIELD} SPEC добавляет зависимости сверх заявленных "
                    f"Оператором без обоснования: {_text(unjustified)} — "
                    f"назови каждую в разделе «## {JUSTIFICATION_SECTION}» "
                    f"SPEC")
    return added, None


def record_added(conn, task_id: str, added: list[str]) -> None:
    """Запись журнала о принятой добавке аналитика — отдельно от
    заявленных (требование 6)."""
    if not added:
        return
    store.journal(conn, task_id, "operator", ADDED_ACTION, _text(added))
    print(f"[{task_id}] {ADDED_ACTION}: {_text(added)}")


def rewrite(conn, task_id: str, new_ids: list[str], channel: str,
            actor: str) -> None:
    """Записывает уже проверенное значение и строку журнала «было →
    стало» с названием канала (требование 3)."""
    old = stored(store.get_task(conn, task_id)["merge_after"])
    store.update_task(conn, task_id, merge_after=column(new_ids))
    detail = f"{_text(old)} → {_text(new_ids)} (канал: {channel})"
    store.journal(conn, task_id, actor, CHANGED_ACTION, detail)
    print(f"[{task_id}] {CHANGED_ACTION}: {detail}")


class DivisionOrder(NamedTuple):
    """Проверенный порядок частей деления (`division_order`). `deps` — по
    части на элемент списка, в порядке подразделов: зависимости части в
    порядке её «Порядок:» — индекс соседней части (`int`, с 0) или полный
    id задачи (`str`). `successor` — индекс части-преемника родителя.
    `loose` — номера частей (с 1), кроме первой, чей «Порядок:» не задаёт
    зависимостей."""
    deps: list
    successor: int
    loose: list


def division_order_items(order: str | None) -> list[str] | None:
    """Элементы поля «Порядок:» части деления — по правилам строки ТЗ
    «Порядок: после …» (`declared_from_tz`: через запятую, перечень
    кончается на «(» или «.»). `None` — значение не начинается словом
    «после» и зависимостей не задаёт («первая, без зависимостей»)."""
    m = _DIVISION_ORDER_RE.match((order or "").strip())
    if m is None:
        return None
    return guard.merge_after_items(_ORDER_LIST_END.split(m.group(1),
                                                         maxsplit=1)[0])


def _part_label(number: int, title: str) -> str:
    return f"часть {number} «{title}»"


def _part_deps(conn, parent_id: str, target: str, number: int, count: int,
               items: list[str]) -> tuple[list, list[str]]:
    """(зависимости части `number` из `count`, причины отказа) по
    элементам её «Порядок: после …» (SPEC 01M5TB6VDVV6AM8DWPGVQE8CDW,
    требования 4-5). «части N» — индекс соседней части; иначе элемент —
    id задачи по правилам `check`, кроме самого родителя: он этим же
    approve уходит в `killed`, а `check` видит его ещё живым."""
    resolved: list = [None] * len(items)
    reasons: list[str] = []
    parts_seen: set[int] = set()
    id_positions: list[int] = []
    for i, item in enumerate(items):
        m = _PART_ITEM_RE.match(item)
        if m:
            ref = int(m.group(1))
            if not 1 <= ref <= count:
                reasons.append(f"элемент «{item}» — номер части вне 1..{count}")
            elif ref == number:
                reasons.append(f"элемент «{item}» — ссылка части на саму себя")
            elif ref in parts_seen:
                reasons.append(f"элемент «{item}» указан повторно")
            else:
                parts_seen.add(ref)
                resolved[i] = ref - 1
            continue
        if (idgen.is_task_id_form(item)
                and store.task_id_matches(conn, item) == [parent_id]):
            reasons.append(f"элемент «{item}» — мёртвая зависимость: сам "
                           f"родитель {parent_id}, этим approve он уходит в "
                           f"killed")
            continue
        id_positions.append(i)
    ids, id_reasons = check(conn, None, [items[i] for i in id_positions],
                            target=target)
    reasons += id_reasons
    for i, dep in zip(id_positions, ids):
        resolved[i] = dep
    return resolved, reasons


def _part_reach(deps: list, start: int) -> set[int]:
    """Части, от которых часть `start` зависит прямо или через другие
    части."""
    found: set[int] = set()
    stack = [d for d in deps[start] if isinstance(d, int)]
    while stack:
        part = stack.pop()
        if part in found:
            continue
        found.add(part)
        stack += [d for d in deps[part] if isinstance(d, int)]
    return found


def _successor(deps: list) -> int:
    """Часть, которая мержится последней по графу частей (требование 4):
    никто не зависит от последней по номеру — она; иначе из частей,
    зависящих от неё прямо или через другие, та, от которой не зависит
    ни одна часть, а из таких — с наибольшим номером. Граф с циклом
    преемника не имеет — его откажет проверка цикла, здесь — последняя."""
    last = len(deps) - 1
    reach = [_part_reach(deps, p) for p in range(len(deps))]
    above = [p for p in range(len(deps)) if p != last and last in reach[p]]
    if not above:
        return last
    tops = [p for p in above
            if not any(p in reach[q] for q in range(len(deps)) if q != p)]
    return max(tops) if tops else last


def division_order(conn, parent_id: str, target: str,
                   parts: list[tuple[str, str | None]]
                   ) -> tuple[DivisionOrder | None, list[str]]:
    """(порядок частей, причины отказа) деления `parent_id` на гейте SPEC
    (SPEC 01M5TB6VDVV6AM8DWPGVQE8CDW, требования 4-5) — до заведения
    первой части, без записей. `parts` — (название, «Порядок:») каждого
    подраздела секции «## Деление». Причина называет часть.

    Цикл ищется на виртуальном графе: части — узлы ещё не заведённых
    задач, к ним — действующий `merge_after` всех задач БД, где ребро
    зависящей от родителя задачи уже переставлено на преемника
    (`replace_divided`): иначе цикл «часть → D → преемник» не виден."""
    count = len(parts)
    deps: list = []
    loose: list[int] = []
    reasons: list[str] = []
    for number, (title, order) in enumerate(parts, 1):
        items = division_order_items(order)
        if items is None:
            deps.append([])
            if number > 1:
                loose.append(number)
            continue
        if not items:
            reasons.append(f"{_part_label(number, title)}: «Порядок: после» "
                           f"без элементов")
            deps.append([])
            continue
        own, why = _part_deps(conn, parent_id, target, number, count, items)
        reasons += [f"{_part_label(number, title)}: Порядок: {r}" for r in why]
        deps.append(own)
    if reasons:
        return None, reasons
    successor = _successor(deps)

    def node(part: int) -> str:
        return f"#{part + 1}"

    def name(key: str) -> str:
        return f"часть {key[1:]}" if key.startswith("#") else key

    graph = {r["id"]: [node(successor) if d == parent_id else d
                       for d in stored(r["merge_after"])]
             for r in store.all_tasks(conn)}
    for part, own in enumerate(deps):
        graph[node(part)] = [node(d) if isinstance(d, int) else d
                             for d in own]
    for part, (title, _) in enumerate(parts):
        for dep in graph[node(part)]:
            path = _cycle_path(graph, dep, node(part))
            if path is not None:
                reasons.append(
                    f"{_part_label(part + 1, title)}: Порядок: цикл: "
                    f"{' → '.join(name(k) for k in [node(part)] + path)}")
                break
    if reasons:
        return None, reasons
    return DivisionOrder(deps, successor, loose), []


def replace_divided(conn, parent_id: str, successor_id: str) -> None:
    """Деление `parent_id` на гейте SPEC (SPEC 01M4JC58GZFHZ4PZHW254P22M2):
    в `merge_after` каждой задачи, зависящей от родителя, элемент-родитель
    заменяется `successor_id` — частью, которая мержится последней по
    графу частей (`division_order`, SPEC 01M5TB6VDVV6AM8DWPGVQE8CDW,
    требование 4), — на той же позиции, прочие элементы остаются. Без
    замены родитель в `killed` навсегда держал бы зависящую задачу отказом
    гейта мержа «зависимость убита», снимаемым только ответом Оператора.

    Проверки `check` здесь нет: значение отличается от уже принятого
    одним элементом, а цикл через преемника `division_order` уже искал на
    виртуальном графе до заведения частей."""
    for row in store.all_tasks(conn):
        old = stored(row["merge_after"])
        if parent_id not in old:
            continue
        new_ids = [successor_id if dep == parent_id else dep for dep in old]
        # Канал без id родителя: правая часть записи «было → стало» —
        # новое значение, и родитель в ней не называется.
        rewrite(conn, row["id"], new_ids, "деление на гейте SPEC", "operator")


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
    приёмом, что `catalog._zone_wait_suffix`. До гейта SPEC
    (`STATUS_DECLARED_STATES`) — своя добавка «[мерж после: …]» с
    заявленными Оператором зависимостями (SPEC 01M45D29BQJE8FJYJA4JQWSYFZ,
    требование 4)."""
    if t["state"] in STATUS_WAIT_STATES:
        label = "ждёт мержа"
    elif t["state"] in STATUS_DECLARED_STATES:
        label = "мерж после"
    else:
        return ""
    pending = [(d, s) for d, s in _dependency_states(conn, t) if s != "done"]
    if not pending:
        return ""
    return f"  [{label}: {_listing(pending)}]"


def show_line(conn, t) -> str | None:
    """Строка `show` со всеми зависимостями, включая завершённые;
    `None` — зависимостей нет."""
    states = _dependency_states(conn, t)
    if not states:
        return None
    return f"  зависимости мержа: {_listing(states)}"
