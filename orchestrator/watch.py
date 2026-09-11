"""Команда `watch`: дозор событий журнала для сессии Оператора (SPEC
01M1VBEKRN0GA029J98S0K2DAQ).

Заменяет внерепозиторные сценарии сессии (`watch_tasks.py`,
`watch_spec_gate.py`, docs/operator-session.md, «Возобновление сессии»,
п.4): то же чтение БД, что и у остального CLI (`store.db()`), без
lease, без записи в `steps`/`alerts`, без мутации `tasks.state` —
только печать потока новых записей журнала выбранных задач, начиная с
момента запуска.

Монолит — один модуль на разбор argv, выборку задач, опрос и печать
(решение Оператора 06.09, SPEC «Оценка объёма»): резать нечего — ни
поток без фильтров, ни фильтры без потока не дают наблюдаемого
поведения ТЗ по отдельности. `cmd_watch(argv)` — единственная точка
входа, разбирает сырой argv сама, тем же приёмом ручного разбора, что
и остальные команды `artel.py` (`_tz_arg`/`_k_arg`/`_reason_arg`).
"""
import sys
import time

from . import ci, session, store

_SELECTOR_FLAGS = ("--tasks", "--mine", "--all")
_EVENT_CLASSES = {"transitions", "refusals", "gates", "steps", "budget",
                  "alerts", "stops", "ci"}
_DEFAULT_EVENTS = ("transitions", "refusals", "gates", "steps", "stops", "ci")
_GATE_STATES = ("spec_gate", "acceptance", "merge_gate", "escalated")
_GATE_ACTIONS = tuple(f"state -> {state}" for state in _GATE_STATES)
_TERMINAL_STATES = ("done", "killed")

# Действие журнала остановки цикла `auto` (`auto.auto_stop`, `orchestrator/
# auto.py:421`) — любой `actor`, любая причина (SPEC 01M290PP4KBTG1KYS1PWKQJH6T,
# требование 1, AC-2).
_AUTO_STOP_ACTION = "auto остановлен"
# Префикс действия журнала статуса CI ветки — покрывает и
# `fsm.VERIFYING_STATUS_ACTION` ("статус CI ветки (verifying)"), и
# "статус CI ветки (ре-ран)" `fsm_merge_gate.py` (требование 1, AC-3);
# вердикт «не зелёный» решает `ci.verifying_is_red` по тексту detail —
# та же подстрока, которой сам `ci.py` помечает красный исход что в
# `verifying_status`, что в `branch_status`, переиспользуется, а не
# копируется заново.
_CI_STATUS_ACTION_PREFIX = "статус CI ветки"

# Отказы предварительного advance класса «роль ещё не закончила» (SPEC
# 01M290PP4KBTG1KYS1PWKQJH6T, требование 5) — тексты, которые
# `auto._pre_advance_step` журналирует actor'ом "fsm": копия
# `auto.REWORK_REFUSAL_ACTION` и литерала "переход отклонён: дерево не на
# ветке задачи" (`orchestrator/fsm.py`/`orchestrator/fsm_advance.py`), не
# импорт — зона этой задачи не включает `auto.py`/`fsm.py`/`fsm_advance.py`
# (SPEC «Не входит»: отдельная пометка класса отказа в самом журнале —
# задача другой роли), а дозор и так классифицирует события чтением текста
# журнала, не кодом источника. Артефакт роли просто ещё не готов — не
# событие, которое Оператору нужно видеть в дозоре наравне с настоящими
# отказами.
_PRE_ADVANCE_REFUSAL_ACTIONS = (
    "переход отклонён: замечания ревью не отработаны",
    "переход отклонён: дерево не на ветке задачи",
)


def _flag_value(argv: list, flag: str) -> str | None:
    """Значение флага `<flag> <value>` — тем же приёмом, что
    `artel._tz_arg`/`artel._reason_arg`: флаг без значения последним
    аргументом — именованный отказ, не `IndexError`."""
    if flag not in argv:
        return None
    idx = argv.index(flag)
    if idx + 1 >= len(argv):
        sys.exit(f"{flag} требует значение следующим аргументом.")
    return argv[idx + 1]


