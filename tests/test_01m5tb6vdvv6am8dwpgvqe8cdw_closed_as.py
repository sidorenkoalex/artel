"""Признак поделённого родителя `closed_as`: миграция прежних делений и
отметка «поделена: части слиты N/M (…)» в `status`.

Группа: долгоживущий
Красен до реализации: колонки `tasks.closed_as` нет — миграция её не добавляет и не заполняет, `update_task(closed_as=…)` падает, а `status` печатает прежнюю добавку «[поделена: <ids>]» по наличию частей.

Миграция держит связку «схема — строки `tasks` — журнал»: БД прошлой
версии изображается снятой колонкой `closed_as`, строки и журнал пишутся
сырым подключением без миграции, затем зовётся `schema.migrate`. Отметка
`status` держит связку «строки `tasks` — вывод команды». Тексты журнала,
порядок вставки и выбор слитых частей порождаются модулем `random` при
каждом запуске; зерно печатается и входит в текст провала.
"""
import random
import sqlite3

import pytest

from orchestrator import catalog, config, idgen, schema, store
from tests.sandbox import capture_new_task_id

DIVIDED_DETAIL = "поделена на:"


@pytest.fixture
def stand(light_transition):
    """Лёгкая песочница переходов с зерном случайных входов."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    return light_transition


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


# --- AC-2: миграция ---

def raw_connection() -> sqlite3.Connection:
    """Подключение к БД песочницы без `store.db()`: тот зовёт миграцию на
    каждом подключении, а сценарию нужна БД прошлой версии до неё."""
    conn = sqlite3.connect(config.DB)
    conn.row_factory = sqlite3.Row
    return conn


def as_previous_version(conn: sqlite3.Connection) -> None:
    if "closed_as" in schema.table_columns(conn, "tasks"):
        conn.execute("ALTER TABLE tasks DROP COLUMN closed_as")
        conn.commit()


def steps_of(conn, task_id: str) -> list[tuple]:
    return [tuple(r) for r in conn.execute(
        "SELECT * FROM steps WHERE task_id=? ORDER BY id", (task_id,))]


def all_steps(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute("SELECT * FROM steps ORDER BY id")]


def all_rows(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute("SELECT * FROM tasks ORDER BY id")]


def test_ac2_migration_marks_only_divided_and_is_idempotent(stand):
    """БД прошлой версии с двумя `killed`: у одной переход «поделена на: …», у другой нет; миграция ставит `closed_as='divided'` только первой с одной записью журнала, повторная — ничего не меняет.

    Порядок заведения двух задач и посторонние записи их журналов
    случайны.

    Ловит мутацию: миграция метит любую `killed` (не сверяя журнал) —
    у второй задачи `closed_as='divided'`; ищет «поделена на» в любой
    записи, а не в переходе в `killed`, и метит по посторонней записи;
    при повторном запуске пишет запись журнала заново (нет проверки
    «уже заполнено») — журнал растёт; миграция ставит колонку, но не
    пишет записи журнала.
    """
    conn = raw_connection()
    as_previous_version(conn)
    divided, liquidated = idgen.new_task_id(), idgen.new_task_id()
    order = [divided, liquidated]
    stand.rng.shuffle(order)
    for task_id in order:
        store.insert_task(conn, task_id, f"Задача {task_id}", "killed",
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        for _ in range(stand.rng.randint(0, 2)):
            store.journal(conn, task_id, "fsm", "бюджет из SPEC",
                          f"${stand.rng.randint(5, 60)}.00")
    parts = ", ".join(idgen.new_task_id()
                      for _ in range(stand.rng.randint(2, 4)))
    store.journal(conn, divided, "operator", "state -> killed",
                  f"{DIVIDED_DETAIL} {parts}")
    store.journal(conn, liquidated, "operator", "state -> killed",
                  stand.rng.choice(["kill switch: решение Оператора",
                                    "kill switch: дубль задачи"]))
    conn.commit()
    divided_before = steps_of(conn, divided)
    liquidated_before = steps_of(conn, liquidated)

    schema.migrate(conn)

    def closed_as(task_id: str):
        return conn.execute("SELECT closed_as FROM tasks WHERE id=?",
                            (task_id,)).fetchone()["closed_as"]

    assert closed_as(divided) == "divided", note(stand, "поделённая не помечена")
    assert not closed_as(liquidated), note(
        stand, f"ликвидированная помечена: {closed_as(liquidated)!r}")
    assert len(steps_of(conn, divided)) == len(divided_before) + 1, note(
        stand, f"записей журнала поделённой: было {len(divided_before)}, "
               f"стало {len(steps_of(conn, divided))}")
    assert steps_of(conn, divided)[:len(divided_before)] == divided_before
    assert steps_of(conn, liquidated) == liquidated_before, note(
        stand, "журнал ликвидированной изменён")

    rows, steps = all_rows(conn), all_steps(conn)
    schema.migrate(conn)
    assert all_rows(conn) == rows, note(stand, "повторная миграция "
                                               "изменила строки tasks")
    assert all_steps(conn) == steps, note(stand, "повторная миграция "
                                                 "добавила записи журнала")


# --- AC-17: отметка status ---

def new_task(title: str) -> str:
    _, task_id = capture_new_task_id(catalog.cmd_new, title)
    return task_id


def set_state(task_id: str, state: str) -> None:
    conn = store.db()
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()


def status_line(stand, task_id: str) -> str:
    out = stand.capture(catalog.cmd_status)
    lines = [line for line in out.splitlines() if line.startswith(task_id)]
    assert len(lines) == 1, note(stand, f"строка {task_id} в status:\n{out}")
    return lines[0]


def test_ac17_status_counts_merged_parts_of_divided_parent(stand):
    """Поделённый родитель с тремя частями: `status` показывает «поделена: части слиты 1/3 (<ids>)», после слития второй — 2/3, прежней добавки нет; `killed` с частями без `closed_as` отметки не несёт.

    Какие части сливаются первыми — случайно.

    Ловит мутацию: N считается по всем частям, а не по `done` (всегда
    3/3) или M — по частям в `done`; отметка вычисляется один раз и не
    пересчитывается от текущих состояний; отметка строится по наличию
    строк с `parent_task_id`, а не по `closed_as` — у второй убитой
    задачи появляется «поделена:»; прежняя добавка «[поделена: <ids>]»
    оставлена рядом с новой.
    """
    conn = store.db()
    parent = new_task("Поделённый родитель")
    parts = [new_task(f"Часть {n}") for n in range(1, 4)]
    for part in parts:
        store.update_task(conn, part, parent_task_id=parent)
    set_state(parent, "killed")
    store.update_task(conn, parent, closed_as="divided")
    listed = ", ".join(sorted(parts))
    merged = stand.rng.sample(parts, 2)

    set_state(merged[0], "done")
    line = status_line(stand, parent)
    assert f"поделена: части слиты 1/3 ({listed})" in line, note(stand, line)
    assert f"[поделена: {sorted(parts)[0]}" not in line, note(stand, line)

    set_state(merged[1], "done")
    line = status_line(stand, parent)
    assert f"поделена: части слиты 2/3 ({listed})" in line, note(stand, line)
    assert f"[поделена: {sorted(parts)[0]}" not in line, note(stand, line)

    plain = new_task("Убитая задача с частями")
    for n in range(stand.rng.randint(1, 3)):
        store.update_task(conn, new_task(f"Часть убитой {n}"),
                          parent_task_id=plain)
    set_state(plain, "killed")
    line = status_line(stand, plain)
    assert "поделена:" not in line, note(stand, line)
