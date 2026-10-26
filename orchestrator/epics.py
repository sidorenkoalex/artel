"""Эпик — сущность пульта: задачи одного проекта под общей целью (SPEC
01M5TBBDFS6DWQY6MS263T1KPY, требования 2-6, 9, 12; ADR-0028 уровень 1).

Команды `epic new|show|edit|close|add|remove`. Lease по id эпика не
берётся ни одной командой (решение гейта SPEC 26.10, аудит 4): команды
самого эпика — одна транзакция `BEGIN IMMEDIATE` (проверки, изменение,
запись журнала последней — её `commit` закрывает транзакцию); `add`/
`remove` меняют задачу и берут lease ЭТОЙ задачи (`lease.run_locked`), а
транзакция идёт внутри него. Так `epic close` и привязка к тому же эпику
взаимно исключены: проверка каждой видит состояние, которое другая уже
закоммитила либо ещё не начала менять.

Существование эпика проверяется до lease и до транзакции: нет эпика —
отказ «эпик <id> не найден», БД не меняется. SQL — в `store.py`.
"""
import sys

from . import board, config, idgen, lease, store, targets

EPIC_PREFIX = "E"
NEW_ACTION = "эпик заведён"
EDIT_ACTION = "эпик изменён"
CLOSE_ACTION = "эпик закрыт"
ADD_ACTION = "задача добавлена в эпик"
REMOVE_ACTION = "задача убрана из эпика"
# Запись журнала самой задачи о её эпике — после транзакции привязки, для
# `log <задача>`.
TASK_EPIC_ACTION = "эпик задачи"
READY_TEXT = "эпик готов к закрытию"
TABLE_COLUMNS = ("задача", "родитель", "от чего зависит", "состояние",
                 "кто держит", "потрачено/потолок", "итог")
USAGE = """\
epic new <проект> "<название>" --goal "<цель>" [--envelope N]
epic show <id>
epic edit <id> [--title "<название>"] [--goal "<цель>"]
epic close <id> "<итог>"
epic add <id> <задача>
epic remove <id> <задача>"""


def new_epic_id() -> str:
    """Id эпика — приставка `E` и id в формате идентификатора пульта
    (требование 2): с `E` он не проходит форму id задачи и не совпадает ни
    с одним её префиксом (id задачи начинается с цифры)."""
    return EPIC_PREFIX + idgen.new_task_id()


def not_found(epic_id: str) -> str:
    return f"эпик {epic_id} не найден"


def binding_refusal(conn, epic_id: str, project: str) -> str | None:
    """Причина, по которой задачу проекта `project` нельзя привязать к
    эпику (требования 3, 6); `None` — можно. Общая для `epic add`,
    `new --epic` и наследования эпика частями деления."""
    epic = store.get_epic(conn, epic_id)
    if epic is None:
        return not_found(epic_id)
    if epic["state"] != "open":
        return f"эпик {epic_id} закрыт — задачу в него не привязать"
    if epic["project"] != project:
        return (f"эпик {epic_id} проекта {epic['project']}, а задача — "
                f"проекта {project}")
    return None


def _existing(conn, epic_id: str):
    epic = store.get_epic(conn, epic_id)
    if epic is None:
        sys.exit(not_found(epic_id))
    return epic


def _transaction(conn, body) -> None:
    """`body()` в транзакции `BEGIN IMMEDIATE`: строка — отказ (откат и
    выход с ней), `None` — изменение сделано, и `body` закрыл транзакцию
    записью журнала."""
    store.begin_immediate(conn)
    try:
        refusal = body()
    except BaseException:
        conn.rollback()
        raise
    if refusal is not None:
        conn.rollback()
        sys.exit(refusal)
    conn.commit()


