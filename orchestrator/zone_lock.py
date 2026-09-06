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

«Занимает зону» (требования 1-2, SPEC 01M1REVJ8AJDKAMK5VTKES5J6D) —
признак, который эта задача применяет к КАЖДОМУ кандидату цикла
`blocking_conflict`, не только к самой проверяемой задаче (части 1-3
проверяли только её): без этого условия любая задача диапазона
`BLOCKING_STATES` с пересекающейся зоной считалась бы занявшей её, даже
сама ни разу не начав код (факты «а»/«б» SPEC, «Контекст» — ждущая
зону задача блокировала пять других). Граница признака — не последний
визит `in_dev` буквально (`review -> in_dev` сдвигал бы её на каждый
возврат, факт «б»), а начало ТЕКУЩЕГО непрерывного пребывания в
диапазоне `in_dev`…`merge_gate`: id последней записи `"state ->
tests_writing"` этой задачи (`_stay_since_id`) — `tests_writing`
проходится ровно один раз за пребывание (предыдущая фаза диапазона), в
отличие от `in_dev`, куда пребывание заходит повторно. Сам факт «занимает»
(`_occupies`) — запись `"agent run started"` роли developer (её
журналирует `runner.run_agent_once`) либо `RELEASE_ACTION` (см. ниже)
ПОСЛЕ этой границы; без неё задача только ждёт — зон не держит ни для
себя (как и в частях 1-3), ни (новое здесь) для остальных кандидатов,
что её сканируют. Синтетика песочниц, заводящая задачи прямой правкой
строки в обход `set_state` (`tests/test_invariants.py::FsmTest.
set_state`), не пишет маркер `"state -> tests_writing"` вовсе — граница
остаётся `0` (весь журнал задачи), что для одного непрерывного тестового
сценария поведенчески то же самое: маркеров «занимает»/«снято
Оператором» в свежей задаче до первого вызова всё равно нет.

Оператор может снять ожидание явной командой (требование 6, AC-7) даже
БЕЗ того, чтобы занявшая зону задача куда-то делась — иначе команда была
бы неотличима от естественного снятия (требование 5, AC-6) и не давала бы
никакого recourse (SPEC, «Оценка объёма и деление»). Снятие — тем же
маркерным приёмом: запись `RELEASE_ACTION` после границы текущего
пребывания считается для него равнозначной «занимает зону» — обе записи
одного семейства «это пребывание больше не в режиме ожидания»; граница не
сдвигается промежуточными визитами `in_dev` (`review -> in_dev`), поэтому
снятое ожидание не нужно снимать заново после возврата из ревью (AC-3).

Очередь (требования 7-9, AC-8/AC-9) — чистая функция от переданных id, не
от факта блокировки (это уже AC-1..AC-3): порядок по возрастанию
времени approve, если Оператор явно не переставил её `cmd_zone_reorder`
— тогда позиция, записанная им, решает раньше времени approve (колонка
`zone_queue_position`, `NULL` — переставлено не было).

