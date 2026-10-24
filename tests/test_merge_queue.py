"""Тесты `orchestrator/merge_queue.py`: очередь FIFO ожидания мьютекса
merge-окна (SPEC 01M291EPQ2VFGCHZTXXC81616V), записи очереди процессов
одной сессии (SPEC 01M2XFSE8G3MBRHHQR38H53J1M), очередь и тексты ожидания
по проекту задачи (SPEC 01M57PM7NBFX34319TR0F9CB4F) — волна 3м-1 сведения
тестов, SPEC 01M5QJTVJB1ZM8B6DDEFQBP6RX; ADR-0027 п. 8.

Свод прежнего `tests/test_merge_queue.py` (unittest-классы на
`_QueueTestBase`) и классов `WaitForWindowOtherProjectQueueTest`,
`WaitTextsAnyOrderTest` из `tests/test_merge_lock_by_project.py`.
Приёмочные тесты 01M291EPQ2VFGCHZTXXC81616V кроют сквозной путь через
`fsm_merge_gate._cmd_approve_merge_gate_cycle`; здесь — сам модуль в
изоляции: пруна мёртвых записей, голова очереди, минуты ожидания, добавка
`status`, `wait_for_window` без полного цикла гейта. Доказательство
неослабления — таблицы `mutation-run` «до» и «после» в PLAN задачи.

Стенды — фикстуры поверх `tmp_root` с телами прежних `setUp`:
`queue_stand` (бывший `_QueueTestBase`) и `project_stand` (бывший `_Base`).
"""
import itertools
import socket
import time
from unittest import mock

import pytest

from orchestrator import catalog, config, merge_lock, merge_queue, store
from tests.sandbox import (_alive_foreign_pid, _dead_pid, _ts_ago, capture,
                           declare_target, patch_sleep)

TASK_A = "T001"
TASK_B = "T002"
TASK_C = "T003"
OTHER_HOST = "other-host.invalid"


@pytest.fixture
def queue_stand(tmp_root):
    """Стенд бывшего `_QueueTestBase`: схема и три задачи на `merge_gate`."""
    capture(catalog.cmd_init)
    for tid, branch in ((TASK_A, "task/t001-a"),
                        (TASK_B, "task/t002-b"),
                        (TASK_C, "task/t003-c")):
        store.insert_task(store.db(), tid, tid, "merge_gate", branch,
                          config.DEFAULT_TARGET, 25.0)
    return tmp_root


@pytest.fixture
def project_stand(tmp_root):
    """Стенд бывшего `_Base` (`tests/test_merge_lock_by_project.py`):
    подключение `conn`, счётчик задач `counter`, объявленные проекты
    `extone` и `exttwo`."""
    capture(catalog.cmd_init)
    tmp_root.conn = store.db()
    tmp_root.counter = 0
    for name in ("extone", "exttwo"):
        declare_target(name)
    return tmp_root


def enqueue(stand, task_id, session_id, pid, hostname, ts):
    store.enqueue_merge_wait(store.db(), task_id, session_id, pid,
                             hostname, ts)


def rows_by_pid(stand) -> dict:
    return {r["pid"]: r for r in store.merge_queue_rows(store.db())}


def new_task(stand, target: str) -> str:
    stand.counter += 1
    tid = f"T{stand.counter:03d}"
    store.insert_task(stand.conn, tid, "мерж", "merge_gate",
                      f"task/{tid.lower()}", target, 25.0)
    return tid


def seed_lock(stand, task_id: str, session_id: str, pid: int,
              heartbeat_ts: str = None) -> dict:
    stand.conn.execute(
        "INSERT INTO merge_locks (task_id, session_id, pid, hostname,"
        " heartbeat_ts) VALUES (?,?,?,?,?)",
        (task_id, session_id, pid, OTHER_HOST,
         heartbeat_ts or store.now()))
    stand.conn.commit()
    return locks(stand)[task_id]


def locks(stand) -> dict:
    return {r["task_id"]: dict(r) for r in
            stand.conn.execute("SELECT * FROM merge_locks").fetchall()}


def clear(stand) -> None:
    stand.conn.execute("DELETE FROM merge_locks")
    stand.conn.execute("DELETE FROM merge_queue")
    stand.conn.commit()


# --- пруна мёртвых записей (бывший `PruneDeadEntriesTest`) ---

