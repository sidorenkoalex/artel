"""Виды из модели доски: `epic show` (таблица задач эпика) и `status` с
группами эпиков и блоками проектов, «эпик готов к закрытию».

Группа: долгоживущий
Красен до реализации: команды `epic` и таблицы `epics` нет (предпосылка `epic new` падает), модуля `orchestrator/board.py` нет — его импорт в теле теста падает `ModuleNotFoundError`; `status` не знает групп эпиков и блоков проектов; колонка `closed_as` и `fsm.STATES` появятся только с мержем Э0.

Держит связку «БД — модель доски — вывод команды»: задачи заводятся
`store.insert_task` в лёгкой песочнице переходов (`light_transition`),
эпики и привязка — командами `epic` через `artel.main()`, виды — вывод
`status` и `epic show`. Таблица `epic show` читается по заголовку:
столбцы разделены `|` или табуляцией, иначе — выравниванием по позициям
названий столбцов в строке заголовка. Названия, суммы, конверт,
состояния и число слитых частей порождаются модулем `random` при каждом
запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import importlib
import io
import random
import re
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, fsm, idgen, merge_after, store
from tests.sandbox import declare_target

READY = "эпик готов к закрытию"
# Столбцы таблицы `epic show` в порядке требования; «потрачено/потолок»
# узнаётся по первому слову.
COLUMNS = ("задача", "родитель", "от чего зависит", "состояние", "кто держит",
           "потрачено", "итог")
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук", "Кедр", "Пихта")
OTHER_PROJECTS = ("vega", "orion", "lyra", "draco")


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


def words(stand, count: int = 2) -> str:
    return " ".join(stand.rng.sample(WORDS, count))


def epics() -> dict:
    return {r["id"]: dict(r) for r in store.db().execute("SELECT * FROM epics")}


def carries_id(line: str) -> bool:
    """Строка несёт id заведённой фикстурой задачи или эпика — id берутся
    из БД, не из формата: формат id знает только `orchestrator/idgen.py`."""
    known = [r["id"] for r in store.all_tasks(store.db())]
    known += list(epics())
    return any(item in line for item in known)


def epic_new(stand, project: str, *, title: str | None = None,
             envelope=None) -> str:
    before = set(epics())
    args = ["epic", "new", project, title or f"Эпик {words(stand, 3)}",
            "--goal", f"Цель {words(stand, 3)}"]
    if envelope is not None:
        args += ["--envelope", str(envelope)]
    out = cli(*args)
    added = set(epics()) - before
    assert len(added) == 1, note(stand, f"предпосылка: epic new:\n{out}")
    return added.pop()


def insert_task(stand, project: str, state: str = "in_dev", *,
                epic: str | None = None, spent: float = 0.0,
                task_id: str | None = None) -> str:
    """Задача проекта: заводится в `in_dev`, привязывается `epic add`, затем
    получает `state` и `spent_usd`."""
    task_id = task_id or idgen.new_task_id()
    conn = store.db()
    store.insert_task(conn, task_id, f"Задача {words(stand)}", "in_dev",
                      f"task/{task_id.lower()}-x", project,
                      config.DEFAULT_BUDGET_USD)
    if epic is not None:
        out = cli("epic", "add", epic, task_id)
        assert store.get_task(conn, task_id)["epic_id"] == epic, note(
            stand, f"предпосылка: epic add:\n{out}")
    conn.execute("UPDATE tasks SET state=?, spent_usd=? WHERE id=?",
                 (state, spent, task_id))
    conn.commit()
    return task_id


def divide(parent: str, parts: list[str]) -> None:
    conn = store.db()
    for part in parts:
        store.update_task(conn, part, parent_task_id=parent)
    conn.execute("UPDATE tasks SET state='killed' WHERE id=?", (parent,))
    conn.commit()
    store.update_task(conn, parent, closed_as="divided")


def lines_of(text: str) -> list[str]:
    return text.splitlines()


def line_index(lines: list[str], predicate) -> int:
    found = [i for i, line in enumerate(lines) if predicate(line)]
    assert found, "строка не найдена"
    return found[0]


def task_line(lines: list[str], task_id: str) -> int:
    """Строка задачи: начинается (без отступа) с её id."""
    return line_index(lines, lambda line: line.strip().startswith(task_id))


def epic_header(lines: list[str], epic_id: str) -> int:
    return line_index(lines, lambda line: line.strip().startswith(f"{epic_id} "))


# --- таблица epic show ---

def table_cells(text: str, task_id: str) -> dict:
    """{столбец: ячейка} строки задачи `task_id` таблицы `epic show`."""
    lines = lines_of(text)
    header_i = line_index(lines, lambda line: all(
        c in line.lower() for c in COLUMNS))
    header = lines[header_i]
    row_i = line_index(lines[header_i + 1:],
                       lambda line: line.strip().startswith(task_id)
                       or line.strip().lstrip("|").strip().startswith(task_id))
    row = lines[header_i + 1 + row_i]
    for sep in ("|", "\t"):
        if sep in header:
            names = [c.strip().lower() for c in header.strip().strip(sep).split(sep)]
            cells = [c.strip() for c in row.strip().strip(sep).split(sep)]
            return dict(zip(names, cells))
    low = header.lower()
    starts = sorted((low.index(c), c) for c in COLUMNS)
    cells = {}
    for n, (start, name) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else None
        cells[name] = row[start:end].strip()
    return cells


def cell(cells: dict, name: str) -> str:
    keys = [k for k in cells if name in k]
    assert keys, f"нет столбца «{name}»: {sorted(cells)}"
    return cells[keys[0]]


def test_ac2_epic_show_table_names_parent_and_dependency(stand):
    """`epic show` эпика с поделённым P, его частью C и D после C: название и цель эпика, таблица со столбцами задача, родитель, от чего зависит, состояние, кто держит, потрачено/потолок, итог; у C в «родитель» — P, у D в «от чего зависит» — C.

    Ловит мутацию: столбцы «родитель» и «от чего зависит» перепутаны;
    «от чего зависит» берётся у родителя части, а не из `merge_after`
    строки; цель эпика не выводится.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.project])
    title = f"Эпик {words(stand, 3)}"
    epic_id = epic_new(stand, project, title=title)
    parent = insert_task(stand, project, epic=epic_id)
    part = insert_task(stand, project, stand.rng.choice(["in_dev", "review"]),
                       epic=epic_id)
    dependent = insert_task(stand, project, "spec_writing", epic=epic_id)
    divide(parent, [part])
    store.update_task(store.db(), dependent,
                      merge_after=merge_after.column([part]))

    out = cli("epic", "show", epic_id)

    assert title in out and epics()[epic_id]["goal"] in out, note(stand, out)
    part_cells = table_cells(out, part)
    assert parent in cell(part_cells, "родитель"), note(stand, f"{part_cells}\n{out}")
    assert parent not in cell(part_cells, "от чего зависит"), note(stand, out)
    dep_cells = table_cells(out, dependent)
    assert part in cell(dep_cells, "от чего зависит"), note(stand, f"{dep_cells}\n{out}")
    assert part not in cell(dep_cells, "родитель"), note(stand, out)


