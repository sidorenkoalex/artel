"""Команда `watch`: дозор событий журнала для сессии Оператора (SPEC
01M1VBEKRN0GA029J98S0K2DAQ).

Заменяет внерепозиторные сценарии сессии (`watch_tasks.py`,
`watch_spec_gate.py`, docs/operator-session.md, «Возобновление сессии»,
п.4): то же чтение БД, что и у остального CLI (`store.db()`), без
lease, без записи в `steps`/`alerts`, без мутации `tasks.state` —
только печать потока новых записей журнала выбранных задач, начиная с
момента запуска. Режим `--observation` дополнительно записывает связь
наблюдения в том же цикле опроса.

Монолит — один модуль на разбор argv, выборку задач, опрос и печать
(решение Оператора 06.09, SPEC «Оценка объёма»): резать нечего — ни
поток без фильтров, ни фильтры без потока не дают наблюдаемого
поведения ТЗ по отдельности. `cmd_watch(argv)` — единственная точка
входа, разбирает сырой argv сама, тем же приёмом ручного разбора, что
и остальные команды `artel.py` (`_tz_arg`/`_k_arg`/`_reason_arg`).
"""
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from . import agent_log, ci, config, gitcmd, session, spend, store, workspace
from .advance_gates import refusal_classes
from .providers.claude import TOOL_CALL_LINE_PREFIX

_SELECTOR_FLAGS = ("--tasks", "--mine", "--all", "--observation")
_EVENT_CLASSES = {"transitions", "refusals", "gates", "steps", "budget",
                  "alerts", "stops", "ci", "pytest"}
_DEFAULT_EVENTS = ("transitions", "refusals", "gates", "steps", "stops", "ci",
                   "pytest")
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

# Отказы предварительного advance подкласса «роль ещё не закончила» (SPEC
# 01M290PP4KBTG1KYS1PWKQJH6T, требование 5) — из единого перечня классов
# отказов (SPEC 01M446WEVJXARR5CDED8RE9CCR, требование 1). Артефакт роли
# просто ещё не готов — не событие, которое Оператору нужно видеть в
# дозоре наравне с настоящими отказами.
_PRE_ADVANCE_REFUSAL_ACTIONS = refusal_classes.ROLE_NOT_FINISHED_REFUSAL_ACTIONS

# Ход живого шага роли (SPEC 01M446X1B7FB8JDMYFP5APWTVE, требования 3-7).
# Живой шаг — последняя «agent run started» задачи без более поздней
# записи завершения; строки хода печатает сам дозор actor'ом `watch`, в
# журнал они не пишутся.
_STEP_START_ACTION = "agent run started"
_STEP_END_ACTIONS = ("agent run finished", "agent run TIMEOUT",
                     "agent run FAILED")
_WATCH_ACTOR = "watch"
_PROGRESS_ACTION = "ход шага"
_WARNING_ACTION = "предупреждение"
_TS_FORMAT = "%Y-%m-%d %H:%M:%SZ"
# Путь лога в detail «agent run started» (`runner.py`): «…, лог: <path>,
# промпт: <path>, …».
_STEP_LOG_RE = re.compile(r"лог: (.+?)(?:, промпт: |$)")
_LAST_CALLS = 3
_CALL_CHARS = 40
_PROGRESS_LINE_CHARS = 240
# Хвост лога шага, в котором ищутся последние вызовы инструментов: лог
# 45-минутного шага бывает в мегабайты, а нужны три последние строки.
_LOG_TAIL_BYTES = 64 * 1024
_LINES_WINDOW_SEC = 3600


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
            "--mine, --all либо --observation <ID>")

    events_raw = _flag_value(argv, "--events")
    events = _parse_event_set(events_raw, "--events") if events_raw is not None \
        else set(_DEFAULT_EVENTS)

    interval_raw = _flag_value(argv, "--interval")
    if interval_raw is None:
        interval = float(config.OBSERVATION_HEARTBEAT_PERIOD)
    else:
        try:
            interval = float(interval_raw)
        except ValueError:
            sys.exit(f"--interval требует число, получено {interval_raw!r}.")
    if interval <= 0 or ("--observation" in argv and
                         interval > config.OBSERVATION_HEARTBEAT_PERIOD):
        sys.exit("watch: interval должен быть положительным и не больше периода heartbeat")

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
        "observation": _flag_value(argv, "--observation"),
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
    if opts["observation"] is not None:
        return store.observation_tasks(conn, opts["observation"])
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
    if "pytest" in events and action == agent_log.PYTEST_RUN_ACTION:
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
                exit_on: set | None, budget=None) -> bool:
    """Печатает новые строки `steps` этой задачи; `True` — среди них была
    строка класса из `exit_on` (SPEC 01M290PP4KBTG1KYS1PWKQJH6T, требование
    4) и вызывающий обязан остановиться НЕМЕДЛЕННО, той же итерацией, не
    дожидаясь `time.sleep(interval)` (AC-7).

    Отбор новых записей — фильтром `id > known` в SQL (SPEC
    01M3GKJFN90ATK2KECNDZXPPP6, требование 4): дозор опрашивает БД каждые
    `--interval` секунд, и прежнее чтение всей истории задачи ради её
    хвоста было тем же дефектом CR-2026-09-26-2, что и в `report`.

    `budget` — граница строк хода шага (`_LineBudget`, SPEC
    01M446X1B7FB8JDMYFP5APWTVE, требование 7): строка класса `pytest`
    сверх неё не печатается и `exit_on` не срабатывает — её как будто не
    было в потоке; журнал не меняется."""
    new_rows = store.task_steps_since(conn, task_id, known_step_id[task_id])
    if not new_rows:
        return False
    known_step_id[task_id] = new_rows[-1]["id"]
    for row in new_rows:
        if _matches_class(row["action"], row["detail"], events):
            if (budget is not None
                    and row["action"] == agent_log.PYTEST_RUN_ACTION
                    and not budget.take(task_id)):
                continue
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


