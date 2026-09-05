"""Занятость зоны на старте кода — предусловие перед первым шагом роли
developer, снятие ожидания Оператором, порядок очереди (SPEC
01M1P9QAG65GVF69YJEV0V18D9, требования 1-2, 6-9; часть 2 «Механика зон»,
родитель 01M1NKVPD2A79PQ6K0JVV1B2Q1, часть 1 которого вводит поле `zones`
и `config.COMMON_ZONES`, читаемые здесь).

Занятость — не новое состояние FSM (требование 1, инварианты 1/18/32):
предусловие перед стартом шага, по образцу `budget.budget_block`/
`parallel_limit.refusal`. Диапазон занимающих фаз (`BLOCKING_STATES`) —
`in_dev`…`merge_gate` буквально (SPEC требование 1), не «любая фаза,
кроме done/killed» — задача до `in_dev` (`tests_writing`) или уже закрытая
(`done`) зону не держит.

«Первый шаг» (требование 1, ключевое слово): без пометки — проверка
блокировала бы КАЖДЫЙ последующий запуск `run`/`auto` этой задачи, пока
она остаётся в `in_dev`, включая уже начатую разработку, если конфликт
возник позже первого успешного старта агента — SPEC явно говорит «перед
первым», не «на каждом». Признак «первый шаг уже был» — без новой
колонки, тем же приёмом, что `store.refusal_history`/`brief.
advance_refusal_history` (SPEC T078) уже используют для «истории ТЕКУЩЕГО
визита состояния»: граница — id записи `"state -> in_dev"` в журнале
задачи (её пишет `store.set_state` на каждом переходе), а сам факт
«старт уже был» читается по записи `"agent run started"` роли developer
(её же журналирует `runner.run_agent_once`) после этой границы. Синтетика
песочниц, что заводит задачи прямым `UPDATE tasks` без прохода через
`set_state` (`tests/test_invariants.py::FsmTest.set_state`), не пишет
маркер `"state -> in_dev"` вовсе — граница остаётся `0` (весь журнал
задачи), что для одного непрерывного тестового сценария поведенчески то
же самое: маркеров «уже стартовал»/«снято Оператором» в свежей задаче до
первого вызова всё равно нет.

Оператор может снять ожидание явной командой (требование 6, AC-7) даже
БЕЗ того, чтобы занявшая зону задача куда-то делась — иначе команда была
бы неотличима от естественного снятия (требование 5, AC-6) и не давала бы
никакого recourse (SPEC, «Оценка объёма и деление»). Снятие — тем же
маркерным приёмом: запись `RELEASE_ACTION` после границы визита `in_dev`
считается для этого визита равнозначной «первый шаг уже был» — обе
записи одного семейства «этот визит больше не в режиме ожидания».

Очередь (требования 7-9, AC-8/AC-9) — чистая функция от переданных id, не
от факта блокировки (это уже AC-1..AC-3): порядок по возрастанию
`tasks.updated_at` (естественная отметка approve — докстринг `_sandbox.py`
задачи, раздел «Допущения интерфейса»), если Оператор явно не переставил
её `cmd_zone_reorder` — тогда позиция, записанная им, решает раньше
времени approve (колонка `zone_queue_position`, `NULL` — переставлено не
было).
"""
from . import config, store

# SPEC требование 1: диапазон фаз FSM, в которых занятость зоны другой
# задачи блокирует первый шаг developer этой — `in_dev`…`merge_gate`
# буквально (тот же порядок состояний, что `report.STATE_ORDER`).
BLOCKING_STATES = ("in_dev", "review", "verifying", "acceptance", "merge_gate")

# Actor/action журнала отказа `run`/`auto` по занятости зоны (требования
# 2-3): `auto._run_zone_wait_refusal` ищет это действие буквально, тем же
# приёмом, что `auto._run_paused_refusal` ищет `pause.REFUSAL_ACTION` —
# отличить эту причину остановки цикла от прочих отказов `run`.
REFUSAL_ACTION = "run отклонён: ждёт зоны"

# Маркер операторского снятия ожидания (требование 6, AC-7): текст,
# буквально несущий «осознанный риск» — Оператор должен увидеть в журнале,
# что решение сознательное, а не автоматическое снятие по AC-6.
RELEASE_ACTION = "ждёт зоны — снято Оператором (осознанный риск)"

# Действие, которым `runner.run_agent_once` журналирует старт агента —
# используется здесь только как ЧТЕНИЕ (маркер «первый шаг уже был»), не
# журналируется этим модулем.
_AGENT_STARTED_ACTION = "agent run started"


def _own_paths(zones: str | None) -> set[str]:
    """Список путей/масок `zones` (часть 1: строка через запятую) —
    множеством, без общих зон (`config.COMMON_ZONES`, требование 2)."""
    if not zones:
        return set()
    paths = {p.strip() for p in zones.split(",") if p.strip()}
    return paths - set(config.COMMON_ZONES)