def test_dead_pid_on_own_host_is_pruned(queue_stand):
    """Запись с мёртвым pid на своём host удаляется пруной.

    Ловит мутацию: `_prune_dead_entries` удаляет запись по её `pid`
    вместо `rowid` — мёртвая запись остаётся, `assert merge_queue_rows ==
    []` покраснеет.
    """
    enqueue(queue_stand, TASK_A, "sess-a", _dead_pid(),
            socket.gethostname(), store.now())

    merge_queue._prune_dead_entries(store.db())

    assert store.merge_queue_rows(store.db()) == []


def test_stale_heartbeat_on_foreign_host_is_pruned(queue_stand):
    """Запись чужого host с протухшим heartbeat удаляется пруной.

    Ловит мутацию: `_holder_is_dead` не считает протухший heartbeat
    признаком смерти — запись остаётся, `assert merge_queue_rows == []`
    покраснеет.
    """
    stale = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
    enqueue(queue_stand, TASK_A, "sess-a", 999, "other-host", stale)

    merge_queue._prune_dead_entries(store.db())

    assert store.merge_queue_rows(store.db()) == []


def test_live_entry_survives_pruning(queue_stand):
    """Живая запись чужого host со свежим heartbeat пруну переживает.

    Ловит мутацию: `_holder_is_dead` признаёт мёртвой любую запись чужого
    host (`!=` вместо `==` в сверке host) — живая запись удалится, сверка
    списка задач покраснеет.
    """
    enqueue(queue_stand, TASK_A, "sess-a", 999, "other-host", store.now())

    merge_queue._prune_dead_entries(store.db())

    rows = store.merge_queue_rows(store.db())
    assert [r["task_id"] for r in rows] == [TASK_A]


def test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it(
        queue_stand):
    """Мёртвая голова очереди уступает место живой записи за ней.

    Ловит мутацию: `_holder_is_dead` не проверяет живость pid своего host
    — мёртвая запись останется головой, `assert _head_task_id == TASK_B`
    покраснеет.
    """
    enqueue(queue_stand, TASK_A, "sess-dead", _dead_pid(),
            socket.gethostname(), _ts_ago(1))
    enqueue(queue_stand, TASK_B, "sess-b", 999, "other-host", store.now())

    merge_queue._prune_dead_entries(store.db())

    assert merge_queue._head_task_id(store.db()) == TASK_B


# --- голова очереди (бывший `HeadTaskIdTest`) ---

def test_empty_queue_has_no_head(queue_stand):
    """У пустой очереди головы нет — `None`.

    Ловит мутацию: `_head_task_id` пустой очереди отдаёт `""` вместо
    `None` — `assert ... is None` покраснеет.
    """
    assert merge_queue._head_task_id(store.db()) is None


def test_head_is_earliest_by_enqueued_ts(queue_stand):
    """Голова — запись с самым ранним временем входа, не порядок вставки.

    Ловит мутацию: `_head_task_id` берёт последнюю запись (`rows[-1]`)
    вместо первой — головой станет поздняя запись, `assert ... == TASK_A`
    покраснеет.
    """
    enqueue(queue_stand, TASK_B, "sess-b", 999, "other-host", _ts_ago(5))
    enqueue(queue_stand, TASK_A, "sess-a", 999, "other-host", _ts_ago(10))

    assert merge_queue._head_task_id(store.db()) == TASK_A


# --- задача держателя (бывший `CurrentHolderIdTest`) ---

def test_no_holder_degrades_to_placeholder(queue_stand):
    """Без держателя `_current_holder_id` — заглушка «?».

    Ловит мутацию: заглушка без держателя — пустая строка вместо «?» —
    `assert ... == "?"` покраснеет.
    """
    assert merge_queue._current_holder_id(store.db()) == "?"


def test_names_the_holder_task(queue_stand):
    """`_current_holder_id` называет задачу строки мьютекса.

    Ловит мутацию: `_current_holder_id` отдаёт `session_id` строки вместо
    `task_id` — `assert ... == TASK_A` покраснеет.
    """
    store.set_merge_lock(store.db(), TASK_A, "sess-a", 999,
                         "holder-host", store.now())

    assert merge_queue._current_holder_id(store.db()) == TASK_A


# --- минуты ожидания и добавка `status` (бывший `QueueWaitMinutesAndStatusSuffixTest`) ---

def test_not_queued_returns_none_and_empty_suffix(queue_stand):
    """Задача вне очереди: минут ожидания нет (`None`), добавка пуста.

    Ловит мутацию: `queue_wait_minutes` для задачи вне очереди отдаёт `0`
    вместо `None` — `assert ... is None` покраснеет.
    """
    t = store.get_task(store.db(), TASK_B)

    assert merge_queue.queue_wait_minutes(store.db(), TASK_B) is None
    assert merge_queue.wait_suffix(store.db(), t) == ""


