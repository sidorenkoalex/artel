"""`report` из модели доски: группы эпиков внутри колонки, плитка из
карточки модели, поля плитки в карточке, постоянное число запросов к
`steps` и одно соединение за прогон.

Группа: долгоживущий
Красен до реализации: `report` строит доску из строк `store.all_tasks` мимо `board.build_model` — групп эпиков на доске нет, подмена модели доску не меняет; у карточки модели нет полей `review_iters`/`escalated_from`/`project`; модуль `orchestrator/board.py` придёт в ветку только подтяжкой main с Э1.

Держит связку «БД — модель доски — HTML `report`»: задачи заводятся
`store.insert_task`, эпики и привязка — командой `epic` через
`artel.main()`, доска — раздел «Борд задач» файла `.artel/report.html`
после `report.cmd_report()`; колонка доски читается текстом без тегов.
Число запросов к `steps` считает обратный вызов трассировки соединения,
через которое идёт весь прогон (`store.db` подменён). Названия,
состояния, проекты и числа порождаются модулем `random` при каждом
запуске; зерно печатается и входит в текст провала.
"""
import collections
import contextlib
import html as html_lib
import importlib
import io
import random
import re
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, idgen, report, store, zone_lock
from tests.sandbox import declare_target

OTHER_PROJECTS = ("vega", "orion", "lyra", "draco")
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук", "Кедр", "Пихта")
ROLE_STATES = ("tests_writing", "in_dev", "review")
BOARD_HEAD = "<h2>Борд задач — состояния FSM</h2>"


# --- окружение сценария ---

@pytest.fixture
def stand(light_transition):
    """Лёгкая песочница переходов с зерном и вторым проектом."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    light_transition.other = light_transition.rng.choice(OTHER_PROJECTS)
    declare_target(light_transition.other)
    return light_transition


def board():
    """Модуль модели доски — импортом при вызове: модуль тестов обязан
    собираться и там, где модели ещё нет."""
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


def epic_new(stand, project: str, title: str) -> str:
    before = set(epics())
    out = cli("epic", "new", project, title, "--goal", f"Цель {words(stand, 3)}")
    added = set(epics()) - before
    assert len(added) == 1, note(stand, f"предпосылка: epic new:\n{out}")
    return added.pop()


def insert_task(stand, project: str, state: str, *, task_id: str | None = None,
                epic: str | None = None, title: str | None = None) -> str:
    """Задача проекта: заводится в `in_dev`, привязывается `epic add`, затем
    получает `state`."""
    task_id = task_id or idgen.new_task_id()
    conn = store.db()
    store.insert_task(conn, task_id, title or f"Задача {words(stand)}", "in_dev",
                      f"task/{task_id.lower()}-x", project,
                      config.DEFAULT_BUDGET_USD)
    if epic is not None:
        out = cli("epic", "add", epic, task_id)
        assert store.get_task(conn, task_id)["epic_id"] == epic, note(
            stand, f"предпосылка: epic add:\n{out}")
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()
    return task_id


def run_report() -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        report.cmd_report()
    return (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")


def board_section(page: str) -> str:
    start = page.index(BOARD_HEAD) + len(BOARD_HEAD)
    return page[start:page.index("</section>", start)]


def text_of(fragment: str) -> str:
    """Текст HTML без тегов, пробелы схлопнуты."""
    plain = html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"\s+", " ", plain).strip()


def columns(section: str) -> dict:
    """{состояние колонки: HTML колонки} доски."""
    chunks = section.split('<div class="col">')[1:]
    found = {}
    for chunk in chunks:
        head = re.search(r'class="state-tag">([^<]*)<', chunk)
        if head:
            found[html_lib.unescape(head.group(1))] = chunk
    return found


# --- AC-6 ---

def test_ac6_epic_groups_inside_column(stand):
    """Колонка с двумя эпиками и задачами без эпика: сначала группы эпиков по возрастанию id эпика — у каждой заголовок «<id эпика> <название>», под ним её карточки по возрастанию id задачи, — затем карточки без эпика по возрастанию id.

    Задачи первого эпика заведены в БД в порядке, обратном id; у задачи без
    эпика id меньше всех, у задачи второго эпика — меньше, чем у задач
    первого: порядок групп и карточек не совпадает ни с порядком
    заведения, ни со сквозным порядком id.

    Ловит мутацию: карточки группы идут в порядке заведения (`rowid`) или
    модели эпика `nodes`, а не по id; группы упорядочены по первой задаче,
    а не по id эпика; карточки без эпика идут раньше групп.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    state = stand.rng.choice(ROLE_STATES)
    titles = [f"Эпик {words(stand, 2)} {n}" for n in range(2)]
    made = [epic_new(stand, project, t) for t in titles]
    first, second = sorted(made)
    title = dict(zip(made, titles))
    ids = sorted(idgen.new_task_id() for _ in range(6))
    loose = [ids[0], ids[5]]
    second_tasks = [ids[1]]
    first_tasks = [ids[2], ids[3], ids[4]]
    for task_id in reversed(first_tasks):
        insert_task(stand, project, state, task_id=task_id, epic=first)
    insert_task(stand, project, state, task_id=second_tasks[0], epic=second)
    for task_id in stand.rng.sample(loose, 2):
        insert_task(stand, project, state, task_id=task_id)

    section = board_section(run_report())
    column = columns(section).get(state)
    assert column is not None, note(stand, f"нет колонки {state}:\n{section}")
    text = text_of(column)
    marks = [f"{first} {title[first]}", *first_tasks,
             f"{second} {title[second]}", *second_tasks, *loose]
    positions = [text.find(m) for m in marks]
    assert -1 not in positions, note(
        stand, f"нет {[m for m, p in zip(marks, positions) if p < 0]} в колонке:\n{text}")
    assert positions == sorted(positions), note(
        stand, f"порядок {sorted(marks, key=lambda m: text.find(m))}\n"
               f"ожидался {marks}")


