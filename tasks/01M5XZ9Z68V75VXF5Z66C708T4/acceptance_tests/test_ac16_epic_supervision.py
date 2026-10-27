"""Надзор эпика по задаче в `awaiting_human`: не перезапускает её, не держит ею место лимита параллельности эпика, показывает статус «ждёт людей проекта».

Группа: разовый
Красен до реализации: разбор линии эпика (`auto._epic_view`, `auto.py:1293-1321`) не знает `awaiting_human` — задача, уже получавшая шаг роли, получает статус «готова» и попадает в очередь перезапуска.

Статус задачи в надзоре эпика не выводится ни одной публичной поверхностью
(ни печатью, ни журналом, ни алертом — только внутри разбора опроса), а
критерий требует именно статуса; SPEC адресует место прямо
(`auto.py:1298-1306`, `:1338`). Поэтому файл разовый и читает разбор
опроса надзора `auto._epic_view` — тот же разбор, по которому `_supervise`
запускает дочерние `auto` (`view.ready[:view.free]`): задача вне `ready`
не перезапускается, место в `free` — лимит параллельности эпика.

Песочница — `initialized_tmp_root`; эпик заводится `store.insert_epic`,
задачи — `store.insert_task` с `epic_id`, состояние `awaiting_human` —
прямой установкой. Порядок задач в эпике и id — из `random`, зерно
печатается и входит в текст провала.
"""
import random

import pytest

from orchestrator import auto, config, idgen, merge_after, store

STATE = "awaiting_human"


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


def new_task(epic_id: str, state: str, started: bool) -> str:
    task_id = idgen.new_task_id()
    conn = store.db()
    store.insert_task(conn, task_id, f"Задача эпика {task_id[-6:]}", "in_dev",
                      f"task/{task_id.lower()}-e", config.DEFAULT_TARGET,
                      config.DEFAULT_BUDGET_USD)
    store.update_task(conn, task_id, epic_id=epic_id)
    if started:
        store.journal(conn, task_id, "developer",
                      merge_after.ROLE_STEP_STARTED_ACTION, "шаг роли был")
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()
    return task_id


def test_ac16_epic_supervisor_skips_awaiting_human_task(initialized_tmp_root, seed):
    """Задача эпика в `awaiting_human` не в очереди перезапуска, не занимает место лимита и имеет статус «ждёт людей проекта».

    Сценарий: эпик с лимитом параллельности по умолчанию (1); в нём задача
    A в `awaiting_human`, уже получавшая шаг роли (запись «agent run
    started»), и задача B в `in_dev` без шага роли (готова к первому
    запуску); порядок заведения A и B случаен. Разбор опроса надзора:
    - статус A содержит «ждёт людей проекта» (не «ждёт Оператора…», не
      «готова»);
    - A нет среди готовых к запуску (`ready`) — надзор её не перезапускает;
    - B среди готовых и свободное место есть (`free >= 1`, B входит в
      `ready[:free]`) — A не считается в лимите параллельности эпика.

    Ловит мутацию: ветки `awaiting_human` в разборе нет — A, получавшая
    шаг роли, становится «готова» и перезапускается (и занимает
    единственное место вместо B); `awaiting_human` приравнен к гейту —
    статус «ждёт Оператора на гейте или в эскалации»; задачи, ждущие людей
    проекта, вычитаются из свободных мест — `free` 0, B не запускается.
    """
    rng = random.Random(seed)
    conn = store.db()
    epic_id = idgen.new_task_id()
    store.insert_epic(conn, epic_id, config.DEFAULT_TARGET, "Эпик ожидания",
                      "Цель", None)
    conn.commit()
    order = ["A", "B"]
    rng.shuffle(order)
    made = {}
    for name in order:
        made[name] = (new_task(epic_id, STATE, True) if name == "A"
                      else new_task(epic_id, "in_dev", False))
    a, b = made["A"], made["B"]
    note = f"зерно: {seed}; порядок {order}; A {a}; B {b}"

    view = auto._epic_view(store.db(), store.get_epic(store.db(), epic_id))

    status = view.status.get(a, "")
    assert "ждёт людей проекта" in status, f"{note}: статус A {status!r}"
    assert a not in view.ready, f"{note}: A в очереди перезапуска: {view.ready}"
    assert b in view.ready[:max(view.free, 0)], (
        f"{note}: B не запускается: ready {view.ready}, free {view.free}")
