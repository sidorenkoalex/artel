"""AC-5 — 01M3HJQV2QV9BXNXSH3F8STAYH: эскалация по бюджету закрывается
ОДНИМ подъёмом потолка, и поднятый потолок — конечная граница.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Задача клона, эскалировавшая по бюджету, получает от прогона ровно
один подъём потолка — до значения «потолок из SPEC клона × константа-
множитель `orchestrator/config.py`» (значение константы не меньше 2) —
возвращается в состояние, из которого эскалировала, и прогон продолжается;
повторное исчерпание уже поднятого потолка нового подъёма не даёт, то есть
поднятый потолок — конечная верхняя граница расхода этой задачи.

Сценарий — `_util.ClonelessRunSandbox` в режиме `exhaust`: вождение задачи
настоящее (`canary._drive_task`), шаг роли синтетический, а эскалацию по
бюджету пишет живой `budget.enforce_budget` — та самая причина перехода,
которой требование 6 велит отличать эту эскалацию от остальных.

Имя константы-множителя планка не угадывает: множитель снимается с
наблюдаемого подъёма, а затем ищется среди числовых констант `config`,
которых до этой задачи не было (`_util.new_numeric_config_constants`).

Красен до реализации: эскалацию по бюджету прогон закрывает синтетическим
ANSWER, не меняя потолка (`canary._drive_task`, ветка `escalated`) — потолок
задачи остаётся прежним, подъёма нет ни одного.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class SingleCeilingRaiseTest(_util.ClonelessRunSandbox):

    def setUp(self):
        super().setUp()
        self.run_one_task(mode="exhaust")

    def _budget_escalations(self) -> list:
        return [text for text in self.journal_texts()
                if text.startswith("state -> escalated")
                and "бюджет исчерпан" in text]

    def _ceiling_before_after(self) -> tuple:
        """(исходный потолок, поднятый потолок) — с названной причиной,
        если подъёма не было вовсе."""
        ceilings = self.ceilings_seen()
        self.assertEqual(
            2, len(ceilings),
            "шаг роли видел не два потолка (исходный и поднятый), а "
            f"{ceilings} — подъёма потолка не было либо он не один")
        return ceilings[0], ceilings[1]

    def test_ac5_budget_escalation_raises_the_ceiling_exactly_once(self):
        """Потолок задачи поднимается ровно один раз, хотя по бюджету задача
        эскалировала дважды: шаг роли видел два разных потолка, не три.

        Ловит мутацию: подъём делается на КАЖДОЙ эскалации по бюджету
        (признак «это бюджетная эскалация» есть, а памяти о том, что подъём
        уже был, нет) — канареечная задача тратила бы кошелёк Оператора без
        верхней границы, ровно от чего требование 8 и ставит границу.
        """
        self.assertGreaterEqual(
            len(self._budget_escalations()), 2,
            "сценарий не пробил потолок дважды — проверять однократность "
            f"нечем: {self.journal_texts()}")

        self.assertEqual(
            2, len(self.ceilings_seen()),
            "шаг роли видел не два потолка (исходный и поднятый), а "
            f"{self.ceilings_seen()}")
        self.assertEqual(self.ceilings_seen()[1],
                         self.task_row()["budget_usd"],
                         "потолок в БД не равен последнему потолку, который "
                         "видел шаг роли — был ещё один подъём")

    def test_ac5_new_ceiling_is_the_spec_ceiling_times_a_named_config_constant(self):
        """Поднятый потолок равен исходному, умноженному на новую числовую
        константу `orchestrator/config.py`, и множитель не меньше 2.

        Ловит мутацию: потолок поднимается прибавкой фиксированной суммы
        (либо множителем-литералом 1.5, зашитым в код) — у наблюдавшегося
        расхода 20-27.09 (до $26.25 при минимуме потолка $25) запаса не
        осталось бы, и прогон падал бы на том же месте, а Оператор не имел бы
        крутилки, чтобы это поправить.
        """
        before, after = self._ceiling_before_after()
        ratio = after / before

        self.assertGreaterEqual(
            ratio, 2,
            f"множитель потолка меньше 2: {before} -> {after}")

        named = {name: value
                 for name, value in _util.new_numeric_config_constants().items()
                 if abs(value - ratio) < 1e-9}
        self.assertTrue(
            named,
            f"подъём потолка {before} -> {after} (множитель {ratio}) не выражен "
            "ни одной новой числовой константой orchestrator/config.py; новые "
            f"константы: {_util.new_numeric_config_constants()}")

    def test_ac5_task_returns_to_the_state_it_escalated_from_and_the_run_goes_on(self):
        """После подъёма задача возвращается в состояние, из которого
        эскалировала, и прогон её ведёт дальше — шаг роли исполняется уже на
        поднятом потолке.

        Ловит мутацию: потолок поднят, но задача оставлена в `escalated`
        (или возвращена в `in_dev` жёстко, мимо `escalated_from`) — прогон
        либо встал бы на том же месте, либо терял точку возврата задачи,
        эскалировавшей не из разработки.
        """
        transitions = self.transitions()
        first = transitions.index("state -> escalated")

        self.assertLess(first + 1, len(transitions),
                        f"после эскалации по бюджету переходов нет: {transitions}")
        self.assertEqual("state -> in_dev", transitions[first + 1],
                         "задача вернулась не в состояние, из которого "
                         f"эскалировала: {transitions}")
        self.assertEqual(2, len(self.ceilings_seen()),
                         "шаг роли на поднятом потолке не исполнялся — прогон "
                         "после подъёма не продолжился")

    def test_ac5_second_exhaustion_of_the_raised_ceiling_does_not_raise_again(self):
        """Повторное исчерпание уже поднятого потолка нового подъёма не даёт:
        потолок задачи по итогам прогона равен первому поднятому значению.

        Ловит мутацию: признак «подъём уже был» читается из переменной цикла,
        которая обнуляется при уходе из `escalated` (как `dev_retries`) —
        каждая новая эскалация по бюджету снова поднимала бы потолок, и
        конечной верхней границы расхода не существовало бы.
        """
        before, after = self._ceiling_before_after()

        self.assertEqual(after, self.task_row()["budget_usd"])
        self.assertGreaterEqual(self.task_row()["spent_usd"], after,
                                "сценарий не исчерпал поднятый потолок — "
                                "проверять второй подъём нечем")
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
