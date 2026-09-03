"""Приёмочные тесты AC-17 — tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/SPEC.md:
повторный вызов `auto`, застающий ту же незакрытую причину, не заводит
дубликат алерта — переиспользуется существующий дедуп `alerts.
raise_alert` (SPEC «Не входит»: сам дедуп эта задача не меняет).

Красен до реализации: ДА. Сегодня остановка `auto` вообще не заводит
`kind=attention` алерт (`alerts.KINDS` без `"attention"`) — после ДВУХ
подряд вызовов `self.auto()` на одной и той же незакрытой эскалации
`self.open_attention_alerts()` останется пуст, тест падает на
`assertEqual(len(...), 1)` (получит 0), а не на дубликате: сам дедуп
`alerts.raise_alert` уже сегодня рабочий и не новый код этой задачи —
падать может только факт «алерт вообще не заведён».

Песочница — `_sandbox.StallDetectionSandbox`, тот же приём, что и в
остальных файлах этой задачи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import StallDetectionSandbox  # noqa: E402


class Ac17RepeatedStopOnTheSameUnclosedCauseDoesNotDuplicateTheAlertTest(
        StallDetectionSandbox):
    """AC-17: повторный вызов `auto`, останавливающийся по той же
    незакрытой причине (тот же `target`/`kind`/`source`/`message`), не
    заводит дубликат алерта — открытый алерт остаётся один."""

    def setUp(self):
        super().setUp()
        self.write_plan()
        self.set_state("in_dev")

    def test_ac17_two_auto_calls_on_the_same_unclosed_escalation_open_one_alert(self):
        """Первый вызов роняет задачу в `escalated` и заводит алерт
        (AC-7); задача остаётся в `escalated` (auto не проходит гейт
        эскалации сама, только Оператор через `approve`) — второй вызов
        `auto` из того же состояния встаёт по той же причине немедленно
        (роли у `escalated` нет, ни одного шага `run`+`advance`).

        Ловит мутацию: хук алерта заводит запись через `store.insert_
        alert` напрямую (в обход `alerts.raise_alert` и его дедупа по
        `(target, kind, source, message)`) — тогда второй вызов на той
        же незакрытой причине завёл бы вторую строку вместо переиспользования
        первой, и Оператор увидел бы дублирующиеся сигналы об одной и
        той же проблеме.
        """
        self.agent.script = [lambda: self.set_state("escalated")]
        self.auto()
        opened_after_first = self.open_attention_alerts()
        self.assertEqual(len(opened_after_first), 1,
                         f"после первого вызова открытых алертов: "
                         f"{len(opened_after_first)}")

        self.auto()

        opened_after_second = self.open_attention_alerts()
        self.assertEqual(
            len(opened_after_second), 1,
            f"повторный вызов auto на той же незакрытой причине завёл "
            f"дубликат алерта: открытых алертов "
            f"{len(opened_after_second)}")
        self.assertEqual(opened_after_first[0]["id"], opened_after_second[0]["id"],
                         "переиспользована должна быть ТА ЖЕ строка алерта")


if __name__ == "__main__":
    unittest.main()
