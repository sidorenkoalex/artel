"""Команда `board --project <имя> [--json | --md | --html]`: вывод модели
доски проекта, повторяемость, только чтение и без сети, виды из одной
модели, отказ на неизвестном проекте, `waiting_on` из очереди зон, догон
таблицы внешних ссылок на старой БД.

Группа: долгоживущий
Красен до реализации: команды `board` и `link` в `artel.py` нет («Неизвестная команда»), таблицы `external_refs` нет, у карточек модели нет поля `refs`; модуль `orchestrator/board.py` придёт в ветку только подтяжкой main с Э1.

Держит связку «команда CLI `artel.py` — модель доски — БД»: сценарий
идёт через `artel.main()` в лёгкой песочнице переходов
(`light_transition`), задачи заводятся `store.insert_task`, эпики и
привязка — командой `epic`, ссылки — командой `link`. Проверка «без
сети» идёт в песочнице `initialized_tmp_root`, где git не подменён:
сетевой вызов git любым путём доходит до `subprocess.run`/`Popen` и
виден подмене вместе с `socket`. Элементы `refs` и
строки `external_refs` сверяются по значениям (система, ключ): имена их
полей SPEC не задаёт. Проект, названия, состояния, системы и ключи ссылок
порождаются модулем `random` при каждом запуске; зерно печатается и
входит в текст провала.
"""
import contextlib
import importlib
import io
import json
import random
import socket
import subprocess
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, idgen, store, zone_lock
from tests.sandbox import declare_target

OTHER_PROJECTS = ("vega", "orion", "lyra", "draco")
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук", "Кедр", "Пихта")
SYSTEMS = ("kaiten", "jira", "youtrack", "gitlab-issue", "redmine")
ROLE_STATES = ("spec_writing", "tests_writing", "in_dev", "review")
NETWORK_GIT = ("fetch", "push", "ls-remote")
VIEWS = ("--json", "--md", "--html")


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


