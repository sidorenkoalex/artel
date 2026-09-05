"""Юнит-тесты orchestrator/zone_lock.py (SPEC 01M1P9QAG65GVF69YJEV0V18D9).

Приёмочные тесты (tasks/01M1P9QAG65GVF69YJEV0V18D9/acceptance_tests) кроют
AC-1..AC-9 сквозным путём через `run`/`auto`/`status`/`doctor`; здесь — сам
модуль `zone_lock.py` в изоляции: чистые функции `blocking_conflict`,
`refusal`, `queue_order` и CLI-команды `cmd_zone_release`/
`cmd_zone_reorder`, без прогона команд CLI верхнего уровня.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class ZoneLockTest(TmpRootTest):
    TASK = "T001"
    OTHER = "T901"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def set_own_zones(self, zones: str | None) -> None:
        store.update_task(store.db(), self.TASK, zones=zones)

    def set_own_state(self, state: str) -> None:
        store.update_task(store.db(), self.TASK, state=state)

    def seed_other(self, state: str, zones: str | None,
                   target: str = config.DEFAULT_TARGET,
                   task_id: str | None = None) -> str:
        task_id = task_id or self.OTHER
        store.insert_task(store.db(), task_id, f"Другая {task_id}", state,
                          f"task/{task_id.lower()}-fake", target,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(store.db(), task_id, zones=zones)
        return task_id

    def get_task(self, task_id: str | None = None):
        return store.get_task(store.db(), task_id or self.TASK)

    # ----------------------------------------------------------- no conflict

    def test_no_zones_means_no_conflict(self):
        self.seed_other("in_dev", "a/b")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_own_state_other_than_in_dev_never_conflicts(self):
        self.set_own_zones("a/b")
        self.set_own_state("review")
        self.seed_other("in_dev", "a/b")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_disjoint_zones_do_not_conflict(self):
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "c/d")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_intersection_only_on_common_zone_does_not_conflict(self):
        common = ("orchestrator/config.py",)
        with mock.patch.object(config, "COMMON_ZONES", common,
                              create=True):
            self.set_own_zones("orchestrator/config.py,a/b")
            self.seed_other("in_dev", "orchestrator/config.py,c/d")

            self.assertIsNone(zone_lock.blocking_conflict(
                store.db(), self.TASK, self.get_task()))

    def test_other_target_never_conflicts(self):
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "a/b", target="other-target")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_own_task_excluded_from_scan(self):
        self.set_own_zones("a/b")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    # -------------------------------------------------- blocking states range

    def _clear_other_tasks(self) -> None:
        conn = store.db()
        conn.execute("DELETE FROM tasks WHERE id != ?", (self.TASK,))
        conn.commit()

    def test_occupier_in_each_blocking_state_conflicts(self):
        self.set_own_zones("a/b")
        for state in ("in_dev", "review", "verifying", "acceptance",
                      "merge_gate"):
            with self.subTest(state=state):
                self._clear_other_tasks()
                occupier = f"T9{state[:3]}"
                self.seed_other(state, "a/b", task_id=occupier)

                conflict = zone_lock.blocking_conflict(
                    store.db(), self.TASK, self.get_task())

                self.assertIsNotNone(conflict)
                self.assertEqual(conflict, ("a/b", occupier, state))

    def test_occupier_outside_range_does_not_conflict(self):
        self.set_own_zones("a/b")
        for state in ("tests_writing", "spec_writing", "done", "killed"):
            with self.subTest(state=state):
                self._clear_other_tasks()
                occupier = f"T9{state[:3]}"
                self.seed_other(state, "a/b", task_id=occupier)

                self.assertIsNone(zone_lock.blocking_conflict(
                    store.db(), self.TASK, self.get_task()))

    # ------------------------------------------------------------ first-step

    def test_first_step_boundary_uses_current_in_dev_visit(self):
        """Маркер `agent run started`, записанный ДО перехода в текущий
        визит `in_dev` (например, в предыдущем визите того же состояния),
        не освобождает от проверки — граница считается от последней
        записи `"state -> in_dev"`."""
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "a/b")
        store.journal(store.db(), self.TASK, "developer",
                     "agent run started", "визит #1")
        store.set_state(store.db(), self.TASK, "review", "system",
                        expected_state="in_dev")
        store.set_state(store.db(), self.TASK, "in_dev", "system",
                        expected_state="review")

        conflict = zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task())

        self.assertIsNotNone(conflict)

    def test_agent_started_after_in_dev_boundary_lifts_conflict(self):
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "a/b")
        store.journal(store.db(), self.TASK, "system", "state -> in_dev", "")
        store.journal(store.db(), self.TASK, "developer",
                     "agent run started", "визит #2")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_operator_release_after_boundary_lifts_conflict(self):
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "a/b")
        store.journal(store.db(), self.TASK, "system", "state -> in_dev", "")

        zone_lock.cmd_zone_release(self.TASK)

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_release_before_boundary_does_not_lift_a_later_visit(self):
        """Снятие ожидания в ПРЕДЫДУЩЕМ визите `in_dev` не переносится на
        новый визит — Оператор снимает риск конкретно для того конфликта,
        что видел, не навсегда."""
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "a/b")
        zone_lock.cmd_zone_release(self.TASK)
        store.journal(store.db(), self.TASK, "system", "state -> in_dev", "")

        conflict = zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task())

        self.assertIsNotNone(conflict)

    # ------------------------------------------------------------ cmd_release

    def test_cmd_zone_release_journals_conscious_risk(self):
        out = capture(zone_lock.cmd_zone_release, self.TASK)

        tail = store.task_steps(store.db(), self.TASK)[-1]
        self.assertEqual(tail["actor"], "operator")
        self.assertEqual(tail["action"], zone_lock.RELEASE_ACTION)
        self.assertIn("риск", tail["detail"])
        self.assertIn(self.TASK, out)

    def test_cmd_zone_release_resolves_prefix(self):
        capture(zone_lock.cmd_zone_release, "T00")

        tail = store.task_steps(store.db(), self.TASK)[-1]
        self.assertEqual(tail["action"], zone_lock.RELEASE_ACTION)

    # ------------------------------------------------------------------- refusal

    def test_refusal_names_path_task_and_state(self):
        self.set_own_zones("a/b")
        self.seed_other("review", "a/b")

        text = zone_lock.refusal(store.db(), self.TASK, self.get_task())

        self.assertIsNotNone(text)
        self.assertIn("a/b", text)
        self.assertIn(self.OTHER, text)
        self.assertIn("review", text)

    def test_refusal_is_none_without_conflict(self):
        self.set_own_zones("a/b")

        self.assertIsNone(
            zone_lock.refusal(store.db(), self.TASK, self.get_task()))

    # --------------------------------------------------------------- queue_order

    def test_queue_order_sorts_by_updated_at_ascending(self):
        self.seed_other("in_dev", "a/b", task_id="T902")
        store.update_task(store.db(), "T902", updated_at="2026-09-01 10:00:00.000000Z")
        self.seed_other("in_dev", "a/b", task_id="T903")
        store.update_task(store.db(), "T903", updated_at="2026-09-01 09:00:00.000000Z")

        order = zone_lock.queue_order(store.db(), ["T902", "T903"])

        self.assertEqual(order, ["T903", "T902"])

    def test_explicit_position_overrides_updated_at(self):
        self.seed_other("in_dev", "a/b", task_id="T902")
        store.update_task(store.db(), "T902", updated_at="2026-09-01 09:00:00.000000Z")
        self.seed_other("in_dev", "a/b", task_id="T903")
        store.update_task(store.db(), "T903", updated_at="2026-09-01 10:00:00.000000Z")

        zone_lock.cmd_zone_reorder(["T903", "T902"])
        order = zone_lock.queue_order(store.db(), ["T902", "T903"])

        self.assertEqual(order, ["T903", "T902"])

    def test_reorder_positions_take_priority_over_unpositioned_natural_order(self):
        self.seed_other("in_dev", "a/b", task_id="T902")
        store.update_task(store.db(), "T902", updated_at="2026-09-01 08:00:00.000000Z")
        self.seed_other("in_dev", "a/b", task_id="T903")
        store.update_task(store.db(), "T903", updated_at="2026-09-01 09:00:00.000000Z")
        self.seed_other("in_dev", "a/b", task_id="T904")
        store.update_task(store.db(), "T904", updated_at="2026-09-01 10:00:00.000000Z")

        zone_lock.cmd_zone_reorder(["T904"])
        order = zone_lock.queue_order(store.db(), ["T902", "T903", "T904"])

        self.assertEqual(order, ["T904", "T902", "T903"])


if __name__ == "__main__":
    unittest.main()