def _visit_since_id(conn, task_id: str, state: str) -> int:
    """Id последней записи `"state -> {state}"` этой задачи — та же
    граница «текущий визит состояния», что и `store.refusal_history`."""
    marker = f"state -> {state}"
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] == marker:
            return row["id"]
    return 0


def _visit_has_action(conn, task_id: str, since_id: int, action: str) -> bool:
    return any(row["id"] > since_id and row["action"] == action
              for row in store.task_steps(conn, task_id))


def blocking_conflict(conn, task_id: str, t) -> tuple[str, str, str] | None:
    """(путь, id занявшей задачи, её состояние) — конфликт зоны, который
    блокирует ПЕРВЫЙ шаг developer этой задачи прямо сейчас, либо `None`
    (нет конфликта, первый шаг уже состоялся в этом визите `in_dev`, либо
    Оператор явно снял ожидание — требования 1-2, 5-6).

    `t` — строка задачи, уже прочитанная вызывающим (`store.get_task`/
    `store.all_tasks`); функция не читает её сама — тот же приём, что
    `budget.budget_block(t)`. Задача не в `in_dev` — не в режиме
    ожидания зоны вовсе (требование 1 говорит буквально о ПЕРВОМ шаге
    developer): `catalog`/`doctor` уже сами ограничивают вызов состоянием
    `in_dev`, эта проверка — второй рубеж на случай прямого вызова.

    Зоны — механика только основного (dogfood) target'а (SPEC, «Не
    входит»: «зоны для внешних target» — отдельная задача) — задача
    другого target'а никогда не считается ни занявшей, ни заблокированной.
    """
    if t["state"] != "in_dev" or t["target"] != config.DEFAULT_TARGET:
        return None
    own = _own_paths(t["zones"])
    if not own:
        return None
    since_id = _visit_since_id(conn, task_id, "in_dev")
    if _visit_has_action(conn, task_id, since_id, _AGENT_STARTED_ACTION):
        return None
    if _visit_has_action(conn, task_id, since_id, RELEASE_ACTION):
        return None
    for row in store.all_tasks(conn):
        if row["id"] == task_id or row["target"] != config.DEFAULT_TARGET:
            continue
        if row["state"] not in BLOCKING_STATES:
            continue
        shared = sorted(own & _own_paths(row["zones"]))
        if shared:
            return shared[0], row["id"], row["state"]
    return None


def refusal(conn, task_id: str, t) -> str | None:
    """Именованный отказ вида «зона <путь> занята задачей <id>
    (<состояние>)» (требование 2, AC-2), либо `None` — конфликта нет."""
    conflict = blocking_conflict(conn, task_id, t)
    if conflict is None:
        return None
    path, occupier_id, occupier_state = conflict
    return (f"[{task_id}] зона {path} занята задачей {occupier_id} "
            f"({occupier_state}) — ждёт зоны, первый шаг разработчика не "
            f"запускается")


def cmd_zone_release(task_id: str) -> None:
    """Снимает ожидание зоны для `task_id` явной командой Оператора
    (требование 6, AC-7): следующий `run`/`auto` этой задачи проходит,
    даже если занявшая зону задача осталась в прежней фазе. Пишется в
    журнал задачи как осознанный риск — не пытается снять/выяснить
    занятость ещё раз, решение целиком на Операторе."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    store.journal(conn, task_id, "operator", RELEASE_ACTION,
                 "ожидание зоны снято явной командой — Оператор принимает "
                 "риск конфликта с занявшей зону задачей")
    print(f"[{task_id}] ожидание зоны снято Оператором (осознанный риск)")


def queue_order(conn, task_ids: list[str]) -> list[str]:
    """`task_ids`, отсортированные по очереди ожидания зоны (требования
    7-9): задачи, чью позицию Оператор переставил явно
    (`cmd_zone_reorder`), — по этой позиции; остальные — по возрастанию
    `tasks.updated_at` (момент approve их SPEC — допущение источника
    времени, докстринг `_sandbox.py` этой задачи, раздел «Допущения
    интерфейса»). Переставленные вперёд позиций естественного порядка —
    иначе `cmd_zone_reorder` был бы виден только пока НИ у одной задачи
    очереди нет естественного порядка вовсе."""
    def sort_key(task_id: str):
        row = store.get_task(conn, task_id)
        position = row["zone_queue_position"]
        if position is not None:
            return (0, position)
        return (1, row["updated_at"])
    return sorted(task_ids, key=sort_key)


def cmd_zone_reorder(task_ids_in_order: list[str]) -> None:
    """Явная операторская перестановка очереди ожидания зоны (требование
    9, AC-9): `task_ids_in_order` становится порядком `queue_order` для
    этого же множества id, независимо от времени approve их SPEC."""
    conn = store.db()
    resolved = [store.resolve_task_id(conn, tid) for tid in task_ids_in_order]
    for position, task_id in enumerate(resolved):
        conn.execute("UPDATE tasks SET zone_queue_position=? WHERE id=?",
                     (position, task_id))
    conn.commit()
    print(f"[очередь ожидания зоны] переставлена Оператором: "
          f"{', '.join(resolved)}")
