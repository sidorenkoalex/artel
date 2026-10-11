"""AC-18 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): существующий состав
компонентов, включаемых в бриф разработчика (T028) и ревью-пакет (T011),
не меняется этой задачей — меняется только дисциплина размера и опись.

Зелёный с рождения: тот же состав компонентов, что тесты T028/T011 уже
проверяют сегодня (tests/test_brief.py::DeveloperBriefTest,
tests/test_review_package.py::ReviewPackageTest.
test_all_parts_are_present_in_a_stable_order) — эта задача добавляет
опись/дисциплину частей, но не имеет права убрать или добавить
компонент.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BriefSandbox, CONVENTIONS_SMALL, FakeGitDiff,  # noqa: E402
                      MAP_FRESH, PLAN_MD, SPEC_MD, SPEC_SMALL, TASK,
                      build_review_package, standard_files)


class Ac18BriefCompositionTest(BriefSandbox):

    def test_ac18_developer_brief_still_carries_exactly_spec_map_conventions(self):
        text = self.build_brief()

        for marker in (SPEC_SMALL.strip(), MAP_FRESH.strip(),
                      CONVENTIONS_SMALL.strip()):
            self.assertIn(marker, text,
                         f"состав брифа не должен потерять компонент: "
                         f"{marker!r}")


class Ac18ReviewPackageCompositionTest(unittest.TestCase):

    def test_ac18_review_package_still_carries_spec_plan_and_the_verdict_form(self):
        git = FakeGitDiff(files=standard_files())

        package = build_review_package(git)
        text = package["text"]

        self.assertIn("### Задача", text)
        self.assertIn(f"tasks/{TASK}/SPEC.md", text)
        self.assertIn(f"tasks/{TASK}/PLAN.md", text)
        self.assertIn("templates/REVIEW.md", text)
        self.assertIn("### Изменённые файлы", text)
        self.assertIn("### Diff", text)
        # Тело артефактов — не только заголовки: состав контента, не
        # только состав заголовков.
        self.assertIn(SPEC_MD.format(task=TASK).strip().splitlines()[-1], text)
        self.assertIn(PLAN_MD.format(task=TASK).strip().splitlines()[-1], text)


if __name__ == "__main__":
    unittest.main()