def cli(*args: str) -> tuple[str, str, int]:
    """`artel.py <args>`: (stdout, stderr вместе с текстом выхода, код)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code or 0
            if isinstance(code, str):
                err.write(f"\n{code}")
                code = 1
    return out.getvalue(), err.getvalue(), code


def words(stand, count: int = 2) -> str:
    return " ".join(stand.rng.sample(WORDS, count))


def epics() -> dict:
    return {r["id"]: dict(r) for r in store.db().execute("SELECT * FROM epics")}


def epic_new(stand, project: str) -> str:
    before = set(epics())
    out, err, code = cli("epic", "new", project, f"Эпик {words(stand)}",
                         "--goal", f"Цель {words(stand, 3)}")
    added = set(epics()) - before
    assert len(added) == 1, note(stand, f"предпосылка: epic new ({code}):\n{out}{err}")
    return added.pop()


def insert_task(stand, project: str, state: str = "in_dev", *,
                epic: str | None = None, title: str | None = None) -> str:
    """Задача проекта: заводится в `in_dev`, привязывается `epic add`, затем
    получает `state`."""
    task_id = idgen.new_task_id()
    conn = store.db()
    store.insert_task(conn, task_id, title or f"Задача {words(stand)}", "in_dev",
                      f"task/{task_id.lower()}-x", project,
                      config.DEFAULT_BUDGET_USD)
    if epic is not None:
        out, err, code = cli("epic", "add", epic, task_id)
        assert store.get_task(conn, task_id)["epic_id"] == epic, note(
            stand, f"предпосылка: epic add ({code}):\n{out}{err}")
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()
    return task_id


def ref_key(stand) -> str:
    return f"{stand.rng.choice(['', 'ABC-', 'T'])}{stand.rng.randrange(10, 10 ** 6)}"


def link(stand, kind: str, obj: str, system: str, key: str) -> None:
    out, err, code = cli("link", kind, obj, system, key)
    assert code == 0, note(stand, f"предпосылка: link {kind} {obj} {system} "
                                  f"{key} ({code}):\n{out}{err}")


def parse_json(stand, text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    assert start >= 0 and end > start, note(stand, f"в выводе нет JSON:\n{text}")
    return json.loads(text[start:end + 1])


def board_json(stand, project: str) -> dict:
    out, err, code = cli("board", "--project", project, "--json")
    assert code == 0, note(stand, f"board --json ({code}):\n{out}{err}")
    return parse_json(stand, out)


def card(stand, built: dict, task_id: str) -> dict:
    found = [c for c in built["cards"] if c.get("task") == task_id]
    assert len(found) == 1, note(stand, f"карточек {task_id}: {len(found)}")
    return found[0]


def has_ref(refs, system: str, key: str) -> bool:
    return any(system in ref.values() and key in ref.values() for ref in refs)


def populated(stand, project: str) -> dict:
    """Эпик и задачи проекта, у одной задачи две ссылки, у эпика — одна."""
    epic_id = epic_new(stand, project)
    tasks = [insert_task(stand, project, stand.rng.choice(ROLE_STATES),
                         epic=stand.rng.choice([epic_id, None]))
             for _ in range(stand.rng.randint(2, 4))]
    linked = stand.rng.choice(tasks)
    systems = stand.rng.sample(SYSTEMS, 2)
    refs = [(system, ref_key(stand)) for system in systems]
    for system, key in refs:
        link(stand, "task", linked, system, key)
    link(stand, "epic", epic_id, stand.rng.choice(SYSTEMS), ref_key(stand))
    return {"epic": epic_id, "tasks": tasks, "linked": linked, "refs": refs}


class SharedDb:
    """Подмена `store.db`: одно измеряемое соединение на весь прогон."""

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


# --- AC-1 ---

def test_ac1_json_carries_top_fields_and_card_fields(stand):
    """Проект с эпиком, задачами и ссылками: `board --project <проект> --json` печатает словарь с `schema_version`, `columns`, `epics`, `cards`; каждая карточка несёт `waiting_on` и `refs`, карточка задачи со ссылками — обе её ссылки.

    Ловит мутацию: `--json` печатает только список карточек (без
    `schema_version`/`epics`) или карточки без `refs`/`waiting_on` —
    ключа в словаре нет; ссылки задачи в карточку не попадают.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    fixture = populated(stand, project)
    built = board_json(stand, project)
    assert {"schema_version", "columns", "epics", "cards"} <= set(built), note(
        stand, f"ключи {sorted(built)}")
    assert {c.get("task") for c in built["cards"]} >= set(fixture["tasks"]), note(
        stand, f"карточки {built['cards']}")
    for item in built["cards"]:
        assert {"waiting_on", "refs"} <= set(item), note(stand, f"карточка {item}")
    refs = card(stand, built, fixture["linked"])["refs"]
    for system, key in fixture["refs"]:
        assert has_ref(refs, system, key), note(stand, f"нет {system}:{key} в {refs}")


# --- AC-2 ---

def test_ac2_two_json_runs_are_equal_but_generated_at(stand):
    """Два `board --json` одного проекта без изменений БД между ними дают равные словари без `generated_at`; у одной карточки фикстуры две ссылки.

    Ловит мутацию: в вывод попадает отметка момента вызова помимо
    `generated_at` (время чтения ссылок `datetime.now()` в элементе
    `refs` или в карточке) — два вывода различаются; `board` пишет
    запись журнала о показе — `last_event_at` второй выдачи иной.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    fixture = populated(stand, project)
    first = board_json(stand, project)
    second = board_json(stand, project)
    assert len(card(stand, first, fixture["linked"])["refs"]) >= 2, note(
        stand, f"предпосылка: две ссылки у {fixture['linked']}")
    first.pop("generated_at", None)
    second.pop("generated_at", None)
    assert first == second, note(stand, f"{first}\n!=\n{second}")


# --- AC-3 ---

@pytest.mark.parametrize("view", VIEWS)
def test_ac3_board_does_not_change_db(stand, view):
    """`board` каждого вида на подменённом измеряемом `store.db()`: команда работает через это соединение, `total_changes` его до и после вызова равны.

    Ловит мутацию: `board` пишет в БД — запись журнала «доска показана»
    (`store.journal`), кэш модели или догон ссылок вставкой строки — число
    изменений соединения растёт.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    populated(stand, project)
    conn = store.db()
    shared = SharedDb(conn)
    before = conn.total_changes
    with mock.patch.object(store, "db", shared):
        out, err, code = cli("board", "--project", project, view)
    assert code == 0, note(stand, f"board {view} ({code}):\n{out}{err}")
    assert shared.opened >= 1, note(stand, "board не открыл store.db()")
    assert conn.total_changes - before == 0, note(
        stand, f"board {view}: изменений {conn.total_changes - before}")


