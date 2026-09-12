"""AC-6 (tasks/01M290PS4ZXK1RCZ3PXQSXK0Y9/SPEC.md): гонка двух и более
перехватчиков ОДНОГО и того же мёртвого lease — успешен только один
перехват; остальные вызывающие получают именованный отказ «lease уже
перехвачен сессией …», не создавая вторую запись журнала о перехвате.

Песочница и приём — тот же, что `tests/test_lease.py::ConcurrentAcquireTest`
(T044, реальная гонка настоящих подключений `store.db()` каждое в своём
потоке, барьер перед самим вызовом `acquire()`) и
`tasks/T050/acceptance_tests/test_ac1_ac2_concurrent_cas.py` (гонка CAS
`store.set_state`, на которую SPEC прямо ссылается как на образец приёма
для этого требования, «Материалы»): «землёй истины» служит сама БД
(сколько записей о перехвате реально появилось), а не то, что вернул
КОНКРЕТНЫЙ проигравший поток — при `N` конкурентных попытках возможно,
что поток стартует настолько поздно, что застаёт лизинг уже перехваченным
живым держателем, и получает обычный отказ «подожди её» (не баг: лизинг
на тот момент правда жив) — поэтому текст «уже перехвачен» проверяется
как «хотя бы у одного из проигравших», не у каждого.

Красен до реализации: сегодня чужой lease того же hostname с heartbeat
моложе порога отказывает БЕЗУСЛОВНО (`orchestrator/lease.py:84`, до
всякой проверки pid) — ни один из конкурентных вызовов не перехватит
мёртвый lease вовсе, `wins` ниже останется пустым списком.
"""
import socket
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, _dead_pid, _ts_ago, capture  # noqa: E402

TASK = "T001"
THREADS = 8


class ConcurrentDeadPidInterceptTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (TASK, "sess-dead-holder", _dead_pid(), socket.gethostname(),
             _ts_ago(5)))
        conn.commit()
        # Догоняет migrate()/seed_task_counters ПОСЛЕ вставки задачи, пока
        # тест ещё однопоточный — тот же приём, что
        # tests/test_lease.py::ConcurrentAcquireTest.setUp (иначе гонка
        # ниже ловит не перехват AC-6, а несвязанный check-then-insert
        # посева task_counters внутри store.migrate()).
        store.db()

    def _run_concurrently(self, session_ids):
        barrier = threading.Barrier(len(session_ids))
        results = [None] * len(session_ids)
        errors = []

        def worker(i, sid):
            try:
                conn = store.db()
                barrier.wait(timeout=5)
                results[i] = lease.acquire(conn, TASK, sid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i, sid))
                  for i, sid in enumerate(session_ids)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        return results, errors

    def test_ac6_only_one_interceptor_wins_and_losers_are_named(self):
        """`THREADS` сессий одновременно зовут `lease.acquire()` на один и
        тот же мёртвый lease с heartbeat моложе порога — ровно один
        перехват засчитывается, ровно одна запись журнала о перехвате,
        и хотя бы один проигравший получает именно отказ «lease уже
        перехвачен сессией <победитель>» (не общий «подожди её»).

        Ловит мутацию: если перехват реализовать БЕЗУСЛОВНОЙ записью
        строки без CAS-проверки прежних значений (session_id/pid/
        heartbeat держателя перед UPDATE), несколько потоков одновременно
        решат, что лизинг мёртв, и все запишут СВОЙ `UPDATE` — тогда
        `journal` о перехвате появится больше одного раза (см. проверку
        `intercept_steps` ниже), что и обязан ловить этот тест.
        """
        session_ids = [f"sess-taker-{i}" for i in range(THREADS)]
        journalled_before = len(store.task_steps(store.db(), TASK))

        results, errors = self._run_concurrently(session_ids)

        self.assertEqual(errors, [], "acquire() не должна падать под гонкой")
        wins = [(i, r) for i, r in enumerate(results)
               if r is not None and r[0] is None]
        self.assertEqual(len(wins), 1, results)
        winner_sid = session_ids[wins[0][0]]

        row = store.lease_row(store.db(), TASK)
        self.assertEqual(row["session_id"], winner_sid)

        new_steps = store.task_steps(store.db(), TASK)[journalled_before:]
        intercept_steps = [s for s in new_steps
                           if (s["action"] or "") == "lease перехвачен"]
        self.assertEqual(len(intercept_steps), 1, new_steps)

        refusals = [r[0] for i, r in enumerate(results)
                   if r is not None and r[0] is not None]
        self.assertEqual(len(refusals), THREADS - 1, results)
        self.assertTrue(
            any("уже перехвачен" in refusal and winner_sid in refusal
                for refusal in refusals),
            f"ни один из {len(refusals)} проигравших не получил "
            f"именованный отказ «lease уже перехвачен сессией "
            f"{winner_sid}»: {refusals}")


if __name__ == "__main__":
    unittest.main()