def _flag_values(args: list, flags: tuple, command: str) -> tuple[list, dict]:
    """(позиционные аргументы, {флаг: значение}); флаг без значения или
    незнакомый флаг — отказ."""
    positional, values = [], {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in flags:
            if i + 1 >= len(args):
                sys.exit(f"epic {command}: {arg} требует значение следующим "
                         f"аргументом\n{USAGE}")
            values[arg] = args[i + 1]
            i += 2
            continue
        if arg.startswith("--"):
            sys.exit(f"epic {command}: нераспознанный аргумент {arg}\n{USAGE}")
        positional.append(arg)
        i += 1
    return positional, values


def _checked_project(project: str) -> str:
    """Проект эпика сверяется с `targets.yaml` тем же правилом, что проект
    `new`: необъявленное имя — отказ; нечитаемый файл — отказ, кроме
    артели, которая разрешается и без него."""
    try:
        entries = targets.load()
    except targets.TargetsError as exc:
        if project != config.DEFAULT_TARGET:
            sys.exit(f"epic new: проект {project} не сверен: {exc}")
        return project
    if project not in entries:
        sys.exit(f"epic new: проект {project} не объявлен в "
                 f"{config.TARGETS.name} (есть: {', '.join(entries)})")
    return project


def cmd_new(args: list) -> str:
    positional, values = _flag_values(args, ("--goal", "--envelope"), "new")
    if len(positional) != 2 or "--goal" not in values:
        sys.exit(f"epic new: нужны проект, название и --goal\n{USAGE}")
    project, title = positional
    goal = values["--goal"]
    if not title.strip() or not goal.strip():
        sys.exit("epic new: название и цель не могут быть пустыми")
    envelope = None
    if "--envelope" in values:
        try:
            envelope = float(values["--envelope"])
        except ValueError:
            sys.exit(f"epic new: --envelope требует число, получено "
                     f"{values['--envelope']!r}")
        if envelope <= 0:
            sys.exit("epic new: --envelope должен быть больше нуля")
    _checked_project(project)
    conn = store.db()
    epic_id = new_epic_id()

    def body():
        store.insert_epic(conn, epic_id, project, title, goal, envelope)
        store.journal(conn, epic_id, "operator", NEW_ACTION,
                      f"«{title}»; цель: {goal}; конверт: "
                      f"{_envelope_text(envelope)}", target=project)

    _transaction(conn, body)
    print(f"[{epic_id}] эпик «{title}» заведён (проект {project})")
    return epic_id


def cmd_edit(args: list) -> None:
    positional, values = _flag_values(args, ("--title", "--goal"), "edit")
    if len(positional) != 1 or not values:
        sys.exit(f"epic edit: нужны id эпика и --title и/или --goal\n{USAGE}")
    epic_id = positional[0]
    fields = {name: values[flag] for flag, name in (("--title", "title"),
                                                    ("--goal", "goal"))
              if flag in values}
    if any(not value.strip() for value in fields.values()):
        sys.exit("epic edit: название и цель не могут быть пустыми")
    conn = store.db()
    epic = _existing(conn, epic_id)

    def body():
        store.update_epic(conn, epic_id, **fields)
        store.journal(conn, epic_id, "operator", EDIT_ACTION,
                      "; ".join(f"{name}: {value}"
                                for name, value in fields.items()),
                      target=epic["project"])

    _transaction(conn, body)
    print(f"[{epic_id}] эпик изменён: {', '.join(fields)}")


def cmd_close(args: list) -> None:
    """Закрывает эпик — только Оператор (требование 9): при задаче эпика
    не в окончательном состоянии — отказ с их перечнем, эпик остаётся
    `open`."""
    if len(args) != 2 or not args[1].strip():
        sys.exit(f"epic close: нужны id эпика и итог\n{USAGE}")
    epic_id, outcome = args
    from . import fsm  # отложенно: `fsm` тянет граф, импортирующий `catalog`
    conn = store.db()
    _existing(conn, epic_id)

    def body():
        epic = store.get_epic(conn, epic_id)
        if epic["state"] != "open":
            return f"epic close: эпик {epic_id} уже закрыт"
        open_tasks = [t for t in store.epic_tasks(conn, epic_id)
                      if t["state"] not in fsm.TERMINAL_STATES]
        if open_tasks:
            listing = ", ".join(f"{t['id']} ({t['state']})" for t in open_tasks)
            return (f"epic close: эпик {epic_id} не закрыт — задачи не в "
                    f"окончательном состоянии: {listing}")
        store.update_epic(conn, epic_id, state="closed", outcome=outcome,
                          closed_at=store.now())
        store.journal(conn, epic_id, "operator", CLOSE_ACTION, outcome,
                      target=epic["project"])

    _transaction(conn, body)
    print(f"[{epic_id}] эпик закрыт: {outcome}")


def _bind(args: list, command: str, body_for, task_detail: str) -> None:
    """Общая обвязка `epic add|remove`: эпик проверяется до lease задачи,
    затем lease задачи и транзакция внутри неё; после неё — запись журнала
    самой задачи."""
    if len(args) != 2:
        sys.exit(f"epic {command}: нужны id эпика и id задачи\n{USAGE}")
    epic_id, task_ref = args
    conn = store.db()
    epic = _existing(conn, epic_id)
    task_id = store.get_task(conn, task_ref)["id"]

    def locked(_sid):
        _transaction(conn, lambda: body_for(conn, epic, task_id))
        store.journal(conn, task_id, "operator", TASK_EPIC_ACTION,
                      f"{task_detail} {epic_id}")
        return True

    lease.run_locked(conn, task_id, None, locked)
    print(f"[{epic_id}] задача {task_id} {task_detail}")


def cmd_add(args: list) -> None:
    def body(conn, epic, task_id):
        t = store.get_task(conn, task_id)
        current = t["epic_id"]
        if current == epic["id"]:
            return f"epic add: задача {task_id} уже в эпике {epic['id']}"
        if current:
            return (f"epic add: задача {task_id} уже в эпике {current} — "
                    f"сначала epic remove {current} {task_id}")
        refusal = binding_refusal(conn, epic["id"],
                                  t["target"] or config.DEFAULT_TARGET)
        if refusal is not None:
            return f"epic add: {refusal}"
        store.set_task_epic(conn, task_id, epic["id"])
        store.journal(conn, epic["id"], "operator", ADD_ACTION, task_id,
                      target=epic["project"])

    _bind(args, "add", body, "добавлена в эпик")


def cmd_remove(args: list) -> None:
    def body(conn, epic, task_id):
        t = store.get_task(conn, task_id)
        if t["epic_id"] != epic["id"]:
            where = (f"в эпике {t['epic_id']}" if t["epic_id"]
                     else "без эпика")
            return (f"epic remove: задача {task_id} не в эпике {epic['id']} "
                    f"({where})")
        store.set_task_epic(conn, task_id, None)
        store.journal(conn, epic["id"], "operator", REMOVE_ACTION, task_id,
                      target=epic["project"])

    _bind(args, "remove", body, "убрана из эпика")


def create_from_division(conn, parent_id: str, title: str, project: str,
                         goal: str) -> str:
    """Эпик из поделённого родителя (`approve --as-epic`, требование 7):
    проект и название — родителя, цель — первый абзац «Контекст» его
    SPEC, конверт не задан; родитель входит в эпик той же транзакцией.
    Зовётся только из заведения частей деления — эпик без частей не
    рождается."""
    epic_id = new_epic_id()
    store.begin_immediate(conn)
    try:
        store.insert_epic(conn, epic_id, project, title, goal, None)
        store.set_task_epic(conn, parent_id, epic_id)
        store.journal(conn, epic_id, "operator", NEW_ACTION,
                      f"«{title}» из деления {parent_id}; цель: {goal}; "
                      f"конверт: {_envelope_text(None)}", target=project)
    except BaseException:
        conn.rollback()
        raise
    store.journal(conn, parent_id, "operator", TASK_EPIC_ACTION,
                  f"эпик {epic_id} заведён из деления (--as-epic)")
    print(f"[{epic_id}] эпик «{title}» заведён из деления {parent_id} "
          f"(проект {project})")
    return epic_id


# ===== Вид `epic show` (требование 12) =====


def _envelope_text(envelope) -> str:
    return f"${envelope:.2f}" if envelope is not None else "без конверта"


def _task_outcome(card: dict) -> str:
    if card["state"] == "done":
        return "слита"
    if card["closed_as"] == store.CLOSED_AS_DIVIDED:
        return "поделена"
    if card["state"] == "killed":
        return "убита"
    return "—"


def counts_text(counts: dict) -> str:
    return ", ".join(f"{state} {n}" for state, n in counts.items()) or "задач нет"


def show_lines(item: dict, cards: dict) -> list[str]:
    """Строки вида `epic show` по элементу эпика модели доски и её
    карточкам (`{id: карточка}`)."""
    state = item.get("state") or "open"
    lines = [f"{item['id']} {item['title']} [{state}]",
             f"Цель: {item['goal']}",
             f"Потрачено ${item['spent_usd']:.2f} / конверт "
             f"{_envelope_text(item['envelope_usd'])}; "
             f"{counts_text(item['counts'])}"]
    if item.get("outcome"):
        lines.append(f"Итог: {item['outcome']}")
    if not item["nodes"]:
        lines += ["", "задач нет"]
        return lines
    lines += ["", " | ".join(TABLE_COLUMNS)]
    for task_id in item["nodes"]:
        card = cards[task_id]
        lines.append(" | ".join((
            task_id,
            card.get("parent") or "—",
            ", ".join(card["depends_on"]) or "—",
            card["state"],
            card["waiting_on"] or "—",
            f"${card['spent_usd']:.2f}/${card['budget_usd'] or 0:.2f}",
            _task_outcome(card))))
    if item.get("ready_to_close"):
        lines += ["", READY_TEXT]
    return lines


def cmd_show(args: list) -> None:
    """Только чтение: ни lease, ни журнала."""
    if len(args) != 1:
        sys.exit(f"epic show: нужен id эпика\n{USAGE}")
    epic_id = args[0]
    conn = store.db()
    epic = _existing(conn, epic_id)
    model = board.build_model(conn, epic["project"])
    item = next(e for e in model["epics"] if e["id"] == epic_id)
    cards = {c["task"]: c for c in model["cards"]}
    print(f"Проект {epic['project']}")
    print("\n".join(show_lines(item, cards)))


def cmd_epic(rest: list) -> None:
    commands = {"new": cmd_new, "show": cmd_show, "edit": cmd_edit,
                "close": cmd_close, "add": cmd_add, "remove": cmd_remove}
    if not rest or rest[0] not in commands:
        sys.exit(f"epic: нужна подкоманда\n{USAGE}")
    commands[rest[0]](rest[1:])
