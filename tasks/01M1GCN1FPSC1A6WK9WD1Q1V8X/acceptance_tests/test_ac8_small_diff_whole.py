"""AC-8 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): diff в
`review.review_package`, чей размер не превышает потолок части (65536
байт), включается в пакет целиком одним куском.

Зелёный с рождения: сегодняшнее поведение уже включает diff под
потолком `REVIEW_DIFF_MAX_LINES`/`REVIEW_PACKAGE_MAX_BYTES` целиком, без
усечения (см. tests/test_review_package.py::ReviewPackageTest.
test_all_parts_are_present_in_a_stable_order) — эта задача не имеет
права это регрессировать (AC-18); тест фиксирует именно это как планку
после задачи, не только до неё.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FakeGitDiff, build_review_package, standard_files  # noqa: E402


class Ac8SmallDiffWholeTest(unittest.TestCase):

    def test_ac8_diff_under_the_part_cap_is_included_verbatim_as_one_piece(self):
        diff = "\n".join(f"+строка {n}" for n in range(1, 51))
        git = FakeGitDiff(files=standard_files(), diff=diff)

        package = build_review_package(git)
        text = package["text"]

        self.assertIn(diff, text,
                      "diff под потолком части обязан появиться в тексте "
                      "целиком, одним непрерывным куском")
        self.assertNotIn("по порядку", text,
                         "диф в один кусок — читать по частям нечего")


if __name__ == "__main__":
    unittest.main()
