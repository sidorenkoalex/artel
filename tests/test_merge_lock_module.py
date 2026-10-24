"""Тесты `orchestrator/merge_lock.py`: мьютекс merge-окна (SPEC T053),
владение процессом (SPEC 01M2XFSE8G3MBRHHQR38H53J1M), общая точка окна
`run_window` (SPEC T057), атомарность взятия под гонкой и прежняя форма
`touch_heartbeat(conn)` при строках нескольких проектов (SPEC
01M57PM7NBFX34319TR0F9CB4F) — волна 3м-1 сведения тестов, SPEC
01M5QJTVJB1ZM8B6DDEFQBP6RX; ADR-0027 п. 8.

Свод прежних `tests/test_merge_lock.py` (классы `AcquireReleaseTest`,
`ProcessOwnershipTest`, `RunWindowTest`, `ConcurrentAcquireTest`) и класса
`LegacyTouchHeartbeatTest` из `tests/test_merge_lock_by_project.py`.
Приёмочные тесты T053 кроют сквозной путь через `fsm.cmd_approve`; здесь —
сам модуль в изоляции: что именно меняется в строке БД на каждой ветке
`acquire`/`release`. Доказательство неослабления — таблицы `mutation-run`
«до» и «после» в PLAN задачи.

Стенды — фикстуры поверх `tmp_root` с телами прежних `setUp`:
`lock_stand` (`AcquireReleaseTest` и `RunWindowTest` — тела равны),
`ownership_stand`, `race_stand`, `project_stand` (бывший `_Base`).
"""
import os
import socket
import threading
from unittest import mock

import pytest

from orchestrator import catalog, config, liveness, merge_lock, store
from tests.sandbox import (_alive_foreign_pid, _dead_pid, _ts_ago, capture,
                           declare_target)

TASK = "T001"
HOLDER_TASK = "T999"
THREADS = 8
OTHER_HOST = "other-host.invalid"


@pytest.fixture
def lock_stand(tmp_root):
    """Стенд бывших `AcquireReleaseTest` и `RunWindowTest`: схема и две
    задачи на `merge_gate` — `TASK` и держатель `HOLDER_TASK`."""
    capture(catalog.cmd_init)
    store.insert_task(store.db(), TASK, "Задача",
                      "merge_gate", "task/t001-zadacha",
                      config.DEFAULT_TARGET, 25.0)
    store.insert_task(store.db(), HOLDER_TASK, "Держит окно",
                      "merge_gate", "task/t999-holder",
                      config.DEFAULT_TARGET, 25.0)
    return tmp_root


@pytest.fixture
def ownership_stand(tmp_root):
    """Стенд бывшего `ProcessOwnershipTest`: те же две задачи, заголовок
    задачи — её идентификатор."""
    capture(catalog.cmd_init)
    for tid, branch in ((TASK, "task/t001-zadacha"),
                        (HOLDER_TASK, "task/t999-holder")):
        store.insert_task(store.db(), tid, tid, "merge_gate", branch,
                          config.DEFAULT_TARGET, 25.0)
    return tmp_root


