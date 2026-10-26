"""Эпик как сущность пульта: команды `epic new|edit|close|add|remove|show`,
`new --epic`/`--after`, отказы привязки, журнал и lease команд эпика,
взаимное исключение `epic close` и привязки.

Группа: долгоживущий
Красен до реализации: команды `epic` в `artel.py` нет («Неизвестная команда epic»), таблицы `epics` и колонки `tasks.epic_id` нет, `new` не знает флагов `--epic`/`--after`, а `fsm.STATES`/`fsm.TERMINAL_STATES` появятся только с мержем Э0.

Держит связку «команда CLI `artel.py` — БД — журнал — lease»: каждый
сценарий идёт через `artel.main()` в лёгкой песочнице переходов
(`light_transition`), состояние сверяется по строкам `tasks`, `epics`,
`steps`, `leases`. Ссылка документов задачи `refs/artifacts/<id>` в этой
песочнице пишется вызовом `update-ref` через `gitcmd.in_repo` — его
записывает хук `in_repo_handlers`. Проект эпика, названия, цели, конверт,
состояния задач и форма ссылки на задачу (полный id или префикс)
порождаются модулем `random` при каждом запуске; зерно печатается и
входит в текст провала.
"""
import contextlib
import io
import os
import random
import re
import socket
import sys
import threading
from unittest import mock

import pytest

from orchestrator import artel, config, fsm, idgen, lease, store
from tests.sandbox import declare_target

EPIC_ID = re.compile(r"E[0-9A-HJKMNP-TV-Z]{26}")
OTHER_PROJECTS = ("vega", "orion", "lyra", "draco")
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук", "Кедр", "Пихта")
LEASE_TAKEN = "lease взят"
FOREIGN_SESSION = "чужая-сессия-фикстуры"


# --- окружение сценария ---