# --- AC-7 ---

def test_ac7_report_tile_takes_values_from_model(stand):
    """Подмена `board().build_model` меняет у карточки название, состояние, `review_iters`, `escalated_from` и проект: доска `report` показывает подменённые значения, настоящих нет.

    Ловит мутацию: плитка `report` по-прежнему читает строку `tasks`
    (название, состояние, итерации ревью, эскалация, `target`) мимо
    модели — на доске остаются настоящие значения.
    """
    real_project = stand.other
    real_state, fake_state = stand.rng.sample(ROLE_STATES, 2)
    real_title = f"Настоящее {words(stand, 3)}"
    task_id = insert_task(stand, real_project, real_state, title=real_title)
    store.update_task(store.db(), task_id, review_iters=0)
    fake = {"title": f"Подменённое{stand.rng.randrange(10 ** 6, 10 ** 7)}",
            "state": fake_state,
            "review_iters": stand.rng.randrange(2, 9),
            "escalated_from": f"шаг{stand.rng.randrange(10 ** 4)}",
            "project": f"proj{stand.rng.randrange(10 ** 4)}"}
    real_build = board().build_model

    def fake_build(conn, project, *args, **kwargs):
        built = real_build(conn, project, *args, **kwargs)
        for item in built["cards"]:
            if item["task"] == task_id:
                item.update(fake)
        return built

    with mock.patch.object(board(), "build_model", fake_build):
        section = board_section(run_report())
    tile = [c for c in columns(section).items() if task_id in c[1]]
    assert [state for state, _ in tile] == [fake_state], note(
        stand, f"колонки задачи {[s for s, _ in tile]}:\n{section}")
    text = text_of(section)
    assert fake["title"] in text and real_title not in text, note(stand, text)
    assert f"Итерации ревью: {fake['review_iters']}/" in text, note(stand, text)
    assert f"Эскалация (из {fake['escalated_from']})" in text, note(stand, text)
    assert f"[ {fake['project']} ]" in text or f"[{fake['project']}]" in text, note(
        stand, text)
    assert real_project not in text, note(stand, f"настоящий проект:\n{text}")


# --- AC-8 ---

@pytest.mark.parametrize("escalated", [None, "in_dev", "review"])
def test_ac8_card_carries_tile_fields(stand, escalated):
    """Карточка модели несёт `review_iters`, `escalated_from` и `project` со значениями строки задачи (у `reviewed_iter` нарочно другое число).

    Ловит мутацию: `review_iters` карточки берётся из соседней колонки
    `reviewed_iter`; `escalated_from` не переносится (всегда `None`);
    `project` — константа артели вместо `target` задачи.
    """
    project = stand.other
    task_id = insert_task(stand, project, stand.rng.choice(ROLE_STATES))
    iters = stand.rng.randrange(1, 5)
    store.update_task(store.db(), task_id, review_iters=iters,
                      reviewed_iter=iters + stand.rng.randrange(1, 4),
                      escalated_from=escalated)
    built = board().build_model(store.db(), project)
    found = [c for c in built["cards"] if c["task"] == task_id]
    assert len(found) == 1, note(stand, f"карточек {task_id}: {len(found)}")
    item = found[0]
    assert (item.get("review_iters"), item.get("escalated_from"), item.get("project")) \
        == (iters, escalated, project), note(stand, f"карточка {item}")