@pytest.fixture
def race_stand(tmp_root):
    """Стенд бывшего `ConcurrentAcquireTest`: одна задача, миграции догнаны
    до старта потоков."""
    capture(catalog.cmd_init)
    store.insert_task(store.db(), TASK, "Задача", "merge_gate",
                      "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
    # Догоняет migrate()/seed_task_counters ПОСЛЕ вставки T001, пока
    # тест ещё однопоточный — тот же приём, что
    # `tests/test_lease.py::ConcurrentAcquireTest.setUp`.
    store.db()
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


def lock_row(stand):
    """Строка мьютекса (бывший `row` трёх классов; имя с префиксом — тесты
    держат локальную `row`)."""
    return store.merge_lock_row(store.db())


def acquire_release_seed(stand, session_id, pid, hostname, heartbeat_ts,
                         task_id) -> None:
    store.set_merge_lock(store.db(), task_id, session_id, pid, hostname,
                         heartbeat_ts)


def process_ownership_seed(stand, session_id, pid, hostname=None,
                           heartbeat_ts=None):
    store.set_merge_lock(store.db(), HOLDER_TASK, session_id, pid,
                         hostname or socket.gethostname(),
                         heartbeat_ts or store.now())


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


# --- взятие и снятие (бывший `AcquireReleaseTest`) ---

def test_fresh_acquire_on_empty_table_takes_the_lock(lock_stand):
    """Пустая таблица: `acquire` берёт мьютекс и пишет строку этого
    процесса — сессия, задача, pid и host вызывающего.

    Ловит мутацию: `acquire` пишет в строку не `socket.gethostname()`, а
    иной host (`"localhost"`) — сверка host строки покраснеет.
    """
    refusal = merge_lock.acquire(store.db(), TASK, "sess-a")

    assert refusal is None
    row = lock_row(lock_stand)
    assert row["session_id"] == "sess-a"
    assert row["task_id"] == TASK
    assert row["pid"] == os.getpid()
    assert row["hostname"] == socket.gethostname()


def test_own_session_re_enters_without_refusal(lock_stand):
    """Повторный `acquire` той же сессией из того же процесса — без отказа.

    Ловит мутацию: из условия взятия выпала ветка «свой процесс»
    (`row is None` без `_is_own_process`) — свой живой мьютекс откажет
    самому себе, `assert refusal is None` покраснеет.
    """
    merge_lock.acquire(store.db(), TASK, "sess-a")

    refusal = merge_lock.acquire(store.db(), TASK, "sess-a")

    assert refusal is None
    assert lock_row(lock_stand)["session_id"] == "sess-a"


def test_foreign_fresh_lock_refuses_and_names_holder_and_task(lock_stand):
    """Чужой живой держатель: отказ называет его сессию и задачу, строка
    мьютекса не тронута.

    Ловит мутацию: текст отказа `acquire` потерял session_id держателя —
    `assert "sess-holder" in refusal` покраснеет.
    """
    acquire_release_seed(lock_stand, "sess-holder", 999, "holder-host",
                         store.now(), HOLDER_TASK)
    before = dict(lock_row(lock_stand))

    refusal = merge_lock.acquire(store.db(), TASK, "sess-caller")

    assert refusal is not None
    assert "sess-holder" in refusal
    assert HOLDER_TASK in refusal
    assert dict(lock_row(lock_stand)) == before, (
        "отказанное взятие не имеет права тронуть чужой "
        "мьютекс")


def test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled(lock_stand):
    """Чужой держатель с протухшим heartbeat перехватывается, перехват
    пишется в журнал задачи.

    Ловит мутацию: `_holder_is_dead` не считает протухший heartbeat
    признаком смерти — `acquire` откажет, `assert refusal is None`
    покраснеет; либо перехват идёт без записи журнала — сверка записей
    журнала покраснеет.
    """
    stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
    acquire_release_seed(lock_stand, "sess-holder", 999, "holder-host",
                         stale_ts, HOLDER_TASK)
    before = len(store.task_steps(store.db(), TASK))

    refusal = merge_lock.acquire(store.db(), TASK, "sess-caller")

    assert refusal is None
    row = lock_row(lock_stand)
    assert row["session_id"] == "sess-caller"
    assert row["task_id"] == TASK
    new_steps = store.task_steps(store.db(), TASK)[before:]
    assert any("мьютекс" in s["action"] for s in new_steps), new_steps


def test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat(
        lock_stand):
    """Мёртвый pid держателя на этом host перешагивается и при свежем
    heartbeat.

    Ловит мутацию: `_holder_is_dead` не проверяет живость pid своего host
    (`return False` после heartbeat) — `acquire` откажет, `assert refusal
    is None` покраснеет.
    """
    acquire_release_seed(lock_stand, "sess-holder", _dead_pid(),
                         socket.gethostname(), store.now(), HOLDER_TASK)

    refusal = merge_lock.acquire(store.db(), TASK, "sess-caller")

    assert refusal is None, (
        "мёртвый pid держателя обязан перешагиваться даже при "
        "свежем heartbeat (требование 4)")
    assert lock_row(lock_stand)["session_id"] == "sess-caller"


def test_foreign_dead_pid_on_a_different_host_is_not_taken_over(lock_stand):
    """Чужой host — pid чужой процессной таблицы нельзя ни
    подтвердить, ни опровергнуть; решает только heartbeat (тот же
    приём, что `doctor.check_leases`/`check_merge_lock`).

    Ловит мутацию: `_holder_is_dead` признаёт мёртвым держателя чужого
    host (`!=` вместо `==` в сверке host) — свежий держатель другого host
    перехватится, `assert refusal is not None` покраснеет.
    """
    acquire_release_seed(lock_stand, "sess-holder", 999999, "other-host",
                         store.now(), HOLDER_TASK)

    refusal = merge_lock.acquire(store.db(), TASK, "sess-caller")

    assert refusal is not None


def test_release_removes_only_the_matching_session(lock_stand):
    """`release` чужой сессией мьютекс не снимает, своей — снимает.

    Ловит мутацию: `store.release_merge_lock` удаляет по одному pid
    (`session_id` не в `WHERE`) — `release` сессией `sess-b` из того же
    процесса снимет мьютекс, первая сверка покраснеет.
    """
    merge_lock.acquire(store.db(), TASK, "sess-a")

    merge_lock.release(store.db(), "sess-b")
    assert lock_row(lock_stand) is not None, "release чужой сессией снял мьютекс"

    merge_lock.release(store.db(), "sess-a")
    assert lock_row(lock_stand) is None


# --- владение процессом (бывший `ProcessOwnershipTest`) ---
# SPEC 01M2XFSE8G3MBRHHQR38H53J1M, требования 1-4: держатель мьютекса
# — процесс (session_id И pid), не сессия. Второй живой процесс той же
# рабочей копии пульта (тот же session_id, другой pid) — чужой
# держатель: тот же отказ, что чужой сессии; мёртвый — прежний перехват;
# `release` снимает только строку своего процесса.

def test_live_other_process_of_same_session_is_refused_with_holder_pid(
        ownership_stand):
    """Мьютекс держит живой процесс той же сессии с другим pid —
    `acquire` отказывает, называет pid держателя, строку не трогает.

    Ловит мутацию: условие «свой» оставлено по одному session_id —
    вызов вернёт `None`, строка окажется переписана на `os.getpid()`,
    и `assertIsNotNone`/сверка строки «до/после» покраснеют.
    """
    holder_pid = _alive_foreign_pid(ownership_stand)
    process_ownership_seed(ownership_stand, "sess-a", holder_pid)
    before = dict(lock_row(ownership_stand))

    refusal = merge_lock.acquire(store.db(), TASK, "sess-a")

    assert refusal is not None
    assert str(holder_pid) in refusal
    assert HOLDER_TASK in refusal
    assert dict(lock_row(ownership_stand)) == before


def test_refusal_text_for_own_session_equals_foreign_session_text(
        ownership_stand):
    """Один живой держатель отказывает своей и чужой сессии одним и тем
    же текстом — разница только в самом session_id.

    Ловит мутацию: для процесса своей сессии заведена отдельная ветка
    с другим текстом отказа — нормализованные строки разойдутся.
    """
    holder_pid = _alive_foreign_pid(ownership_stand)
    with mock.patch.object(liveness, "_age_seconds", lambda ts: 5.0):
        process_ownership_seed(ownership_stand, "sess-holder", holder_pid)
        foreign = merge_lock.acquire(store.db(), TASK, "sess-caller")
        process_ownership_seed(ownership_stand, "sess-caller", holder_pid)
        own = merge_lock.acquire(store.db(), TASK, "sess-caller")

    assert foreign is not None
    assert own is not None
    assert own.replace("sess-caller", "SID") == \
        foreign.replace("sess-holder", "SID")


def test_own_process_re_enters_and_refreshes_the_row(ownership_stand):
    """Строка этого процесса (session_id И `os.getpid()`) с протухшим
    на две минуты heartbeat — повторный `acquire` даёт `None`, ставит
    текущую задачу и свежий heartbeat.

    Ловит мутацию: условие «свой» требует ещё и совпадения task_id
    (либо ветка «свой» не пишет строку) — `acquire` откажет своему же
    процессу или оставит старый heartbeat, обе сверки покраснеют.
    """
    process_ownership_seed(ownership_stand, "sess-a", os.getpid(),
                           heartbeat_ts=_ts_ago(120))

    refusal = merge_lock.acquire(store.db(), TASK, "sess-a")

    assert refusal is None
    row = lock_row(ownership_stand)
    assert row["task_id"] == TASK
    assert row["pid"] == os.getpid()
    assert liveness._age_seconds(row["heartbeat_ts"]) < 60


def test_dead_process_of_own_session_is_intercepted_and_journalled(
        ownership_stand):
    """Держатель той же сессии, но с неживым pid на этом host —
    перехват прежней записью «мьютекс merge перехвачен», не отказ.

    Ловит мутацию: отказ «другой pid той же сессии» поставлен ПЕРЕД
    проверкой живости — мёртвый держатель своей сессии перестанет
    перехватываться, `assertIsNone` покраснеет; либо перехват своей
    сессии идёт молча без записи — сверка журнала покраснеет.
    """
    process_ownership_seed(ownership_stand, "sess-a", _dead_pid())

    refusal = merge_lock.acquire(store.db(), TASK, "sess-a")

    assert refusal is None
    assert lock_row(ownership_stand)["pid"] == os.getpid()
    actions = [s["action"] for s in store.task_steps(store.db(), TASK)]
    assert "мьютекс merge перехвачен" in actions, actions


def test_release_from_non_holder_process_keeps_the_mutex(ownership_stand):
    """`release` с тем же session_id из процесса, который окна не
    держит (строка за живым другим pid), мьютекс НЕ снимает.

    Ловит мутацию: `store.release_merge_lock` удаляет по одному
    `session_id` (pid не в `WHERE`) — строка живого держателя исчезнет,
    `assertIsNotNone` покраснеет.
    """
    holder_pid = _alive_foreign_pid(ownership_stand)
    process_ownership_seed(ownership_stand, "sess-a", holder_pid)

    merge_lock.release(store.db(), "sess-a")

    row = lock_row(ownership_stand)
    assert row is not None
    assert row["pid"] == holder_pid


def test_release_from_holder_process_removes_the_mutex(ownership_stand):
    """`release` из процесса-держателя (мьютекс взят через `acquire`
    этим же процессом) снимает строку.

    Ловит мутацию: pid в `release` берётся не из вызывающего процесса
    (либо сверка pid написана наоборот) — свой мьютекс перестанет
    сниматься, `assertIsNone` покраснеет.
    """
    merge_lock.acquire(store.db(), TASK, "sess-a")

    merge_lock.release(store.db(), "sess-a")

    assert lock_row(ownership_stand) is None


def test_store_release_merge_lock_requires_both_session_and_pid(
        ownership_stand):
    """`store.release_merge_lock(conn, session_id, pid)` — опорная
    функция снимает строку только при совпадении ОБОИХ ключей.

    Ловит мутацию: в `WHERE` остался один из ключей — вызов с чужим
    pid (или чужой сессией) снимет строку, и первые две сверки
    покраснеют.
    """
    conn = store.db()
    process_ownership_seed(ownership_stand, "sess-a", 4242)

    store.release_merge_lock(conn, "sess-a", 4243)
    assert lock_row(ownership_stand) is not None, "pid не совпал — строка остаётся"
    store.release_merge_lock(conn, "sess-b", 4242)
    assert lock_row(ownership_stand) is not None, "сессия не совпала — строка остаётся"
    store.release_merge_lock(conn, "sess-a", 4242)
    assert lock_row(ownership_stand) is None


# --- окно `run_window` (бывший `RunWindowTest`) ---
# SPEC T057, требование 2 rev. AC-3: общая точка окна merge-мьютекса —
# `acquire` -> отказ (`sys.exit`) -> `body()` -> `release` безусловно.

def test_success_runs_body_and_releases_the_mutex_afterwards(lock_stand):
    """Успешное окно исполняет тело, возвращает его итог и отпускает
    мьютекс.

    Ловит мутацию: `run_window` не снимает мьютекс после тела (`release`
    выпал вместе с `finally`) — `assert lock_row(...) is None` покраснеет.
    """
    conn = store.db()
    seen = []

    result = merge_lock.run_window(conn, TASK, "sess-a",
                                   lambda: seen.append("done") or "ok")

    assert result == "ok"
    assert seen == ["done"]
    assert lock_row(lock_stand) is None, ("мьютекс обязан быть отпущен после "
                                          "тела окна")


def test_refusal_exits_without_running_the_body(lock_stand):
    """Занятое окно — `sys.exit` с текстом отказа, тело не исполнено,
    чужой мьютекс не тронут.

    Ловит мутацию: `run_window` исполняет тело перед выходом по отказу —
    `assert called == []` покраснеет.
    """
    conn = store.db()
    store.set_merge_lock(conn, HOLDER_TASK, "sess-holder", 999,
                         "holder-host", store.now())
    called = []

    with pytest.raises(SystemExit) as excinfo:
        merge_lock.run_window(conn, TASK, "sess-caller",
                              lambda: called.append("ran"))

    assert "sess-holder" in str(excinfo.value)
    assert called == []
    assert lock_row(lock_stand)["session_id"] == "sess-holder", (
        "отказанное взятие не имеет права тронуть чужой "
        "мьютекс")


def test_mutex_is_released_even_when_the_body_raises(lock_stand):
    """Тело окна упало — мьютекс всё равно отпущен.

    Ловит мутацию: `release` в `run_window` стоит после тела вне
    `finally` — исключение тела оставит мьютекс занятым, `assert
    lock_row(...) is None` покраснеет.
    """
    conn = store.db()

    with pytest.raises(ValueError):
        merge_lock.run_window(
            conn, TASK, "sess-a",
            lambda: (_ for _ in ()).throw(ValueError))

    assert lock_row(lock_stand) is None, ("тело упало — мьютекс всё равно "
                                          "обязан быть отпущен")


# --- гонка взятия (бывший `ConcurrentAcquireTest`) ---
# Read-then-write в `acquire()` (`merge_lock_row` -> `set_merge_lock`)
# обязан быть атомарным под конкурентным доступом (SPEC T053, требование
# 1 — `BEGIN IMMEDIATE` по образцу `lease.acquire`, ревью T044 итерация
# 1 замечание 1). Каждый поток открывает своё собственное подключение
# (`store.db()`), как и делают отдельные процессы CLI, — общий только
# файл БД.

def test_concurrent_acquire_on_free_lock_exactly_one_wins(race_stand):
    """Восемь потоков берут свободный мьютекс одновременно — побеждает
    ровно один, остальные получают отказ.

    Ловит мутацию: `acquire` не проверяет занятость строки замка (условие
    взятия `if True:`) — при любом порядке потоков все восемь вернут
    `None`, `assert len(wins) == 1` покраснеет.
    """
    barrier = threading.Barrier(THREADS)
    results = [None] * THREADS
    errors = []

    def worker(i):
        try:
            conn = store.db()
            barrier.wait(timeout=5)
            results[i] = merge_lock.acquire(conn, TASK, f"sess-{i}")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,))
               for i in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == [], "acquire() не должна падать под гонкой"
    wins = [r for r in results if r is None]
    assert len(wins) == 1, results
    row = store.merge_lock_row(store.db())
    assert row["session_id"].startswith("sess-")


