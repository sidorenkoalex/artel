"""AC-1, AC-2 (tasks/T050/SPEC.md): конкурентный CAS-переход состояния —
ровно один вызов побеждает, у проигравшего нет следов ни в `steps`, ни в
хэш-фиксации.

Песочница — `tests.sandbox.TmpRootTest` (лёгкая: БД и артефакты во
временном каталоге, без git) тем же приёмом, что
`tests/test_lease.py::ConcurrentAcquireTest` (T044) — гонка на реальном
файле sqlite между настоящими подключениями `store.db()`, каждое в своём
потоке, как у отдельных CLI-процессов.

Победителя ищем не по возврату/исключению `set_state` (SPEC требование 3
сознательно оставляет форму отказа открытой — «возвращается/бросается»),
а по земле истины — самой БД: сколько записей о переходе и о
хэш-фиксации реально появилось в `steps`.
"""
import sys
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK = "T001"
THREADS = 8


class ConcurrentSetStateTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        # Догоняет migrate()/seed_task_counters ПОСЛЕ вставки задачи, пока
        # тест ещё однопоточный (тот же приём, что
        # tests/test_lease.py::ConcurrentAcquireTest.setUp) — иначе гонка
        # ниже ловит не CAS `set_state`, а несвязанный check-then-insert
        # посева task_counters внутри store.migrate().
        store.db()

    def _race(self) -> None:
        barrier = threading.Barrier(THREADS)

        def worker(i: int) -> None:
            conn = store.db()
            barrier.wait(timeout=5)
            try:
                store.set_state(conn, task_id=TASK, state="review",
                                actor=f"actor-{i}", expected_state="in_dev")
            except BaseException:
                # Проигрыш CAS может уйти исключением (требование 3
                # позволяет и это) — исход теста решает состояние БД, не
                # форма отказа.
                pass

        threads = [threading.Thread(target=worker, args=(i,))
                  for i in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

    def test_ac1_exactly_one_concurrent_call_wins(self):
        self._race()

        row = store.db().execute(
            "SELECT state FROM tasks WHERE id=?", (TASK,)).fetchone()
        self.assertEqual(row["state"], "review",
                         "ни один из конкурентных вызовов не победил")
        transitions = store.db().execute(
            "SELECT COUNT(*) AS n FROM steps WHERE task_id=? AND action=?",
            (TASK, "state -> review")).fetchone()["n"]
        self.assertEqual(
            transitions, 1,
            f"ровно один вызов из {THREADS} обязан победить CAS, а "
            f"записей о переходе в журнале {transitions}")

    def test_ac2_losing_calls_leave_no_trace_in_steps_or_fixation(self):
        steps_before = len(store.task_steps(store.db(), TASK))

        self._race()

        new_steps = store.task_steps(store.db(), TASK)[steps_before:]
        # Победитель оставляет РОВНО два следа: сам переход и хэш-
        # фиксацию (`store.set_state` -> `journal` + `record_fixation`);
        # семь проигравших вызовов не имеют права оставить ни одного.
        self.assertEqual(
            len(new_steps), 2,
            f"проигравшие вызовы оставили след в журнале сверх победителя: "
            f"{[dict(s) for s in new_steps]}")
        self.assertEqual({s["action"] for s in new_steps},
                         {"state -> review", "sha зафиксирован"})


if __name__ == "__main__":
    unittest.main()
