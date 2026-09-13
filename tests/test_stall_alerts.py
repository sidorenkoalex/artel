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
from tests.sandbox import SchemaSeededTmpRootTest, SchemaTmpRootTest  # noqa: E402

TASK = "T001"
OTHER_TASK = "T002"


class AttentionKindTest(unittest.TestCase):

    def test_attention_is_a_registered_alert_kind(self):
        """"attention" зарегистрирован как валидный `kind` алерта.

        Ловит мутацию: kind "attention" не добавлен в `alerts.KINDS` (или
        опечатан) — любой вызов `raise_alert(..., "attention", ...)`
        бросит `ValueError` раньше, чем дело дойдёт до алерта.
        """
        self.assertIn("attention", alerts.KINDS)


class RaiseAttentionAlertTest(SchemaTmpRootTest):

    def test_raises_an_open_alert_of_kind_attention_naming_the_task(self):
        """Первый вызов `raise_attention_alert` заводит открытый алерт
        `kind=attention` с задачей в `target` и в тексте сообщения.

        Ловит мутацию: `raise_attention_alert` передаст в `raise_alert`
        не тот `kind` (например, оставит "incident") или не передаст
        `task_id` в `target` — фильтр `open_alerts(..., "attention")`
        не найдёт строку, либо `rows[0]["target"]` разойдётся с TASK.
        """
        opened = alerts.raise_attention_alert(store.db(), TASK,
                                              f"[{TASK}] auto остановлен: причина")

        self.assertTrue(opened)
        rows = store.open_alerts(store.db(), "attention")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["target"], TASK)
        self.assertIn(TASK, rows[0]["message"])

    def test_repeated_call_with_the_same_message_does_not_duplicate(self):
        """AC-17: дедуп — существующий `alerts.raise_alert`, не
        переопределяется этой задачей.

        Ловит мутацию: `raise_attention_alert` перестанет опираться на
        дедуп `raise_alert` (например, позовёт `store.insert_alert`
        напрямую) — повторный вызов с тем же сообщением откроет второй
        алерт вместо переиспользования первого.
        """
        message = f"[{TASK}] auto остановлен: причина"
        alerts.raise_attention_alert(store.db(), TASK, message)

        opened_again = alerts.raise_attention_alert(store.db(), TASK, message)

        self.assertFalse(opened_again)
        self.assertEqual(len(store.open_alerts(store.db(), "attention")), 1)

    def test_different_message_opens_a_second_alert(self):
        """Два вызова с РАЗНЫМИ сообщениями для одной задачи открывают
        два разных алерта — дедуп различает алерты по всему кортежу
        `(target, kind, source, message)`, не только по `target`.

        Ловит мутацию: `raise_attention_alert` начнёт дедуплицировать
        только по `(target, kind)` без учёта `message` — второй вызов
        будет молча проглочен, и открытых алертов останется один вместо
        двух.
        """
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина A")
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина B")

        self.assertEqual(len(store.open_alerts(store.db(), "attention")), 2)