def test_queued_reports_minutes_waited_and_the_current_holder(queue_stand):
    """Суффикс `status` ожидающей задачи называет задачу держателя,
    его pid и минуты ожидания точной строкой.

    Ловит мутацию: `wait_suffix` вернулся к `_current_holder_id` (без
    pid) либо формат label изменён — точная сверка строки с
    «T001 (pid 999)» покраснеет; сломан подсчёт минут — `assertEqual
    (minutes, 3)` покраснеет.
    """
    store.set_merge_lock(store.db(), TASK_A, "sess-a", 999,
                         "holder-host", store.now())
    enqueue(queue_stand, TASK_B, "sess-b", 999, "other-host", _ts_ago(180))
    t = store.get_task(store.db(), TASK_B)

    minutes = merge_queue.queue_wait_minutes(store.db(), TASK_B)
    suffix = merge_queue.wait_suffix(store.db(), t)

    assert minutes == 3
    # Формат суффикса с pid держателя — SPEC 01M2XFSE8G3MBRHHQR38H53J1M,
    # требование 7 (прежняя точная сверка без pid обновлена под него).
    assert suffix == \
        f"  [ждёт merge-окна: занято {TASK_A} (pid 999), 3 мин]"


# --- держатель с pid (бывший `CurrentHolderLabelTest`) ---
# SPEC 01M2XFSE8G3MBRHHQR38H53J1M, требования 6-7: держатель в журнале
# входа в очередь и суффиксе `status` называется с pid.

def test_no_holder_degrades_to_the_same_placeholder(queue_stand):
    """Без держателя label — прежний «?», как у `_current_holder_id`.

    Ловит мутацию: label без держателя стал иным текстом (например
    «? (pid ?)») — запись «ждёт merge-окна: держит ?» из
    `WaitForWindowTest` и эта сверка покраснеют.
    """
    assert merge_queue._current_holder_label(store.db()) == "?"


def test_label_names_task_and_pid_of_the_holder(queue_stand):
    """Label держателя — «<task_id> (pid <pid>)» из строки мьютекса.

    Ловит мутацию: label собран по одному `task_id` (pid из строки не
    читается) — `assertEqual` с «T001 (pid 4242)» покраснеет.
    """
    store.set_merge_lock(store.db(), TASK_A, "sess-a", 4242,
                         "holder-host", store.now())

    assert merge_queue._current_holder_label(store.db()) == \
        f"{TASK_A} (pid 4242)"


def test_queue_entry_journal_names_the_holder_pid(queue_stand):
    """Вход в очередь при занятом окне журналируется записью «ждёт
    merge-окна: держит <task> (pid <pid>)» (требование 6).

    Ловит мутацию: запись журнала осталась на `_current_holder_id`
    (только task_id) — `assertIn("4242", ...)` по действию покраснеет.
    """
    conn = store.db()
    store.set_merge_lock(conn, TASK_B, "sess-holder", 4242,
                         "holder-host", store.now())
    clock = {"value": 0.0}

    def fake_sleep(seconds):
        clock["value"] += seconds

    with mock.patch.object(time, "monotonic", lambda: clock["value"]), \
         patch_sleep(merge_queue, fake_sleep):
        with pytest.raises(SystemExit):
            merge_queue.wait_for_window(conn, TASK_A, "sess-a")

    actions = [s["action"] for s in store.task_steps(conn, TASK_A)]
    assert f"ждёт merge-окна: держит {TASK_B} (pid 4242)" in actions, actions


# --- записи очереди процессов одной сессии (бывший `ProcessScopedQueueRowsTest`) ---
# SPEC 01M2XFSE8G3MBRHHQR38H53J1M, требование 5: записи очереди двух
# процессов одной сессии независимы — продление heartbeat и снятие
# адресуются парой (session_id, pid).

def test_two_processes_of_one_session_live_as_two_rows_in_fifo_order(
        queue_stand):
    """Две записи одной сессии с разными pid живут в очереди
    одновременно; голова — та, что вошла раньше, независимо от pid.

    Ловит мутацию: `enqueue_merge_wait` сведён к «одна запись на
    сессию» (UPSERT по session_id) — в очереди останется одна строка и
    сверка списка pid покраснеет.
    """
    enqueue(queue_stand, TASK_B, "sess-a", 222, "other-host", _ts_ago(10))
    enqueue(queue_stand, TASK_A, "sess-a", 111, "other-host", _ts_ago(5))

    rows = store.merge_queue_rows(store.db())

    assert [r["pid"] for r in rows] == [222, 111]
    assert merge_queue._head_task_id(store.db()) == TASK_B


