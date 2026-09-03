"""Юнит-тесты новых функций tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/SPEC.md
(детекция буксования цикла `auto` и алерты `kind=attention`).

Сквозные сценарии (порог холостых шагов внутри `_cmd_auto`, открытие
алерта на каждой причине остановки, закрытие через реальный
`fsm.cmd_advance`/`cmd_approve`/`cmd_reject`) гоняют приёмочные тесты
задачи (`tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/`); здесь —
сами новые функции в изоляции, без FSM/git: `alerts.raise_attention_alert`/
`close_attention_alerts`, хук `store.set_state -> _close_attention_alert`,
`auto._final_stop_raises_alert`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, auto, config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK = "T001"
OTHER_TASK = "T002"


class AttentionKindTest(unittest.TestCase):

    def test_attention_is_a_registered_alert_kind(self):
        self.assertIn("attention", alerts.KINDS)


class RaiseAttentionAlertTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())

    def test_raises_an_open_alert_of_kind_attention_naming_the_task(self):
        opened = alerts.raise_attention_alert(store.db(), TASK,
                                              f"[{TASK}] auto остановлен: причина")

        self.assertTrue(opened)
        rows = store.open_alerts(store.db(), "attention")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["target"], TASK)
        self.assertIn(TASK, rows[0]["message"])

    def test_repeated_call_with_the_same_message_does_not_duplicate(self):
        """AC-17: дедуп — существующий `alerts.raise_alert`, не
        переопределяется этой задачей."""
        message = f"[{TASK}] auto остановлен: причина"
        alerts.raise_attention_alert(store.db(), TASK, message)

        opened_again = alerts.raise_attention_alert(store.db(), TASK, message)

        self.assertFalse(opened_again)
        self.assertEqual(len(store.open_alerts(store.db(), "attention")), 1)

    def test_different_message_opens_a_second_alert(self):
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина A")
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина B")

        self.assertEqual(len(store.open_alerts(store.db(), "attention")), 2)


class CloseAttentionAlertsTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())

    def test_closes_open_attention_alerts_of_this_task(self):
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина")

        alerts.close_attention_alerts(store.db(), TASK)

        self.assertEqual(store.open_alerts(store.db(), "attention"), [])

    def test_leaves_another_tasks_attention_alert_open(self):
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина")
        alerts.raise_attention_alert(store.db(), OTHER_TASK,
                                     f"[{OTHER_TASK}] причина")

        alerts.close_attention_alerts(store.db(), TASK)

        opened = store.open_alerts(store.db(), "attention")
        self.assertEqual([r["target"] for r in opened], [OTHER_TASK])

    def test_leaves_other_kinds_of_this_task_open(self):
        """Требование «Не входит»: закрытие требования 4 — только
        `kind=attention`, дедуп/ack других видов (incident/threshold/
        trigger) не переопределяется."""
        alerts.raise_alert(store.db(), TASK, "incident", "doctor", "инцидент")

        alerts.close_attention_alerts(store.db(), TASK)

        self.assertEqual(len(store.open_alerts(store.db(), "incident")), 1)

    def test_no_open_alert_is_a_no_op(self):
        alerts.close_attention_alerts(store.db(), TASK)

        self.assertEqual(store.open_alerts(store.db(), "attention"), [])


class SetStateClosesAttentionAlertTest(TmpRootTest):
    """Требование 4 (ANSWER-1, вопрос 1, вариант B): хук висит в
    `store.set_state`, единственной точке ЛЮБОГО перехода FSM — не
    привязан к тому, кто её вызвал (`auto`, ручной `advance`/`approve`/
    `reject`)."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def test_a_transition_closes_the_open_attention_alert(self):
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина")

        store.set_state(store.db(), TASK, "review", "test",
                        expected_state="in_dev")

        self.assertEqual(store.open_alerts(store.db(), "attention"), [])

    def test_a_transition_without_an_open_alert_does_not_fail(self):
        store.set_state(store.db(), TASK, "review", "test",
                        expected_state="in_dev")

        self.assertEqual(store.get_task(store.db(), TASK)["state"], "review")

    def test_a_losing_cas_call_does_not_close_the_alert(self):
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина")

        with self.assertRaises(store.CasConflict):
            store.set_state(store.db(), TASK, "review", "test",
                            expected_state="acceptance")

        self.assertEqual(len(store.open_alerts(store.db(), "attention")), 1)


class FinalStopRaisesAlertTest(unittest.TestCase):
    """`auto._final_stop_raises_alert` — решение финального выхода цикла
    (нет агентской роли, `auto_stop_advice`), в изоляции от FSM/БД."""

    def test_manual_gates_raise_no_alert(self):
        for state in ("spec_gate", "acceptance", "merge_gate"):
            with self.subTest(state=state):
                self.assertFalse(auto._final_stop_raises_alert(state, 3))

    def test_terminal_states_raise_no_alert(self):
        for state in ("done", "killed"):
            with self.subTest(state=state):
                self.assertFalse(auto._final_stop_raises_alert(state, 0))

    def test_spec_writing_with_zero_steps_raises_no_alert(self):
        """AC-16: TZ.md ещё не заведён — роли не было с самого начала."""
        self.assertFalse(auto._final_stop_raises_alert("spec_writing", 0))

    def test_spec_writing_with_at_least_one_step_raises_an_alert(self):
        self.assertTrue(auto._final_stop_raises_alert("spec_writing", 1))

    def test_escalated_with_zero_steps_raises_an_alert(self):
        """AC-17: эскалация, случившаяся до вызова (`auto` не выполнила
        ни одного шага) — по-прежнему сигнал, не «роли не было»."""
        self.assertTrue(auto._final_stop_raises_alert("escalated", 0))

    def test_other_states_raise_an_alert(self):
        for state in ("in_dev", "review", "verifying", "tests_writing"):
            with self.subTest(state=state):
                self.assertTrue(auto._final_stop_raises_alert(state, 5))


if __name__ == "__main__":
    unittest.main()