Источник времени approve (R1-F2, REVIEW.md итерация 1) — id записи
журнала `"state -> {X}"`, первой ПОСЛЕ последней `"state -> spec_gate"`
этой задачи (тот же приём границы, что и выше): `set_state` пишет её
буквально в момент `cmd_approve` на гейте SPEC, независимо от того, в
какое состояние ведёт переход (штатно `tests_writing`) — в отличие от
`tasks.updated_at`, которую двигает и следующий переход `tests_writing
-> in_dev`, никак не привязанный к моменту approve. `steps.id` — общий
монотонный счётчик по ВСЕМ задачам одной БД (докстринг `store.py`: «БД
одна на все target'ы»), так что порядок этих id между задачами и есть
порядок approve во времени, без коллизий secondной точности `steps.ts`.
Задача, заведённая в обход `set_state` (приёмочная песочница `_sandbox.
ZoneSandbox.seed_task`, докстринг «Допущения интерфейса»: обе задачи
входят в `in_dev` НАПРЯМУЮ, без `state -> spec_gate` вовсе) — такой
записи не несёт; `queue_order` в этом случае деградирует к
`tasks.updated_at`, тот же фолбэк, что приёмочные тесты AC-8/AC-9 уже
фиксируют для этого случая буквально.
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


def _paths_overlap(a: str, b: str) -> bool:
    """`a` и `b` пересекаются с учётом вложенности файл/каталог (R1-F1,
    REVIEW.md итерация 1): точное совпадение, либо одна из зон — каталог
    (оканчивается на `"/"`, конвенция `config.COMMON_ZONES`), под который
    попадает другая. Симметрично — порядок аргументов не важен."""
    if a == b:
        return True
    if a.endswith("/") and b.startswith(a):
        return True
    if b.endswith("/") and a.startswith(b):
        return True
    return False


def _narrower(a: str, b: str) -> str:
    """Более узкий (глубже вложенный) из пары пересекающихся `a`/`b` —
    конкретное место конфликта для сообщения, не всё дерево каталога,
    который его покрывает."""
    if a == b:
        return a
    if a.endswith("/") and b.startswith(a):
        return b
    if b.endswith("/") and a.startswith(b):
        return a
    return min(a, b)


def _covered_by(path: str, common: str) -> bool:
    """`path` целиком покрыт зоной `common`: точное совпадение, либо
    `common` — каталог (оканчивается на `"/"`), под который попадает
    `path`. НЕ симметрично (в отличие от `_paths_overlap`): своя зона-
    каталог, лишь СОДЕРЖАЩАЯ где-то внутри общий файл (`orchestrator/`
    содержит общий `orchestrator/config.py`), этим не «покрыта» — общей
    считается только зона, целиком лежащая ВНУТРИ общей."""
    if path == common:
        return True
    return common.endswith("/") and path.startswith(common)


def _is_common_zone(path: str) -> bool:
    """`path` покрыт общим списком зон (`config.COMMON_ZONES`, требование
    2) — с учётом вложенности (R1-F1): путь внутри общей директории
    (например, `tests/test_zone_lock.py` внутри общей `tests/`) тоже
    общий, даже если сам путь не встречается в `COMMON_ZONES` буквально."""
    return any(_covered_by(path, common) for common in config.COMMON_ZONES)


def _own_paths(zones: str | None) -> set[str]:
    """Список путей/масок `zones` (часть 1: строка через запятую) —
    множеством, без путей, покрытых общими зонами (`config.COMMON_ZONES`,
    требование 2) — с учётом вложенности файл/каталог (R1-F1)."""
    if not zones:
        return set()
    paths = {p.strip() for p in zones.split(",") if p.strip()}
    return {p for p in paths if not _is_common_zone(p)}


def _shared_zone(own: set[str], other: set[str]) -> str | None:
    """Первый (по алфавиту, для детерминизма) путь пересечения `own` и
    `other`, с учётом вложенности файл/каталог (R1-F1): для пары,
    пересекающейся через вложенность, сообщается более узкий путь — он
    и есть конкретное место конфликта."""
    matches = {_narrower(p, q) for p in own for q in other
              if _paths_overlap(p, q)}
    if not matches:
        return None
    return sorted(matches)[0]


def _stay_since_id(conn, task_id: str) -> int:
    """Id последней записи `"state -> tests_writing"` этой задачи — начало
    ТЕКУЩЕГО непрерывного пребывания в диапазоне `in_dev`…`merge_gate`
    (SPEC 01M1REVJ8AJDKAMK5VTKES5J6D, требования 1-2): `tests_writing`
    предшествует всему диапазону и проходится ровно один раз за
    пребывание — в отличие от `_visit_since_id` частей 1-3 (последняя
    запись `"state -> in_dev"` буквально), эта граница НЕ сдвигается
    повторным визитом `in_dev` (`review -> in_dev`) внутри того же
    пребывания. `0` — задача заведена в обход `set_state` (нет ни одной
    записи `"state -> tests_writing"`) — весь журнал задачи считается
    текущим пребыванием, тот же фолбэк, что и в частях 1-3."""
    marker = "state -> tests_writing"
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] == marker:
            return row["id"]
    return 0


