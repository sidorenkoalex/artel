"""Юнит-тесты orchestrator/lease.py (SPEC T044).

Приёмочные тесты (tasks/T044/acceptance_tests) кроют AC-1..AC-7 сквозным
путём через семь мутирующих команд; здесь — сам модуль `lease.py` в
изоляции: `resolve_session_id` и границы `acquire`/`release`, которые
критериям не нужны напрямую (форма отказа, что именно меняется в строке
БД на каждой ветке).
"""
import os
import socket
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, _dead_pid, _ts_ago, capture  # noqa: E402


class ResolveSessionIdTest(TmpRootTest):
    """Требование 9: identity вызова — явный параметр, иначе окружение/ppid.

    Наследует `TmpRootTest`, не голый `unittest.TestCase` (регресс SPEC
    01M290PP4KBTG1KYS1PWKQJH6T): с той задачи `resolve_session_id`
    (`lease.resolve_session_id` — тот же объект функции) при отсутствии
    аргумента/переменной читает и заводит файл `.artel/session-id` —
    непропатченный `config.ROOT` подхватил бы `ppid-fallback` из файла,
    оставшегося на диске от предыдущего вызова CLI на этой машине, а не
    посчитал бы живой `os.getppid()`, как ожидают проверки ниже."""

    def test_explicit_argument_wins(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-sess"}):
            self.assertEqual(lease.resolve_session_id("explicit"), "explicit")

    def test_env_var_wins_over_ppid_fallback(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-sess"}):
            self.assertEqual(lease.resolve_session_id(None), "env-sess")

    def test_falls_back_to_parent_pid(self):
        env = dict(os.environ)
        env.pop("ARTEL_SESSION_ID", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(lease.resolve_session_id(None),
                             f"ppid-{os.getppid()}")

    def test_same_process_resolves_the_same_id_twice(self):
        """Требование 9: последовательные вызовы без явного параметра —
        одна и та же identity (без него замок блокировал бы сессию саму
        на себя)."""
        env = dict(os.environ)
        env.pop("ARTEL_SESSION_ID", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(lease.resolve_session_id(None),
                             lease.resolve_session_id(None))


class AcquireReleaseTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.lease_row(store.db(), self.TASK)

    def test_fresh_acquire_inserts_the_row_and_reports_fresh(self):
        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        self.assertTrue(fresh)
        row = self.row()
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(row["hostname"], socket.gethostname())

    def test_own_session_renews_and_is_not_fresh(self):
        lease.acquire(store.db(), self.TASK, "sess-a")

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        self.assertFalse(fresh, "продление предсуществующего lease — не "
                                "«с нуля» (см. release)")

    def test_foreign_fresh_lease_refuses_without_mutating_the_row(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", store.now()))
        conn.commit()
        before = dict(self.row())

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNotNone(refusal)
        self.assertIn("sess-holder", refusal)
        self.assertIn("holder-host", refusal)
        self.assertFalse(fresh)
        self.assertEqual(dict(self.row()), before)

    def test_foreign_stale_lease_is_taken_over_and_journalled(self):
        conn = store.db()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", stale_ts))
        conn.commit()
        journalled_before = len(store.task_steps(store.db(), self.TASK))

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNone(refusal)
        self.assertFalse(fresh, "перехват существующей строки — не «с нуля»")
        row = self.row()
        self.assertEqual(row["session_id"], "sess-caller")
        self.assertEqual(row["pid"], os.getpid())
        new_steps = store.task_steps(store.db(), self.TASK)[journalled_before:]
        self.assertTrue(any("lease" in s["action"] for s in new_steps))

    def test_release_removes_only_the_matching_session(self):
        lease.acquire(store.db(), self.TASK, "sess-a")

        lease.release(store.db(), self.TASK, "sess-b")
        self.assertIsNotNone(self.row(), "release чужой сессией снял lease")

        lease.release(store.db(), self.TASK, "sess-a")
        self.assertIsNone(self.row())


class AcquireJournalCauseTest(TmpRootTest):
    """SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC: identity в журнале lease-событий
    (требования 1-3, AC-1, AC-4..AC-6)."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def steps(self):
        return store.task_steps(store.db(), self.TASK)

    def test_fresh_acquire_records_the_taking_session_id_in_the_column(self):
        """AC-4: захват свободного lease несёт identity взявшей сессии не
        только в `detail`, но и в новой колонке `steps.session_id`."""
        lease.acquire(store.db(), self.TASK, "sess-fresh")

        new = self.steps()
        self.assertTrue(new)
        self.assertEqual(new[-1]["session_id"], "sess-fresh")

    def test_intercept_of_dead_pid_on_this_host_names_the_cause(self):
        """AC-5, сценарий A: прежний держатель на этом host, pid мёртв —
        причина перехвата называет именно это, не общий «heartbeat
        протух»."""
        conn = store.db()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-dead-holder", _dead_pid(), socket.gethostname(),
             stale_ts))
        conn.commit()

        lease.acquire(store.db(), self.TASK, "sess-taker")

        detail = self.steps()[-1]["detail"]
        self.assertIn("pid", detail)
        self.assertTrue("мёртв" in detail or "мертв" in detail)

    def test_intercept_of_foreign_host_keeps_the_heartbeat_cause(self):
        """AC-5, сценарий Б: прежний держатель на чужом host — pid
        непроверяем, причина остаётся прежней «heartbeat протух»
        (регресс существующего поведения)."""
        conn = store.db()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-foreign-holder", 999999, "other-host.invalid",
             stale_ts))
        conn.commit()

        lease.acquire(store.db(), self.TASK, "sess-taker")

        detail = self.steps()[-1]["detail"]
        self.assertIn("heartbeat", detail)
        self.assertIn("протух", detail)


class ReleaseAnyTest(TmpRootTest):
    """SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC, требование 3, AC-6: снятие lease
    «любым путём» — общий узел `lease.release_any` для `kill`/`done`."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def test_releases_a_lease_held_by_a_different_session_and_names_the_caller(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-other-holder", 424242, "holder-host", store.now()))
        conn.commit()

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-releaser"}):
            detail = lease.release_any(conn, self.TASK, "orchestrator",
                                       "тестовое снятие")

        self.assertIsNotNone(detail)
        self.assertIsNone(store.lease_row(store.db(), self.TASK))
        last = store.task_steps(store.db(), self.TASK)[-1]
        self.assertEqual(last["action"], "тестовое снятие")
        self.assertEqual(last["session_id"], "sess-releaser")
        self.assertIn("sess-other-holder", last["detail"])

    def test_no_lease_is_a_silent_no_op(self):
        conn = store.db()

        result = lease.release_any(conn, self.TASK, "orchestrator", "снятие")

        self.assertIsNone(result)
        self.assertEqual(store.task_steps(conn, self.TASK), [])


class RunLockedTest(TmpRootTest):
    """SPEC T057, требование 2: общая точка обвязки — `resolve_session_id`
    -> `acquire` -> отказ -> `body(sid)` -> `release`-если-`fresh`."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.lease_row(store.db(), self.TASK)

    def test_fresh_acquire_runs_body_and_releases_afterwards(self):
        conn = store.db()
        seen = []

        result = lease.run_locked(conn, self.TASK, "sess-a",
                                  lambda sid: seen.append(sid) or "ok")

        self.assertEqual(result, "ok")
        self.assertEqual(seen, ["sess-a"])
        self.assertIsNone(self.row(), "lease, взятый с нуля, обязан быть "
                                      "отпущен после тела")

    def test_renewed_own_lease_runs_body_and_is_not_released(self):
        conn = store.db()
        lease.acquire(conn, self.TASK, "sess-a")

        lease.run_locked(conn, self.TASK, "sess-a", lambda sid: None)

        self.assertIsNotNone(self.row(), "lease, продлённый (не с нуля), "
                                        "не имеет права быть отпущенным")

    def test_refusal_defaults_to_sys_exit_and_does_not_run_body(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", store.now()))
        conn.commit()
        called = []

        with self.assertRaises(SystemExit) as ctx:
            lease.run_locked(conn, self.TASK, "sess-caller",
                             lambda sid: called.append(sid))

        self.assertIn("sess-holder", str(ctx.exception))
        self.assertEqual(called, [])

    def test_refusal_with_print_channel_prints_and_returns_none_without_body(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", store.now()))
        conn.commit()
        called = []
        result = {}

        def call():
            result["value"] = lease.run_locked(
                conn, self.TASK, "sess-caller", lambda sid: called.append(sid),
                on_refusal="print")

        out = capture(call)

        self.assertIsNone(result["value"])
        self.assertEqual(called, [])
        self.assertIn("sess-holder", out)

    def test_body_result_is_released_even_when_body_raises(self):
        conn = store.db()

        with self.assertRaises(ValueError):
            lease.run_locked(conn, self.TASK, "sess-a",
                             lambda sid: (_ for _ in ()).throw(ValueError))

        self.assertIsNone(self.row(), "тело упало — lease, взятый с нуля, "
                                      "всё равно обязан быть отпущен")


class ForeignLiveLeaseTest(TmpRootTest):
    """SPEC 01M1NEEYSP0QWPMXHG0BK591M7, требование 1: `foreign_live_lease`/
    `warn_foreign_live` в изоляции — сквозной путь через `pause`/`release`
    покрыт приёмочными тестами AC-1..AC-7."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def insert_lease(self, session_id: str, pid: int, hostname: str,
                     heartbeat_ts: str) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    def steps(self):
        return store.task_steps(store.db(), self.TASK)

    def test_no_lease_returns_none(self):
        """Ловит мутацию: если `foreign_live_lease` перестанет возвращать
        `None` для задачи без строки lease вовсе (например, начнёт падать
        на `row["session_id"]` без проверки `row is None`), тест
        провалится на `AssertionError`, а не на исключении."""
        self.assertIsNone(
            lease.foreign_live_lease(store.db(), self.TASK, "sess-current"))

    def test_own_live_lease_returns_none(self):
        """Ловит мутацию: если проверка `row["session_id"] == session_id`
        будет убрана или инвертирована, функция начнёт возвращать строку
        СВОЕГО lease как «чужую» — тест провалится."""
        self.insert_lease("sess-current", os.getpid(), socket.gethostname(),
                          store.now())

        self.assertIsNone(
            lease.foreign_live_lease(store.db(), self.TASK, "sess-current"))

    def test_foreign_live_lease_returns_the_row(self):
        """Ловит мутацию: чужой lease на СВОЕМ host, свежий heartbeat,
        живой pid — если ветка `age > LEASE_STALE_AFTER_SEC` или проверка
        `_pid_alive` начнёт отказывать здесь ошибочно, `row` станет
        `None` вместо строки держателя."""
        self.insert_lease("sess-holder", os.getpid(), socket.gethostname(),
                          _ts_ago(5))

        row = lease.foreign_live_lease(store.db(), self.TASK, "sess-current")

        self.assertIsNotNone(row)
        self.assertEqual(row["session_id"], "sess-holder")

    def test_foreign_host_live_heartbeat_unaddressable_pid_returns_the_row(self):
        """Ловит мутацию R1-F1: чужой lease на ДРУГОМ host (типичный
        межхостовый случай, инцидент 02.09.2026 из SPEC «Контекст») с
        pid, заведомо мёртвым НА ЭТОЙ машине (`_dead_pid()`) — если код
        вернётся к безусловной проверке `_pid_alive` без сверки hostname,
        функция ошибочно вернёт `None` вместо строки держателя, хотя
        heartbeat свежий и lease реально жив на своём host."""
        self.insert_lease("sess-holder", _dead_pid(), "other-host",
                          _ts_ago(5))

        row = lease.foreign_live_lease(store.db(), self.TASK, "sess-current")

        self.assertIsNotNone(row)
        self.assertEqual(row["session_id"], "sess-holder")

    def test_foreign_stale_heartbeat_returns_none(self):
        """Ловит мутацию: если порог `config.LEASE_STALE_AFTER_SEC` в
        сравнении `age > ...` будет сдвинут или убран, протухший чужой
        lease начнёт ошибочно считаться живым."""
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        self.insert_lease("sess-holder", os.getpid(), socket.gethostname(),
                          stale_ts)

        self.assertIsNone(
            lease.foreign_live_lease(store.db(), self.TASK, "sess-current"))

    def test_foreign_dead_pid_returns_none(self):
        """Ловит мутацию: чужой lease на СВОЕМ host с мёртвым pid — если
        сверка `row["hostname"] == socket.gethostname()` перед
        `_pid_alive` будет убрана или инвертирована, мёртвый держатель на
        своём же host начнёт ошибочно считаться живым."""
        self.insert_lease("sess-holder", _dead_pid(), socket.gethostname(),
                          _ts_ago(5))

        self.assertIsNone(
            lease.foreign_live_lease(store.db(), self.TASK, "sess-current"))

    def test_warn_foreign_live_prints_holder_and_heartbeat_age(self):
        """Ловит мутацию: если `warn_foreign_live` перестанет печатать
        `session_id` держателя или числовой возраст heartbeat, регекс
        `\\d+\\s*сек`/`assertIn` перестанут находить их в выводе."""
        self.insert_lease("sess-holder", os.getpid(), socket.gethostname(),
                          _ts_ago(5))

        output = capture(lease.warn_foreign_live, store.db(), self.TASK,
                         "sess-current")

        self.assertIn("sess-holder", output)
        self.assertRegex(output, r"\d+\s*сек")

    def test_warn_foreign_live_includes_role_and_step_when_known(self):
        """Ловит мутацию R1-F2: `T001` заведена в состоянии `in_dev`
        (`config.STATE_ROLE["in_dev"] == "developer"`) — если
        `warn_foreign_live` перестанет подмешивать `role=`/`step=` в
        вывод и журнал, когда `runner.step_role` резолвится не в `None`,
        `assertIn` ниже не найдут ни то, ни другое."""
        self.insert_lease("sess-holder", os.getpid(), socket.gethostname(),
                          _ts_ago(5))

        output = capture(lease.warn_foreign_live, store.db(), self.TASK,
                         "sess-current")

        self.assertIn("role=developer", output)
        self.assertIn("step=in_dev", output)
        self.assertIn("role=developer", self.steps()[0]["detail"])
        self.assertIn("step=in_dev", self.steps()[0]["detail"])

    def test_warn_foreign_live_journals_with_holder_session_id(self):
        """Ловит мутацию: если `store.journal` внутри `warn_foreign_live`
        перестанет вызываться, или вызовется с `session_id` ТЕКУЩЕЙ
        сессии вместо держателя, `new[0]["session_id"]` разойдётся с
        `"sess-holder"` (требование 3 — identity держателя, не
        текущей)."""
        self.insert_lease("sess-holder", os.getpid(), socket.gethostname(),
                          _ts_ago(5))

        capture(lease.warn_foreign_live, store.db(), self.TASK,
               "sess-current")

        new = self.steps()
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["session_id"], "sess-holder")
        self.assertIn("sess-holder", new[0]["detail"])

    def test_warn_own_live_lease_prints_nothing_and_does_not_journal(self):
        """Ловит мутацию: если `warn_foreign_live` перестанет полагаться
        на `foreign_live_lease` (например, начнёт печатать для ЛЮБОГО
        lease вне зависимости от identity), собственный живой lease
        текущей сессии начнёт ошибочно печататься и журналироваться —
        требование 2."""
        self.insert_lease("sess-current", os.getpid(), socket.gethostname(),
                          store.now())

        output = capture(lease.warn_foreign_live, store.db(), self.TASK,
                         "sess-current")

        self.assertEqual(output, "")
        self.assertEqual(self.steps(), [])

    def test_warn_no_lease_prints_nothing_and_does_not_journal(self):
        """Ловит мутацию: если `warn_foreign_live` перестанет проверять
        `foreign_live_lease is None` перед печатью/журналом, задача без
        lease вовсе начнёт ошибочно порождать вывод или запись."""
        output = capture(lease.warn_foreign_live, store.db(), self.TASK,
                         "sess-current")

        self.assertEqual(output, "")
        self.assertEqual(self.steps(), [])


class ConcurrentAcquireTest(TmpRootTest):
    """Ревью T044 (итерация 1), Замечание 1: read-then-write в `acquire()`
    (`lease_row` -> `insert_lease`/`update_lease`) должен быть атомарным
    под конкурентным доступом двух и более сессий к одной задаче — не
    только в однопоточных прогонах остальных тестов этого файла. Каждый
    поток открывает своё собственное подключение (`store.db()`), как и
    делают отдельные процессы CLI, — общий только файл БД."""

    TASK = "T001"
    THREADS = 8

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        # Догоняет migrate()/seed_task_counters ПОСЛЕ вставки T001, пока
        # тест ещё однопоточный: без этого первый же `store.db()` каждого
        # потока ниже гонится за посевом task_counters.artel — отдельный,
        # не связанный с T044 дефект (check-then-insert без транзакции в
        # `store.seed_task_counters`), который иначе маскирует проверяемую
        # здесь гонку `lease.acquire()`.
        store.db()

    def _run_concurrently(self, session_ids):
        """Каждая сессия — своё подключение, как у реального CLI-процесса.
        sqlite3 запрещает использовать Connection не из того потока, где
        она создана, поэтому каждый поток открывает её сам — но ДО
        барьера, который синхронизирует только сам вызов `acquire()`.
        Иначе тест ловит не гонку `acquire()`, а несвязанную с T044 гонку
        на посев `task_counters` внутри `store.migrate()`, который зовёт
        каждый `store.db()` (эта гонка уже закрыта разово в `setUp()`,
        до которого сюда никакой поток не доходит)."""
        barrier = threading.Barrier(len(session_ids))
        results = [None] * len(session_ids)
        errors = []

        def worker(i, sid):
            try:
                conn = store.db()
                barrier.wait(timeout=5)
                results[i] = lease.acquire(conn, self.TASK, sid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i, sid))
                  for i, sid in enumerate(session_ids)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        return results, errors

    def test_concurrent_acquire_on_free_lease_exactly_one_wins(self):
        """Случай 1 из Замечания 1: гонка на INSERT при свободном lease —
        раньше вторая сессия получала необработанный
        `sqlite3.IntegrityError` вместо именованного отказа."""
        session_ids = [f"sess-{i}" for i in range(self.THREADS)]

        results, errors = self._run_concurrently(session_ids)

        self.assertEqual(errors, [], "acquire() не должна падать под гонкой")
        fresh_wins = [r for r in results if r[1]]
        refusals = [r for r in results if r[0] is not None]
        self.assertEqual(len(fresh_wins), 1, results)
        self.assertEqual(len(refusals), self.THREADS - 1, results)

    def test_concurrent_acquire_on_stale_lease_exactly_one_intercepts(self):
        """Случай 2 из Замечания 1: гонка на UPDATE протухшего чужого
        lease — раньше обе сессии молча считали лизинг своим и обе шли
        выполнять тело мутирующей команды параллельно."""
        conn = store.db()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", stale_ts))
        conn.commit()
        journalled_before = len(store.task_steps(store.db(), self.TASK))
        session_ids = [f"sess-{i}" for i in range(self.THREADS)]

        results, errors = self._run_concurrently(session_ids)

        self.assertEqual(errors, [], "acquire() не должна падать под гонкой")
        wins = [r for r in results if r[0] is None]
        self.assertEqual(len(wins), 1, results)
        row = store.lease_row(store.db(), self.TASK)
        self.assertIn(row["session_id"], session_ids)
        new_steps = store.task_steps(store.db(), self.TASK)[journalled_before:]
        intercept_steps = [s for s in new_steps if "lease" in s["action"]]
        self.assertEqual(len(intercept_steps), 1, new_steps)


if __name__ == "__main__":
    unittest.main()
