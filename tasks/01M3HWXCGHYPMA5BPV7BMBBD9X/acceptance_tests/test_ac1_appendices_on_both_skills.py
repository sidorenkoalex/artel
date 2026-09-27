"""AC-1 — приложения PLAN.md на оба скила: штатный разбор без ошибок и
применимость к базе сравнения ветки задачи.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. PLAN.md задачи несёт приложение на `skills/test-authoring.md` и
приложение на `skills/review-checklist.md` — разделами «## Приложение…» с
блоками ```diff действующего формата: оба разбираются штатным разбором
приложений без ошибок, и оба применяются к базе сравнения ветки задачи
(`git apply --check` проходит, гейт применимости на выходе `in_dev` не
отказывает).

Разбор — `guard.plan_appendices`, применение — `plan_appendix.git_apply`
на дереве базы сравнения `gitcmd.diff_base`: тот же разбор и тот же вызов
git, которыми пользуются сам гейт применимости и цикл мержа, а не своя
копия их логики (иначе «планка зелена» ничего не говорило бы о гейте).

Красен до реализации: PLAN.md задачи ещё не заведён разработчиком — с
артефактной ветки он не читается, приложений на скилы нет вовсе, и оба
метода падают на пустом разборе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix  # noqa: E402


class PlanAppendicesTest(unittest.TestCase):

    def setUp(self):
        self.state = _appendix.state()

    def test_ac1_plan_carries_appendices_on_both_skills(self):
        """PLAN.md с артефактной ветки разбирается штатным разбором
        приложений без единой ошибки, и среди путей разобранных приложений
        есть и `skills/test-authoring.md`, и `skills/review-checklist.md`.

        Ловит мутацию: правка второго скила внесена не приложением, а
        коммитом в ветку задачи (или блок ```diff остался без заголовка
        `diff --git`) — путь этого скила не попадёт в разобранные
        приложения (а ошибка разбора — в список ошибок), и проверка
        покраснеет на конкретном имени файла.
        """
        self.assertIsNotNone(
            self.state.plan,
            f"PLAN.md задачи не прочитан с артефактной ветки — приложения "
            f"на скилы пишет разработчик в PLAN.md ({self.state.diagnosis()})")
        self.assertEqual(
            [], list(self.state.parse_errors),
            f"штатный разбор приложений PLAN вернул ошибки — гейт "
            f"применимости на выходе in_dev отказал бы теми же словами "
            f"({self.state.diagnosis()})")
        attached = [rel for paths in self.state.appendix_paths for rel in paths]
        for rel in _appendix.SKILLS:
            self.assertIn(
                rel, attached,
                f"в PLAN.md нет приложения на {rel}: разобранные пути — "
                f"{attached} ({self.state.diagnosis()})")

    def test_ac1_appendices_apply_to_diff_base(self):
        """Все приложения PLAN, положенные подряд в порядке разбора на
        дерево базы сравнения ветки задачи (merge-base с
        `origin/<основная ветка>`), применяются без отказа git.

        Ловит мутацию: хедер хунка приложения не совпадает с реальным
        диапазоном файла базы (дифф собран руками, без сверки `git apply
        --check`) — git ответит «patch does not apply»/«patch with only
        garbage», список отказов применения станет непустым.
        """
        self.assertTrue(
            self.state.base_sha,
            f"база сравнения ветки задачи не определена — применимость "
            f"приложения проверить нечем ({self.state.diagnosis()})")
        self.assertTrue(
            self.state.appendix_paths,
            f"ни одного приложения в PLAN.md — применять нечего "
            f"({self.state.diagnosis()})")
        self.assertEqual(
            [], list(self.state.apply_failures),
            f"приложение PLAN не применилось к базе сравнения "
            f"{self.state.base_sha} — гейт применимости на выходе in_dev "
            f"отказал бы тем же ответом git ({self.state.diagnosis()})")


if __name__ == "__main__":
    unittest.main()
