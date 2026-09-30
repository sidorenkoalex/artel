"""Разовые проверки текста скилов после применения приложения PLAN.

Группа: разовый
Красен до реализации: PLAN ещё не содержит приложений с правками двух скилов.
"""

# AC-4: escalate — как проверить долгоживущим тестом в tests/ тексты обоих защищённых скилов до мержа, если приёмочный гейт запускает этот тест до применения приложений PLAN? Уточнить момент проверки или скорректировать критерий.

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, gitcmd  # noqa: E402
from orchestrator.advance_gates import plan_appendix  # noqa: E402
from scripts import guard  # noqa: E402


TASK_ID = "01M3S9HRZYT0C6TC1CZJPNYKZ1"
SPEC_SKILL = "skills/spec-authoring.md"
TEST_SKILL = "skills/test-authoring.md"
SKILLS = (SPEC_SKILL, TEST_SKILL)


def applied_skills():
    """PLAN из артефактной ветки; приложение на временной копии базы."""
    plan, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                               f"tasks/{TASK_ID}/PLAN.md")
    if plan is None:
        raise AssertionError(f"PLAN не прочитан из артефактной ветки: {reason}")
    appendices, errors = guard.plan_appendices(plan)
    if errors:
        raise AssertionError(f"приложения PLAN не разобраны: {errors}")
    covered = {path for appendix in appendices for path in appendix.paths}
    if not set(SKILLS) <= covered:
        raise AssertionError(f"в приложениях PLAN нет обоих скилов: {covered}")
    branch = gitcmd.current_branch()
    base = gitcmd.diff_base(branch)
    if not base:
        raise AssertionError(f"не определена база сравнения ветки {branch}")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for rel in covered:
            original, failure = gitcmd.show(base, rel)
            if original is None:
                raise AssertionError(f"{rel} не прочитан из базы {base}: {failure}")
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(original, encoding="utf-8")
        for appendix in appendices:
            failure = plan_appendix.git_apply(root, appendix)
            if failure:
                raise AssertionError(f"приложение {appendix.paths} неприменимо: {failure}")
        result = {rel: (root / rel).read_text(encoding="utf-8") for rel in SKILLS}
    return plan, result


def flat(value):
    return re.sub(r"\s+", " ", value.lower().replace("`", ""))


class SkillAppendixAcceptance(unittest.TestCase):
    def test_ac1_spec_skill_excludes_pult_checks(self):
        """Приложение к скилу аналитика запрещает дублировать проверки пульта.

        Ловит мутацию: правило перечисляет полный набор и CI, но забывает
        защищённые пути или бюджет — соответствующее слово отсутствует в
        тексте после применения приложения, и тест падает.
        """
        _, skills = applied_skills()
        text = flat(skills[SPEC_SKILL])
        for part in ("критери", "пульт", "для любой задач", "полный",
                     "tests/", "ci", "ветк", "защищённ", "бюджет",
                     "не входит", "одной строк", "тз"):
            with self.subTest(part=part):
                self.assertIn(part, text)
        self.assertRegex(text, r"(?:не включ|не станов|не добав).{0,100}критери")
        self.assertRegex(text, r"не входит.{0,250}(?:пульт|держит)")

    def test_ac2_test_author_escalates_duplicate_criterion(self):
        """Оставшийся в SPEC критерий получает вопрос об удалении.

        Ловит мутацию: автор тестов получает совет пометить критерий
        skip/manual — отсутствие запрета этих пометок или вопроса для
        escalate делает проверку красной.
        """
        _, skills = applied_skills()
        text = flat(skills[TEST_SKILL])
        for part in ("критери", "spec", "пульт", "escalate", "skip",
                     "manual", "критерий держит пульт — убрать из spec?"):
            with self.subTest(part=part):
                self.assertIn(part, text)
        self.assertRegex(text, r"(?:не|вместо).{0,100}(?:skip|manual)")

    def test_ac3_plan_carries_applicable_skill_changes(self):
        """Оба защищённых скила получают применимые правки из PLAN.

        Ловит мутацию: хунк второго скила собран со старым диапазоном
        строк — штатное применение во временном дереве откажет, и тест
        покажет имя неприменимого приложения.
        """
        plan, skills = applied_skills()
        self.assertIn("## Приложение", plan)
        for rel in SKILLS:
            with self.subTest(skill=rel):
                self.assertTrue(skills[rel], rel)


if __name__ == "__main__":
    unittest.main()
