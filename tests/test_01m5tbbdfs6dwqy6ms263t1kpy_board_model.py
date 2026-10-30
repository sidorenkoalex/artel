"""Модель доски `board().build_model(conn, project)`: ключи модели, элементы
эпиков и карточек, `waiting_on`, повторяемость без записи в БД, пин.

Группа: долгоживущий
Красен до реализации: модуля `orchestrator/board.py` нет — его импорт в теле теста падает `ModuleNotFoundError`, команды `epic` и таблицы `epics` нет; `fsm.STATES`/`fsm.TERMINAL_STATES` и колонка `closed_as` появятся только с мержем Э0.

Свойства модели — по БД песочницы (`light_transition`): задачи
заводятся `store.insert_task`, эпики и привязка — командами `epic`
через `artel.main()`. Ожидание зоны подменяется на публичном
`zone_lock.queue_wait` (`zone_lock.QueueWait`). Пин читается из `.git`
корня песочницы (`config.ROOT`), куда сценарий кладёт `HEAD` и ссылку.
Состояния, суммы, названия и sha порождаются модулем `random` при каждом
запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import importlib
import io
import random
import shutil
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, fsm, idgen, merge_after, store
from orchestrator import zone_lock
from tests.sandbox import declare_target

OTHER_PROJECTS = ("vega", "orion", "lyra", "draco")
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина")
TOP_KEYS = {"schema_version", "project", "generated_at", "pin", "columns",
            "epics", "cards"}
EPIC_KEYS = {"id", "title", "goal", "envelope_usd", "spent_usd", "counts",
             "nodes", "edges"}
CARD_KEYS = {"task", "title", "epic", "state", "closed_as", "waiting_on",
             "depends_on", "spent_usd", "budget_usd", "branch", "last_event_at"}
OPERATOR_STATES = ("spec_gate", "acceptance", "merge_gate", "escalated")
EDGE_KINDS = ("merge_after", "parent")


@pytest.fixture
def stand(light_transition):
    """Лёгкая песочница переходов с зерном и вторым проектом."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    light_transition.project = light_transition.rng.choice(OTHER_PROJECTS)
    declare_target(light_transition.project)
    return light_transition


def board():
    """Модуль модели доски — импортом при вызове: до реализации его нет,
    а модуль тестов обязан собираться."""
    return importlib.import_module("orchestrator.board")


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def cli(*args: str) -> str:
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            buf.write(f"\n{exc.code}")
    return buf.getvalue()


def epics() -> dict:
    return {r["id"]: dict(r) for r in store.db().execute("SELECT * FROM epics")}


def epic_new(stand, project: str, envelope=None) -> str:
    before = set(epics())
    args = ["epic", "new", project, f"Эпик {stand.rng.choice(WORDS)}",
            "--goal", f"Цель {stand.rng.choice(WORDS)}"]
    if envelope is not None:
        args += ["--envelope", str(envelope)]
    out = cli(*args)
    added = set(epics()) - before
    assert len(added) == 1, note(stand, f"предпосылка: epic new:\n{out}")
    return added.pop()


def insert_task(stand, project: str, state: str = "in_dev", *,
                spent: float = 0.0, epic: str | None = None) -> str:
    """Задача проекта; `epic` — привязка командой `epic add` до перевода в
    `state`."""
    task_id = idgen.new_task_id()
    conn = store.db()
    store.insert_task(conn, task_id, f"Задача {stand.rng.choice(WORDS)}",
                      "in_dev", f"task/{task_id.lower()}-x", project,
                      config.DEFAULT_BUDGET_USD)
    if epic is not None:
        out = cli("epic", "add", epic, task_id)
        assert store.get_task(conn, task_id)["epic_id"] == epic, note(
            stand, f"предпосылка: epic add:\n{out}")
    conn.execute("UPDATE tasks SET state=?, spent_usd=? WHERE id=?",
                 (state, spent, task_id))
    conn.commit()
    return task_id


def model(project: str) -> dict:
    return board().build_model(store.db(), project)


def card(built: dict, task_id: str) -> dict:
    found = [c for c in built["cards"] if c["task"] == task_id]
    assert len(found) == 1, f"карточек {task_id}: {len(found)}"
    return found[0]


def epic_item(built: dict, epic_id: str) -> dict:
    found = [e for e in built["epics"] if e["id"] == epic_id]
    assert len(found) == 1, f"элементов эпика {epic_id}: {len(found)}"
    return found[0]


def no_zone_wait(*args, **kwargs):
    return None


# --- AC-20 ---