class NetworkTrace:
    """Обращения к сети за прогон: создание соединения `socket` и сетевые
    подкоманды git (`fetch`/`push`/`ls-remote`) запуском процесса —
    `subprocess.run` и `subprocess.Popen`, через которые идёт любой
    git-вызов песочницы `initialized_tmp_root` (git в ней не подменён)."""

    def __init__(self):
        self.calls: list = []

    def record(self, where: str, args) -> None:
        flat = [str(a) for a in (args if isinstance(args, (list, tuple)) else [args])]
        nested = []
        for item in flat:
            nested.extend(item.split())
        if where == "socket" or any(a in NETWORK_GIT for a in nested):
            self.calls.append((where, flat))

    @contextlib.contextmanager
    def active(self):
        real_run = subprocess.run
        real_popen = subprocess.Popen

        def run(*args, **kwargs):
            self.record("subprocess.run", args[0] if args else kwargs.get("args"))
            return real_run(*args, **kwargs)

        def popen(*args, **kwargs):
            self.record("subprocess.Popen", args[0] if args else kwargs.get("args"))
            return real_popen(*args, **kwargs)

        def connect(*args, **kwargs):
            self.record("socket", args)
            raise OSError("сеть запрещена сценарием")

        with mock.patch.object(subprocess, "run", run), \
                mock.patch.object(subprocess, "Popen", popen), \
                mock.patch.object(socket, "create_connection", connect), \
                mock.patch.object(socket.socket, "connect", connect), \
                mock.patch.object(socket.socket, "connect_ex", connect):
            yield self


@pytest.fixture
def plain(initialized_tmp_root):
    """Песочница без подмены git (`initialized_tmp_root`): сетевой вызов git
    любым путём доходит до запуска процесса и виден `NetworkTrace`."""
    initialized_tmp_root.seed = random.randrange(1 << 30)
    print(f"зерно: {initialized_tmp_root.seed}")
    initialized_tmp_root.rng = random.Random(initialized_tmp_root.seed)
    initialized_tmp_root.other = initialized_tmp_root.rng.choice(OTHER_PROJECTS)
    declare_target(initialized_tmp_root.other)
    return initialized_tmp_root


@pytest.mark.parametrize("command", [["board", "--json"], ["board", "--md"],
                                     ["board", "--html"], ["report"]])
def test_ac3_board_and_report_do_not_touch_network(plain, command):
    """`board` каждого вида и `report` при подменённых `socket` и запуске процессов: за прогон ни одного создания соединения и ни одного git `fetch`/`push`/`ls-remote`, команда завершается успешно.

    Ловит мутацию: перед построением модели `board`/`report` освежает пин
    `git fetch origin` или сверяет ссылку документов `git ls-remote`, либо
    читает трекер по URL ссылки (`urllib` → `socket.create_connection`) —
    обращение попадёт в журнал подмены.
    """
    stand = plain
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    populated(stand, project)
    args = list(command)
    if args[0] == "board":
        args[1:1] = ["--project", project]
    with NetworkTrace().active() as trace:
        out, err, code = cli(*args)
    assert code == 0, note(stand, f"{' '.join(args)} ({code}):\n{out}{err}")
    assert trace.calls == [], note(stand, f"{' '.join(args)}: сеть {trace.calls}")


# --- AC-4 ---

def test_ac4_md_and_html_are_built_from_the_model(stand):
    """Подмена `board().build_model` меняет название карточки: вывод `board --md` и `board --html` несёт подменённое название, настоящего нет.

    Ловит мутацию: `--md` или `--html` строится прямым чтением строк
    `tasks` (`store.project_tasks`) мимо модели — на выводе остаётся
    настоящее название.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    real_title = f"Настоящее {words(stand, 3)}"
    task_id = insert_task(stand, project, stand.rng.choice(ROLE_STATES),
                          title=real_title)
    marker = f"Подменённое{stand.rng.randrange(10 ** 6, 10 ** 7)}"
    real_build = board().build_model

    def fake_build(conn, target, *args, **kwargs):
        built = real_build(conn, target, *args, **kwargs)
        for item in built["cards"]:
            if item["task"] == task_id:
                item["title"] = marker
        return built

    with mock.patch.object(board(), "build_model", fake_build):
        shown = {view: cli("board", "--project", project, view)
                 for view in ("--md", "--html")}
    for view, (out, err, code) in shown.items():
        assert code == 0, note(stand, f"board {view} ({code}):\n{out}{err}")
        assert marker in out, note(stand, f"board {view} не из модели:\n{out}")
        assert real_title not in out, note(stand, f"board {view}:\n{out}")


def test_ac4_default_view_equals_md(stand):
    """`board --project <проект>` без флага вида печатает ровно то же, что `board --project <проект> --md` (часы `store.now` остановлены на оба вызова).

    Ловит мутацию: без флага печатается JSON или HTML (вид по умолчанию
    не `--md`) — тексты различаются.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    populated(stand, project)
    with mock.patch.object(store, "now", lambda: "2026-01-02 03:04:05Z"):
        default = cli("board", "--project", project)
        md = cli("board", "--project", project, "--md")
    assert md[2] == 0, note(stand, f"board --md ({md[2]}):\n{md[0]}{md[1]}")
    assert default == md, note(stand, f"без флага:\n{default[0]}\n--md:\n{md[0]}")


