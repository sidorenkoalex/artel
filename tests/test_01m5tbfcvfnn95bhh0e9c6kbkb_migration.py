"""Миграция схемы под черновики и решения эпика: таблицы `epic_drafts` и
`epic_decisions` в БД, где их нет, без изменения прочих строк;
идемпотентность повторного `migrate`.

Группа: долгоживущий
Красен до реализации: ни свежая схема, ни `schema.migrate` не заводят таблиц `epic_drafts` и `epic_decisions` — сверка их колонок падает, а команд `epic draft`/`epic decision` нет.

Держит связку «схема — строки прочих таблиц — команды эпика»: БД прошлой
версии — свежая схема (`store.create_schema`) со снятыми таблицами
черновиков и решений; строки задач, эпиков и журнала пишутся сырым
подключением без миграции (`store.db()` зовёт `migrate` на каждом
открытии). Поля требований 1 и 9 SPEC не названы именами колонок, поэтому
полнота сверяется так: колонки догнанных таблиц равны колонкам свежей
схемы, а `epic draft add` и `epic decision` на догнанной БД пишут строки,
несущие все значения своих полей. Число и содержимое строк порождаются
модулем `random` при каждом запуске; зерно печатается и входит в текст
провала.
"""
import contextlib
import io
import random
import sqlite3
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, idgen, schema, store

NEW_TABLES = ("epic_drafts", "epic_decisions")
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина")


@pytest.fixture
def stand(tmp_root):
    """Песочница путей `config` с зерном; БД прошлой версии — `config.DB`."""
    tmp_root.seed = random.randrange(1 << 30)
    print(f"зерно: {tmp_root.seed}")
    tmp_root.rng = random.Random(tmp_root.seed)
    config.DB.parent.mkdir(parents=True, exist_ok=True)
    return tmp_root


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def connect(path) -> sqlite3.Connection:
    """Подключение без `store.db()` (без миграции на открытии)."""
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    store.enable_wal(conn)
    return conn


def tables(conn) -> set:
    return {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def columns(conn, table: str) -> list[tuple]:
    return [tuple(r) for r in conn.execute(f"PRAGMA table_info({table})")]


def other_rows(conn) -> dict:
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")]
            for t in sorted(tables(conn) - set(NEW_TABLES))
            if not t.startswith("sqlite_")}


def schema_dump(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, sql FROM sqlite_master ORDER BY type, name")]


def previous_version(stand) -> dict:
    """БД прошлой версии по `config.DB`: без таблиц черновиков и решений, с
    задачами, эпиками и записями журнала. Возвращает id заведённых строк."""
    conn = connect(config.DB)
    store.create_schema(conn)
    made = {"tasks": [], "epics": []}
    for _ in range(stand.rng.randint(1, 4)):
        task_id = idgen.new_task_id()
        conn.execute(
            "INSERT INTO tasks (id, title, state, branch, target, budget_usd) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, f"Задача {task_id[-4:]}",
             stand.rng.choice(["in_dev", "done", "spec_gate"]),
             f"task/{task_id.lower()}-x", config.DEFAULT_TARGET, 25.0))
        conn.execute("INSERT INTO steps (task_id, ts, actor, action, detail) "
                     "VALUES (?, ?, 'operator', 'created', ?)",
                     (task_id, store.now(), f"фикстура {stand.seed}"))
        made["tasks"].append(task_id)
    for _ in range(stand.rng.randint(1, 3)):
        epic_id = "E" + idgen.new_task_id()
        conn.execute(
            "INSERT INTO epics (id, project, title, goal, state, created_at) "
            "VALUES (?, ?, ?, ?, 'open', ?)",
            (epic_id, config.DEFAULT_TARGET,
             f"Эпик {' '.join(stand.rng.sample(WORDS, 2))}",
             f"Цель {stand.seed}", store.now()))
        made["epics"].append(epic_id)
    conn.commit()
    # Прежние догоны (счётчики задач и т.п.) отрабатывают до снятия таблиц:
    # сверка строк ниже видит только догон черновиков и решений.
    schema.migrate(conn)
    conn.commit()
    for table in NEW_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    conn.close()
    return made


def fresh_columns(stand) -> dict:
    conn = connect(stand.root / "fresh.db")
    store.create_schema(conn)
    found = {t: columns(conn, t) for t in NEW_TABLES}
    conn.close()
    return found