@pytest.fixture
def stand(light_transition):
    """Лёгкая песочница переходов: зерно, второй проект в `targets.yaml`,
    запись вызовов `update-ref` ссылок документов."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    light_transition.other = light_transition.rng.choice(OTHER_PROJECTS)
    declare_target(light_transition.other)
    light_transition.artifact_refs = []
    light_transition.in_repo_handlers.append(
        artifact_ref_recorder(light_transition.artifact_refs))
    return light_transition


def artifact_ref_recorder(log: list):
    """Хук `gitcmd.in_repo` песочницы: запоминает ссылки `refs/artifacts/…`,
    которые пишет `update-ref`, и отдаёт вызов дальше (`None`)."""
    def handler(repo, *args):
        if "update-ref" in args:
            log.extend(a for a in args if str(a).startswith("refs/artifacts/"))
        return None
    return handler


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def cli(*args: str) -> tuple[str, int]:
    """`artel.py <args>`: (весь вывод вместе с текстом выхода, код выхода)."""
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


def words(stand, count: int = 2) -> str:
    return " ".join(stand.rng.sample(WORDS, count))


def epics() -> dict:
    return {r["id"]: dict(r) for r in store.db().execute("SELECT * FROM epics")}


def epic_new(stand, project: str, *, envelope=None) -> str:
    """Эпик через `epic new`; id — единственная новая строка `epics`."""
    before = set(epics())
    args = ["epic", "new", project, f"Эпик {words(stand)}",
            "--goal", f"Цель {words(stand, 3)}"]
    if envelope is not None:
        args += ["--envelope", str(envelope)]
    out, code = cli(*args)
    added = set(epics()) - before
    assert len(added) == 1, note(stand, f"epic new не завёл эпик ({code}):\n{out}")
    return added.pop()


def insert_task(stand, project: str = config.DEFAULT_TARGET,
                state: str = "in_dev") -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, f"Задача {words(stand)}", state,
                      f"task/{task_id.lower()}-x", project,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def set_state(task_id: str, state: str) -> None:
    conn = store.db()
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()


def task(task_id: str):
    return store.get_task(store.db(), task_id)


def task_ids() -> set:
    return {r["id"] for r in store.all_tasks(store.db())}


def epic_of(task_id: str):
    return task(task_id)["epic_id"]


def deps(task_id: str) -> list[str]:
    return re.findall(r"[0-9A-Z]+", task(task_id)["merge_after"] or "")


def last_step_id() -> int:
    return store.db().execute(
        "SELECT COALESCE(MAX(id), 0) FROM steps").fetchone()[0]


def steps_since(since: int) -> list[dict]:
    return [dict(r) for r in store.db().execute(
        "SELECT * FROM steps WHERE id > ? ORDER BY id", (since,))]


def snapshot() -> dict:
    conn = store.db()
    return {table: [tuple(r) for r in conn.execute(
        f"SELECT * FROM {table} ORDER BY rowid")]
        for table in ("tasks", "epics", "steps", "leases")}


def tz_file(stand, *lines: str) -> str:
    path = stand.root / f"tz-{stand.rng.randrange(1 << 30)}.md"
    body = "".join(f"{line}\n\n" for line in lines)
    path.write_text(f"Источник: фикстура {stand.seed}.\n\nТребуется:\n"
                    f"1. Фикстура {words(stand)}.\n\n{body}", encoding="utf-8")
    return str(path)


def new_cli(stand, *flags: str, tz_lines=()) -> tuple[str, int, set]:
    """`new "<название>" --tz <файл> --target artel <flags>`: (вывод, код,
    id заведённых задач)."""
    before = task_ids()
    out, code = cli("new", f"Новая {words(stand)}", "--tz",
                    tz_file(stand, *tz_lines), "--target",
                    config.DEFAULT_TARGET, *flags)
    return out, code, task_ids() - before


def unique_prefix(stand, task_id: str) -> str:
    """Собственный префикс `task_id`, однозначный среди задач БД."""
    others = [i for i in task_ids() if i != task_id]
    shortest = next(n for n in range(1, len(task_id))
                    if not any(o.startswith(task_id[:n]) for o in others))
    return task_id[:stand.rng.randint(shortest, len(task_id) - 1)]


def non_terminal_states() -> list[str]:
    return [s for s in fsm.STATES if s not in fsm.TERMINAL_STATES]


def bound(stand, epic_id: str, state: str = "in_dev",
          project: str = config.DEFAULT_TARGET) -> str:
    """Задача проекта `project`, привязанная к эпику `epic add`, затем
    переведённая в `state`."""
    task_id = insert_task(stand, project)
    out, code = cli("epic", "add", epic_id, task_id)
    assert epic_of(task_id) == epic_id, note(
        stand, f"предпосылка: epic add не привязал ({code}):\n{out}")
    set_state(task_id, state)
    return task_id


def closed_epic(stand) -> str:
    """Эпик артели, закрытый `epic close` (одна задача в `done`)."""
    epic_id = epic_new(stand, config.DEFAULT_TARGET)
    bound(stand, epic_id, "done")
    out, code = cli("epic", "close", epic_id, f"Итог {words(stand)}")
    assert epics()[epic_id]["state"] == "closed", note(
        stand, f"предпосылка: epic close не закрыл ({code}):\n{out}")
    return epic_id


# --- AC-1 ---

@pytest.mark.parametrize("with_envelope", [True, False])
def test_ac1_epic_new_creates_open_epic_with_journal(stand, with_envelope):
    """`epic new <проект> "<название>" --goal … [--envelope N]`: строка `epics` этого проекта, `open`, название, цель, конверт N либо пусто; id — `E` и 26 знаков алфавита ULID; запись журнала с id эпика.

    Ловит мутацию: конверт пишется нулём, а не пустым, когда флага нет
    (или флаг игнорируется — конверт пуст при `--envelope N`); id эпика
    берётся `idgen.new_task_id()` без приставки `E`; состояние нового
    эпика не `open`; команда не пишет запись журнала.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    title, goal = f"Эпик {words(stand, 3)}", f"Цель: {words(stand, 4)}"
    envelope = round(stand.rng.uniform(5, 300), 2) if with_envelope else None
    args = ["epic", "new", project, title, "--goal", goal]
    if envelope is not None:
        args += ["--envelope", str(envelope)]
    before, since = set(epics()), last_step_id()

    out, code = cli(*args)

    added = set(epics()) - before
    assert len(added) == 1, note(stand, f"новых эпиков {len(added)} ({code}):\n{out}")
    epic_id = added.pop()
    row = epics()[epic_id]
    assert EPIC_ID.fullmatch(epic_id), note(stand, f"id эпика {epic_id!r}")
    assert (row["project"], row["state"], row["title"], row["goal"]) == (
        project, "open", title, goal), note(stand, f"строка эпика {row}")
    if envelope is None:
        assert row["envelope_usd"] is None, note(stand, f"конверт {row['envelope_usd']!r}")
    else:
        assert row["envelope_usd"] == pytest.approx(envelope), note(
            stand, f"конверт {row['envelope_usd']!r} ≠ {envelope}")
    assert any(r["task_id"] == epic_id for r in steps_since(since)), note(
        stand, f"нет записи журнала с id эпика: {steps_since(since)}")