# --- прежняя форма `touch_heartbeat(conn)` (бывший `LegacyTouchHeartbeatTest`) ---

def test_no_args_with_several_projects_renews_only_current_session(
        project_stand):
    """Строки двух проектов, обе с heartbeat десять минут назад: строка
    текущей сессии (`ARTEL_SESSION_ID`) и строка другой сессии.
    `touch_heartbeat(conn)` делает свежей только первую — при любом
    порядке вставки.

    Ловит мутацию: прежняя форма продлевает все строки либо первую
    строку таблицы — строка чужой сессии станет свежей (или своя
    останется старой в одном из порядков вставки)."""
    old = _ts_ago(600)
    for own_first in (True, False):
        clear(project_stand)
        own_task, other_task = (new_task(project_stand, config.DEFAULT_TARGET),
                                new_task(project_stand, "extone"))
        seeds = [(own_task, "s-own", 101), (other_task, "s-other", 202)]
        for args in (seeds if own_first else seeds[::-1]):
            seed_lock(project_stand, *args, heartbeat_ts=old)

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "s-own"}):
            merge_lock.touch_heartbeat(project_stand.conn)

        rows = locks(project_stand)
        assert rows[other_task]["heartbeat_ts"] == old, f"own_first={own_first}"
        assert rows[own_task]["heartbeat_ts"] != old, f"own_first={own_first}"