# --- AC-16, AC-17: «эпик готов к закрытию» ---

def test_ac16_all_terminal_shows_ready_and_close_closes(stand):
    """Эпик, все задачи которого окончательны (одна `done`, одна `killed`, порядок случаен): `status` и `epic show` пишут «эпик готов к закрытию», эпик `open`; `epic close` — `closed` с итогом и временем.

    Ловит мутацию: «готов» требует, чтобы все задачи были в `done`
    (`killed` мешает); пульт сам закрывает эпик, увидев готовность;
    `epic close` не пишет `outcome`/`closed_at`.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.project])
    epic_id = epic_new(stand, project)
    finals = ["done", "killed"]
    stand.rng.shuffle(finals)
    for state in finals:
        insert_task(stand, project, state, epic=epic_id)

    status = cli("status")
    shown = cli("epic", "show", epic_id)
    assert READY in status, note(stand, f"status:\n{status}")
    assert READY in shown, note(stand, f"epic show:\n{shown}")
    assert epics()[epic_id]["state"] == "open", note(stand, "эпик закрыт пультом")

    outcome = f"Итог {words(stand, 3)}"
    out = cli("epic", "close", epic_id, outcome)
    row = epics()[epic_id]
    assert (row["state"], row["outcome"]) == ("closed", outcome), note(
        stand, f"{row}\n{out}")
    assert row["closed_at"], note(stand, "closed_at пуст")


def test_ac17_empty_epic_is_not_ready(stand):
    """Эпик без задач и второй эпик того же проекта с задачей в неокончательном состоянии: «эпик готов к закрытию» нет ни в `status`, ни в `epic show` пустого эпика.

    Ловит мутацию: готовность — `all(...)` по пустому перечню задач
    (истина для эпика без задач).
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.project])
    empty = epic_new(stand, project)
    busy = epic_new(stand, project)
    state = stand.rng.choice([s for s in fsm.STATES
                              if s not in fsm.TERMINAL_STATES])
    insert_task(stand, project, state, epic=busy)

    status = cli("status")
    shown = cli("epic", "show", empty)
    assert READY not in status, note(stand, f"status:\n{status}")
    assert READY not in shown, note(stand, f"epic show:\n{shown}")