# --- AC-3 ---

def test_ac3_epic_edit_changes_title_and_goal(stand):
    """`epic edit <id> --title … --goal …` меняет название и цель эпика в БД и пишет запись журнала эпика; соседний эпик не меняется.

    Ловит мутацию: `--goal` пишется в `title` (или наоборот); правка
    идёт без WHERE по id — соседний эпик получает те же значения;
    команда меняет строку, но не пишет журнал.
    """
    epic_id = epic_new(stand, stand.other)
    neighbour = epic_new(stand, stand.other)
    neighbour_before = epics()[neighbour]
    title, goal = f"Новое {words(stand, 3)}", f"Новая цель {words(stand, 3)}"
    since = last_step_id()

    out, code = cli("epic", "edit", epic_id, "--title", title, "--goal", goal)

    row = epics()[epic_id]
    assert (row["title"], row["goal"]) == (title, goal), note(
        stand, f"после edit: {row} ({code}):\n{out}")
    assert epics()[neighbour] == neighbour_before, note(stand, "соседний эпик изменён")
    assert any(r["task_id"] == epic_id for r in steps_since(since)), note(
        stand, "нет записи журнала edit")


# --- AC-4 ---

def test_ac4_epic_add_and_remove_with_journal(stand):
    """`epic add` пишет `tasks.epic_id` задачи того же проекта, `epic remove` задачи в неокончательном состоянии делает его пустым; у каждой операции запись журнала эпика.

    Ловит мутацию: `epic remove` отказывает задаче в неокончательном
    состоянии (разрешает только окончательные); `epic add` пишет
    `epic_id` другой задаче (перепутаны аргументы); операция меняет
    строку без записи журнала.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    epic_id = epic_new(stand, project)
    state = stand.rng.choice(non_terminal_states())
    target_task = insert_task(stand, project, state)
    bystander = insert_task(stand, project, state)

    since = last_step_id()
    out, code = cli("epic", "add", epic_id, target_task)
    assert epic_of(target_task) == epic_id, note(stand, f"add ({code}):\n{out}")
    assert epic_of(bystander) is None, note(stand, "add задел соседнюю задачу")
    assert any(r["task_id"] == epic_id for r in steps_since(since)), note(
        stand, "нет записи журнала add")

    since = last_step_id()
    out, code = cli("epic", "remove", epic_id, target_task)
    assert not epic_of(target_task), note(
        stand, f"remove в состоянии {state} ({code}):\n{out}")
    assert any(r["task_id"] == epic_id for r in steps_since(since)), note(
        stand, "нет записи журнала remove")


# --- AC-5, AC-6: отказы привязки ---

def assert_new_epic_refused(stand, epic_id: str) -> None:
    """`new --epic <id>` отказан: задачи не заведено, ссылка документов не
    писалась."""
    refs_before = list(stand.artifact_refs)
    out, code, created = new_cli(stand, "--epic", epic_id)
    assert created == set(), note(stand, f"new завёл {created} ({code}):\n{out}")
    assert stand.artifact_refs == refs_before, note(
        stand, f"при отказе писалась ссылка документов: "
               f"{stand.artifact_refs[len(refs_before):]}\n{out}")
    assert out.strip(), note(stand, "отказ new без причины")
    out, code, created = new_cli(stand)
    assert [f"refs/artifacts/{t}" for t in created] == stand.artifact_refs[
        len(refs_before):], note(
        stand, f"предпосылка: хук не видит ссылку документов new ({code}):\n{out}")


def test_ac5_binding_to_other_project_epic_refused(stand):
    """Эпик другого проекта: `epic add` задачи артели и `new --target artel --epic` отказывают с причиной; `epic_id` не записан, задача не заведена, `update-ref refs/artifacts/…` не вызывался.

    Ловит мутацию: проект при привязке не сверяется (задача чужого
    проекта входит в эпик); проверка эпика у `new --epic` стоит после
    создания ссылки документов `refs/artifacts/<id>` (отказ оставляет
    ссылку без строки задачи).
    """
    epic_id = epic_new(stand, stand.other)
    task_id = insert_task(stand, config.DEFAULT_TARGET,
                          stand.rng.choice(non_terminal_states()))

    out, code = cli("epic", "add", epic_id, task_id)
    assert epic_of(task_id) is None, note(stand, f"add чужого проекта ({code}):\n{out}")
    assert out.strip(), note(stand, "отказ add без причины")

    assert_new_epic_refused(stand, epic_id)


def test_ac6_binding_to_closed_epic_refused(stand):
    """Закрытый эпик своего проекта: `epic add` и `new --epic` отказывают с причиной; `epic_id` не записан, задача не заведена, ссылка документов не писалась.

    Ловит мутацию: привязка проверяет существование эпика, но не его
    состояние (`closed` принимает задачу); у `new --epic` проверка
    состояния идёт только в транзакции вставки — после `update-ref`
    ссылки документов.
    """
    epic_id = closed_epic(stand)
    task_id = insert_task(stand, config.DEFAULT_TARGET,
                          stand.rng.choice(non_terminal_states()))

    out, code = cli("epic", "add", epic_id, task_id)
    assert epic_of(task_id) is None, note(stand, f"add в закрытый ({code}):\n{out}")
    assert out.strip(), note(stand, "отказ add без причины")

    assert_new_epic_refused(stand, epic_id)


# --- AC-7…AC-10, AC-32: new с --epic/--after ---

def test_ac7_new_with_epic_and_after(stand):
    """`new … --target artel --epic E --after <id>`: задача заведена с `epic_id` эпика и `merge_after`, равным полному id.

    Ловит мутацию: `--after` разбирается, но не записывается в
    `merge_after`; `--epic` принят флагом, но `epic_id` строки задачи
    пуст; значение `--after` принято названием задачи.
    """
    epic_id = epic_new(stand, config.DEFAULT_TARGET)
    dependency = insert_task(stand)

    out, code, created = new_cli(stand, "--epic", epic_id, "--after", dependency)

    assert len(created) == 1, note(stand, f"задач заведено {created} ({code}):\n{out}")
    new_id = created.pop()
    assert epic_of(new_id) == epic_id, note(stand, f"epic_id {epic_of(new_id)!r}")
    assert deps(new_id) == [dependency], note(stand, f"merge_after {deps(new_id)}")


@pytest.mark.parametrize("with_epic", [True, False])
def test_ac8_after_unknown_task_refused(stand, with_epic):
    """`new … --after <id>` с id, которого нет среди задач: отказ, задача не заведена.

    Предпосылка — тот же вызов с id существующей задачи заводит задачу:
    отказ относится к зависимости, а не к флагу.

    Ловит мутацию: `--after` записывается без `merge_after.check` —
    несуществующая зависимость принимается.
    """
    lead = ["--epic", epic_new(stand, config.DEFAULT_TARGET)] if with_epic else []
    out, code, created = new_cli(stand, *lead, "--after", insert_task(stand))
    assert len(created) == 1, note(
        stand, f"предпосылка: new с существующей зависимостью ({code}):\n{out}")

    out, code, created = new_cli(stand, *lead, "--after", idgen.new_task_id())
    assert created == set(), note(stand, f"new завёл {created} ({code}):\n{out}")


def test_ac9_epic_id_is_not_a_task_id(stand):
    """`new … --after <id эпика>` — отказ с причиной `merge_after.check` о форме элемента, задача не заведена; `show <id эпика>` — «Задача <id> не найдена».

    Ловит мутацию: разрешение id задачи ищет и в `epics` — `--after`
    принимает эпик зависимостью, `show` показывает эпик; для id эпика
    введён особый текст отказа вместо причины существующей проверки.
    """
    epic_id = epic_new(stand, config.DEFAULT_TARGET)

    out, code, created = new_cli(stand, "--after", epic_id)
    assert created == set(), note(stand, f"new завёл {created} ({code}):\n{out}")
    reason = (f"merge_after: элемент «{epic_id}» не в формате id задачи "
              f"(полный id или его префикс)")
    assert reason in out, note(stand, f"нет причины «{reason}» в:\n{out}")

    out, code = cli("show", epic_id)
    assert f"Задача {epic_id} не найдена" in out, note(stand, f"show:\n{out}")


def test_ac10_tz_order_line_and_after_are_merged(stand):
    """ТЗ «Порядок: после X» и `--after Y`: `merge_after = X, Y`; несуществующий Y или несуществующий X — отказ, задача не заведена.

    Ловит мутацию: `--after` заменяет значение строки ТЗ (или строка
    ТЗ — значение `--after`); объединение без проверки элементов
    второго источника — непрошедший Y или X принимается.
    """
    x, y = insert_task(stand), insert_task(stand)
    order = f"Порядок: после {x}"

    out, code, created = new_cli(stand, "--after", y, tz_lines=[order])
    assert len(created) == 1, note(stand, f"задач {created} ({code}):\n{out}")
    assert deps(created.pop()) == [x, y], note(stand, out)

    out, code, created = new_cli(stand, "--after", idgen.new_task_id(),
                                 tz_lines=[order])
    assert created == set(), note(stand, f"несуществующий Y принят:\n{out}")

    out, code, created = new_cli(
        stand, "--after", y, tz_lines=[f"Порядок: после {idgen.new_task_id()}"])
    assert created == set(), note(stand, f"несуществующий X принят:\n{out}")


def test_ac32_prefix_dedup_and_after_without_epic(stand):
    """ТЗ «Порядок: после X» и `--after <префикс X>`: `merge_after` — один полный X; `new --after <id>` без `--epic` — задача без эпика с полным id в `merge_after`.

    Ловит мутацию: дедупликация по строке, а не по полному id — `check`
    отказывает на повторе (или пишет X дважды); префикс пишется в
    `merge_after` как есть; `--after` без `--epic` игнорируется.
    """
    x = insert_task(stand)
    out, code, created = new_cli(stand, "--after", unique_prefix(stand, x),
                                 tz_lines=[f"Порядок: после {x}"])
    assert len(created) == 1, note(stand, f"задач {created} ({code}):\n{out}")
    assert deps(created.pop()) == [x], note(stand, out)

    dependency = insert_task(stand)
    ref = stand.rng.choice([dependency, unique_prefix(stand, dependency)])
    out, code, created = new_cli(stand, "--after", ref)
    assert len(created) == 1, note(stand, f"задач {created} ({code}):\n{out}")
    new_id = created.pop()
    assert epic_of(new_id) is None, note(stand, f"epic_id {epic_of(new_id)!r}")
    assert deps(new_id) == [dependency], note(stand, f"{ref!r} → {deps(new_id)}")


# --- AC-15 ---

def test_ac15_close_refused_while_task_not_terminal(stand):
    """`epic close` при задаче эпика не в `fsm.TERMINAL_STATES`: отказ, текст называет её id, эпик остаётся `open` без итога.

    Ловит мутацию: проверка смотрит только на `done` (задача в
    `escalated`/`in_dev` не мешает закрытию) или только на первую задачу
    эпика; отказ не перечисляет задачи.
    """
    epic_id = epic_new(stand, stand.other)
    bound(stand, epic_id, stand.rng.choice(sorted(fsm.TERMINAL_STATES)),
          stand.other)
    blocker = bound(stand, epic_id, stand.rng.choice(non_terminal_states()),
                    stand.other)

    out, code = cli("epic", "close", epic_id, f"Итог {words(stand)}")

    row = epics()[epic_id]
    assert row["state"] == "open", note(stand, f"эпик закрыт:\n{out}")
    assert not row["outcome"] and not row["closed_at"], note(stand, f"{row}")
    assert blocker in out, note(stand, f"отказ не называет {blocker}:\n{out}")


# --- AC-18, AC-30, AC-35: lease и журнал команд эпика ---

def foreign_lease(task_id: str) -> None:
    """Живая чужая lease: другая сессия, этот host, живой pid, свежий heartbeat."""
    store.insert_lease(store.db(), task_id, FOREIGN_SESSION, os.getpid(),
                       socket.gethostname(), store.now())


@pytest.mark.parametrize("command", ["add", "remove"])
def test_ac18_foreign_live_lease_refuses_add_and_remove(stand, command):
    """Чужая живая lease задачи: `epic add`/`epic remove` отказывают текстом `lease.run_locked`, строки `tasks`, `epics`, `steps` не меняются.

    Ловит мутацию: `epic add`/`remove` меняют `tasks.epic_id` без
    `lease.run_locked` (или берут lease по id эпика, а не задачи) —
    задача, которую ведёт другая сессия, меняется.
    """
    epic_id = epic_new(stand, stand.other)
    task_id = insert_task(stand, stand.other)
    if command == "remove":
        cli("epic", "add", epic_id, task_id)
        assert epic_of(task_id) == epic_id, note(stand, "предпосылка: add")
    foreign_lease(task_id)
    before = snapshot()

    out, code = cli("epic", command, epic_id, task_id)

    assert "задачу ведёт сессия" in out and FOREIGN_SESSION in out, note(
        stand, f"нет отказа lease:\n{out}")
    after = snapshot()
    for table in ("tasks", "epics", "steps"):
        assert after[table] == before[table], note(stand, f"{table} изменена")


def lease_spies():
    return (mock.patch.object(lease, "acquire", wraps=lease.acquire),
            mock.patch.object(store, "insert_lease", wraps=store.insert_lease))


def leased_ids(acquire_spy, insert_spy) -> set:
    ids = {c.args[1] for c in acquire_spy.call_args_list if len(c.args) > 1}
    ids |= {c.kwargs["task_id"] for c in acquire_spy.call_args_list
            if "task_id" in c.kwargs}
    ids |= {c.args[1] for c in insert_spy.call_args_list if len(c.args) > 1}
    return ids


def test_ac18_no_command_takes_lease_by_epic_id(stand):
    """Ни одна из `epic new|edit|close|add|remove|show` и `new --epic` не берёт lease по id эпика — ни вызовом, ни строкой `leases`, ни записью «lease взят»; после `epic add`/`remove` lease задачи не остаётся.

    Ловит мутацию: команды эпика обёрнуты `lease.run_locked(conn,
    epic_id, …)` — `acquire` зовётся с id эпика, в журнале эпика «lease
    взят»; `epic add` не снимает lease задачи (`release` не в `finally`).
    """
    acquire_patch, insert_patch = lease_spies()
    with acquire_patch as acquire_spy, insert_patch as insert_spy:
        epic_id = epic_new(stand, config.DEFAULT_TARGET)
        task_id = insert_task(stand)
        runs = [("epic", "edit", epic_id, "--title", f"Т {words(stand)}"),
                ("epic", "add", epic_id, task_id),
                ("epic", "show", epic_id),
                ("epic", "remove", epic_id, task_id)]
        outputs = [cli(*args) for args in runs]
        outputs.append(new_cli(stand, "--epic", epic_id)[:2])
        bound(stand, epic_id, "done")
        for member in task_ids():
            if epic_of(member) == epic_id:
                set_state(member, "done")
        outputs.append(cli("epic", "close", epic_id, f"Итог {words(stand)}"))
        assert epics()[epic_id]["state"] == "closed", note(
            stand, f"предпосылка: close {outputs[-1]}")
        taken = leased_ids(acquire_spy, insert_spy)

    assert epic_id not in taken, note(stand, f"lease по id эпика: {outputs}")
    conn = store.db()
    assert conn.execute("SELECT COUNT(*) FROM leases WHERE task_id=?",
                        (epic_id,)).fetchone()[0] == 0
    assert not [r for r in store.task_steps(conn, epic_id)
                if r["action"] == LEASE_TAKEN], note(stand, "«lease взят» эпика")
    assert store.lease_row(conn, task_id) is None, note(
        stand, "lease задачи осталась после add/remove")


def test_ac30_journal_of_epic_commands_carries_epic_and_project(stand):
    """Записи журнала `epic new|edit|add|remove|close` несут `task_id` = id эпика и `target` = проект эпика; `epic show` журнала не пишет и lease не берёт.

    Проект эпика — не проект по умолчанию: запись без явного `target`
    получила бы `artel`.

    Ловит мутацию: `store.journal` зовётся без `target=` (запись несёт
    проект по умолчанию); запись пишется под id задачи вместо id эпика;
    `epic show` пишет запись «показан» в журнал или берёт lease.
    """
    project = stand.other
    since = last_step_id()
    epic_id = epic_new(stand, project)
    task_id = insert_task(stand, project)
    commands = [("epic", "edit", epic_id, "--goal", f"Цель {words(stand)}"),
                ("epic", "add", epic_id, task_id),
                ("epic", "remove", epic_id, task_id),
                ("epic", "add", epic_id, task_id)]
    for args in commands:
        cli(*args)
    set_state(task_id, "done")
    cli("epic", "close", epic_id, f"Итог {words(stand)}")
    assert epics()[epic_id]["state"] == "closed", note(stand, "предпосылка: close")

    own = [r for r in steps_since(since) if r["task_id"] == epic_id]
    assert len(own) >= 6, note(stand, f"записей эпика {len(own)}: {own}")
    assert {r["target"] for r in own} == {project}, note(
        stand, f"target записей эпика: {[r['target'] for r in own]}")

    before = snapshot()
    with mock.patch.object(lease, "run_locked", wraps=lease.run_locked) as spy:
        out, code = cli("epic", "show", epic_id)
    assert snapshot() == before, note(stand, f"epic show изменил БД:\n{out}")
    assert not spy.called, note(stand, "epic show взял lease")


@pytest.mark.parametrize("command", ["show", "edit", "close", "add", "remove",
                                     "new"])
def test_ac35_unknown_epic_refused_before_lease(stand, command):
    """Команда с id эпика, которого нет в `epics`: отказ «эпик <id> не найден», `lease.run_locked` не вызывался, строки `tasks`, `epics`, `steps` равны снимку.

    Ловит мутацию: `epic add`/`remove` берут lease задачи до проверки
    эпика (запись «lease взят» в журнале); `new --epic` заводит задачу и
    лишь потом проверяет эпик; отказ говорит «задача не найдена».
    """
    epic_new(stand, config.DEFAULT_TARGET)
    ghost = "E" + idgen.new_task_id()
    task_id = insert_task(stand)
    runs = {
        "show": lambda: cli("epic", "show", ghost),
        "edit": lambda: cli("epic", "edit", ghost, "--title", "Т"),
        "close": lambda: cli("epic", "close", ghost, "Итог"),
        "add": lambda: cli("epic", "add", ghost, task_id),
        "remove": lambda: cli("epic", "remove", ghost, task_id),
        "new": lambda: new_cli(stand, "--epic", ghost)[:2],
    }
    before = snapshot()
    with mock.patch.object(lease, "run_locked", wraps=lease.run_locked) as spy:
        out, code = runs[command]()

    assert re.search(rf"эпик {ghost} не найден", out, re.IGNORECASE), note(
        stand, f"нет отказа «эпик {ghost} не найден»:\n{out}")
    assert not spy.called, note(stand, "lease.run_locked вызван")
    after = snapshot()
    for table in ("tasks", "epics", "steps"):
        assert after[table] == before[table], note(stand, f"{table} изменена")


# --- AC-31 ---

def test_ac31_add_to_second_epic_and_remove_from_foreign_refused(stand):
    """Задача в E1: `epic add E2` и `epic remove E2` отказывают, `epic_id` остаётся E1; задача без эпика: `epic remove E2` отказывает, `epic_id` пуст.

    Ловит мутацию: `epic add` перезаписывает эпик задачи, уже
    состоящей в другом; `epic remove` очищает `epic_id`, не сверив, что
    задача состоит именно в названном эпике.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    first, second = epic_new(stand, project), epic_new(stand, project)
    member = bound(stand, first, stand.rng.choice(non_terminal_states()),
                   project)
    loose = insert_task(stand, project)

    out, code = cli("epic", "add", second, member)
    assert epic_of(member) == first, note(stand, f"add во второй:\n{out}")
    assert out.strip(), note(stand, "отказ add без причины")
    out, code = cli("epic", "remove", second, member)
    assert epic_of(member) == first, note(stand, f"remove из чужого:\n{out}")
    assert out.strip(), note(stand, "отказ remove без причины")
    out, code = cli("epic", "remove", second, loose)
    assert epic_of(loose) is None, note(stand, f"remove без эпика:\n{out}")
    assert out.strip(), note(stand, "отказ remove без причины")