def _visit_has_action(conn, task_id: str, since_id: int, action: str,
                      actor: str | None = None) -> bool:
    """Есть ли после `since_id` запись `action` — `actor` (если задан)
    сверяется дополнительно (регрессия 01M1REVJ8AJ, требование 1): без
    сверки любой актор того же действия (например `test_author` на
    стадии `tests_writing`) ложно считался бы искомым событием."""
    return any(row["id"] > since_id and row["action"] == action
              and (actor is None or row["actor"] == actor)
              for row in store.task_steps(conn, task_id))


def _occupies(conn, task_id: str) -> bool:
    """`task_id` занимает свои зоны в ТЕКУЩЕМ непрерывном пребывании
    (требования 1-2, SPEC 01M1RR1PZC926T13NB1JSZ7F8T требование 1):
    хотя бы один `"agent run started"` ИМЕННО РОЛИ `developer` либо
    `RELEASE_ACTION` (любым актором) ПОСЛЕ границы `_stay_since_id`.

    Фильтр по актору `developer` применяется только к `"agent run
    started"` — эту же точку (`runner.run_agent_once`) журналирует
    прогон ЛЮБОЙ роли шага (в т.ч. `test_author` на стадии
    `tests_writing`, той же задачи, до первого шага developer вовсе);
    без сверки актора `_occupies` ложно считала занятой ещё не начатую
    developer'ом задачу (регрессия 01M1REVJ8AJ, коммит d617c148).
    `RELEASE_ACTION` актора не сверяет — его журналирует только
    `cmd_zone_release` (актором `operator`), сверка тут ничего не
    закрывает и не входит в регрессию требования 1.

    Без этого признака задача только ждёт — зон не держит ни для себя,
    ни (требование 1 SPEC 01M1P9QAG65GVF69YJEV0V18D9, впервые здесь)
    для остальных кандидатов `blocking_conflict`, что её сканируют как
    потенциального владельца."""
    since_id = _stay_since_id(conn, task_id)
    return (_visit_has_action(conn, task_id, since_id,
                              _AGENT_STARTED_ACTION, actor="developer")
            or _visit_has_action(conn, task_id, since_id, RELEASE_ACTION))