def cli(*args: str) -> tuple[str, int]:
    buf = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code or 0
            if isinstance(code, str):
                buf.write(f"\n{code}")
                code = 1
    return buf.getvalue(), code


# --- AC-15 ---

def test_ac15_migrate_creates_both_tables_and_keeps_other_rows(stand):
    """БД без `epic_drafts` и `epic_decisions`: `migrate` заводит обе с колонками свежей схемы, строки прочих таблиц (в том числе журнала) не меняются; повторный `migrate` не меняет ни схему, ни строки.

    Ловит мутацию: таблицы есть только в DDL свежей БД, а `migrate` их
    не догоняет; догон пишет запись журнала о миграции или трогает
    строки `tasks`/`epics`; у догнанной таблицы колонок меньше, чем у
    свежей (DDL догона — отдельная устаревшая копия); повторный
    `migrate` пересоздаёт таблицы.
    """
    previous_version(stand)
    conn = connect(config.DB)
    assert not set(NEW_TABLES) & tables(conn), note(stand, "предпосылка")
    before = other_rows(conn)

    schema.migrate(conn)
    conn.commit()

    assert set(NEW_TABLES) <= tables(conn), note(
        stand, f"таблицы после migrate: {sorted(tables(conn))}")
    expected = fresh_columns(stand)
    for table in NEW_TABLES:
        assert columns(conn, table) == expected[table], note(
            stand, f"колонки {table}: {columns(conn, table)} ≠ {expected[table]}")
    assert other_rows(conn) == before, note(stand, "строки прочих таблиц изменены")

    dump, rows_after = schema_dump(conn), other_rows(conn)
    schema.migrate(conn)
    conn.commit()
    assert schema_dump(conn) == dump, note(stand, "повторный migrate сменил схему")
    assert other_rows(conn) == rows_after, note(stand, "повторный migrate писал строки")
    conn.close()


def test_ac15_migrated_tables_carry_fields_of_drafts_and_decisions(stand):
    """На догнанной БД `epic draft add` с рамкой, `--start-after`, `--after` и `epic decision --for envelope` пишут строки, несущие эпик, номер 1, название, текст ТЗ, рамку, оба перечня, состояние `draft`, текст решения.

    Ловит мутацию: догон заводит таблицу черновиков без колонок
    перечней или рамки (команда падает либо значение теряется);
    таблица решений догоняется без колонки текста или привязки.
    """
    made = previous_version(stand)
    conn = connect(config.DB)
    schema.migrate(conn)
    conn.commit()
    conn.close()
    epic_id = stand.rng.choice(made["epics"])
    first, second = made["tasks"][0], made["tasks"][-1]
    title = f"Черновик {stand.rng.randrange(1 << 30)}"
    text = (f"# {title}\n\nИсточник: фикстура {stand.seed}.\n\n"
            f"Требуется:\n1. Поправить.\n")
    path = stand.root / "tz.md"
    path.write_text(text, encoding="utf-8")
    frame = round(stand.rng.uniform(5, 60), 2) + 0.25

    out, code = cli("epic", "draft", "add", epic_id, "--tz", str(path),
                    "--budget", str(frame), "--start-after", first,
                    "--after", second)
    rows = [dict(r) for r in store.db().execute("SELECT * FROM epic_drafts")]
    assert len(rows) == 1, note(stand, f"черновик не заведён ({code}):\n{out}")
    values = list(rows[0].values())
    for expected in (epic_id, 1, title, text, "draft"):
        assert expected in values, note(stand, f"нет {expected!r} в {rows[0]}")
    assert any(isinstance(v, float) and abs(v - frame) < 1e-6 for v in values)
    assert any(isinstance(v, str) and first in v and v != text for v in values)
    assert any(isinstance(v, str) and second in v and v != text for v in values)

    decision = f" Решение {stand.rng.randrange(1 << 30)} "
    out, code = cli("epic", "decision", epic_id, decision, "--for", "envelope")
    rows = [dict(r) for r in store.db().execute("SELECT * FROM epic_decisions")]
    assert len(rows) == 1 and decision in rows[0].values(), note(
        stand, f"решение не записано ({code}): {rows}\n{out}")
    assert epic_id in rows[0].values(), note(stand, f"эпик решения: {rows[0]}")
