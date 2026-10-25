"""Миграция схемы под эпики: таблица `epics`, колонка `tasks.epic_id`, одна
запись журнала системной записью, идемпотентность, БД без `steps`, догон
одной БД двумя соединениями с перемежением.

Группа: долгоживущий
Красен до реализации: `schema.migrate` не заводит таблицу `epics` и колонку `tasks.epic_id` и не пишет записи журнала о миграции.

Держит связку «схема — строки `tasks` — журнал»: БД прошлой версии —
свежая схема (`store.create_schema`) со снятыми таблицей `epics`,
колонкой `epic_id` и их индексами; строки задач и журнала пишутся сырым
подключением без миграции (`store.db()` зовёт `migrate` на каждом
открытии). Перемежение двух соединений — потоки и обратный вызов
трассировки `sqlite3`: первое соединение останавливается на `COMMIT`
своей транзакции миграции, второе начинает `migrate` в это время. Число
задач и записей журнала, их состояния и тексты порождаются модулем
`random` при каждом запуске; зерно печатается и входит в текст провала.
"""
import random
import sqlite3
import threading

import pytest

from orchestrator import config, idgen, schema, store

EPIC_COLUMNS = {"id", "project", "title", "goal", "envelope_usd", "state",
                "outcome", "created_at", "closed_at"}


@pytest.fixture
def stand(tmp_root):
    """Песочница путей `config` с зерном и путём отдельной БД прошлой версии."""
    tmp_root.seed = random.randrange(1 << 30)
    print(f"зерно: {tmp_root.seed}")
    tmp_root.rng = random.Random(tmp_root.seed)
    tmp_root.path = tmp_root.root / "previous.db"
    return tmp_root


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def connect(path) -> sqlite3.Connection:
    """Подключение без `store.db()` (без миграции на открытии)."""
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    store.enable_wal(conn)
    return conn


def previous_version(stand, *, with_steps: bool = True) -> None:
    """БД прошлой версии по пути `stand.path`: без `epics` и `epic_id`, с
    задачами и записями журнала."""
    conn = connect(stand.path)
    store.create_schema(conn)
    for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND sql LIKE '%epic%'").fetchall():
        conn.execute(f"DROP INDEX {name}")
    conn.execute("DROP TABLE IF EXISTS epics")
    if "epic_id" in schema.table_columns(conn, "tasks"):
        conn.execute("ALTER TABLE tasks DROP COLUMN epic_id")
    for _ in range(stand.rng.randint(1, 4)):
        task_id = idgen.new_task_id()
        conn.execute(
            "INSERT INTO tasks (id, title, state, branch, target, budget_usd) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, f"Задача {task_id[-4:]}",
             stand.rng.choice(["in_dev", "done", "spec_gate"]),
             f"task/{task_id.lower()}-x", config.DEFAULT_TARGET, 25.0))
        if with_steps:
            conn.execute("INSERT INTO steps (task_id, ts, actor, action, detail) "
                         "VALUES (?, ?, 'operator', 'created', ?)",
                         (task_id, store.now(), f"фикстура {stand.seed}"))
    if not with_steps:
        conn.execute("DROP TABLE steps")
    conn.commit()
    conn.close()


def all_steps(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute("SELECT * FROM steps ORDER BY id")]


def schema_dump(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, sql FROM sqlite_master ORDER BY type, name")]


def config_strings() -> set:
    return {value for name, value in vars(config).items()
            if name.isupper() and isinstance(value, str)}


# --- AC-19 ---

def test_ac19_migration_adds_epics_once_with_one_system_record(stand):
    """БД прошлой версии с задачами: `migrate` заводит `epics` и `tasks.epic_id` (у прежних задач пусто), пишет ровно одну запись журнала с `task_id` — значением строковой константы `config`; повторный `migrate` не меняет схему и журнал.

    Ловит мутацию: признак «догон нужен» проверяет таблицу `epics`, а не
    колонку `tasks.epic_id`, — повторный `migrate` пишет запись снова;
    запись журнала пишется под id задачи или литералом мимо `config`;
    колонке задан DEFAULT, заполняющий прежние строки.
    """
    previous_version(stand)
    conn = connect(stand.path)
    tasks_before = {r["id"] for r in conn.execute("SELECT id FROM tasks")}
    steps_before = all_steps(conn)

    schema.migrate(conn)

    assert EPIC_COLUMNS <= schema.table_columns(conn, "epics"), note(
        stand, f"колонки epics: {schema.table_columns(conn, 'epics')}")
    assert "epic_id" in schema.table_columns(conn, "tasks")
    assert [r["epic_id"] for r in conn.execute("SELECT epic_id FROM tasks")] == [
        None] * len(tasks_before), note(stand, "epic_id прежних задач не пуст")
    steps = all_steps(conn)
    assert steps[:len(steps_before)] == steps_before
    added = [dict(r) for r in conn.execute(
        "SELECT * FROM steps ORDER BY id")][len(steps_before):]
    assert len(added) == 1, note(stand, f"записей миграции {len(added)}: {added}")
    assert added[0]["task_id"] in config_strings(), note(
        stand, f"task_id записи {added[0]['task_id']!r} — не константа config")
    assert added[0]["task_id"] not in tasks_before

    dump = schema_dump(conn)
    schema.migrate(conn)
    assert schema_dump(conn) == dump, note(stand, "повторный migrate сменил схему")
    assert all_steps(conn) == steps, note(stand, "повторный migrate писал журнал")


# --- AC-34 ---

def test_ac34_migration_without_steps_table(stand):
    """БД прошлой версии без таблицы `steps`: `migrate` заводит `epics` и `tasks.epic_id` без исключения.

    Ловит мутацию: запись журнала о миграции пишется безусловно —
    `no such table: steps` роняет миграцию, а с ней любое открытие БД.
    """
    previous_version(stand, with_steps=False)
    conn = connect(stand.path)
    schema.migrate(conn)
    assert EPIC_COLUMNS <= schema.table_columns(conn, "epics")
    assert "epic_id" in schema.table_columns(conn, "tasks")


# Точки остановки первого соединения — внутри транзакции миграции эпиков:
# statement, трогающий `epics`/`epic_id`, и `COMMIT` после него. Записи,
# после которых соединение держит блокировку записи до конца транзакции.
WRITE_HEADS = ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER",
               "DROP", "BEGIN IMMEDIATE", "BEGIN EXCLUSIVE")
