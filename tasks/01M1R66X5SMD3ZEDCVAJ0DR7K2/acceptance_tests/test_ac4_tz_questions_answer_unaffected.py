"""Приёмочные тесты 01M1R66X5SMD3ZEDCVAJ0DR7K2 — AC-4 (типы `tz`,
`questions`, `answer` проверяются как и без режима — при любом status,
валидном для типа; режим артефактной ветки их не касается вовсе).

Красен до реализации: сегодня `--artifact-branch` не распознан вовсе,
и «с флагом»-прогон падает на двух фиктивных «файл не найден» (см.
докстринг `test_ac2_draft_downgraded_to_warning.py`) — реальная
фикстура (`tasks/T1/QUESTIONS.md` и т.п.) при этом вообще не читается
(`--all` не сработал), exit-код 1 совпадает с ожидаемым СЛУЧАЙНО, по
причине, не связанной с содержимым фикстуры. Тесты ловят это честно:
`assertIn` на текст самого нарушения («Вопросы»/«999»/«Ответы») не
находит его в выводе, где сегодня вместо этого «файл не найден:
--all»/«--artifact-branch» — покраснение на `assertIn`, не на коде
возврата.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (answer_missing_section_text,  # noqa: E402
                      questions_missing_section_text, run_main,
                      tz_too_new_text)


class QuestionsDraftStillFailsWithTheFlagTest(unittest.TestCase):
    """`questions` со `status: draft` — режим не спасает от нарушения
    (в отличие от четырёх типов требования 2): это не один из них."""

    def test_ac4_draft_questions_without_section_still_fails_with_the_flag(self):
        """QUESTIONS.md со `status: draft` без секции «Вопросы» — даже с
        флагом `--artifact-branch` прогон отказывает (exit 1), и сводка
        не учитывает это нарушение как черновичное «предупреждение»
        (`нарушений` совпадает с тем, что видно и без флага).

        Ловит мутацию: разработчик проверяет ТОЛЬКО `status == "draft"`
        для решения «понизить до предупреждения», забыв ограничить это
        типами `spec`/`plan`/`review`/`test_report` (требование 2) — тогда
        `questions` со `status: draft` тоже получил бы мягкий проход,
        exit-код стал бы 0 вместо ожидаемого 1.
        """
        code_off, out_off = run_main(
            {"tasks/T1/QUESTIONS.md": questions_missing_section_text()},
            artifact_branch=False)
        code_on, out_on = run_main(
            {"tasks/T1/QUESTIONS.md": questions_missing_section_text()},
            artifact_branch=True)

        self.assertEqual(code_off, 1, out_off)
        self.assertEqual(code_on, 1, out_on)
        self.assertIn("Вопросы", out_off)
        self.assertIn("Вопросы", out_on)


class TzDraftFrontmatterViolationUnaffectedTest(unittest.TestCase):
    """`tz` со `status: draft` и нечитаемой (слишком новой) версией схемы
    — базовая проверка есть и без режима, и с ним, тем же способом."""

    def test_ac4_tz_with_unsupported_schema_version_fails_with_or_without_the_flag(self):
        """ТЗ со `status: draft` и `schema_version: 999` — прогон
        отказывает (exit 1) одинаково с флагом и без него; сообщение
        называет версию.

        Ловит мутацию: реализация «режима» ошибочно затрагивает ЛЮБОЙ тип
        с полем `status`, не только четвёрку требования 2, — например
        глобальный `if meta.get("status") == "draft": errors = []` без
        проверки типа обнулил бы даже frontmatter-нарушение `tz`.
        """
        code_off, out_off = run_main(
            {"tasks/T1/TZ.md": tz_too_new_text()}, artifact_branch=False)
        code_on, out_on = run_main(
            {"tasks/T1/TZ.md": tz_too_new_text()}, artifact_branch=True)

        self.assertEqual(code_off, 1, out_off)
        self.assertEqual(code_on, 1, out_on)
        self.assertIn("999", out_off)
        self.assertIn("999", out_on)


class AnswerMissingSectionUnaffectedTest(unittest.TestCase):
    """`answer` не несёт понятия «черновик» вовсе (единственный валидный
    status — `ready`) — нарушение отказывает независимо от режима."""

    def test_ac4_answer_without_section_fails_with_or_without_the_flag(self):
        code_off, out_off = run_main(
            {"tasks/T1/ANSWER.md": answer_missing_section_text()},
            artifact_branch=False)
        code_on, out_on = run_main(
            {"tasks/T1/ANSWER.md": answer_missing_section_text()},
            artifact_branch=True)

        self.assertEqual(code_off, 1, out_off)
        self.assertEqual(code_on, 1, out_on)
        self.assertIn("Ответы", out_off)
        self.assertIn("Ответы", out_on)


if __name__ == "__main__":
    unittest.main()
