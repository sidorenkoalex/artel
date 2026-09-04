"""AC-3 (tasks/01M1NBWRTAHSX9FQGTQWENY80A/SPEC.md): «Существующие
компоненты ревью-пакета (SPEC, PLAN, прошлый REVIEW, форма вердикта,
stat, diff) НЕ получают новую запись sha256-фингерпринта в журнале в
рамках этой задачи — их обработка не меняется.»

Смешанный статус двух тестов этого файла — по разной причине:

- `test_ac3_spec_plan_review_form_stat_diff_get_no_new_journal_entries`
  — Красен до реализации: его предпосылка (см. `assertTrue(answer_entries,
  ...)`, помечено «AC-2 нарушен» в сообщении) — что ANSWER-1.md УЖЕ
  журналируется (AC-2) — сегодня не выполняется (`review.review_package`
  ANSWER-n.md вовсе не читает), поэтому тест падает на этой предпосылке
  раньше, чем успевает проверить собственно AC-3 (что остальные
  компоненты НЕ журналируются). Красен по зависимости от AC-2 этой же
  задачи, не по постороннему сбою фикстуры.
- `test_ac3_diff_and_stat_are_not_referenced_by_any_journal_entry` —
  Зелёный с рождения: не зависит от AC-1/AC-2 (список записей «бриф:
  компонент» сегодня пуст для diff/stat независимо от того, журналируется
  ли что-то ещё) — ловит РЕГРЕССИЮ, которую эта же задача рискует внести
  (журналирование ошибочно задевает diff/stat как «ещё один компонент
  пакета»), не сегодняшний дефект — тем же приёмом, что
  `tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/acceptance_tests/
  test_ac1_head_already_pushed_unchanged.py`.

Фон обоих: сегодня `orchestrator/review.py` не журналирует НИ ОДИН
компонент пакета сквозь `store.journal` (единственная запись шага ревью —
сводная «ревью-пакет собран», `orchestrator/runner.py:254`, по всему
пакету целиком, не по компонентам) — записи с action «бриф: компонент» в
журнале ревьювера сегодня есть, но только от скилов роли (`brief.
skills_text`), и они никогда не упоминают пути SPEC/PLAN/REVIEW/формы/
diff/stat (см. докстринг `test_ac2_answer_component_journaled.py`).
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

# ANSWER-1: батч AC-3

## Ответы

Маркер-ac3-e61f.
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: changes_requested
iteration: 1
---

# REVIEW: прошлая итерация

## Замечания
major — orchestrator/artel.py:1 — замечание прошлой итерации.
"""


class Ac3ExistingComponentsNotJournaledTest(AnswerInReviewPackageSandbox):

    def test_ac3_spec_plan_review_form_stat_diff_get_no_new_journal_entries(self):
        """Задача несёт ANSWER-1.md (включённый в пакет по AC-1/AC-2) и
        прошлый REVIEW.md (iteration 2) — журнальные записи «бриф:
        компонент» появляются ТОЛЬКО для ANSWER-1.md, ни для одного из
        остальных компонентов пакета (SPEC/PLAN/прошлый REVIEW/форма/
        stat/diff) — их путей в детали записей быть не должно.

        Ловит мутацию: журналирование компонентов пакета реализовано
        циклом по ВСЕМ элементам списка `parts` (SPEC/PLAN/REVIEW/форма/
        stat/diff/ANSWER) вместо выборочного вызова только для найденных
        ANSWER-n.md — тест обнаружит `tasks/<TASK>/SPEC.md`,
        `tasks/<TASK>/PLAN.md` или `templates/REVIEW.md` среди деталей
        записей «бриф: компонент» и покраснеет.
        """
        self.add_answer(1, ANSWER_1.format(task=self.TASK))
        self.git.files[f"tasks/{self.TASK}/REVIEW.md"] = REVIEW_MD.format(
            task=self.TASK)

        self.run_agent("review")

        entries = self.journal_details("бриф: компонент")
        answer_entries = [d for d in entries
                          if f"tasks/{self.TASK}/ANSWER-1.md" in d]
        self.assertTrue(answer_entries, "AC-2 нарушен: ANSWER-1.md ожидался "
                        f"в записях, получено: {entries}")

        forbidden = (f"tasks/{self.TASK}/SPEC.md", f"tasks/{self.TASK}/PLAN.md",
                    f"tasks/{self.TASK}/REVIEW.md", "templates/REVIEW.md")
        for detail in entries:
            for path in forbidden:
                self.assertNotIn(
                    path, detail,
                    f"компонент {path} получил запись «бриф: компонент», "
                    f"хотя AC-3 запрещает журналировать существующие "
                    f"компоненты пакета: {detail!r}")

    def test_ac3_diff_and_stat_are_not_referenced_by_any_journal_entry(self):
        """Стат-список и diff — тоже существующие компоненты пакета
        (не ANSWER): их содержимое не должно всплывать в деталях записей
        «бриф: компонент» (у них там вообще нет причины быть, раз это
        не ANSWER-компонент).

        Ловит мутацию: журналирование ошибочно берёт diff/stat как
        «дополнительный компонент, раз уж он тоже часть пакета» —
        detail записи «бриф: компонент» тогда содержал бы текст diff
        (`self.git.diff` фикстуры, «diff --git a b») или заголовок
        «### Diff»/«### Изменённые файлы».
        """
        self.add_answer(1, ANSWER_1.format(task=self.TASK))

        self.run_agent("review")

        entries = self.journal_details("бриф: компонент")
        for detail in entries:
            self.assertNotIn("### Diff", detail)
            self.assertNotIn("### Изменённые файлы", detail)
            self.assertNotIn(self.git.diff, detail)


if __name__ == "__main__":
    import unittest
    unittest.main()
