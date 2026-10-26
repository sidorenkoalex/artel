"""Зависимость запуска `start_after`: запись каналом `new --start-after`,
снятие словом «нет», признак ожидания до первого шага роли и канал в
причинах отказа (SPEC 01M5TBCY7WTN121S136XP2C6SR, требования 11-16, 19).

Свойства, которых не держат долгоживущие файлы задачи
(`tests/test_01m5tbcy7wtn121s136xp2c6sr_*.py`): там канал `new` проверен
только на отказах, а снятие зависимости и правило «ждёт» модели доски
после первого шага — не проверены.
"""
import io
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import pytest

from orchestrator import artel, config, merge_after, store

DEP = "01" + "A" * 24
DEP2 = "01" + "B" * 24
TASK = "01" + "C" * 24


def cli(*argv: str) -> str:
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
            redirect_stdout(buf), redirect_stderr(buf):
        artel.main()
    return buf.getvalue()


def add_task(task_id: str, state: str) -> None:
    store.insert_task(store.db(), task_id, f"Задача {task_id[-4:]}", state,
                      f"task/{task_id.lower()}-zavisimost",
                      config.DEFAULT_TARGET, 50.0)


@pytest.fixture
def sandbox(light_transition):
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield light_transition


def test_new_start_after_records_value_with_journal(sandbox):
    """`new … --start-after <id>` записывает зависимость запуска новой задаче
    и пишет ей запись журнала «start_after изменён».

    Ловит мутацию: `catalog.cmd_new` проверяет `--start-after`, но не
    пишет проверенное значение в колонку (`start_after` новой задачи
    пуст, записи журнала нет).
    """
    add_task(DEP, "in_dev")
    title = "Новая с зависимостью запуска"
    tz = sandbox.root / "tz-start-after.md"
    tz.write_text(f"# {title}\n\nЦель.\n", encoding="utf-8")
    cli("new", title, "--tz", str(tz), "--target", config.DEFAULT_TARGET,
        "--start-after", DEP)
    row = store.db().execute("SELECT * FROM tasks WHERE title=?",
                             (title,)).fetchone()
    assert row["start_after"] == DEP
    assert any(s["action"] == merge_after.START_AFTER_CHANGED_ACTION
               for s in store.task_steps(store.db(), row["id"]))


def test_epic_start_after_none_clears_value(sandbox):
    """`epic start-after <задача> нет` снимает все зависимости запуска —
    канал, которым снимают убитую зависимость.

    Ловит мутацию: слово «нет» уходит в проверку как id (отказ формы) —
    значение не снимается.
    """
    add_task(DEP, "in_dev")
    add_task(TASK, "tests_writing")
    cli("epic", "start-after", TASK, DEP)
    assert store.get_task(store.db(), TASK)["start_after"] == DEP
    cli("epic", "start-after", TASK, merge_after.NONE_WORD)
    assert store.get_task(store.db(), TASK)["start_after"] is None


def test_start_after_blocks_only_before_first_step(sandbox):
    """Задача с `start_after` не в `done` ждёт зависимость, пока в её журнале
    нет «agent run started»; убитая зависимость — тоже ожидание.

    Ловит мутацию: `start_after_blocks` не смотрит на первый шаг роли —
    задача, чей агент уже стартовал, остаётся «ждущей».
    """
    add_task(DEP, "in_dev")
    add_task(DEP2, "done")
    add_task(TASK, "tests_writing")
    cli("epic", "start-after", TASK, f"{DEP},{DEP2}")
    conn = store.db()
    assert merge_after.start_after_blocks(conn, store.get_task(conn, TASK))
    conn.execute("UPDATE tasks SET state='killed' WHERE id=?", (DEP,))
    conn.commit()
    t = store.get_task(conn, TASK)
    assert merge_after.start_after_pending(conn, t) == ([], [(DEP, "killed")])
    assert merge_after.start_after_blocks(conn, t)
    store.journal(conn, TASK, "test_author",
                  merge_after.ROLE_STEP_STARTED_ACTION, "попытка 1/3")
    assert not merge_after.start_after_blocks(conn, store.get_task(conn, TASK))


def test_start_after_refusal_names_its_channel(sandbox):
    """Причина отказа записи `start_after` называет свой канал, а не
    `merge_after`.

    Ловит мутацию: `merge_after.check` не переименовывает причины канала
    `start_after` — Оператор читает «merge_after: …» в отказе
    `epic start-after`.
    """
    add_task(TASK, "tests_writing")
    ids, reasons = merge_after.start_after_value(store.db(), TASK, [DEP])
    assert ids == [] and reasons
    assert all(r.startswith(f"{merge_after.START_AFTER}:") for r in reasons)