def _split_csv(value: str) -> list:
    return [item for item in value.split(",") if item]


def _parse_event_set(raw: str, flag: str) -> set:
    """Множество классов из `<flag> a,b,c` — общий разбор/валидация для
    `--events` и `--exit-on` (SPEC 01M290PP4KBTG1KYS1PWKQJH6T, требования
    1/4): неизвестный класс — именованный отказ, перечисляющий ВСЕ
    доступные классы (AC-1), не только сам неизвестный."""
    classes = set(_split_csv(raw))
    unknown = classes - _EVENT_CLASSES
    if unknown:
        sys.exit(f"watch: неизвестные классы событий у {flag}: "
                 f"{', '.join(sorted(unknown))} (доступны: "
                 f"{', '.join(sorted(_EVENT_CLASSES))})")
    return classes


def _parse_args(argv: list) -> dict:
    """Разбор и валидация argv — БЕЗ единого обращения к БД (AC-1):
    счётчик селекторов `--tasks`/`--mine`/`--all` проверяется первым
    действием, до разбора значений остальных флагов."""
    present = [flag for flag in _SELECTOR_FLAGS if flag in argv]
    if len(present) != 1:
        sys.exit(
            "watch: нужен ровно один селектор — --tasks <id>[,<id>...], "
            "--mine либо --all")

    events_raw = _flag_value(argv, "--events")
    events = _parse_event_set(events_raw, "--events") if events_raw is not None \
        else set(_DEFAULT_EVENTS)

    interval_raw = _flag_value(argv, "--interval")
    if interval_raw is None:
        interval = 30.0
    else:
        try:
            interval = float(interval_raw)
        except ValueError:
            sys.exit(f"--interval требует число, получено {interval_raw!r}.")

    exit_on_raw = _flag_value(argv, "--exit-on")
    once = "--once" in argv
    if once and exit_on_raw is not None:
        sys.exit("watch: --once и --exit-on взаимоисключающие — выбери один")
    if once:
        exit_on = set(_DEFAULT_EVENTS)
    elif exit_on_raw is not None:
        exit_on = _parse_event_set(exit_on_raw, "--exit-on")
    else:
        exit_on = None

    tasks_raw = _flag_value(argv, "--tasks")
    return {
        "tasks": _split_csv(tasks_raw) if tasks_raw is not None else None,
        "mine": "--mine" in argv,
        "all": "--all" in argv,
        "events": events,
        "interval": interval,
        "until": _flag_value(argv, "--until"),
        "exit_on": exit_on,
    }


def _owner_session_id(conn, task_id: str) -> str | None:
    """Identity владельца задачи для `--mine` (AC-4): `session_id`
    ПОСЛЕДНЕЙ (по возрастанию id) записи `actor="lease"` (взят/перехвачен)
    этой задачи; такой записи нет ни одной — `session_id` записи
    `created`; нет и её — задача ничья (`None`)."""
    steps = store.task_steps(conn, task_id)
    for row in reversed(steps):
        if row["actor"] == "lease" and row["action"] in (
                "lease взят", "lease перехвачен"):
            return row["session_id"]
    for row in steps:
        if row["action"] == "created":
            return row["session_id"]
    return None


def _select_tasks(conn, opts: dict, session_id: str) -> list:
    if opts["tasks"] is not None:
        return list(opts["tasks"])
    if opts["mine"]:
        return [row["id"] for row in store.all_tasks(conn)
                if _owner_session_id(conn, row["id"]) == session_id]
    return [row["id"] for row in store.all_tasks(conn)
            if row["state"] not in _TERMINAL_STATES]