# --- AC-39: epic close и привязка на двух соединениях ---

class ThreadOutput(io.TextIOBase):
    """stdout, раздельный по потокам: вывод каждого потока — в свой буфер."""

    def __init__(self):
        self.buffers: dict = {}

    def write(self, text: str) -> int:
        self.buffers.setdefault(threading.get_ident(), io.StringIO()).write(text)
        return len(text)

    def text(self, ident) -> str:
        buf = self.buffers.get(ident)
        return buf.getvalue() if buf else ""


# Точки остановки первой команды: начало транзакции, запись эпика или
# привязки и `COMMIT` транзакции, держащей блокировку записи. Записи,
# после которых соединение держит блокировку записи до конца транзакции.
WRITE_HEADS = ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER",
               "DROP", "BEGIN IMMEDIATE", "BEGIN EXCLUSIVE")
END_HEADS = ("COMMIT", "ROLLBACK", "END")


def is_pause_point(head: str, locked: bool) -> bool:
    return head.startswith("BEGIN") or (
        head.startswith(("INSERT", "UPDATE", "DELETE")) and "EPIC" in head) or (
        head.startswith("COMMIT") and locked)


def interleave_at(first: tuple, second: tuple, point: int) -> dict | None:
    """Две команды CLI в двух потоках, каждая на своём соединении
    (`store.db()` потока). Первая останавливается перед `point`-й точкой
    (`is_pause_point`) и ждёт; вторая начинает в это время. Держит первая
    блокировку записи — её отпускает `BEGIN` второй (та встаёт в ожидание
    блокировки); не держит — завершение второй. `None` — первая
    закончилась, не дойдя до точки."""
    real_db = store.db
    roles: dict = {}
    paused, first_ready, release = (threading.Event(), threading.Event(),
                                    threading.Event())
    track = {"seen": 0, "locked": False, "on_begin": False}

    def trace_first(sql: str) -> None:
        head = sql.lstrip().upper()
        if is_pause_point(head, track["locked"]) and not paused.is_set():
            track["seen"] += 1
            if track["seen"] == point:
                track["on_begin"] = track["locked"]
                paused.set()
                first_ready.set()
                release.wait(60)
        if head.startswith(WRITE_HEADS):
            track["locked"] = True
        elif head.startswith(END_HEADS):
            track["locked"] = False

    def trace_second(sql: str) -> None:
        if track["on_begin"] and sql.lstrip().upper().startswith("BEGIN"):
            release.set()

    def db_with_trace():
        conn = real_db()
        role = roles.get(threading.get_ident())
        if role == "first":
            conn.set_trace_callback(trace_first)
        elif role == "second":
            conn.set_trace_callback(trace_second)
        return conn

    results: dict = {}
    output = ThreadOutput()

    def runner(role: str) -> None:
        roles[threading.get_ident()] = role
        results[role] = {"ident": threading.get_ident(), "code": 0, "error": None}
        try:
            artel.main()
        except SystemExit as exc:
            results[role]["code"] = exc.code
        except BaseException as exc:  # исход сверяет тест
            results[role]["error"] = repr(exc)
        finally:
            (first_ready if role == "first" else release).set()

    with mock.patch.object(store, "db", db_with_trace), \
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        saved_argv = sys.argv
        try:
            sys.argv = ["artel.py", *first]
            one = threading.Thread(target=runner, args=("first",))
            one.start()
            first_ready.wait(60)
            if paused.is_set():
                sys.argv = ["artel.py", *second]
                two = threading.Thread(target=runner, args=("second",))
                two.start()
                two.join(60)
            release.set()
            one.join(60)
        finally:
            sys.argv = saved_argv
    if not paused.is_set():
        return None
    for role in ("first", "second"):
        results[role]["out"] = output.text(results[role]["ident"])
    return results