# --- AC-25: оба вида берут данные из модели ---

def test_ac25_views_take_title_and_counts_from_model(stand):
    """Подмена `board().build_model` моделью с другим названием эпика и счётчиками: `status` выводит подменённые название и счётчик в заголовке группы, `epic show` — подменённое название; настоящего названия нет.

    Ловит мутацию: `status`/`epic show` читают название и счётчики из
    БД напрямую (`epics.title`, `COUNT(*)`) мимо модели доски.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.project])
    real_title = f"Настоящее {words(stand, 3)}"
    epic_id = epic_new(stand, project, title=real_title)
    insert_task(stand, project, "in_dev", epic=epic_id)
    marker = f"Подменённое {stand.rng.randrange(10 ** 6, 10 ** 7)}"
    fake_count = stand.rng.randrange(700, 999)
    real_build = board().build_model

    def fake_build(conn, target):
        built = real_build(conn, target)
        for item in built["epics"]:
            if item["id"] == epic_id:
                item["title"] = marker
                item["counts"] = {"in_dev": fake_count}
        return built

    with mock.patch.object(board(), "build_model", fake_build):
        status = cli("status")
        shown = cli("epic", "show", epic_id)

    header = lines_of(status)[epic_header(lines_of(status), epic_id)]
    assert marker in header and real_title not in status, note(stand, status)
    assert str(fake_count) in header, note(stand, f"счётчик не из модели: {header}")
    assert marker in shown and real_title not in shown, note(stand, shown)


# --- AC-26 ---

def money(value: float) -> str:
    """Шаблон суммы: две цифры после точки (или запятой) обязательны,
    если они не нули."""
    whole, cents = f"{value:.2f}".split(".")
    tail = rf"[.,]{cents}" if cents != "00" else r"(?:[.,]00?)?"
    return rf"(?<![\d.,]){whole}{tail}(?![\d])"


def count_near(header: str, state: str, count: int) -> bool:
    return bool(re.search(rf"\b{state}\b\W{{0,3}}{count}\b|\b{count}\W{{0,3}}{state}\b",
                          header))


def test_ac26_status_epic_group_header_and_order(stand):
    """`status` с эпиком: заголовок группы начинается с `<id> <название> — `, несёт потрачено и конверт (у эпика без конверта — «без конверта»), счётчики по состояниям и «части слиты N/M» поделённой задачи; задача с большим id, от которой зависит задача с меньшим id, идёт раньше.

    Ловит мутацию: строки группы идут по возрастанию id без учёта
    `merge_after`; конверт без значения печатается как `0.00`, а не «без
    конверта»; N считается по всем частям, а не по `done`.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.project])
    envelope = stand.rng.choice([40, 60, 90])
    title = f"Эпик {words(stand, 3)}"
    epic_id = epic_new(stand, project, title=title, envelope=envelope)
    bare = epic_new(stand, project)
    insert_task(stand, project, "review", epic=bare)
    low, high = sorted(idgen.new_task_id() for _ in range(2))
    spent_low, spent_high = (round(stand.rng.uniform(0.11, 4), 2) for _ in range(2))
    insert_task(stand, project, "in_dev", epic=epic_id, spent=spent_low,
                task_id=low)
    insert_task(stand, project, "in_dev", epic=epic_id, spent=spent_high,
                task_id=high)
    store.update_task(store.db(), low, merge_after=merge_after.column([high]))
    parent = insert_task(stand, project, epic=epic_id)
    parts = [insert_task(stand, project) for _ in range(3)]
    merged = stand.rng.randint(1, 2)
    for part in parts[:merged]:
        insert_task_state(part, "done")
    divide(parent, parts)

    status = cli("status")
    lines = lines_of(status)
    header = lines[epic_header(lines, epic_id)].strip()
    assert header.startswith(f"{epic_id} {title} — "), note(stand, header)
    assert re.search(money(spent_low + spent_high), header), note(
        stand, f"нет потраченного {spent_low + spent_high:.2f}: {header}")
    assert re.search(money(envelope), header), note(stand, f"нет конверта: {header}")
    assert count_near(header, "in_dev", 2), note(stand, f"нет in_dev 2: {header}")
    assert count_near(header, "killed", 1), note(stand, f"нет killed 1: {header}")
    assert f"части слиты {merged}/3" in header, note(stand, header)
    bare_header = lines[epic_header(lines, bare)]
    assert "без конверта" in bare_header, note(stand, bare_header)
    assert task_line(lines, high) < task_line(lines, low), note(
        stand, f"{high} (зависимость) после {low}:\n{status}")


