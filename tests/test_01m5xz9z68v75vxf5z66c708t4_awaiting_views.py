"""Задача в `awaiting_human` и ссылка на MR задачи в представлениях пульта: модель доски, доска, `status`, `report`, `watch`.

Группа: долгоживущий
Красен до реализации: у таблицы `tasks` нет столбцов `mr_iid`/`mr_url` — `store.update_task` отказывает «нет колонок»; модель доски даёт `awaiting_human` значение `role`, а не `human`.

Песочница — `initialized_tmp_root` (`cmd_init`, схема БД); задача
заводится `store.insert_task`, состояние `awaiting_human` ставится прямой
установкой в БД (SPEC: «состояние — прямой установкой в песочнице»),
ссылка на MR пишется функцией `store.update_task`. Проект — объявленный
внешний (`declare_target`) со случайным именем; номер MR и адрес
порождаются модулем `random` при каждом запуске, зерно печатается и
входит в текст провала.
"""
import random

import pytest

from orchestrator import board, catalog, config, idgen, report, store, watch
from tests.sandbox import capture, declare_target, patch_sleep

LETTERS = "abcdefghijkmnopqrstuvwxyz"
STATE = "awaiting_human"


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


def scenario(seed: int) -> dict:
    """Имя проекта, номер и адрес MR сценария из зерна."""
    rng = random.Random(seed)
    project = "v" + "".join(rng.choice(LETTERS) for _ in range(7))
    iid = rng.randrange(2, 10 ** 5)
    url = f"https://localhost/team/{project}/-/merge_requests/{iid}"
    return {"rng": rng, "project": project, "iid": iid, "url": url}


def new_task(project: str, state: str, mr: dict | None = None) -> str:
    """Задача проекта `project` в состоянии `state`; `mr` — ссылка на MR
    задачи, записанная функцией `store.py`."""
    declare_target(project)
    task_id = idgen.new_task_id()
    conn = store.db()
    store.insert_task(conn, task_id, f"Задача {project}", "in_dev",
                      f"task/{task_id.lower()}-x", project,
                      config.DEFAULT_BUDGET_USD)
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()
    if mr is not None:
        store.update_task(conn, task_id, mr_iid=mr["iid"], mr_url=mr["url"])
    return task_id


def card_of(project: str, task_id: str) -> dict:
    built = board.build_model(store.db(), project)
    found = [c for c in built["cards"] if c["task"] == task_id]
    assert len(found) == 1, f"карточка {task_id}: {built['cards']}"
    return found[0]


def status_line(task_id: str) -> str:
    lines = [ln for ln in capture(catalog.cmd_status).splitlines()
             if task_id in ln]
    assert lines, f"status не показал задачу {task_id}"
    return "\n".join(lines)


def test_ac13_board_model_waiting_on_human(initialized_tmp_root, seed):
    """Карточка задачи в `awaiting_human` в модели доски несёт `waiting_on: "human"`.

    Сценарий: задача случайного проекта в `awaiting_human` (с ссылкой на
    MR и без неё — значение не зависит от ссылки); `board.build_model`
    по проекту даёт её карточке `waiting_on == "human"`.

    Ловит мутацию: правило `awaiting_human → human` в `board.waiting_on`
    не добавлено — задача падает в последнее правило и получает `role`;
    `awaiting_human` занесён в `board.OPERATOR_STATES` — `operator`.
    """
    sc = scenario(seed)
    note = f"зерно: {seed}; проект {sc['project']}"
    bare = new_task(sc["project"], STATE)
    linked = new_task(sc["project"], STATE, sc)
    assert card_of(sc["project"], bare)["waiting_on"] == "human", note
    assert card_of(sc["project"], linked)["waiting_on"] == "human", note


LINK_STATES = ["in_dev", "review", "merge_gate", STATE]


@pytest.mark.parametrize("view", ["--md", "--html", "--json"])
def test_ac14_board_shows_mr_link_from_db(initialized_tmp_root, seed, view):
    """Доска по задаче со ссылкой на MR в БД показывает адрес MR во всех видах.

    Сценарий: задача случайного проекта в случайном неокончательном
    состоянии со ссылкой на MR (`mr_iid`, `mr_url`, записанные
    `store.update_task`); вид доски `--md`/`--html`/`--json` (`board.RENDERERS`
    над `board.build_model`) содержит id задачи и её `mr_url`; рядом —
    задача того же проекта без ссылки (доска многозадачная).

    Ловит мутацию: карточка модели не берёт `mr_url` из строки задачи —
    адреса в выводе нет; вид `--md` (умолчание `board`) или `--html` не
    выводит поле ссылки карточки.
    """
    sc = scenario(seed)
    state = sc["rng"].choice(LINK_STATES)
    note = f"зерно: {seed}; проект {sc['project']}; состояние {state}; вид {view}"
    task_id = new_task(sc["project"], state, sc)
    new_task(sc["project"], state)
    text = board.RENDERERS[view](board.build_model(store.db(), sc["project"]))
    assert task_id in text, f"{note}: {text}"
    assert sc["url"] in text, f"{note}: ссылки MR нет: {text}"