@pytest.mark.parametrize("order", ["add-first", "close-first"])
def test_ac39_close_and_add_are_mutually_exclusive(stand, order):
    """`epic add <id> T` и `epic close <id>` на двух соединениях с перемежением: при каждой точке остановки первой команды ровно один исход — T в эпике и эпик `open`, либо эпик `closed` и T без эпика; исключений нет.

    Первая команда останавливается перед каждым своим `BEGIN` и перед
    каждой записью эпика или привязки по очереди (свежая фикстура на
    точку); вторая начинает в это время — в том числе пока первая держит
    открытую транзакцию до своего `COMMIT`.

    Ловит мутацию: проверка «эпик `open`» у `epic add` или «все задачи
    окончательны» у `epic close` идёт до `BEGIN IMMEDIATE` своей
    транзакции записи — другая команда проходит между проверкой и
    записью, в закрытом эпике остаётся неокончательная T; транзакция
    записи отложенная (`BEGIN`) — запись после чужого `COMMIT` падает
    `database is locked`.
    """
    outcomes = []
    for point in range(1, 40):
        epic_id = epic_new(stand, config.DEFAULT_TARGET)
        bound(stand, epic_id, "done")
        t = insert_task(stand, config.DEFAULT_TARGET,
                        stand.rng.choice(non_terminal_states()))
        add = ("epic", "add", epic_id, t)
        close = ("epic", "close", epic_id, f"Итог {words(stand)}")
        first, second = (add, close) if order == "add-first" else (close, add)

        results = interleave_at(first, second, point)
        if results is None:
            break
        errors = [results[k]["error"] for k in ("first", "second")
                  if results[k]["error"]]
        assert errors == [], note(stand, f"точка {point}: исключения {errors}; "
                                         f"{results}")
        state, member = epics()[epic_id]["state"], epic_of(t)
        joined = member == epic_id and state == "open"
        closed = state == "closed" and member is None
        assert joined != closed, note(
            stand, f"точка {point}: эпик {state}, epic_id T {member!r}; {results}")
        outcomes.append("joined" if joined else "closed")
    assert outcomes, note(stand, "первая команда не дошла ни до одной точки")