class _LineBudget:
    """Граница строк хода шага на задачу за скользящие 60 минут (SPEC
    01M446X1B7FB8JDMYFP5APWTVE, требование 7): класс `pytest`, сводки и
    предупреждения — один счётчик, иначе граница не держала бы общий
    поток строк задачи."""

    def __init__(self):
        self.printed: dict = {}

    def take(self, task_id: str) -> bool:
        """`True` — строку печатать, она учтена; `False` — граница
        исчерпана."""
        now = time.monotonic()
        stamps = self.printed.setdefault(task_id, deque())
        while stamps and now - stamps[0] >= _LINES_WINDOW_SEC:
            stamps.popleft()
        if len(stamps) >= config.WATCH_PROGRESS_LINES_PER_HOUR:
            return False
        stamps.append(now)
        return True


class _LiveStep:
    """Что дозор помнит о живом шаге задачи между итерациями опроса:
    выданные отметки сводки и виды предупреждений — по одному разу на
    шаг, поэтому состояние заводится заново на каждую новую «agent run
    started»."""

    def __init__(self, row):
        self.step_id = row["id"]
        self.role = row["actor"]
        self.started = datetime.strptime(row["ts"], _TS_FORMAT).replace(
            tzinfo=timezone.utc)
        match = _STEP_LOG_RE.search(row["detail"] or "")
        self.log_path = Path(match.group(1).strip()) if match else None
        self.last_mark = 0
        self.warned: set = set()
        self.cost_log_size = None

    def elapsed_sec(self) -> float:
        return (datetime.now(timezone.utc) - self.started).total_seconds()


def _live_step_row(conn, task_id: str):
    """Запись «agent run started» живого шага задачи; `None` — живого
    шага нет (SPEC 01M446X1B7FB8JDMYFP5APWTVE, требование 4)."""
    started = store.last_task_step_of(conn, task_id, (_STEP_START_ACTION,))
    if started is None:
        return None
    ended = store.last_task_step_of(conn, task_id, _STEP_END_ACTIONS)
    if ended is not None and ended["id"] > started["id"]:
        return None
    return started


def _shorten(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit - 1] + "…"


def _last_tool_calls(log_path: Path | None) -> list:
    """Последние вызовы инструментов из хвоста лога шага — строки
    «· <Tool> <аргумент>» отрисовки провайдера, каждая не длиннее
    `_CALL_CHARS`; лог не прочитан — пустой список."""
    if log_path is None:
        return []
    try:
        with open(log_path, "rb") as log:
            log.seek(0, 2)
            size = log.tell()
            log.seek(max(0, size - _LOG_TAIL_BYTES))
            tail = log.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    calls = [line[len(TOOL_CALL_LINE_PREFIX):] for line in tail.splitlines()
             if line.startswith(TOOL_CALL_LINE_PREFIX)]
    return [_shorten(call, _CALL_CHARS) for call in calls[-_LAST_CALLS:]]


def _changed_files(task_id: str) -> str:
    """Число изменённых файлов рабочей копии задачи строкой; «?» — копии
    нет или git не ответил."""
    path = workspace.path(task_id)
    if not path.is_dir():
        return "?"
    res = gitcmd.in_repo(path, "status", "--porcelain",
                         "--untracked-files=all")
    if res is None or res.returncode != 0:
        return "?"
    return str(len([line for line in res.stdout.splitlines() if line.strip()]))


def _has_commit_since(task_row, started: datetime) -> bool | None:
    """Есть ли у ветки задачи коммит новее начала шага; `None` — git не
    ответил (тогда и предупреждать не о чем: «не знаю» не «нет»)."""
    branch = task_row["branch"]
    if not branch:
        return None
    res = gitcmd.in_repo(workspace.task_repo(task_row["id"]), "log", "-1",
                         "--format=%ct", f"--since=@{int(started.timestamp())}",
                         branch, "--")
    if res is None or res.returncode != 0:
        return None
    return bool(res.stdout.strip())


