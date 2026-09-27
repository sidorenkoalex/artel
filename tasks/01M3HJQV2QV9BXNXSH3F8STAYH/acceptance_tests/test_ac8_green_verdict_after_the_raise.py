"""AC-8 — 01M3HJQV2QV9BXNXSH3F8STAYH: однократный подъём потолка сам по себе
прогон не красит.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. Задача, прошедшая после однократного подъёма потолка штатно до
`merge_gate` без расхождения маркера ожидания эскалации, даёт вердикт
`green`; факт подъёма записан в журнал задачи и напечатан в отчёте прогона.

Сценарий — `_util.ClonelessRunSandbox` в режиме `green`: до подъёма шаги
пробивают потолок (эскалацию пишет живой `budget.enforce_budget`), после
подъёма шаги дешёвые и задача штатно доходит до `merge_gate`, где канарейка
её и убивает — единственный штатный финал прогона. Шаблон пула несёт маркер
«эскалация ожидается» (`canary.MARK_EXPECT_ESCALATION_YES`), поэтому
случившаяся эскалация по бюджету расхождения маркера не даёт.

«Факт подъёма записан» планка сверяет по слову самого критерия («потолок»)
вместе с суммой поднятого потолка — числом, а не подстрокой: форму записи
суммы критерий не фиксирует.

Красен до реализации: подъёма потолка нет вовсе — задача, эскалировавшая по
бюджету, до `merge_gate` не доходит (её снимает потолок повторных эскалаций),
строки `canary_runs` с вердиктом `green` в этом сценарии не появляется, и
записи о подъёме нет ни в журнале, ни в отчёте.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

#: Слово критерия, которым назван предмет записи о подъёме.
CEILING_WORD = "потолок"


class GreenAfterRaiseTest(_util.ClonelessRunSandbox):

    def setUp(self):
        super().setUp()
        self.report = self.run_one_task(mode="green")

    def _raised_ceiling(self) -> float:
        ceilings = self.ceilings_seen()
        self.assertEqual(2, len(ceilings),
                         "сценарий не дал ровно один подъём потолка: "
                         f"{ceilings}")
        return ceilings[1]

    def test_ac8_task_reaches_merge_gate_after_the_single_raise(self):
        """После подъёма потолка задача идёт штатным путём и доходит до
        `merge_gate`, где канарейка её убивает.

        Ловит мутацию: подъём потолка сделан, но задача остаётся в
        `escalated` до исчерпания потолка эскалаций — «прогон продолжается»
        не выполнялось бы, и ни один шаблон, однажды пробивший потолок, не мог
        бы дать зелёный прогон.
        """
        self.assertIn("state -> merge_gate", self.transitions(),
                      f"задача не дошла до merge_gate: {self.transitions()}")
        self.assertEqual([self.task_id], self.killed,
                         "штатного kill на merge_gate не было")

    def test_ac8_verdict_of_such_a_run_is_green(self):
        """Строка `canary_runs` такого прогона несёт вердикт `green`.

        Ловит мутацию: сам факт подъёма потолка записан в вердикт («был
        подъём — значит не green») — прогон, который после подъёма прошёл
        штатно, перестал бы годиться для сдвига пина, то есть механизм
        починки красноты сам красил бы прогоны.
        """
        row = self.run_row()

        self.assertEqual("green", row["verdict"],
                         f"вердикт прогона: {row['verdict']!r}; отчёт:\n"
                         f"{self.report}")

    def test_ac8_raise_is_recorded_in_the_task_journal(self):
        """В журнале задачи есть запись о подъёме потолка: слово «потолок» и
        сумма поднятого потолка.

        Ловит мутацию: потолок поднимается молча, одним `store.update_task` —
        по журналу задачи нельзя было бы понять, почему расход канареечной
        задачи выше её SPEC-потолка, и подъём читался бы как ошибка учёта.
        """
        raised = self._raised_ceiling()
        texts = [text for text in self.journal_texts()
                 if CEILING_WORD in text.lower()
                 and _util.mentions_amount(text, raised)]

        self.assertTrue(
            texts,
            f"в журнале задачи нет записи о подъёме потолка до {raised}: "
            f"{self.journal_texts()}")

    def test_ac8_raise_is_printed_in_the_run_report(self):
        """Отчёт прогона называет подъём потолка: слово «потолок» и сумму
        поднятого потолка в одной строке.

        Ловит мутацию: факт подъёма остаётся только в журнале задачи внутри
        эфемерного клона — клон уничтожается по выходу из блока, и Оператор,
        читая зелёный прогон, не узнал бы, что задача уложилась только со
        второго потолка.
        """
        raised = self._raised_ceiling()
        lines = [line for line in self.report.splitlines()
                 if CEILING_WORD in line.lower()
                 and _util.mentions_amount(line, raised)]

        self.assertTrue(
            lines,
            f"отчёт прогона не называет подъём потолка до {raised}:\n"
            f"{self.report}")


if __name__ == "__main__":
    unittest.main()
