"""AC-1 (tasks/01M1NBWRTAHSX9FQGTQWENY80A/SPEC.md): «Если у задачи есть
один или несколько файлов tasks/<id>/ANSWER-n.md, review.review_package
включает их ВСЕ как отдельные компоненты пакета (не только файл с
наибольшим n).»

Красен до реализации: сегодня `review.review_package`
(`orchestrator/review.py::review_package`) вообще не читает
`tasks/<id>/ANSWER-*.md` — состав частей пакета фиксирован (задача, SPEC,
PLAN, прошлый REVIEW, форма вердикта, стат-список, diff), ANSWER там не
упомянут. Промпт ревьювера этой задачи сегодня не содержит ни маркера
ANSWER-1, ни маркера ANSWER-2 — тест падает именно на их отсутствии, не
на постороннем сбое фикстуры (`AnswerInReviewPackageSandbox` — тот же
`FakeGit`/`cmd_run`, что уже используют существующие тесты
`tests/test_review_package.py`, ничего в нём для этой задачи не меняется).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import AnswerInReviewPackageSandbox  # noqa: E402

ANSWER_1 = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: первый батч

## Ответы

МАРКЕР-ОТВЕТА-AC1-answer-one-7f3a
"""

ANSWER_2 = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: второй батч

## Ответы

МАРКЕР-ОТВЕТА-AC1-answer-two-9c2b
"""


class Ac1AllAnswersIncludedTest(AnswerInReviewPackageSandbox):

    def test_ac1_two_answer_files_both_land_in_the_package_not_just_the_latest(self):
        """Задача несёт ANSWER-1.md и ANSWER-2.md (два разных батча
        эскалации/ответа) — оба обязаны появиться в ревью-пакете, который
        уходит ревьюверу, а не только файл с наибольшим n (ANSWER-2).

        Ловит мутацию: реализация по образцу `brief._latest_answer_rel`
        (используемого для developer/analyst/test_author — SPEC T075)
        подключает в пакет только ПОСЛЕДНИЙ ANSWER-n.md — тест покраснеет
        на отсутствии маркера ANSWER-1 в промпте, хотя маркер ANSWER-2
        (наибольший n) будет присутствовать.
        """
        self.add_answer(1, ANSWER_1.format(task=self.TASK))
        self.add_answer(2, ANSWER_2.format(task=self.TASK))

        self.run_agent("review")

        package = self.package_text()
        self.assertIn("МАРКЕР-ОТВЕТА-AC1-answer-one-7f3a", package,
                      "ANSWER-1.md отсутствует в пакете — включён только "
                      "последний ответ")
        self.assertIn("МАРКЕР-ОТВЕТА-AC1-answer-two-9c2b", package,
                      "ANSWER-2.md отсутствует в пакете")
        self.assertIn(f"tasks/{self.TASK}/ANSWER-1.md", package,
                      "компонент ANSWER-1.md не назван по пути")
        self.assertIn(f"tasks/{self.TASK}/ANSWER-2.md", package,
                      "компонент ANSWER-2.md не назван по пути")

    def test_ac1_single_answer_file_is_included(self):
        """Симметричный случай единственного ответа — он тоже обязан быть
        в пакете (AC-1 покрывает и «один», и «несколько» файлов).

        Ловит мутацию: реализация, случайно требующая ≥2 файлов ANSWER
        (например, срез `[:-1]` по ошибочной логике «остальные, кроме
        последнего») — маркер единственного файла тогда не попал бы в
        пакет вовсе.
        """
        self.add_answer(1, ANSWER_1.format(task=self.TASK))

        self.run_agent("review")

        self.assertIn("МАРКЕР-ОТВЕТА-AC1-answer-one-7f3a", self.package_text())


if __name__ == "__main__":
    import unittest
    unittest.main()