# --- AC-14 (report) ---

class SharedDb:
    """Подмена `store.db`: одно соединение на весь прогон и счёт открытий."""

    def __init__(self, conn):
        self.conn = conn
        self.opened = 0

    def __call__(self):
        self.opened += 1
        return Borrowed(self.conn)


class Borrowed:
    """Соединение, которое вызывающий не может закрыть."""

    def __init__(self, conn):
        self.conn = conn

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def close(self) -> None:
        return None

    def __enter__(self):
        return self.conn.__enter__()

    def __exit__(self, *exc_info):
        return self.conn.__exit__(*exc_info)


@pytest.fixture
def counted(initialized_tmp_root):
    """Песочница без посеянных задач: состав набора задаёт сценарий."""
    initialized_tmp_root.seed = random.randrange(1 << 30)
    print(f"зерно: {initialized_tmp_root.seed}")
    initialized_tmp_root.rng = random.Random(initialized_tmp_root.seed)
    initialized_tmp_root.other = initialized_tmp_root.rng.choice(OTHER_PROJECTS)
    declare_target(initialized_tmp_root.other)
    return initialized_tmp_root


def seed_in_dev(stand, projects: list, zone: str) -> None:
    """Задачи `in_dev` с общей зоной и записью журнала — по одной на проект
    списка."""
    conn = store.db()
    for project in projects:
        task_id = insert_task(stand, project, "in_dev")
        store.update_task(conn, task_id, zones=zone)
        store.journal(conn, task_id, "operator", "created", "фикстура")


def counted_report(conn) -> dict:
    shared = SharedDb(conn)
    steps = []

    def trace(statement) -> None:
        if statement and re.search(r"\bfrom\s+steps\b", str(statement), re.I):
            steps.append(statement)

    with mock.patch.object(store, "db", shared), \
            mock.patch.object(store, "last_step_times",
                              wraps=store.last_step_times) as last, \
            mock.patch.object(zone_lock, "queue_wait",
                              wraps=zone_lock.queue_wait) as queue:
        conn.set_trace_callback(trace)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                report.cmd_report()
        finally:
            conn.set_trace_callback(None)
    per_project = collections.Counter(
        call.args[1] if len(call.args) > 1 else call.kwargs.get("project")
        for call in last.call_args_list)
    return {"steps": len(steps), "opened": shared.opened,
            "last": dict(per_project), "queue": queue.call_count}


def test_ac14_report_steps_queries_do_not_grow_with_tasks(counted):
    """`cmd_report` на 2 и на 7 задачах `in_dev` с общей зоной в тех же двух проектах: число запросов к `steps` одинаково, `store.last_step_times` — по одному разу на проект, `store.db()` открыт один раз за прогон, `zone_lock.queue_wait` не вызван.

    Ловит мутацию: `report` строит модели с расчётом `waiting_on` —
    `zone_lock.queue_wait` читает журнал на каждую карточку (запросов к
    `steps` на 7 задачах больше); `build_model` для `report` открывает своё
    `store.db()` (открытий два); модель строится на каждую задачу, а не на
    проект (`last_step_times` зовётся больше раза на проект).
    """
    stand = counted
    projects = [config.DEFAULT_TARGET, stand.other]
    zone = f"orchestrator/t_report_zone_{stand.rng.randrange(10 ** 6)}.py"
    seed_in_dev(stand, projects, zone)
    conn = store.db()
    small = counted_report(conn)
    extra = [stand.rng.choice(projects) for _ in range(5)]
    seed_in_dev(stand, extra, zone)
    assert len(store.all_tasks(conn)) == 7, note(stand, "предпосылка: 7 задач")
    large = counted_report(conn)

    want_last = {p: 1 for p in projects}
    for name, run in (("2 задачи", small), ("7 задач", large)):
        assert run["opened"] == 1, note(stand, f"{name}: store.db() {run['opened']} раз")
        assert run["queue"] == 0, note(stand, f"{name}: queue_wait {run['queue']} раз")
        assert run["last"] == want_last, note(stand, f"{name}: last_step_times {run['last']}")
    assert small["steps"] > 0, note(stand, "счётчик не увидел запросов к steps")
    assert small["steps"] == large["steps"], note(
        stand, f"запросов к steps: {small['steps']} и {large['steps']}")