class CloseAttentionAlertsTest(SchemaTmpRootTest):

    def test_closes_open_attention_alerts_of_this_task(self):
        """Открытый алерт `attention` этой задачи закрывается вызовом
        `close_attention_alerts`.

        Ловит мутацию: `close_attention_alerts` перестанет звать
        `store.ack_alert` для найденной строки (например, пустое тело
        цикла) — алерт останется открытым после вызова.
        """
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина")

        alerts.close_attention_alerts(store.db(), TASK)

        self.assertEqual(store.open_alerts(store.db(), "attention"), [])

    def test_leaves_another_tasks_attention_alert_open(self):
        """Закрытие алертов задачи TASK не трогает открытый алерт
        другой задачи (OTHER_TASK).

        Ловит мутацию: фильтр `row["target"] == task_id` внутри
        `close_attention_alerts` будет снят — закрытие TASK заодно
        закроет чужой алерт, и список открытых алертов после вызова
        окажется пустым вместо `[OTHER_TASK]`.
        """
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина")
        alerts.raise_attention_alert(store.db(), OTHER_TASK,
                                     f"[{OTHER_TASK}] причина")

        alerts.close_attention_alerts(store.db(), TASK)

        opened = store.open_alerts(store.db(), "attention")
        self.assertEqual([r["target"] for r in opened], [OTHER_TASK])

    def test_leaves_other_kinds_of_this_task_open(self):
        """Требование «Не входит»: закрытие требования 4 — только
        `kind=attention`, дедуп/ack других видов (incident/threshold/
        trigger) не переопределяется.

        Ловит мутацию: `close_attention_alerts` перестанет фильтровать
        по kind при чтении (например, позовёт `open_alerts(conn)` без
        аргумента `kind` вместо `open_alerts(conn, "attention")`) —
        заодно закроет incident-алерт той же задачи, обязанный
        остаться открытым.
        """
        alerts.raise_alert(store.db(), TASK, "incident", "doctor", "инцидент")

        alerts.close_attention_alerts(store.db(), TASK)

        self.assertEqual(len(store.open_alerts(store.db(), "incident")), 1)

    def test_no_open_alert_is_a_no_op(self):
        """Вызов `close_attention_alerts` без единого открытого алерта
        задачи не бросает исключение и не заводит побочных строк.

        Ловит мутацию: цикл по `open_alerts` внутри функции перестанет
        корректно обрабатывать пустой результат (например, обратится к
        первому элементу без проверки длины) — вызов упадёт исключением
        там, где ожидается тихий no-op.
        """
        alerts.close_attention_alerts(store.db(), TASK)

        self.assertEqual(store.open_alerts(store.db(), "attention"), [])


class SetStateClosesAttentionAlertTest(SchemaSeededTmpRootTest):
    """Требование 4 (ANSWER-1, вопрос 1, вариант B): хук висит в
    `store.set_state`, единственной точке ЛЮБОГО перехода FSM — не
    привязан к тому, кто её вызвал (`auto`, ручной `advance`/`approve`/
    `reject`)."""

    def test_a_transition_closes_the_open_attention_alert(self):
        """Успешный CAS-переход `set_state` закрывает открытый алерт
        `attention` этой задачи — хук сидит в единственной точке ЛЮБОГО
        перехода FSM.

        Ловит мутацию: вызов `_close_attention_alert` будет убран из
        `set_state` — алерт останется открытым после успешного перехода
        `in_dev -> review`.
        """
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина")

        store.set_state(store.db(), TASK, "review", "test",
                        expected_state="in_dev")

        self.assertEqual(store.open_alerts(store.db(), "attention"), [])

    def test_a_transition_without_an_open_alert_does_not_fail(self):
        """Переход `set_state` без единого открытого алерта задачи
        проходит штатно — хук закрытия не мешает основной логике
        перехода.

        Ловит мутацию: `_close_attention_alert` перестанет корректно
        обрабатывать отсутствие открытых алертов (например, обратится
        к первому элементу пустого списка без проверки) — переход
        упадёт исключением вместо штатной смены `state`.
        """
        store.set_state(store.db(), TASK, "review", "test",
                        expected_state="in_dev")

        self.assertEqual(store.get_task(store.db(), TASK)["state"], "review")

    def test_a_losing_cas_call_does_not_close_the_alert(self):
        """Проигранный CAS (`expected_state` не совпал с фактическим)
        бросает `CasConflict` и НЕ закрывает открытый алерт — хук стоит
        после проверки `cur.rowcount`, не до неё.

        Ловит мутацию: `_close_attention_alert` переставят выше проверки
        `cur.rowcount == 0` (или вызовут её безусловно) — алерт закроется
        даже на проигранной гонке, когда реального перехода не было.
        """
        alerts.raise_attention_alert(store.db(), TASK, f"[{TASK}] причина")

        with self.assertRaises(store.CasConflict):
            store.set_state(store.db(), TASK, "review", "test",
                            expected_state="acceptance")

        self.assertEqual(len(store.open_alerts(store.db(), "attention")), 1)


