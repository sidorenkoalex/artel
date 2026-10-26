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

Черновики и решения эпика, копия эпика в `refs/artifacts/epic-<id>`
репозитория его проекта, `epic export`/`epic restore` (SPEC
01M5TBFCVFNN95BHH0E9C6KBKB; ADR-0028 уровень 3, п. 11). Ссылку пишет
каждая команда, меняющая эпик, его черновики или решения, — после своей
транзакции, полным состоянием БД (`_write_ref`); вся подкоманда идёт в
одной области `artifact_branch.deferred_sends`, так что ссылка уходит в
`origin` один раз на команду. Файлы ссылки — Markdown для чтения и первой
строкой JSON строк БД (`_data_line`): `epic restore` читает только его.

`epic parallel|stop|retry` — лимит, остановка и разрешение перезапуска
надзора эпика `auto --epic` (SPEC 01M5TBF7JRZ6FGRR4K53KPAJDS); сам надзор —
`auto.cmd_auto_epic`.
"""
import json
import os
import re
import signal
import sys
import time

from scripts import guard

from . import (artifact_branch, board, budget, config, gitcmd, idgen, lease,
               merge_after, spend, store, targets)

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
DRAFT_ADD_ACTION = "черновик эпика заведён"
DRAFT_EDIT_ACTION = "черновик эпика изменён"
DRAFT_DROP_ACTION = "черновик эпика отброшен"
DRAFT_PROMOTE_ACTION = "черновик эпика переведён в задачу"
DECISION_ACTION = "решение эпика"
RESTORE_ACTION = "эпик восстановлен из ссылки"
REF_WRITE_FAILED_ACTION = "запись ссылки эпика FAILED"
PARALLEL_ACTION = "лимит надзора эпика изменён"
STOP_REQUEST_ACTION = "epic stop: SIGTERM надзору"
STOP_CHILD_ACTION = "epic stop: SIGTERM дочернему auto"
# Сколько `epic stop` ждёт остановки надзора, прежде чем трогать дочерние:
# надзор слышит SIGTERM сразу, и во сне опроса, и между запусками.
EPIC_STOP_WAIT_SEC = 60
DRAFT, PROMOTED, DROPPED = "draft", "promoted", "dropped"
# Привязка решения (`epic_decisions.for_kind`).
FOR_EPIC, FOR_DRAFT, FOR_TASK, FOR_ENVELOPE = "epic", "draft", "task", "envelope"
ENVELOPE_WORD = "envelope"
# Адрес черновика `<id эпика>/<n>` (требование 2).
_ADDRESS_RE = re.compile(r"(E\w+)/([1-9][0-9]*)")
TABLE_COLUMNS = ("задача", "родитель", "от чего зависит", "состояние",
                 "кто держит", "потрачено/потолок", "итог")
USAGE = """\
epic new <проект> "<название>" --goal "<цель>" [--envelope N]
epic show <id>
epic edit <id> [--title "<название>"] [--goal "<цель>"]
epic close <id> "<итог>"
epic add <id> <задача>
epic remove <id> <задача>
epic envelope <id> N
epic start-after <задача> <id>…|нет
epic draft add <id> --tz <файл> [--start-after …] [--after …] [--budget N]
epic draft edit <id>/<n> [--tz <файл>] [--start-after …] [--after …] [--budget N]
epic draft drop|promote <id>/<n>
epic decision <id> "<дословно>" [--for <id>/<n>|<задача>|envelope]
epic export <id>
epic restore <проект> <id>
epic parallel <id> N
epic stop <id>
epic retry <id> <задача>"""


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
    _write_ref(conn, epic_id)
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
    _write_ref(conn, epic_id)


def cmd_close(args: list) -> None:
    """Закрывает эпик — только Оператор (требование 9): при задаче эпика
    не в окончательном состоянии или черновике в `draft` (SPEC
    01M5TBFCVFNN95BHH0E9C6KBKB, требование 17) — отказ с их перечнем, эпик
    остаётся `open`."""
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
        drafts = [d for d in store.epic_drafts(conn, epic_id)
                  if d["state"] == DRAFT]
        reasons = []
        if open_tasks:
            listing = ", ".join(f"{t['id']} ({t['state']})" for t in open_tasks)
            reasons.append(f"задачи не в окончательном состоянии: {listing}")
        if drafts:
            listing = ", ".join(_draft_label(d) for d in drafts)
            reasons.append(f"черновики в состоянии {DRAFT}: {listing} — "
                           f"переведи (epic draft promote) или отбрось "
                           f"(epic draft drop)")
        if reasons:
            return (f"epic close: эпик {epic_id} не закрыт — "
                    + "; ".join(reasons))
        store.update_epic(conn, epic_id, state="closed", outcome=outcome,
                          closed_at=store.now())
        store.journal(conn, epic_id, "operator", CLOSE_ACTION, outcome,
                      target=epic["project"])

    _transaction(conn, body)
    print(f"[{epic_id}] эпик закрыт: {outcome}")
    _write_ref(conn, epic_id)


def _bind(args: list, command: str, body_for, task_detail: str) -> None:
    """Общая обвязка `epic add|remove`: эпик проверяется до lease задачи,
    затем lease задачи и транзакция внутри неё; после неё — запись журнала
    самой задачи. Ссылка эпика пишется внутри lease (её область
    отложенной отправки — одна отправка на команду)."""
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
        _write_ref(conn, epic_id)
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


def cmd_envelope(args: list) -> None:
    """Конверт эпика (SPEC 01M5TBCY7WTN121S136XP2C6SR, требование 3): годно
    только число > 0 (`spend.cli_number`); подъём и понижение разрешены,
    каждое изменение — запись журнала эпика, с которой счёт алерта 80 %
    начинается заново (требование 5)."""
    if len(args) != 2:
        sys.exit(f"epic envelope: нужны id эпика и сумма\n{USAGE}")
    epic_id, raw = args
    value = spend.cli_number(raw)
    if value is None:
        sys.exit(f"epic envelope: сумма {raw!r} не число — конверт не изменён")
    if value <= 0:
        sys.exit(f"epic envelope: сумма должна быть больше нуля, получено "
                 f"{raw!r} — конверт не изменён")
    conn = store.db()
    _existing(conn, epic_id)

    def body():
        epic = store.get_epic(conn, epic_id)
        store.update_epic(conn, epic_id, envelope_usd=value)
        store.journal(conn, epic_id, "operator", budget.EPIC_ENVELOPE_ACTION,
                      f"{_envelope_text(epic['envelope_usd'])} → "
                      f"{_envelope_text(value)}", target=epic["project"])

    _transaction(conn, body)
    spent = budget.epic_spent(conn, epic_id)
    print(f"[{epic_id}] конверт эпика: {_envelope_text(value)}; потрачено "
          f"${spent:.2f}")
    _write_ref(conn, epic_id)


def cmd_start_after(args: list) -> None:
    """Зависимость запуска задачи (SPEC 01M5TBCY7WTN121S136XP2C6SR,
    требования 11-14): значение целиком — id через пробел или запятую;
    «нет» снимает все. Поделённые элементы заменяются последней частью,
    затем проверка `merge_after.start_after_value`; отказ — значение
    прежнее. Под lease задачи, как `epic add|remove`."""
    if len(args) < 2:
        sys.exit(f"epic start-after: нужны id задачи и зависимости\n{USAGE}")
    task_ref, raw_items = args[0], args[1:]
    items = guard.merge_after_items(",".join(raw_items))
    conn = store.db()
    task_id = store.get_task(conn, task_ref)["id"]

    def locked(_sid):
        if items == [merge_after.NONE_WORD]:
            ids = []
        else:
            ids, reasons = merge_after.start_after_value(conn, task_id, items)
            if reasons:
                sys.exit("epic start-after: " + "; ".join(reasons)
                         + " — start_after не изменён")
        old = merge_after.stored(store.get_task(conn, task_id)["start_after"])
        if ids == old:
            print(f"[{task_id}] start_after без изменений: "
                  f"{', '.join(ids) or '—'}")
            return True
        merge_after.rewrite_start_after(conn, task_id, ids, "epic start-after",
                                        "operator")
        return True

    lease.run_locked(conn, task_id, None, locked)


# ===== Надзор эпика: лимит, остановка, перезапуск (SPEC
# 01M5TBF7JRZ6FGRR4K53KPAJDS, требования 3, 5, 11) =====


def cmd_parallel(args: list) -> None:
    """Лимит одновременно живых дочерних `auto` надзора эпика: годно только
    целое > 0; иначе отказ, лимит прежний."""
    if len(args) != 2:
        sys.exit(f"epic parallel: нужны id эпика и лимит\n{USAGE}")
    epic_id, raw = args
    try:
        value = int(raw.strip())
    except ValueError:
        sys.exit(f"epic parallel: лимит {raw!r} не целое число — лимит не "
                 f"изменён")
    if value <= 0:
        sys.exit(f"epic parallel: лимит должен быть больше нуля, получено "
                 f"{raw!r} — лимит не изменён")
    from . import auto  # отложенно: `auto` тянет граф, импортирующий этот модуль
    conn = store.db()
    _existing(conn, epic_id)

    def body():
        epic = store.get_epic(conn, epic_id)
        store.update_epic(conn, epic_id, parallel=value)
        old = epic["parallel"]
        if old is None:
            old = f"не задан ({auto.EPIC_DEFAULT_PARALLEL})"
        store.journal(conn, epic_id, "operator", PARALLEL_ACTION,
                      f"{old} → {value}", target=epic["project"])

    _transaction(conn, body)
    print(f"[{epic_id}] лимит дочерних auto надзора эпика: {value}")
    _write_ref(conn, epic_id)


def _wait_supervisor_gone(conn, epic, row) -> bool:
    """Ждёт, пока надзор, получивший SIGTERM, снимет свою блокировку либо
    умрёт (тогда блокировку снимает эта команда); `False` — не дождались."""
    from . import auto
    deadline = time.monotonic() + EPIC_STOP_WAIT_SEC
    while time.monotonic() < deadline:
        current = store.epic_supervisor_row(conn, epic["id"])
        if current is None or current["pid"] != row["pid"]:
            return True
        if not lease.process_alive(row["pid"], row["host"], row["started_at"]):
            auto.drop_dead_supervisor_lock(conn, epic, row, "epic stop")
            return True
        time.sleep(0.2)
    return False


def cmd_stop(args: list) -> None:
    """Сначала надзор (SIGTERM живому, после его остановки новых дочерних
    запусков нет; мёртвая блокировка снимается без сигнала), затем живые
    дочерние `auto`, запущенные надзором, — штатный SIGTERM: `auto`
    доигрывает текущий шаг и пишет остановку сам. `auto <id>`, запущенный
    Оператором, не трогается: его нет среди дочерних надзора."""
    if len(args) != 1:
        sys.exit(f"epic stop: нужен id эпика\n{USAGE}")
    epic_id = args[0]
    from . import auto
    conn = store.db()
    epic = _existing(conn, epic_id)
    project = epic["project"]
    row = store.epic_supervisor_row(conn, epic_id)
    if row is not None:
        if lease.process_alive(row["pid"], row["host"], row["started_at"]):
            try:
                os.kill(row["pid"], signal.SIGTERM)
            except ProcessLookupError:
                auto.drop_dead_supervisor_lock(conn, epic, row, "epic stop")
            else:
                store.journal(conn, epic_id, "operator", STOP_REQUEST_ACTION,
                              f"SIGTERM надзору pid {row['pid']}", target=project)
                print(f"[{epic_id}] epic stop: SIGTERM надзору pid {row['pid']}")
                if not _wait_supervisor_gone(conn, epic, row):
                    sys.exit(f"[{epic_id}] надзор pid {row['pid']} не "
                             f"остановился за {EPIC_STOP_WAIT_SEC} с — дочерние "
                             f"auto не тронуты; повтори artel.py epic stop "
                             f"{epic_id}")
        else:
            auto.drop_dead_supervisor_lock(conn, epic, row, "epic stop")
    children = auto.live_epic_children(conn, epic_id)
    for child in children:
        try:
            os.kill(child["pid"], signal.SIGTERM)
        except ProcessLookupError:
            continue
        detail = f"эпик {epic_id}: SIGTERM дочернему auto pid {child['pid']}"
        store.journal(conn, child["task_id"], "operator", STOP_CHILD_ACTION,
                      detail)
        store.journal(conn, epic_id, "operator", STOP_CHILD_ACTION,
                      f"{child['task_id']}: SIGTERM pid {child['pid']}",
                      target=project)
        print(f"[{epic_id}] epic stop: SIGTERM дочернему auto "
              f"{child['task_id']} pid {child['pid']} — доиграет текущий шаг "
              f"и завершится сам")
    if row is None and not children:
        sys.exit(f"[{epic_id}] надзор эпика не запущен и живых дочерних auto "
                 f"нет — нечего останавливать")


def cmd_retry(args: list) -> None:
    """Явное разрешение перезапуска задачи эпика после остановки не на
    гейте: запись журнала задачи, которую надзор считает новым действием
    Оператора (требования 4, 5)."""
    if len(args) != 2:
        sys.exit(f"epic retry: нужны id эпика и id задачи\n{USAGE}")
    epic_id, task_ref = args
    from . import auto
    conn = store.db()
    _existing(conn, epic_id)
    t = store.get_task(conn, task_ref)
    if t["epic_id"] != epic_id:
        where = f"в эпике {t['epic_id']}" if t["epic_id"] else "без эпика"
        sys.exit(f"epic retry: задача {t['id']} не в эпике {epic_id} ({where}) "
                 f"— запись не сделана")
    store.journal(conn, t["id"], "operator", auto.EPIC_RETRY_ACTION,
                  f"эпик {epic_id}: перезапуск после остановки не на гейте")
    print(f"[{epic_id}] задача {t['id']}: перезапуск разрешён — надзор "
          f"запустит её на ближайшем опросе, когда она готова")


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


# ===== Черновики эпика (SPEC 01M5TBFCVFNN95BHH0E9C6KBKB, требования 2-8) =====


def draft_address(epic_id: str, number: int) -> str:
    return f"{epic_id}/{number}"


def parse_address(text: str) -> tuple[str, int] | None:
    """(id эпика, номер) адреса черновика `<id эпика>/<n>`; `None` — не
    адрес."""
    match = _ADDRESS_RE.fullmatch(text.strip())
    return (match.group(1), int(match.group(2))) if match else None


def _draft_label(draft) -> str:
    address = draft_address(draft["epic_id"], draft["number"])
    return f"{address} «{draft['title']}»"


def _draft_or_exit(conn, address: str, command: str):
    parsed = parse_address(address)
    if parsed is None:
        sys.exit(f"epic draft {command}: {address!r} не адрес черновика "
                 f"(<id эпика>/<n>)\n{USAGE}")
    draft = store.get_draft(conn, *parsed)
    if draft is None:
        sys.exit(f"epic draft {command}: черновика {address} нет")
    return draft


def _state_refusal(draft, command: str) -> str | None:
    """Отказ команды по черновику не в `draft` (требование 8)."""
    if draft["state"] == DRAFT:
        return None
    address = draft_address(draft["epic_id"], draft["number"])
    return (f"epic draft {command}: черновик {address} в состоянии "
            f"{draft['state']} — {command} только черновика в состоянии "
            f"{DRAFT}")


def _read_tz(path: str, command: str) -> tuple[str, str]:
    """(текст ТЗ дословно, название — первый заголовок `# `)."""
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"epic draft {command}: ТЗ не прочитано из {path}: {exc}")
    for line in text.splitlines():
        if line.startswith("# ") and line[2:].strip():
            return text, line[2:].strip()
    sys.exit(f"epic draft {command}: в ТЗ {path} нет заголовка «# » — "
             f"название черновика взять неоткуда")


def _frame_value(raw: str, command: str) -> float:
    value = spend.cli_number(raw)
    if value is None or value <= 0:
        sys.exit(f"epic draft {command}: --budget требует число больше нуля, "
                 f"получено {raw!r}")
    return value


def _list_value(conn, raw: str, flag: str,
                own: tuple[str, int] | None) -> tuple[str | None, list[str]]:
    """(значение колонки, причины отказа) перечня `--start-after`/`--after`
    черновика (требования 2-3): элемент — задача БД (полный id или
    префикс, хранится полным id) либо адрес существующего черновика."""
    resolved, unknown, reasons = [], [], []
    for item in guard.merge_after_items(raw):
        parsed = parse_address(item)
        if parsed is not None:
            if store.get_draft(conn, *parsed) is None:
                unknown.append(item)
                continue
            if parsed == own:
                reasons.append(f"{flag}: черновик {item} ссылается на себя")
                continue
            value = draft_address(*parsed)
        else:
            matches = store.task_id_matches(conn, item)
            if not matches:
                unknown.append(item)
                continue
            if len(matches) > 1:
                reasons.append(f"{flag}: префикс {item} неоднозначен — "
                               f"{', '.join(sorted(matches))}")
                continue
            value = matches[0]
        if value not in resolved:
            resolved.append(value)
    if unknown:
        reasons.insert(0, f"{flag}: не задача БД и не черновик: "
                          f"{', '.join(unknown)}")
    return merge_after.column(resolved), reasons


def _list_fields(conn, values: dict, command: str,
                 own: tuple[str, int] | None) -> dict:
    """Поля перечней черновика из флагов; негодный элемент — отказ
    перечнем всех негодных элементов обоих флагов."""
    fields, reasons = {}, []
    for flag, column in (("--start-after", "start_after"),
                         ("--after", "merge_after")):
        if flag in values:
            fields[column], found = _list_value(conn, values[flag], flag, own)
            reasons += found
    if reasons:
        outcome = "заведён" if command == "add" else "изменён"
        sys.exit("\n".join(f"epic draft {command}: {r}" for r in reasons)
                 + f"\nepic draft {command}: черновик не {outcome}")
    return fields


_DRAFT_FLAGS = ("--tz", "--start-after", "--after", "--budget")


def cmd_draft_add(args: list) -> None:
    positional, values = _flag_values(args, _DRAFT_FLAGS, "draft add")
    if len(positional) != 1 or "--tz" not in values:
        sys.exit(f"epic draft add: нужны id эпика и --tz\n{USAGE}")
    epic_id = positional[0]
    tz, title = _read_tz(values["--tz"], "add")
    frame = (_frame_value(values["--budget"], "add")
             if "--budget" in values else None)
    conn = store.db()
    epic = _existing(conn, epic_id)
    closed = f"epic draft add: эпик {epic_id} закрыт — черновик не заведён"
    if epic["state"] != "open":
        sys.exit(closed)
    lists = _list_fields(conn, values, "add", None)
    made = {}

    def body():
        if store.get_epic(conn, epic_id)["state"] != "open":
            return closed
        number = store.insert_draft(conn, epic_id, title, tz, frame,
                                    lists.get("start_after"),
                                    lists.get("merge_after"))
        made["address"] = draft_address(epic_id, number)
        store.journal(conn, epic_id, "operator", DRAFT_ADD_ACTION,
                      f"{made['address']} «{title}»; рамка: "
                      f"{_frame_text(frame)}", target=epic["project"])

    _transaction(conn, body)
    print(f"[{epic_id}] черновик {made['address']} «{title}» заведён")
    _write_ref(conn, epic_id)


def cmd_draft_edit(args: list) -> None:
    positional, values = _flag_values(args, _DRAFT_FLAGS, "draft edit")
    if len(positional) != 1 or not values:
        sys.exit(f"epic draft edit: нужны адрес черновика и хотя бы один из "
                 f"--tz, --start-after, --after, --budget\n{USAGE}")
    conn = store.db()
    draft = _draft_or_exit(conn, positional[0], "edit")
    refusal = _state_refusal(draft, "edit")
    if refusal is not None:
        sys.exit(refusal)
    key = (draft["epic_id"], draft["number"])
    address = draft_address(*key)
    fields = {}
    if "--tz" in values:
        fields["tz"], fields["title"] = _read_tz(values["--tz"], "edit")
    if "--budget" in values:
        fields["budget_usd"] = _frame_value(values["--budget"], "edit")
    fields.update(_list_fields(conn, values, "edit", key))
    project = store.get_epic(conn, key[0])["project"]

    def body():
        refusal = _state_refusal(store.get_draft(conn, *key), "edit")
        if refusal is not None:
            return refusal
        store.update_draft(conn, *key, **fields)
        store.journal(conn, key[0], "operator", DRAFT_EDIT_ACTION,
                      f"{address}: {', '.join(fields)}", target=project)

    _transaction(conn, body)
    print(f"[{key[0]}] черновик {address} изменён: {', '.join(fields)}")
    _write_ref(conn, key[0])


def cmd_draft_drop(args: list) -> None:
    if len(args) != 1:
        sys.exit(f"epic draft drop: нужен адрес черновика\n{USAGE}")
    conn = store.db()
    draft = _draft_or_exit(conn, args[0], "drop")
    key = (draft["epic_id"], draft["number"])
    project = store.get_epic(conn, key[0])["project"]

    def body():
        current = store.get_draft(conn, *key)
        refusal = _state_refusal(current, "drop")
        if refusal is not None:
            return refusal
        store.update_draft(conn, *key, state=DROPPED)
        store.journal(conn, key[0], "operator", DRAFT_DROP_ACTION,
                      _draft_label(current), target=project)

    _transaction(conn, body)
    print(f"[{key[0]}] черновик {draft_address(*key)} отброшен")
    _write_ref(conn, key[0])


def _resolved_list(conn, value) -> tuple[list[str], list[str]]:
    """(id задач, незаведённые черновики) перечня черновика: адрес
    черновика разрешается в id его задачи-результата (требования 6-7)."""
    ids, pending = [], []
    for item in merge_after.stored(value):
        parsed = parse_address(item)
        if parsed is None:
            task_id = item
        else:
            ref = store.get_draft(conn, *parsed)
            if ref is None:
                pending.append(f"{item} (черновика нет)")
                continue
            if ref["state"] != PROMOTED or not ref["task_id"]:
                pending.append(f"{_draft_label(ref)} ({ref['state']})")
                continue
            task_id = ref["task_id"]
        if task_id not in ids:
            ids.append(task_id)
    return ids, pending


def cmd_draft_promote(args: list) -> None:
    """Задача из черновика путём `new` (требования 6-7): незаведённый
    черновик перечня или отказ любой проверки `new` — задачи нет, черновик
    остаётся `draft`."""
    if len(args) != 1:
        sys.exit(f"epic draft promote: нужен адрес черновика\n{USAGE}")
    conn = store.db()
    draft = _draft_or_exit(conn, args[0], "promote")
    refusal = _state_refusal(draft, "promote")
    if refusal is not None:
        sys.exit(refusal)
    key = (draft["epic_id"], draft["number"])
    address = draft_address(*key)
    start_ids, start_pending = _resolved_list(conn, draft["start_after"])
    merge_ids, merge_pending = _resolved_list(conn, draft["merge_after"])
    pending = list(dict.fromkeys(start_pending + merge_pending))
    if pending:
        sys.exit(f"epic draft promote: черновик {address} не переведён — "
                 f"черновики его перечней ещё не задачи: {', '.join(pending)}; "
                 f"переведи их первыми")
    epic = store.get_epic(conn, key[0])
    from . import catalog  # отложенно: `catalog` импортирует этот модуль
    task_id = catalog.cmd_new(
        draft["title"], f"черновика {address}", target=epic["project"],
        epic_id=epic["id"], after=",".join(merge_ids) or None,
        start_after=",".join(start_ids) or None, tz_text=draft["tz"])
    if draft["budget_usd"] is not None:
        budget.apply_operator_frame(conn, task_id, draft["budget_usd"],
                                    budget.DRAFT_FRAME_ACTION,
                                    f"рамка черновика {address}")

    def body():
        refusal = _state_refusal(store.get_draft(conn, *key), "promote")
        if refusal is not None:
            return (f"{refusal}; задача {task_id} уже заведена — черновик "
                    f"перевела параллельная команда")
        store.update_draft(conn, *key, state=PROMOTED, task_id=task_id)
        store.journal(conn, key[0], "operator", DRAFT_PROMOTE_ACTION,
                      f"{_draft_label(draft)} → {task_id}",
                      target=epic["project"])

    _transaction(conn, body)
    print(f"[{key[0]}] черновик {address} переведён в задачу {task_id}")
    _write_ref(conn, key[0])


def cmd_draft(args: list) -> None:
    commands = {"add": cmd_draft_add, "edit": cmd_draft_edit,
                "drop": cmd_draft_drop, "promote": cmd_draft_promote}
    if not args or args[0] not in commands:
        sys.exit(f"epic draft: нужна подкоманда add|edit|drop|promote\n{USAGE}")
    commands[args[0]](args[1:])


# ===== Решения эпика (требование 9) =====


def _decision_binding(conn, epic_id: str, target: str | None) -> tuple:
    """(for_kind, for_ref) решения по значению `--for`; негодное — отказ."""
    if target is None:
        return FOR_EPIC, None
    if target == ENVELOPE_WORD:
        return FOR_ENVELOPE, None
    parsed = parse_address(target)
    if parsed is not None:
        if parsed[0] != epic_id or store.get_draft(conn, *parsed) is None:
            sys.exit(f"epic decision: черновика {target} в эпике {epic_id} "
                     f"нет — решение не записано")
        return FOR_DRAFT, draft_address(*parsed)
    matches = store.task_id_matches(conn, target)
    if len(matches) > 1:
        sys.exit(f"epic decision: префикс {target} неоднозначен — "
                 f"{', '.join(sorted(matches))}; решение не записано")
    if not matches:
        sys.exit(f"epic decision: --for {target} — не черновик, не задача БД и "
                 f"не {ENVELOPE_WORD}; решение не записано")
    return FOR_TASK, matches[0]


def _binding_text(kind: str, ref: str | None) -> str:
    if kind == FOR_EPIC:
        return "эпик целиком"
    if kind == FOR_ENVELOPE:
        return "конверт"
    if kind == FOR_DRAFT:
        return f"черновик {ref}"
    return f"задача {ref}"


def cmd_decision(args: list) -> None:
    """Решение Оператора по эпику — текст ровно как передан аргументом."""
    positional, values = _flag_values(args, ("--for",), "decision")
    if len(positional) != 2:
        sys.exit(f"epic decision: нужны id эпика и текст решения\n{USAGE}")
    epic_id, text = positional
    if not text.strip():
        sys.exit("epic decision: текст решения пуст — решение не записано")
    conn = store.db()
    epic = _existing(conn, epic_id)
    kind, ref = _decision_binding(conn, epic_id, values.get("--for"))
    made = {}

    def body():
        made["n"] = store.insert_decision(conn, epic_id, text, kind, ref)
        store.journal(conn, epic_id, "operator", DECISION_ACTION,
                      f"№{made['n']} ({_binding_text(kind, ref)}): {text}",
                      target=epic["project"])

    _transaction(conn, body)
    print(f"[{epic_id}] решение №{made['n']} записано "
          f"({_binding_text(kind, ref)})")
    _write_ref(conn, epic_id)


# ===== Копия эпика в ссылке (требования 10-13, 16) =====

_DATA_PREFIX = "<!-- artel-epic-{kind}: "
_DATA_SUFFIX = " -->"


def _data_line(kind: str, data) -> str:
    """Первая строка файла ссылки — JSON строк БД одной строкой; `>`
    экранируется, чтобы текст не закрыл комментарий раньше времени."""
    payload = json.dumps(data, ensure_ascii=False).replace(">", "\\u003e")
    return f"{_DATA_PREFIX.format(kind=kind)}{payload}{_DATA_SUFFIX}"


def _data_of(text: str | None, kind: str):
    """Данные первой строки файла ссылки; `None` — строки нет или она не
    разобрана."""
    if not text:
        return None
    first = text.split("\n", 1)[0]
    prefix = _DATA_PREFIX.format(kind=kind)
    if not (first.startswith(prefix) and first.endswith(_DATA_SUFFIX)):
        return None
    try:
        return json.loads(first[len(prefix):-len(_DATA_SUFFIX)])
    except ValueError:
        return None


def _frame_text(frame) -> str:
    return f"${frame:.2f}" if frame is not None else "без рамки"


def _cell(value) -> str:
    return str(value if value is not None else "—").replace("|", "\\|")


def _dash(value) -> str:
    return str(value) if value is not None else "—"


def _epic_md(conn, epic) -> str:
    tasks = store.epic_tasks(conn, epic["id"])
    lines = [_data_line("row", dict(epic)),
             f"# Эпик {epic['id']}: {epic['title']}", "",
             f"- Проект: {epic['project']}",
             f"- Состояние: {epic['state']}",
             f"- Цель: {epic['goal']}",
             f"- Конверт: {_envelope_text(epic['envelope_usd'])}",
             f"- Итог: {_dash(epic['outcome'])}",
             f"- Заведён: {epic['created_at']}",
             f"- Закрыт: {_dash(epic['closed_at'])}", "", "## Задачи", ""]
    if tasks:
        lines += ["| задача | название | состояние | closed_as |",
                  "|---|---|---|---|"]
        lines += [f"| {t['id']} | {_cell(t['title'])} | {t['state']} | "
                  f"{_cell(t['closed_as'])} |" for t in tasks]
    else:
        lines.append("задач нет")
    return "\n".join(lines) + "\n"


def _draft_md(draft) -> str:
    """Карточка черновика; текст ТЗ — дословно, последним."""
    address = draft_address(draft["epic_id"], draft["number"])
    lines = [_data_line("draft", dict(draft)),
             f"# Черновик {address}: {draft['title']}", "",
             f"- Состояние: {draft['state']}",
             f"- Рамка: {_frame_text(draft['budget_usd'])}",
             f"- start_after: {_dash(draft['start_after'])}",
             f"- merge_after: {_dash(draft['merge_after'])}",
             f"- Задача-результат: {_dash(draft['task_id'])}", "", "## ТЗ", ""]
    return "\n".join(lines) + "\n" + draft["tz"]


def _decisions_md(epic_id: str, decisions: list) -> str:
    lines = [_data_line("decisions", [dict(d) for d in decisions]),
             f"# Решения эпика {epic_id}", ""]
    if not decisions:
        lines.append("решений нет")
    for d in decisions:
        lines += [f"## {d['number']}. {d['created_at']} — "
                  f"{_binding_text(d['for_kind'], d['for_ref'])}", "",
                  d["text"], ""]
    return "\n".join(lines) + "\n"


def _ref_dir(epic_id: str) -> str:
    return f"epics/{epic_id}"


def _ref_name(epic_id: str) -> str:
    return artifact_branch.branch_name(artifact_branch.epic_ref_key(epic_id))


def ref_files(conn, epic) -> dict:
    """{путь: текст} дерева ссылки по БД в порядке `epic export`:
    `EPIC.md`, `drafts/<n>.md` по возрастанию `<n>`, `DECISIONS.md`."""
    base = _ref_dir(epic["id"])
    files = {f"{base}/EPIC.md": _epic_md(conn, epic)}
    for draft in store.epic_drafts(conn, epic["id"]):
        files[f"{base}/drafts/{draft['number']}.md"] = _draft_md(draft)
    files[f"{base}/DECISIONS.md"] = _decisions_md(
        epic["id"], store.epic_decisions(conn, epic["id"]))
    return files


def _write_ref(conn, epic_id: str) -> None:
    """Ссылка `refs/artifacts/epic-<id>` — состояние БД после команды,
    коммит поверх головы (требования 10-11). Неудача записи изменение БД
    не откатывает: предупреждение и запись журнала эпика, ссылку догонит
    следующая команда, меняющая эпик."""
    epic = store.get_epic(conn, epic_id)
    project = epic["project"]
    repo = artifact_branch.repo_for_target(project)
    no_clone = repo == artifact_branch._NO_REPO
    if not no_clone and artifact_branch.commit_files(
            artifact_branch.epic_ref_key(epic_id), ref_files(conn, epic),
            f"{epic_id}: копия эпика", target=project):
        return
    why = f"клона проекта {project} нет" if no_clone else "git не ответил"
    ref = _ref_name(epic_id)
    print(f"[{epic_id}] ВНИМАНИЕ: ссылка {ref} не записана — {why}; "
          f"изменение БД сохранено, ссылку запишет следующая команда epic …, "
          f"меняющая эпик")
    store.journal(conn, epic_id, "orchestrator", REF_WRITE_FAILED_ACTION,
                  f"{ref}: {why}", target=project)


def _draft_file_number(rel: str) -> int | None:
    name = rel.rsplit("/", 1)[-1]
    stem = name[:-len(".md")] if name.endswith(".md") else ""
    return int(stem) if stem.isdigit() else None


def _read_ref(repo, epic_id: str) -> dict | None:
    """{путь: текст} дерева ссылки эпика в порядке `ref_files`; `None` —
    ссылки нет или git не ответил."""
    head = gitcmd.branch_head_sha(_ref_name(epic_id), repo=repo)
    if not head:
        return None
    base = _ref_dir(epic_id)
    paths = gitcmd.ls_tree_files(head, base, repo=repo)
    if paths is None:
        return None
    drafts = sorted((_draft_file_number(rel), rel) for rel in paths
                    if rel.startswith(f"{base}/drafts/")
                    and _draft_file_number(rel) is not None)
    ordered = ([f"{base}/EPIC.md"] + [rel for _n, rel in drafts]
               + [f"{base}/DECISIONS.md"])
    files = {}
    for rel in ordered:
        if rel not in paths:
            continue
        text, _ = gitcmd.show(head, rel, repo=repo)
        if text is None:
            return None
        files[rel] = text
    return files


def cmd_export(args: list) -> None:
    """Только чтение: файлы ссылки эпика дословно и по порядку
    (требование 13). Ссылки нет — тот же Markdown по БД, с
    предупреждением."""
    if len(args) != 1:
        sys.exit(f"epic export: нужен id эпика\n{USAGE}")
    epic_id = args[0]
    conn = store.db()
    epic = _existing(conn, epic_id)
    repo = artifact_branch.repo_for_target(epic["project"])
    files = (_read_ref(repo, epic_id)
             if repo != artifact_branch._NO_REPO else None)
    if not files:
        print(f"[{epic_id}] ВНИМАНИЕ: ссылка {_ref_name(epic_id)} не "
              f"прочитана — вывод собран по БД", file=sys.stderr)
        files = ref_files(conn, epic)
    for text in files.values():
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _ref_rows(files: dict, epic_id: str) -> dict:
    """{таблица: [строка]} из строк данных файлов ссылки; неразобранный
    файл — отказ."""
    base = _ref_dir(epic_id)
    rows = {table: [] for table in store.EPIC_ROW_KEYS}
    for rel, text in files.items():
        if rel == f"{base}/EPIC.md":
            kind, table = "row", "epics"
        elif rel == f"{base}/DECISIONS.md":
            kind, table = "decisions", "epic_decisions"
        else:
            kind, table = "draft", "epic_drafts"
        data = _data_of(text, kind)
        if data is None:
            sys.exit(f"epic restore: {rel} — строка данных не разобрана, БД "
                     f"не изменена")
        rows[table] += data if isinstance(data, list) else [data]
    if [r.get("id") for r in rows["epics"]] != [epic_id]:
        sys.exit(f"epic restore: ссылка не несёт строку эпика {epic_id} — БД "
                 f"не изменена")
    return rows


def _db_rows(conn, table: str, epic_id: str) -> list:
    if table == "epics":
        epic = store.get_epic(conn, epic_id)
        return [epic] if epic is not None else []
    if table == "epic_drafts":
        return store.epic_drafts(conn, epic_id)
    return store.epic_decisions(conn, epic_id)


def _key_text(table: str, row) -> str:
    if table == "epics":
        return str(row["id"])
    if table == "epic_drafts":
        return draft_address(row["epic_id"], row["number"])
    return f"{row['epic_id']} №{row['number']}"


def _restore_plan(conn, source: dict, epic_id: str) -> tuple[list, list]:
    """(недостающие строки [(таблица, строка)], расхождения) БД со
    ссылкой: строка сверяется по ключу таблицы и по каждому полю."""
    missing, diffs = [], []
    for table, keys in store.EPIC_ROW_KEYS.items():
        columns = store.table_columns(conn, table)
        present = {tuple(r[k] for k in keys): r
                   for r in _db_rows(conn, table, epic_id)}
        seen = set()
        for row in source[table]:
            unknown = sorted(set(row) - columns)
            if unknown:
                diffs.append(f"{table} {_key_text(table, row)}: полей "
                             f"{', '.join(unknown)} нет в схеме БД")
                continue
            key = tuple(row.get(k) for k in keys)
            seen.add(key)
            current = present.get(key)
            if current is None:
                missing.append((table, row))
                continue
            diffs += [f"{table} {_key_text(table, row)} поле {column}: в БД "
                      f"{current[column]!r}, в ссылке {value!r}"
                      for column, value in row.items()
                      if current[column] != value]
        diffs += [f"{table} {_key_text(table, row)}: строка есть в БД, в "
                  f"ссылке её нет" for key, row in present.items()
                  if key not in seen]
    return missing, diffs


def cmd_restore(args: list) -> None:
    """Строки `epics`, `epic_drafts`, `epic_decisions` эпика из его ссылки
    (требование 16): недостающие воссоздаются как есть, совпадающие не
    трогаются; любое расхождение — отказ перечнем, БД не меняется."""
    if len(args) != 2:
        sys.exit(f"epic restore: нужны проект и id эпика\n{USAGE}")
    project, epic_id = args
    ref = _ref_name(epic_id)
    repo = artifact_branch.repo_for_target(project)
    if repo == artifact_branch._NO_REPO:
        sys.exit(f"epic restore: клона проекта {project} нет — ссылку {ref} "
                 f"читать негде")
    files = _read_ref(repo, epic_id)
    if not files:
        sys.exit(f"epic restore: ссылки {ref} нет в клоне проекта {project} "
                 f"(из origin её приносит artel.py docs --fetch-all)")
    source = _ref_rows(files, epic_id)
    source_project = source["epics"][0].get("project")
    if source_project != project:
        sys.exit(f"epic restore: ссылка {ref} несёт эпик проекта "
                 f"{source_project}, а не {project} — БД не изменена")
    conn = store.db()
    missing, diffs = _restore_plan(conn, source, epic_id)
    if diffs:
        sys.exit(f"epic restore: БД расходится со ссылкой {ref} — БД не "
                 f"изменена:\n" + "\n".join(f"  {d}" for d in diffs))
    if not missing:
        print(f"[{epic_id}] строки эпика совпадают со ссылкой {ref} — БД не "
              f"изменена")
        return
    counts = {}
    for table, _row in missing:
        counts[table] = counts.get(table, 0) + 1
    summary = ", ".join(f"{table} {n}" for table, n in counts.items())

    def body():
        for table, row in missing:
            store.insert_epic_row(conn, table, row)
        store.journal(conn, epic_id, "operator", RESTORE_ACTION,
                      f"{ref}: {summary}", target=project)

    _transaction(conn, body)
    print(f"[{epic_id}] эпик восстановлен из {ref}: {summary}")


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


def envelope_warning_text(item: dict) -> str:
    """Предупреждение 80 % конверта элемента эпика модели доски (SPEC
    01M5TBCY7WTN121S136XP2C6SR, требования 4, 19) — общее для `status` и
    `epic show`; при исчерпанном конверте называет и отказ первого шага."""
    if item["spent_usd"] >= item["envelope_usd"]:
        return (f"конверт исчерпан — первый шаг роли новых задач эпика не "
                f"начнётся; подними: artel.py epic envelope {item['id']} N")
    return (f"потрачено не ниже {int(budget.EPIC_ALERT_RATIO * 100)} % "
            f"конверта")


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
    if item.get("envelope_warning"):
        lines.append(f"ВНИМАНИЕ: {envelope_warning_text(item)}")
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
    """Подкоманда — в одной области отложенной отправки (SPEC
    01M5TBFCVFNN95BHH0E9C6KBKB, требование 12): ссылка эпика уходит в
    `origin` при выходе, один раз на команду, и без lease задачи."""
    commands = {"new": cmd_new, "show": cmd_show, "edit": cmd_edit,
                "close": cmd_close, "add": cmd_add, "remove": cmd_remove,
                "envelope": cmd_envelope, "start-after": cmd_start_after,
                "draft": cmd_draft, "decision": cmd_decision,
                "export": cmd_export, "restore": cmd_restore,
                "parallel": cmd_parallel, "stop": cmd_stop, "retry": cmd_retry}
    if not rest or rest[0] not in commands:
        sys.exit(f"epic: нужна подкоманда\n{USAGE}")
    with artifact_branch.deferred_sends():
        commands[rest[0]](rest[1:])