def _matches_class(action: str, detail: str, events: set) -> bool:
    if "transitions" in events and action.startswith("state -> "):
        return True
    if "gates" in events and action in _GATE_ACTIONS:
        return True
    if ("refusals" in events and action.startswith(store.REFUSAL_ACTION_PREFIX)
            and action not in _PRE_ADVANCE_REFUSAL_ACTIONS):
        return True
    if "steps" in events and action.startswith("agent run"):
        return True
    if "budget" in events and action.startswith("бюджет"):
        return True
    if "stops" in events and action == _AUTO_STOP_ACTION:
        return True
    if ("ci" in events and action.startswith(_CI_STATUS_ACTION_PREFIX)
            and ci.verifying_is_red(detail)):
        return True
    return False


def _print_line(ts: str, task_id: str, actor: str, action: str,
                detail: str) -> None:
    """Строка формата `log` (ts, actor, action, `| detail`) плюс
    идентификатор задачи (AC-2) — общий вид для строк `steps` и `alerts`
    (для алертов `task_id`=`target`, `actor`=`source`, `action`=
    `alert:<kind>`, `detail`=`message`)."""
    line = f"{ts}  {task_id}  {actor}  {action}"
    if detail:
        line += f"  | {detail}"
    print(line, flush=True)


def _emit_steps(conn, task_id: str, events: set, known_step_id: dict,
                exit_on: set | None) -> bool:
    """Печатает новые строки `steps` этой задачи; `True` — среди них была
    строка класса из `exit_on` (SPEC 01M290PP4KBTG1KYS1PWKQJH6T, требование
    4) и вызывающий обязан остановиться НЕМЕДЛЕННО, той же итерацией, не
    дожидаясь `time.sleep(interval)` (AC-7)."""
    steps = store.task_steps(conn, task_id)
    new_rows = [row for row in steps if row["id"] > known_step_id[task_id]]
    if not new_rows:
        return False
    known_step_id[task_id] = new_rows[-1]["id"]
    for row in new_rows:
        if _matches_class(row["action"], row["detail"], events):
            _print_line(row["ts"], task_id, row["actor"], row["action"],
                       row["detail"])
            if exit_on is not None and _matches_class(
                    row["action"], row["detail"], exit_on):
                return True
    return False


def _emit_alerts(conn, known_ids: set, known_alert_id: int,
                 exit_on: set | None) -> tuple:
    """Новые alerts, чей `target` совпадает с id ЛЮБОЙ когда-либо
    наблюдаемой задачи (AC-3, `kind` не фильтруется) — `known_ids`
    несёт объединение текущей выборки и уже известных задач, тем же
    приёмом, что цикл `cmd_watch` уже применяет для `steps`/`STATE`
    (`watch.py:209`): задача, покинувшая динамическую `--mine`/`--all`
    выборку (стала терминальной либо сменила владельца), обязана
    продолжать наблюдаться — иначе её алерт, возникший после выхода из
    выборки, пропадёт из потока навсегда (REVIEW.md R1-F1).

    Возвращает (новый `known_alert_id`, `exit_on` сработал ли — тот же
    смысл, что и у `_emit_steps`). Класс `alerts` не различается
    `_matches_class` (это уже сделал сам вызов — печатается ЛЮБОЙ alert,
    без фильтра по `kind`, см. докстринг выше), поэтому здесь `exit_on`
    сверяется напрямую по имени класса, не через `_matches_class`."""
    rows = store.alerts_since(conn, known_alert_id)
    if not rows:
        return known_alert_id, False
    for row in rows:
        if row["target"] in known_ids:
            _print_line(row["ts"], row["target"], row["source"],
                       f"alert:{row['kind']}", row["message"])
            if exit_on is not None and "alerts" in exit_on:
                return row["id"], True
    return rows[-1]["id"], False


def _should_stop(opts: dict, selection: list, tasks_by_id: dict) -> bool:
    if opts["until"] is not None:
        row = tasks_by_id.get(selection[0])
        return row is not None and row["state"] == opts["until"]
    return all(
        tasks_by_id.get(task_id) is None
        or tasks_by_id[task_id]["state"] in _TERMINAL_STATES
        for task_id in selection)