def test_touch_heartbeat_updates_only_the_row_of_that_process(queue_stand):
    """`touch_merge_queue_heartbeat(conn, sid, pid, ts)` продлевает
    heartbeat только записи (sid, pid); запись соседа той же сессии не
    трогается.

    Ловит мутацию: `WHERE session_id=?` без pid — heartbeat записи
    соседа тоже станет `fresh`, и `assertEqual(..., stale)` покраснеет.
    """
    stale = _ts_ago(30)
    enqueue(queue_stand, TASK_A, "sess-a", 111, "other-host", stale)
    enqueue(queue_stand, TASK_B, "sess-a", 222, "other-host", stale)
    fresh = store.now()

    store.touch_merge_queue_heartbeat(store.db(), "sess-a", 111, fresh)

    rows = rows_by_pid(queue_stand)
    assert rows[111]["heartbeat_ts"] == fresh
    assert rows[222]["heartbeat_ts"] == stale


def test_dequeue_removes_only_the_row_of_that_process(queue_stand):
    """`dequeue_merge_wait(conn, sid, pid)` снимает только запись
    (sid, pid); сосед той же сессии остаётся в очереди.

    Ловит мутацию: `DELETE ... WHERE session_id=?` без pid — очередь
    опустеет целиком, `assertEqual([...], [222])` покраснеет.
    """
    enqueue(queue_stand, TASK_A, "sess-a", 111, "other-host", _ts_ago(10))
    enqueue(queue_stand, TASK_B, "sess-a", 222, "other-host", _ts_ago(5))

    store.dequeue_merge_wait(store.db(), "sess-a", 111)

    assert [r["pid"] for r in store.merge_queue_rows(store.db())] == [222]


def test_non_head_process_of_the_same_session_does_not_take_the_window(
        queue_stand):
    """В очереди уже стоит живая запись другого процесса той же сессии
    (голова по FIFO); `wait_for_window` этого процесса окно не берёт
    до потолка, свою запись снимает, чужую оставляет нетронутой.

    Ловит мутацию: голова очереди определяется по session_id
    (первая запись «своей» сессии считается своей) — процесс возьмёт
    свободный мьютекс вне очереди, `assertIsNone(merge_lock_row)`
    покраснеет; либо `finally` снимает чужую запись — сверка списка
    задач покраснеет.
    """
    conn = store.db()
    other_pid = _alive_foreign_pid(queue_stand)
    seeded = _ts_ago(30)
    enqueue(queue_stand, TASK_B, "sess-a", other_pid, socket.gethostname(),
            seeded)
    clock = {"value": 0.0}

    def fake_sleep(seconds):
        clock["value"] += seconds

    with mock.patch.object(time, "monotonic", lambda: clock["value"]), \
         patch_sleep(merge_queue, fake_sleep):
        with pytest.raises(SystemExit):
            merge_queue.wait_for_window(conn, TASK_A, "sess-a")

    assert store.merge_lock_row(conn) is None
    rows = store.merge_queue_rows(conn)
    assert [r["task_id"] for r in rows] == [TASK_B]
    assert rows[0]["heartbeat_ts"] == seeded


# --- ожидание окна (бывший `WaitForWindowTest`) ---

def test_free_mutex_registers_then_immediately_takes_the_window(queue_stand):
    """Свободный мьютекс: `wait_for_window` встаёт в очередь, сразу берёт
    окно и снимает свою регистрацию.

    Ловит мутацию: `wait_for_window` снимает свою запись очереди только
    на выходе по потолку (`except SystemExit` вместо `finally`) — после
    взятия окна запись останется, `assert merge_queue_rows == []`
    покраснеет.
    """
    conn = store.db()

    merge_queue.wait_for_window(conn, TASK_A, "sess-a")

    row = store.merge_lock_row(conn)
    assert row["session_id"] == "sess-a"
    assert store.merge_queue_rows(conn) == [], (
        "успешное взятие окна обязано снять регистрацию "
        "в очереди")
    steps = store.task_steps(conn, TASK_A)
    assert any(s["action"] == "ждёт merge-окна: держит ?" for s in steps), \
        [s["action"] for s in steps]