def insert_task_state(task_id: str, state: str) -> None:
    conn = store.db()
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()


# --- AC-27 ---

def test_ac27_task_line_in_group_equals_line_after_remove(stand):
    """Строка задачи внутри группы эпика в `status` совпадает (без отступа) со строкой той же задачи после `epic remove`.

    Ловит мутацию: строки задач группы печатаются своим сокращённым
    форматом (без бюджета, токенов или добавок `[мерж после: …]`) вместо
    прежнего кода `cmd_status`.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.project])
    epic_id = epic_new(stand, project)
    dependency = insert_task(stand, project, "in_dev")
    state = stand.rng.choice(["in_dev", "review", "spec_writing", "acceptance"])
    member = insert_task(stand, project, state, epic=epic_id,
                         spent=round(stand.rng.uniform(0, 9), 2))
    store.update_task(store.db(), member,
                      merge_after=merge_after.column([dependency]))
    insert_task(stand, project, "in_dev", epic=epic_id)

    before = lines_of(cli("status"))
    in_group = before[task_line(before, member)].strip()
    cli("epic", "remove", epic_id, member)
    assert store.get_task(store.db(), member)["epic_id"] is None, note(
        stand, "предпосылка: epic remove")
    after = lines_of(cli("status"))
    assert after[task_line(after, member)].strip() == in_group, note(
        stand, f"в группе: {in_group}\nпосле: {after[task_line(after, member)]}")


# --- AC-28 ---

def block_header(lines: list[str], project: str) -> int:
    """Заголовок блока проекта: строка с именем проекта без id задачи."""
    return line_index(lines, lambda line: re.search(
        rf"(?<![\w-]){re.escape(project)}(?![\w-])", line)
        and not carries_id(line))


def test_ac28_status_project_blocks(stand):
    """Два проекта: `b-proj` с эпиком и задачами без эпика, `a-proj` только без эпика: блоки с заголовками-именами, `a-proj` раньше `b-proj`; в `b-proj` сначала группа эпика, затем задачи без эпика по возрастанию id; в блоке `a-proj` группы эпика нет.

    Ловит мутацию: блоки идут в порядке первой задачи, а не по имени
    проекта; задачи без эпика выводятся перед группами эпиков; группа
    эпика выводится во всех блоках.
    """
    for project in ("a-proj", "b-proj"):
        declare_target(project)
    epic_id = epic_new(stand, "b-proj")
    loose_b = sorted(insert_task(stand, "b-proj", stand.rng.choice(
        ["in_dev", "review"])) for _ in range(2))
    insert_task(stand, "b-proj", "in_dev", epic=epic_id)
    loose_a = [insert_task(stand, "a-proj") for _ in range(2)]

    lines = lines_of(cli("status"))
    a_head, b_head = block_header(lines, "a-proj"), block_header(lines, "b-proj")
    assert a_head < b_head, note(stand, "\n".join(lines))
    later = [i for i in range(len(lines)) if i > a_head and lines[i].strip()
             and not carries_id(lines[i]) and not lines[i].startswith(" ")]
    a_end = min([i for i in later if i <= b_head] or [b_head])
    assert not any(epic_id in line for line in lines[a_head:a_end]), note(
        stand, "группа эпика b-proj в блоке a-proj")
    epic_at = epic_header(lines, epic_id)
    rows_b = [task_line(lines, t) for t in loose_b]
    assert b_head < epic_at < min(rows_b), note(stand, "\n".join(lines))
    assert rows_b == sorted(rows_b), note(stand, "задачи без эпика не по id")
    assert all(a_head < task_line(lines, t) < b_head for t in loose_a), note(
        stand, "\n".join(lines))