def test_ac20_top_level_keys_and_columns(stand):
    """Модель — словарь с ключами верхнего уровня ровно `schema_version`, `project`, `generated_at`, `pin`, `columns`, `epics`, `cards`; `columns` равен `fsm.STATES`; `project` — запрошенный проект.

    Ловит мутацию: `columns` берётся из `report.STATE_ORDER` без
    `verifying` или из списка состояний задач проекта (только
    встречающиеся); модель несёт лишний ключ верхнего уровня (например,
    `alerts`) или не несёт `pin`.
    """
    epic_id = epic_new(stand, stand.project)
    insert_task(stand, stand.project, epic=epic_id)
    built = model(stand.project)
    assert set(built) == TOP_KEYS, note(stand, f"ключи {sorted(built)}")
    assert list(built["columns"]) == list(fsm.STATES), note(
        stand, f"columns {built['columns']}")
    assert built["project"] == stand.project


# --- AC-21 ---

def edge_shape(edge, ids: set) -> tuple:
    """(вид ребра, множество концов) — ребро словарём или кортежем."""
    values = list(edge.values()) if isinstance(edge, dict) else list(edge)
    kinds = [v for v in values if v in EDGE_KINDS]
    ends = frozenset(v for v in values if v in ids)
    return (kinds[0] if len(kinds) == 1 else None), ends


def test_ac21_epic_and_card_elements(stand):
    """Элемент эпика несёт `id`, `title`, `goal`, `envelope_usd`, `spent_usd`, `counts`, `nodes`, `edges`; на фикстуре P→C (родитель) и D после C — ребро `parent` между P и C и ребро `merge_after` между D и C; карточка несёт свои одиннадцать ключей.

    Ловит мутацию: рёбра строятся только из `merge_after` (ребра
    `parent` нет) или вид рёбер перепутан; ребро `merge_after` ведёт к
    родителю части, а не к самой C.
    """
    epic_id = epic_new(stand, stand.project)
    parent = insert_task(stand, stand.project, "spec_gate", epic=epic_id)
    part = insert_task(stand, stand.project,
                       stand.rng.choice(["in_dev", "review", "spec_writing"]),
                       epic=epic_id)
    dependent = insert_task(stand, stand.project, "spec_writing", epic=epic_id)
    conn = store.db()
    store.update_task(conn, part, parent_task_id=parent)
    store.update_task(conn, dependent, merge_after=merge_after.column([part]))
    conn.execute("UPDATE tasks SET state='killed' WHERE id=?", (parent,))
    conn.commit()
    store.update_task(conn, parent, closed_as="divided")

    built = model(stand.project)
    item = epic_item(built, epic_id)
    assert EPIC_KEYS <= set(item), note(stand, f"ключи эпика {sorted(item)}")
    shapes = {edge_shape(e, {parent, part, dependent}) for e in item["edges"]}
    assert ("parent", frozenset({parent, part})) in shapes, note(
        stand, f"нет ребра parent P–C: {item['edges']}")
    assert ("merge_after", frozenset({dependent, part})) in shapes, note(
        stand, f"нет ребра merge_after D–C: {item['edges']}")
    for task_id in (parent, part, dependent):
        assert CARD_KEYS <= set(card(built, task_id)), note(
            stand, f"ключи карточки {sorted(card(built, task_id))}")


# --- AC-22, AC-23 ---

def expected_waiting(state: str):
    if state in fsm.TERMINAL_STATES:
        return None
    if state in OPERATOR_STATES:
        return "operator"
    if state == "verifying":
        return "ci"
    if state == "awaiting_human":
        return "human"
    return "role"


