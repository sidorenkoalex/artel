"""AC-6 — 01M3HJQV2QV9BXNXSH3F8STAYH: повторное исчерпание потолка — свой
исход с числами и ролью шага, не «задача не сходится».

Источник — SPEC.md, «Критерии приёмки»:

AC-6. Повторное исчерпание потолка завершает задачу прогона причиной исхода
«исчерпан потолок задачи: $X из $Y на шаге <роль>» с фактическими числами и
ролью шага; текст отличается от «задача не сходится»/«не сошлась» и виден и
в отчёте прогона, и в журнале задачи.

Сценарий — тот же, что у AC-5 (`_util.ClonelessRunSandbox`, режим
`exhaust`): настоящее `canary._drive_task` поверх синтетического шага роли,
эскалация по бюджету — от живого `budget.enforce_budget`. Отчёт прогона —
настоящая печать `canary._run_one_task`, поэтому «виден в отчёте» проверяется
тем же выводом, который читает Оператор, а не внутренней функцией.

Числа планка не подставляет своими литералами: фактический расход и
фактический потолок читаются из строки задачи ПОСЛЕ прогона, роль шага — из
`config.STATE_ROLE` по состоянию, из которого задача эскалировала.

Красен до реализации: исхода «исчерпан потолок задачи» в пульте нет вовсе —
задача, которой не хватило потолка, снимается сегодня общей причиной «N
повторных эскалаций подряд — задача не сходится» (`canary._drive_task`),
ровно тем диагнозом, который критерий велит от неё отличать.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import config  # noqa: E402

#: Устойчивая часть формулировки исхода из критерия.
REASON = "исчерпан потолок задачи"

#: Диагнозы, от которых новый исход обязан отличаться.
INCONCLUSIVE = ("задача не сходится", "не сошлась")


class CeilingExhaustedOutcomeTest(_util.ClonelessRunSandbox):

    def setUp(self):
        super().setUp()
        self.report = self.run_one_task(mode="exhaust")
        self.role = config.STATE_ROLE["in_dev"]

    def _lines_with_reason(self, text: str) -> list:
        return [line for line in text.splitlines() if REASON in line]

    def test_ac6_task_journal_names_the_numbers_and_the_role_of_the_step(self):
        """В журнале задачи есть запись с причиной исхода, несущая
        фактический расход, фактический потолок и роль шага.

        Ловит мутацию: причина журналируется общим текстом без чисел («потолок
        исчерпан») — по журналу задачи нельзя было бы сказать, на сколько
        именно не хватило поднятого потолка, а именно это число решает, куда
        крутить константу-множитель.
        """
        texts = [text for text in self.journal_texts() if REASON in text]
        self.assertTrue(
            texts,
            f"в журнале задачи нет записи «{REASON}»: {self.journal_texts()}")

        t = self.task_row()
        reason = texts[0]
        self.assertTrue(_util.mentions_amount(reason, t["spent_usd"]),
                        f"запись не называет фактический расход "
                        f"{t['spent_usd']}: {reason}")
        self.assertTrue(_util.mentions_amount(reason, t["budget_usd"]),
                        f"запись не называет фактический потолок "
                        f"{t['budget_usd']}: {reason}")
        self.assertIn(self.role, reason,
                      f"запись не называет роль шага: {reason}")

    def test_ac6_reason_differs_from_the_task_does_not_converge_diagnosis(self):
        """Причина нового исхода не содержит ни «задача не сходится», ни «не
        сошлась».

        Ловит мутацию: новый исход дописан к прежней причине («не сходится:
        исчерпан потолок задачи…») — в отчёте прогона оба диагноза читались бы
        как один, и вердикт прогона снова обвинял бы конвейер там, где шаблон
        просто не уложился в потолок.
        """
        texts = [text for text in self.journal_texts() if REASON in text]
        self.assertTrue(texts, f"в журнале нет записи «{REASON}»")

        for text in texts:
            for diagnosis in INCONCLUSIVE:
                self.assertNotIn(diagnosis, text)

    def test_ac6_run_report_shows_the_reason_with_numbers_and_the_role(self):
        """Отчёт прогона по этой задаче печатает ту же причину: с числами и
        ролью шага.

        Ловит мутацию: причина остаётся только в журнале задачи, а отчёт
        печатает прежнее «исход=killed (не сошлась)» — журнал живёт в БД
        эфемерного клона и умирает вместе с ним, так что причина исчезла бы
        для Оператора совсем.
        """
        lines = self._lines_with_reason(self.report)
        self.assertTrue(lines,
                        f"отчёт прогона не называет «{REASON}»:\n{self.report}")

        t = self.task_row()
        line = lines[0]
        self.assertTrue(_util.mentions_amount(line, t["spent_usd"]),
                        f"строка отчёта не называет расход: {line}")
        self.assertTrue(_util.mentions_amount(line, t["budget_usd"]),
                        f"строка отчёта не называет потолок: {line}")
        self.assertIn(self.role, line,
                      f"строка отчёта не называет роль шага: {line}")

    def test_ac6_run_report_does_not_call_it_an_inconclusive_task(self):
        """Отчёт прогона по задаче, снятой исчерпанием потолка, не называет её
        несошедшейся.

        Ловит мутацию: новый исход добавлен печатью рядом, а прежняя
        классификация исхода оставлена как есть — Оператор видел бы в одной
        строке и «не сошлась», и «исчерпан потолок задачи», то есть два
        взаимоисключающих диагноза одного прогона.
        """
        for diagnosis in INCONCLUSIVE:
            self.assertNotIn(diagnosis, self.report)


if __name__ == "__main__":
    unittest.main()
