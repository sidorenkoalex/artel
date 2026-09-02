"""AC-11, AC-19 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): инкрементальный
diff (T029, `iteration > 1` с `prev_sha`) продолжает считаться от
`prev_sha`, как и до этой задачи (AC-19), и несёт ту же опись/дисциплину
частей, что полный diff (AC-8/AC-9, здесь — AC-11); вырожденный откат на
полный diff без `prev_sha` не регрессирует (AC-19).

Смешивает зелёные-с-рождения проверки (базовая точка отсчёта,
вырожденный откат — уже существующее поведение T029, см.
tests/test_review_package.py::IncrementalReviewPackageTest) с красными
до реализации (дисциплина частей на инкрементальном diff — новая).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config  # noqa: E402
from _sandbox import BRANCH, FakeGitDiff, build_review_package, standard_files  # noqa: E402

PREV_SHA = "abc1234"
LINE_COUNT = 10_000


def _big_diff() -> str:
    return "\n".join(f"+line-{i:05d}" for i in range(LINE_COUNT))


class Ac19BasePointTest(unittest.TestCase):
    """Зелёный с рождения: T029 уже выбирает базу инкрементального diff
    так же — эта задача не имеет права это регрессировать (AC-18/AC-19)."""

    def test_ac19_iteration_gt_1_with_prev_sha_diffs_from_prev_sha_not_main(self):
        git = FakeGitDiff(files=standard_files())

        build_review_package(git, iteration=2, prev_sha=PREV_SHA)

        diff_calls = [c for c in git.calls if c[0] == "diff"]
        self.assertTrue(
            all(c[-1] == f"{PREV_SHA}...{BRANCH}"
               for c in diff_calls),
            f"diff/--stat обязаны считаться от prev_sha, не от main: "
            f"{diff_calls}")

    def test_ac19_missing_prev_sha_falls_back_to_the_full_diff_from_main(self):
        git = FakeGitDiff(files=standard_files())

        package = build_review_package(git, iteration=2, prev_sha="")

        self.assertEqual(package["diff_type"], "полный",
                         "нет prev_sha — вырожденный откат на полный diff, "
                         "как и до этой задачи (T029)")
        diff_calls = [c for c in git.calls if c[0] == "diff"]
        self.assertTrue(
            all(c[-1] == f"{config.MAIN_BRANCH}...{BRANCH}"
               for c in diff_calls),
            f"без prev_sha diff обязан считаться от main, как раньше: "
            f"{diff_calls}")


class Ac11IncrementalDiscplineTest(unittest.TestCase):
    """Красен до реализации: дисциплина частей ещё не существует ни для
    полного, ни для инкрементального diff."""

    def test_ac11_oversized_incremental_diff_gets_the_same_no_loss_discipline(self):
        diff = _big_diff()
        git = FakeGitDiff(files=standard_files(), diff=diff)

        package = build_review_package(git, iteration=2, prev_sha=PREV_SHA)
        text = package["text"]

        output_lines = set(text.splitlines())
        missing = [ln for ln in diff.splitlines() if ln not in output_lines][:5]
        self.assertEqual(
            missing, [],
            f"инкрементальный diff обязан подчиняться той же дисциплине "
            f"частей без потери хвоста (AC-11/AC-9) — пропали строки: "
            f"{missing}")
        self.assertNotIn("diff усечён", text,
                         "старое молчаливое усечение не должно остаться "
                         "и на инкрементальном diff (AC-10/AC-11)")


if __name__ == "__main__":
    unittest.main()