def test_ac22_waiting_on_for_every_state(stand):
    """По задаче в каждом состоянии `fsm.STATES` без ожидания зоны: `operator` в `spec_gate`/`acceptance`/`merge_gate`/`escalated`, `ci` в `verifying`, `None` в `done`/`killed`, `role` в остальных.

    Ловит мутацию: `verifying` попадает под `operator` (правила
    проверяются не в порядке operator → ci → …); окончательные
    состояния получают `role`; `escalated` не входит в набор
    `operator`.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.project])
    states = list(fsm.STATES)
    stand.rng.shuffle(states)
    by_state = {state: insert_task(stand, project, state) for state in states}
    with mock.patch.object(zone_lock, "queue_wait", no_zone_wait):
        built = model(project)
    got = {state: card(built, task_id)["waiting_on"]
           for state, task_id in by_state.items()}
    want = {state: expected_waiting(state) for state in states}
    assert got == want, note(stand, f"waiting_on {got}")


def test_ac23_zone_wait_turns_role_into_dependency(stand):
    """Задача в состоянии с `waiting_on='role'`, у которой `zone_lock.queue_wait` сообщает ожидание зоны, получает `dependency`; соседняя в том же состоянии без ожидания — `role`.

    Ловит мутацию: ожидание зоны не спрашивается у `zone_lock.queue_wait`
    (карточка остаётся `role`); ожидание приписывается всем задачам
    состояния, а не той, которую держит зона.
    """
    role_states = [s for s in fsm.STATES if expected_waiting(s) == "role"]
    state = stand.rng.choice(role_states)
    waiting = insert_task(stand, stand.project, state)
    free = insert_task(stand, stand.project, state)
    wait = zone_lock.QueueWait(f"orchestrator/t_zone_{stand.rng.randrange(99)}.py",
                               "занята", 1, 1, True)

    def queue_wait(conn, task_id, t=None):
        return wait if task_id == waiting else None

    with mock.patch.object(zone_lock, "queue_wait", queue_wait):
        built = model(stand.project)
    assert card(built, waiting)["waiting_on"] == "dependency", note(
        stand, f"{state}: {card(built, waiting)}")
    assert card(built, free)["waiting_on"] == "role", note(
        stand, f"{state}: {card(built, free)}")


# --- AC-24 ---

def test_ac24_build_is_repeatable_and_read_only(stand):
    """Два построения подряд без изменений БД дают равные словари без `generated_at`; `total_changes` соединения не меняется.

    Ловит мутацию: модель кэширует расчёт записью в БД (или пишет журнал
    «модель построена»); порядок карточек/рёбер зависит от порядка
    обхода множества — два построения различаются.
    """
    epic_id = epic_new(stand, stand.project,
                       envelope=stand.rng.choice([None, 40, 75]))
    for _ in range(stand.rng.randint(2, 4)):
        insert_task(stand, stand.project, stand.rng.choice(list(fsm.STATES)),
                    spent=round(stand.rng.uniform(0, 5), 2),
                    epic=stand.rng.choice([epic_id, None]))
    conn = store.db()
    changes = conn.total_changes
    first = board().build_model(conn, stand.project)
    second = board().build_model(conn, stand.project)
    assert conn.total_changes == changes, note(stand, "модель писала в БД")
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second, note(stand, f"{first}\n!=\n{second}")


# --- AC-33 ---

def test_ac33_epic_spent_counts_and_nodes(stand):
    """Эпик с A (`in_dev`, 1.5), B (`done`, 2.0), C (`done`, 0): `spent_usd == 3.5`, `counts` — `in_dev` 1 и `done` 2, `nodes` — {A, B, C}; задачи другого эпика и без эпика не входят.

    Ловит мутацию: `spent_usd` суммируется по всем задачам проекта (или
    по задачам с NULL `epic_id` тоже — `epic_id IS NULL OR …`); `counts`
    считает задачи проекта, а не эпика.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.project])
    epic_id, other_epic = epic_new(stand, project), epic_new(stand, project)
    members = {insert_task(stand, project, "in_dev", spent=1.5, epic=epic_id),
               insert_task(stand, project, "done", spent=2.0, epic=epic_id),
               insert_task(stand, project, "done", spent=0.0, epic=epic_id)}
    insert_task(stand, project, stand.rng.choice(["in_dev", "review"]),
                spent=round(stand.rng.uniform(0.5, 9), 2), epic=other_epic)
    insert_task(stand, project, stand.rng.choice(["in_dev", "done"]),
                spent=round(stand.rng.uniform(0.5, 9), 2))

    item = epic_item(model(project), epic_id)
    assert item["spent_usd"] == pytest.approx(3.5), note(stand, f"{item}")
    counts = {k: v for k, v in item["counts"].items() if v}
    assert counts == {"in_dev": 1, "done": 2}, note(stand, f"counts {item['counts']}")
    assert set(item["nodes"]) == members, note(stand, f"nodes {item['nodes']}")


# --- AC-38 ---

def write_git(root, layout: str, sha: str) -> None:
    """`.git` корня: `HEAD` на ветку с отдельной ссылкой, с упакованной
    ссылкой или отсоединённый."""
    git_dir = root / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir)
    (git_dir / "refs" / "heads").mkdir(parents=True)
    if layout == "detached":
        (git_dir / "HEAD").write_text(f"{sha}\n", encoding="utf-8")
        return
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    if layout == "loose":
        (git_dir / "refs" / "heads" / "main").write_text(f"{sha}\n",
                                                         encoding="utf-8")
    else:
        (git_dir / "packed-refs").write_text(
            f"# pack-refs with: peeled\n{sha} refs/heads/main\n",
            encoding="utf-8")


@pytest.mark.parametrize("layout", ["loose", "packed", "detached"])
def test_ac38_pin_is_head_of_pult_root(stand, layout):
    """Поле `pin` — sha головы `HEAD` главной копии `config.ROOT` (ссылка отдельным файлом, упакованная, отсоединённый `HEAD`); `.git` нет — `None`.

    Ловит мутацию: пин берётся `git rev-parse` из клона проекта или из
    `origin/main`, а не из `HEAD` корня пульта; упакованная ссылка не
    читается (`None`); исключение чтения `.git` не перехватывается.
    """
    sha = "".join(stand.rng.choice("0123456789abcdef") for _ in range(40))
    write_git(config.ROOT, layout, sha)
    assert model(stand.project)["pin"] == sha, note(stand, layout)
    shutil.rmtree(config.ROOT / ".git")
    assert model(stand.project)["pin"] is None, note(stand, "без .git")