def _step_provider(task_row, role: str):
    """Провайдер шага — тот же, что выбрал раннер (набор задачи, иначе
    роль): лог шага Codex разбирается парсером Codex. Провайдер не
    разрешился — `None`, провайдер по умолчанию: дозор не останавливается
    из-за карты исполнителей, её отказ называет сам шаг."""
    from . import runner  # runner тянет за собой FSM; нужен лишь здесь
    try:
        return runner._step_provider(task_row, role)
    except Exception:  # noqa: BLE001 — деградация к разбору по умолчанию
        return None


def _step_cost_usd(step: _LiveStep, task_row) -> float | None:
    """Стоимость шага по usage, уже лёгшему в лог шага; `None` — usage не
    видели или тариф роли не разрешился."""
    if step.log_path is None:
        return None
    tokens, saw = spend.partial_tokens_from_log(
        step.log_path, _step_provider(task_row, step.role))
    if not saw:
        return None
    return spend.partial_cost_usd(step.role, tokens, task_row)


def _emit_progress_line(task_id: str, action: str, detail: str,
                        budget: _LineBudget) -> None:
    if not budget.take(task_id):
        return
    ts = store.now()
    prefix = f"{ts}  {task_id}  {_WATCH_ACTOR}  {action}  | "
    room = _PROGRESS_LINE_CHARS - len(prefix)
    _print_line(ts, task_id, _WATCH_ACTOR, action, _shorten(detail, room))


def _emit_progress(conn, task_row, live_steps: dict,
                   budget: _LineBudget) -> None:
    """Сводка по таймеру и ранние предупреждения живого шага задачи (SPEC
    01M446X1B7FB8JDMYFP5APWTVE, требования 3-7). Отметка k·N, пропущенная
    до запуска дозора, задним числом не печатается: на первой итерации
    выдаётся только текущая. Строка, не напечатанная из-за границы,
    считается выданной."""
    task_id = task_row["id"]
    row = _live_step_row(conn, task_id)
    if row is None:
        live_steps.pop(task_id, None)
        return
    step = live_steps.get(task_id)
    if step is None or step.step_id != row["id"]:
        step = live_steps[task_id] = _LiveStep(row)
    elapsed = step.elapsed_sec()

    mark = int(elapsed // (config.WATCH_PROGRESS_PERIOD_MIN * 60))
    if mark >= 1 and mark > step.last_mark:
        step.last_mark = mark
        calls = _last_tool_calls(step.log_path)
        detail = (f"{int(elapsed // 60)}/{config.AGENT_TIMEOUT_SEC // 60} мин, "
                  f"изменено файлов: {_changed_files(task_id)}, "
                  f"вызовы: {'; '.join(calls) if calls else '—'}")
        _emit_progress_line(task_id, _PROGRESS_ACTION, detail, budget)

    if ("нет коммитов" not in step.warned
            and elapsed >= config.WATCH_NO_COMMIT_WARN_SEC):
        committed = _has_commit_since(task_row, step.started)
        if committed is not None:
            step.warned.add("нет коммитов")
        if committed is False:
            _emit_progress_line(
                task_id, _WARNING_ACTION,
                f"нет коммитов: шаг идёт {int(elapsed // 60)}/"
                f"{config.AGENT_TIMEOUT_SEC // 60} мин, у ветки "
                f"{task_row['branch']} нет коммитов новее начала шага", budget)

    if "стоимость шага" not in step.warned and step.log_path is not None:
        # Лог перечитывается только когда вырос: между итерациями опроса
        # usage в нём не прибавляется, если не прибавилось строк.
        try:
            size = step.log_path.stat().st_size
        except OSError:
            size = None
        if size is not None and size != step.cost_log_size:
            step.cost_log_size = size
            cost = _step_cost_usd(step, task_row)
            if cost is not None and cost > config.WATCH_STEP_COST_WARN_USD:
                step.warned.add("стоимость шага")
                _emit_progress_line(
                    task_id, _WARNING_ACTION,
                    f"стоимость шага: ${cost:.2f} по usage лога — больше "
                    f"порога ${config.WATCH_STEP_COST_WARN_USD:.2f}", budget)


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
    if opts["observation"] is not None:
        observed = store.observation(conn, opts["observation"])
        if observed is None or observed["state"] != "active":
            sys.exit("watch: наблюдение не найдено или прекращено")
        if observed["session_id"] != session_id:
            sys.exit("watch: наблюдение принадлежит другой сессии")
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
    dynamic = (opts["mine"] or opts["all"] or opts["observation"] is not None) and opts["until"] is None

    exit_on = opts["exit_on"]
    known_step_id: dict = {}
    known_state: dict = {}
    known_alert_id = None
    live_steps: dict = {}
    budget = _LineBudget()

    while True:
        conn = store.db()  # свежее чтение на каждой итерации (AC-8)
        if opts["observation"] is not None:
            if not store.touch_observation(conn, opts["observation"]):
                return
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
                          exit_on, budget):
                return
            _emit_progress(conn, row, live_steps, budget)

        if "alerts" in opts["events"]:
            known_alert_id, stop = _emit_alerts(
                conn, set(selection) | set(known_step_id), known_alert_id,
                exit_on)
            if stop:
                return

        if _should_stop(opts, selection, tasks_by_id):
            return

        time.sleep(opts["interval"])