def blocking_conflict(conn, task_id: str, t) -> tuple[str, str, str] | None:
    """(путь, id занявшей задачи, её состояние) — конфликт зоны, который
    блокирует первый шаг developer этой задачи прямо сейчас, либо `None`
    (нет конфликта: эта задача сама уже занимает свои зоны в текущем
    пребывании — требования 1-2, 5-6 — либо ни один кандидат диапазона
    `BLOCKING_STATES` с пересекающейся зоной её не занимает — требование
    1, AC-1/AC-8).

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
    if _occupies(conn, task_id):
        return None
    for row in store.all_tasks(conn):
        if row["id"] == task_id or row["target"] != config.DEFAULT_TARGET:
            continue
        if row["state"] not in BLOCKING_STATES:
            continue
        if not _occupies(conn, row["id"]):
            continue
        shared = _shared_zone(own, _own_paths(row["zones"]))
        if shared is not None:
            return shared, row["id"], row["state"]
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
    занятость ещё раз, решение целиком на Операторе.

    Не проверяет, что для `task_id` СЕЙЧАС вообще есть активный конфликт
    зоны (минорное замечание REVIEW.md итерации 1) — вызов на
    незаблокированной задаче тихо пишет ту же запись «осознанный риск»;
    решение полностью на Операторе, как и остальная семантика этой
    команды."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    store.journal(conn, task_id, "operator", RELEASE_ACTION,
                 "ожидание зоны снято явной командой — Оператор принимает "
                 "риск конфликта с занявшей зону задачей")
    print(f"[{task_id}] ожидание зоны снято Оператором (осознанный риск)")


def _approve_marker_id(conn, task_id: str) -> int | None:
    """Id записи журнала — момент approve SPEC задачи (требование 7,
    R1-F2): первая запись `"state -> {X}"` ПОСЛЕ последней `"state ->
    spec_gate"` этой задачи — `set_state` пишет её буквально в момент
    `cmd_approve` на гейте SPEC, независимо от того, в какое состояние
    ведёт переход (штатно `tests_writing`).

    `None` — такой записи нет (задача заведена в обход `set_state`:
    приёмочная песочница `_sandbox.ZoneSandbox.seed_task` заводит обе
    сравниваемые задачи НАПРЯМУЮ в `in_dev`, без единой записи `"state ->
    ..."`) — `queue_order` в этом случае деградирует к `tasks.updated_at`
    (см. её докстринг)."""
    steps = store.task_steps(conn, task_id)
    since_id = 0
    for row in reversed(steps):
        if row["action"] == "state -> spec_gate":
            since_id = row["id"]
            break
    for row in steps:
        if row["id"] > since_id and row["action"].startswith("state -> "):
            return row["id"]
    return None


def queue_order(conn, task_ids: list[str]) -> list[str]:
    """`task_ids`, отсортированные по очереди ожидания зоны (требования
    7-9): задачи, чью позицию Оператор переставил явно
    (`cmd_zone_reorder`), — по этой позиции; остальные — по возрастанию
    момента approve их SPEC (`_approve_marker_id`, R1-F2), либо, если
    журнал не несёт маркера approve (задача заведена в обход `set_state`
    — приёмочная песочница этой задачи), по возрастанию `tasks.updated_at`
    — фолбэк, зафиксированный приёмочными тестами AC-8/AC-9 буквально для
    этого случая. Переставленные вперёд позиций естественного порядка —
    иначе `cmd_zone_reorder` был бы виден только пока НИ у одной задачи
    очереди нет естественного порядка вовсе."""
    def sort_key(task_id: str):
        row = store.get_task(conn, task_id)
        position = row["zone_queue_position"]
        if position is not None:
            return (0, 0, position)
        marker = _approve_marker_id(conn, task_id)
        if marker is not None:
            return (1, 0, marker)
        return (1, 1, row["updated_at"])
    return sorted(task_ids, key=sort_key)


def queue_position(conn, task_id: str, path: str) -> tuple[int, int]:
    """(позиция, всего) — место `task_id` в очереди задач, СЕЙЧАС
    заблокированных пересечением ИМЕННО зоны `path` (требование 7:
    очередь — среди конкурентов по ОДНОЙ и той же зоне, не глобально
    среди всех ожидающих чего угодно). Наблюдаемость (R1-F3, REVIEW.md
    итерация 1): `queue_order`/`zone_queue_position`/`cmd_zone_reorder`
    сами по себе ничего не решают — кто реально стартует первым, решает
    исключительно занятость (`blocking_conflict`/`refusal`), не эта
    функция; она только показывает Оператору текущий порядок среди
    конкурентов по конкретной зоне (`catalog.cmd_status`,
    `doctor.check_zone_waits`), прежде чем он решит подождать, снять
    ожидание (`cmd_zone_release`) или переставить очередь
    (`cmd_zone_reorder`)."""
    competitors = []
    for row in store.all_tasks(conn):
        if row["state"] != "in_dev" or row["target"] != config.DEFAULT_TARGET:
            continue
        conflict = blocking_conflict(conn, row["id"], row)
        if conflict is not None and conflict[0] == path:
            competitors.append(row["id"])
    ordered = queue_order(conn, competitors)
    if task_id not in ordered:
        return 0, len(ordered)
    return ordered.index(task_id) + 1, len(ordered)


def cmd_zone_reorder(task_ids_in_order: list[str]) -> None:
    """Явная операторская перестановка очереди ожидания зоны (требование
    9, AC-9): `task_ids_in_order` становится порядком `queue_order` для
    этого же множества id, независимо от времени approve их SPEC."""
    conn = store.db()
    resolved = [store.resolve_task_id(conn, tid) for tid in task_ids_in_order]
    for position, task_id in enumerate(resolved):
        store.update_task(conn, task_id, zone_queue_position=position)
    print(f"[очередь ожидания зоны] переставлена Оператором: "
          f"{', '.join(resolved)}")