class FinalStopRaisesAlertTest(unittest.TestCase):
    """`auto._final_stop_raises_alert` — решение финального выхода цикла
    (нет агентской роли, `auto_stop_advice`), в изоляции от FSM/БД."""

    def test_manual_gates_raise_no_alert(self):
        """Финальный выход цикла на ручном гейте (`spec_gate`/
        `acceptance`/`merge_gate`) не поднимает алерт — Оператор уже
        видит «ЖДЁТ ОПЕРАТОРА» в статусе, сигнал был бы избыточен.

        Ловит мутацию: один из трёх гейтов будет по ошибке убран из
        `_NO_ALERT_FINAL_STATES` (опечатка в имени состояния или
        пропущенный элемент кортежа) — `_final_stop_raises_alert`
        вернёт `True` для гейта, ждущего Оператора.
        """
        for state in ("spec_gate", "acceptance", "merge_gate"):
            with self.subTest(state=state):
                self.assertFalse(auto._final_stop_raises_alert(state, 3))

    def test_terminal_states_raise_no_alert(self):
        """Финальный выход в терминальном состоянии (`done`/`killed`)
        не поднимает алерт — задача закрыта, буксовать ей больше негде.

        Ловит мутацию: `done`/`killed` будут по ошибке убраны из
        `_NO_ALERT_FINAL_STATES` — закрытая или убитая задача поднимет
        ложный алерт буксования.
        """
        for state in ("done", "killed"):
            with self.subTest(state=state):
                self.assertFalse(auto._final_stop_raises_alert(state, 0))

    def test_spec_writing_with_zero_steps_raises_no_alert(self):
        """AC-16: TZ.md ещё не заведён — роли не было с самого начала,
        ноль пройденных шагов в `spec_writing` не поднимает алерт.

        Ловит мутацию: условие `state == "spec_writing" and steps == 0`
        ослабят до одного `state == "spec_writing"` (без проверки
        `steps`) — задача, реально буксующая в `spec_writing` (TZ.md
        заведён, шаги были), перестанет поднимать алерт.
        """
        self.assertFalse(auto._final_stop_raises_alert("spec_writing", 0))

    def test_spec_writing_with_at_least_one_step_raises_an_alert(self):
        """`spec_writing` минимум с одним пройденным шагом (роль уже
        работала) поднимает алерт — исключение требования 3 касается
        только НУЛЯ шагов, не состояния целиком.

        Ловит мутацию: проверку `steps == 0` заменят на `steps <= 1`
        (или уберут вовсе) — реально буксующий `spec_writing` с уже
        сделанной попыткой перестанет сигналить Оператору.
        """
        self.assertTrue(auto._final_stop_raises_alert("spec_writing", 1))

    def test_escalated_with_zero_steps_raises_an_alert(self):
        """AC-17: эскалация, случившаяся до вызова (`auto` не выполнила
        ни одного шага) — по-прежнему сигнал, не «роли не было».

        Ловит мутацию: `escalated` по ошибке добавят в исключение по
        нулю шагов (аналогично `spec_writing`) — задача, эскалированная
        ДО этого вызова `auto`, перестанет поднимать алерт при нулевом
        числе шагов текущего вызова.
        """
        self.assertTrue(auto._final_stop_raises_alert("escalated", 0))

    def test_other_states_raise_an_alert(self):
        """Любое прочее агентское состояние (`in_dev`/`review`/
        `verifying`/`tests_writing`) при ненулевом числе шагов поднимает
        алерт — общий случай вне перечисленных исключений.

        Ловит мутацию: список `_NO_ALERT_FINAL_STATES` расширят лишним
        состоянием (например, `in_dev` по ошибке попадёт туда) —
        реальное буксование в рабочем состоянии перестанет сигналить
        Оператору.
        """
        for state in ("in_dev", "review", "verifying", "tests_writing"):
            with self.subTest(state=state):
                self.assertTrue(auto._final_stop_raises_alert(state, 5))


if __name__ == "__main__":
    unittest.main()