def test_ac14_status_shows_mr_link_from_db(initialized_tmp_root, seed):
    """`status` показывает в строке задачи адрес MR, записанный в БД.

    Сценарий: задача случайного проекта в случайном неокончательном
    состоянии со ссылкой на MR, записанной `store.update_task`; строка
    этой задачи в выводе `catalog.cmd_status` содержит `mr_url`; строка
    соседней задачи без ссылки адреса не содержит.

    Ловит мутацию: строка `status` не читает `mr_url` задачи — адреса нет;
    ссылка берётся не из строки задачи, а первой попавшейся — адрес
    появится и у соседней задачи.
    """
    sc = scenario(seed)
    state = sc["rng"].choice(LINK_STATES)
    note = f"зерно: {seed}; проект {sc['project']}; состояние {state}"
    task_id = new_task(sc["project"], state, sc)
    other = new_task(sc["project"], state)
    out = capture(catalog.cmd_status)
    own = [ln for ln in out.splitlines() if task_id in ln]
    assert any(sc["url"] in ln for ln in own), f"{note}: {out}"
    assert not any(sc["url"] in ln for ln in out.splitlines() if other in ln), \
        f"{note}: ссылка чужой задачи: {out}"


def test_ac15_status_awaiting_human_state_link_not_operator(initialized_tmp_root, seed):
    """`status` по задаче в `awaiting_human` показывает состояние и ссылку MR и не пишет «ЖДЁТ ОПЕРАТОРА».

    Сценарий: задача случайного проекта в `awaiting_human` со ссылкой на
    MR; её строка в `catalog.cmd_status` содержит `awaiting_human` и
    `mr_url` и не содержит «ЖДЁТ ОПЕРАТОРА». Контроль: та же картина у
    задачи в `merge_gate` даёт «ЖДЁТ ОПЕРАТОРА» — пометка жива.

    Ловит мутацию: `awaiting_human` занесён в `board.OPERATOR_STATES` —
    строка получит «ЖДЁТ ОПЕРАТОРА»; ссылка MR не выводится.
    """
    sc = scenario(seed)
    note = f"зерно: {seed}; проект {sc['project']}"
    task_id = new_task(sc["project"], STATE, sc)
    gate = new_task(sc["project"], "merge_gate")
    line = status_line(task_id)
    assert STATE in line, f"{note}: {line}"
    assert sc["url"] in line, f"{note}: {line}"
    assert "ЖДЁТ ОПЕРАТОРА" not in line, f"{note}: {line}"
    assert "ЖДЁТ ОПЕРАТОРА" in status_line(gate), note


def test_ac15_report_shows_awaiting_human_and_mr_link(initialized_tmp_root, seed):
    """`report` по задаче в `awaiting_human` показывает её состояние и адрес MR.

    Сценарий: единственная задача случайного проекта — в `awaiting_human`
    со ссылкой на MR; `report.cmd_report` пишет отчёт
    `.artel/report.html`, в нём есть id задачи, `awaiting_human` и
    `mr_url`.

    Ловит мутацию: отчёт не выводит ссылку MR задачи — адреса нет;
    задача в `awaiting_human` выпадает из доски отчёта — нет ни id, ни
    состояния.
    """
    sc = scenario(seed)
    note = f"зерно: {seed}; проект {sc['project']}"
    task_id = new_task(sc["project"], STATE, sc)
    capture(report.cmd_report)
    html = (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")
    assert task_id in html, note
    assert STATE in html, note
    assert sc["url"] in html, f"{note}: ссылки MR нет в отчёте"


def test_ac15_watch_shows_awaiting_human_and_mr_link(initialized_tmp_root, seed):
    """`watch` по задаче, перешедшей в `awaiting_human`, печатает это состояние и адрес MR.

    Сценарий: задача случайного проекта в `merge_gate` со ссылкой на MR;
    `watch.cmd_watch(["--tasks", id, "--until", "awaiting_human"])`.
    Пауза опроса подменена (`patch_sleep`): первая пауза переводит задачу
    в `awaiting_human`, следующая итерация видит смену и завершает
    команду по `--until`. Вывод содержит `awaiting_human` и `mr_url`.
    Реального ожидания нет.

    Ловит мутацию: `watch` не выводит ссылку MR при переходе задачи в
    `awaiting_human` — адреса в выводе нет.
    """
    sc = scenario(seed)
    note = f"зерно: {seed}; проект {sc['project']}"
    task_id = new_task(sc["project"], "merge_gate", sc)
    calls = []

    def sleep(_seconds):
        calls.append(_seconds)
        if len(calls) > 3:
            raise RuntimeError("watch не завершился по --until")
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (STATE, task_id))
        conn.commit()

    with patch_sleep(watch, sleep):
        out = capture(watch.cmd_watch, ["--tasks", task_id, "--until", STATE])
    assert STATE in out, f"{note}: {out}"
    assert sc["url"] in out, f"{note}: ссылки MR нет: {out}"