def test_ac4_unknown_project_refused_with_its_name(stand):
    """`board --project <имя>` проекта, которого нет в `targets.yaml` и у которого нет задач и эпиков в БД, отказывает ненулевым кодом с причиной, называющей проект.

    Ловит мутацию: неизвестный проект печатает пустую модель с кодом 0
    (проверки нет); отказ без имени проекта в тексте.
    """
    ghost = f"ghost{stand.rng.randrange(10 ** 6)}"
    out, err, code = cli("board", "--project", ghost,
                         stand.rng.choice(["--json", "--md", "--html"]))
    assert code != 0, note(stand, f"board {ghost} не отказал:\n{out}{err}")
    assert ghost in out + err, note(stand, f"отказ без имени проекта:\n{out}{err}")


# --- AC-14 (board) ---

def test_ac14_board_json_waiting_on_from_zone_queue(stand):
    """Задача `in_dev`, которой `zone_lock.queue_wait` сообщает ожидание зоны: в `board --json` её карточка несёт `waiting_on == "dependency"`, соседняя `in_dev` без ожидания — `role`.

    Ловит мутацию: `board` строит модель с выключенным расчётом
    `waiting_on` (как для `report`) — ожидание зоны не спрашивается и
    карточка не получает `dependency`.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    waiting = insert_task(stand, project, "in_dev")
    free = insert_task(stand, project, "in_dev")
    wait = zone_lock.QueueWait(f"orchestrator/t_zone_{stand.rng.randrange(99)}.py",
                               "занята", 2, 2, False)

    def queue_wait(conn, task_id, t=None):
        return wait if task_id == waiting else None

    with mock.patch.object(zone_lock, "queue_wait", queue_wait):
        built = board_json(stand, project)
    assert card(stand, built, waiting)["waiting_on"] == "dependency", note(
        stand, f"{card(stand, built, waiting)}")
    assert card(stand, built, free)["waiting_on"] == "role", note(
        stand, f"{card(stand, built, free)}")


# --- AC-15 ---

def test_ac15_old_db_gets_external_refs_on_open(stand):
    """БД без таблицы `external_refs` (снята `DROP TABLE`): следующее `store.db()` её создаёт; `board --json` печатает карточки с пустыми `refs`; `link` записывает ссылку в таблицу.

    Ловит мутацию: таблица заводится только схемой `init`, а догон схемы
    при открытии (`migrate`) её не знает — `board` и `link` падают
    «no such table: external_refs».
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    task_id = insert_task(stand, project, stand.rng.choice(ROLE_STATES))
    conn = store.db()
    conn.execute("DROP TABLE IF EXISTS external_refs")
    conn.commit()
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                        "name='external_refs'").fetchone() is None

    fresh = store.db()
    assert fresh.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                         "name='external_refs'").fetchone() is not None, note(
        stand, "store.db() не создал external_refs")
    built = board_json(stand, project)
    assert all(item["refs"] == [] for item in built["cards"]), note(
        stand, f"refs не пусты: {built['cards']}")
    system, key = stand.rng.choice(SYSTEMS), ref_key(stand)
    link(stand, "task", task_id, system, key)
    rows = [tuple(r) for r in store.db().execute("SELECT * FROM external_refs")]
    assert any(task_id in r and system in r and key in r for r in rows), note(
        stand, f"link не записал: {rows}")