def test_ceiling_expiry_dequeues_and_exits_without_touching_state(
        queue_stand):
    """Истёкший потолок ожидания merge-окна: выход с именем задачи,
    регистрация в очереди снята, состояние задачи не тронуто.

    Ловит мутацию: `finally` в `wait_for_window` не снимает запись
    очереди на истёкшем потолке — `assertEqual(merge_queue_rows, [])`
    покраснеет.
    """
    conn = store.db()
    store.set_merge_lock(conn, TASK_B, "sess-holder", 999,
                         "holder-host", store.now())
    clock = {"value": 0.0}

    def fake_monotonic():
        return clock["value"]

    def fake_sleep(seconds):
        clock["value"] += seconds

    with mock.patch.object(time, "monotonic", fake_monotonic), \
         patch_sleep(merge_queue, fake_sleep):
        with pytest.raises(SystemExit) as excinfo:
            merge_queue.wait_for_window(conn, TASK_A, "sess-a")

    assert TASK_A in str(excinfo.value)
    assert clock["value"] >= config.MERGE_QUEUE_WAIT_CEILING_SEC
    assert store.get_task(conn, TASK_A)["state"] == "merge_gate"
    assert store.merge_queue_rows(conn) == [], (
        "истёкший потолок обязан снять регистрацию в "
        "очереди — иначе она блокирует голову навсегда")


# --- очередь и тексты по проекту (бывшие классы `tests/test_merge_lock_by_project.py`) ---

def test_earlier_entry_of_other_project_does_not_delay_entry(project_stand):
    """В очереди раньше стоит живая запись задачи проекта Q, мьютекс Q
    держит живой держатель; `wait_for_window` задачи проекта P берёт
    мьютекс P без единой паузы, запись Q остаётся в очереди.

    Ловит мутацию: голова очереди в `wait_for_window` — первая запись
    всей очереди (глобальный FIFO) — P не станет головой и уйдёт в
    паузу, `fake_sleep` бросит `AssertionError`."""
    for p_target, q_target in ((config.DEFAULT_TARGET, "extone"),
                               ("extone", config.DEFAULT_TARGET)):
        clear(project_stand)
        q_holder, q_waiting = (new_task(project_stand, q_target),
                               new_task(project_stand, q_target))
        seed_lock(project_stand, q_holder, "s-q", 303)
        store.enqueue_merge_wait(project_stand.conn, q_waiting, "s-qw", 404,
                                 OTHER_HOST, _ts_ago(120))
        caller = new_task(project_stand, p_target)

        def fake_sleep(_seconds):
            raise AssertionError("задача P ушла в паузу очереди")

        with patch_sleep(merge_queue, fake_sleep):
            merge_queue.wait_for_window(project_stand.conn, caller, "s-p")

        label = f"p={p_target}, q={q_target}"
        assert locks(project_stand)[caller]["session_id"] == "s-p", label
        assert [r["task_id"] for r in
                store.merge_queue_rows(project_stand.conn)] == [q_waiting], label


def test_texts_name_own_project_holder_in_every_insertion_order(
        project_stand):
    """Строки мьютекса трёх проектов — во всех шести порядках вставки;
    отказ `acquire`, запись журнала входа в очередь (`wait_for_window`
    с нулевым потолком) и добавка `status` задачи проекта P называют
    держателя P.

    Ловит мутацию: держатель берётся первой (или последней) строкой
    таблицы, а не строкой проекта ждущей задачи — в части порядков
    тексты назовут держателя другого проекта."""
    targets = (config.DEFAULT_TARGET, "extone", "exttwo")
    for order in itertools.permutations(targets):
        for p_target in targets:
            clear(project_stand)
            holders = {}
            for pid, target in enumerate(order, start=500):
                holders[target] = seed_lock(
                    project_stand, new_task(project_stand, target),
                    f"s-{target}", pid)
            hp = holders[p_target]
            caller = new_task(project_stand, p_target)

            refusal = merge_lock.acquire(project_stand.conn, caller, "s-caller")
            with mock.patch.object(config,
                                   "MERGE_QUEUE_WAIT_CEILING_SEC", 0), \
                 pytest.raises(SystemExit):
                merge_queue.wait_for_window(project_stand.conn, caller,
                                            "s-caller")
            entered = [s["action"] for s in
                       store.task_steps(project_stand.conn, caller)
                       if s["action"].startswith("ждёт merge-окна")]
            store.enqueue_merge_wait(project_stand.conn, caller, "s-caller",
                                     909, OTHER_HOST, _ts_ago(130))
            suffix = merge_queue.wait_suffix(
                project_stand.conn, store.get_task(project_stand.conn, caller))

            label = f"order={order}, p={p_target}"
            assert f"задача {hp['task_id']})" in refusal, label
            assert f"(pid {hp['pid']}, " in refusal, label
            assert entered == [f"ждёт merge-окна: держит "
                               f"{hp['task_id']} (pid {hp['pid']})"], label
            assert suffix == f"  [ждёт merge-окна: занято {hp['task_id']} " \
                             f"(pid {hp['pid']}), 2 мин]", label