def _empty_mine_refusal(conn, session_id: str) -> str:
    """Текст отказа пустой выборки `--mine` (SPEC 01M290PP4KBTG1KYS1PWKQJH6T,
    требование 3, AC-6) — «другая identity» это держатели lease ВСЕХ
    нетерминальных задач БД, кроме самой вызывающей сессии и кроме
    ничьих (`_owner_session_id` вернул `None`)."""
    others = set()
    for row in store.all_tasks(conn):
        if row["state"] in _TERMINAL_STATES:
            continue
        owner = _owner_session_id(conn, row["id"])
        if owner is not None and owner != session_id:
            others.add(owner)
    return (f"watch --mine: у сессии {session_id} нет живых задач "
           f"(lease взят другой identity: {', '.join(sorted(others))})")


def cmd_watch(argv: list) -> None:
    opts = _parse_args(argv)
    conn = store.db()
    session_id = session.resolve_session_id(None)
    selection = _select_tasks(conn, opts, session_id)

    if opts["until"] is not None and len(selection) != 1:
        sys.exit(
            "watch: --until требует ровно одну задачу в выборке (сейчас "
            f"{len(selection)}: {', '.join(sorted(selection)) or '—'})")

    if opts["tasks"] is not None:
        # Неизвестный `--tasks` id — именованный отказ, не бесконечный
        # пустой цикл и не молчаливое завершение (SPEC требование 3, AC-6).
        known_ids = {row["id"] for row in store.all_tasks(conn)}
        missing = sorted(t for t in selection if t not in known_ids)
        if missing:
            sys.exit(f"watch --tasks: неизвестный id — {', '.join(missing)}")

    if opts["mine"] and not selection:
        sys.exit(_empty_mine_refusal(conn, session_id))

    # `--until` следит за ОДНОЙ конкретной задачей — динамический
    # пересчёт `--mine`/`--all` (AC-5) здесь не идёт: список из одного
    # id, уже проверенный выше, остаётся тем же самым всю жизнь команды
    # (см. PLAN.md, «Подход», пункт 4).
    dynamic = (opts["mine"] or opts["all"]) and opts["until"] is None

    exit_on = opts["exit_on"]
    known_step_id: dict = {}
    known_state: dict = {}
    known_alert_id = None

    while True:
        conn = store.db()  # свежее чтение на каждой итерации (AC-8)
        if dynamic:
            selection = _select_tasks(conn, opts, session_id)
        tasks_by_id = {row["id"]: row for row in store.all_tasks(conn)}

        if "alerts" in opts["events"] and known_alert_id is None:
            known_alert_id = store.max_alert_id(conn)

        # Объединение с уже известными задачами, не только текущей
        # `selection`: `--all` перестаёт включать задачу, как только она
        # становится терминальной — без объединения её последний переход
        # в `done`/`killed` не попал бы в `STATE=` (AC-7 требует печати
        # смены состояния независимо от `--events`, не «пока задача ещё
        # в выборке»).
        for task_id in sorted(set(selection) | set(known_step_id)):
            row = tasks_by_id.get(task_id)
            if row is None:
                continue
            if task_id not in known_step_id:
                steps = store.task_steps(conn, task_id)
                known_step_id[task_id] = steps[-1]["id"] if steps else 0
                known_state[task_id] = row["state"]
                continue
            if row["state"] != known_state[task_id]:
                known_state[task_id] = row["state"]
                print(f"STATE={row['state']}", flush=True)
            if _emit_steps(conn, task_id, opts["events"], known_step_id,
                          exit_on):
                return

        if "alerts" in opts["events"]:
            known_alert_id, stop = _emit_alerts(
                conn, set(selection) | set(known_step_id), known_alert_id,
                exit_on)
            if stop:
                return

        if _should_stop(opts, selection, tasks_by_id):
            return

        time.sleep(opts["interval"])