END_HEADS = ("COMMIT", "ROLLBACK", "END")


def touches_epics(head: str) -> bool:
    return "EPIC" in head and head.startswith(("CREATE", "ALTER", "INSERT",
                                               "UPDATE"))


def migrate_interleaved(path, point: int) -> dict | None:
    """`migrate` на двух соединениях в двух потоках: первое
    останавливается перед `point`-й точкой (statement, трогающий
    `epics`/`epic_id`, либо `COMMIT` после него), второе
    начинает `migrate` в это время. Держит первое блокировку записи (его
    транзакция миграции открыта до `COMMIT`) — его отпускает `BEGIN`
    второго; не держит — завершение второго. `None` — первое закончило,
    не дойдя до точки."""
    paused, first_ready, release = (threading.Event(), threading.Event(),
                                    threading.Event())
    track = {"seen": 0, "locked": False, "on_begin": False, "epic_tx": False}
    results: dict = {}

    def trace_first(sql: str) -> None:
        head = sql.lstrip().upper()
        point_here = touches_epics(head) or (
            head.startswith("COMMIT") and track["epic_tx"])
        if point_here and not paused.is_set():
            track["seen"] += 1
            if track["seen"] == point:
                track["on_begin"] = track["locked"]
                paused.set()
                first_ready.set()
                release.wait(60)
        if touches_epics(head):
            track["epic_tx"] = True
        if head.startswith(WRITE_HEADS):
            track["locked"] = True
        elif head.startswith(END_HEADS):
            track["locked"] = False
            track["epic_tx"] = False

    def trace_second(sql: str) -> None:
        if track["on_begin"] and sql.lstrip().upper().startswith("BEGIN"):
            release.set()

    def run(role: str, trace) -> None:
        results[role] = None
        try:
            conn = connect(path)
            conn.set_trace_callback(trace)
            schema.migrate(conn)
            conn.set_trace_callback(None)
            conn.close()
        except BaseException as exc:  # исход сверяет тест
            results[role] = repr(exc)
        finally:
            (first_ready if role == "first" else release).set()

    one = threading.Thread(target=run, args=("first", trace_first))
    one.start()
    first_ready.wait(60)
    if paused.is_set():
        two = threading.Thread(target=run, args=("second", trace_second))
        two.start()
        two.join(60)
    release.set()
    one.join(60)
    return results if paused.is_set() else None


def test_ac34_two_connections_in_sequence_leave_one_record(stand):
    """Два `migrate` подряд на двух соединениях одной БД прошлой версии: одна запись журнала о миграции, исключений нет.

    Ловит мутацию: признак «догон нужен» на втором соединении читается
    по кэшу первого или по таблице `epics` без колонки — второе
    соединение пишет вторую запись журнала.
    """
    previous_version(stand)
    conn = connect(stand.path)
    steps_before = len(all_steps(conn))
    conn.close()
    for _ in range(2):
        other = connect(stand.path)
        schema.migrate(other)
        other.close()
    conn = connect(stand.path)
    assert len(all_steps(conn)) == steps_before + 1, note(
        stand, f"записей о миграции {len(all_steps(conn)) - steps_before}")


def test_ac34_two_connections_interleaved_leave_one_record(stand):
    """Два `migrate` на двух соединениях одной БД прошлой версии с перемежением — второе начинает при каждой точке остановки первого внутри его транзакции миграции (перед statement, трогающим `epics`/`epic_id`, и перед её `COMMIT`): одна запись журнала о миграции, исключений нет.

    Ловит мутацию: проверка «колонки нет» и `ALTER` идут без `BEGIN
    IMMEDIATE` (прежний `schema.add_column`) или без повторной проверки
    в транзакции — второе соединение видит старую схему и падает
    `duplicate column name: epic_id` либо пишет вторую запись журнала.
    """
    checked = 0
    for point in range(1, 40):
        stand.path = stand.root / f"previous-{point}.db"
        previous_version(stand)
        conn = connect(stand.path)
        steps_before = len(all_steps(conn))
        conn.close()

        results = migrate_interleaved(stand.path, point)
        if results is None:
            break
        checked += 1
        errors = [results["first"], results["second"]]
        assert errors == [None, None], note(
            stand, f"точка {point}: исключения {errors}")
        conn = connect(stand.path)
        assert len(all_steps(conn)) == steps_before + 1, note(
            stand, f"точка {point}: записей о миграции "
                   f"{len(all_steps(conn)) - steps_before}")
        assert "epic_id" in schema.table_columns(conn, "tasks")
        conn.close()
    assert checked, note(stand, "первое соединение не дошло ни до одной точки")
