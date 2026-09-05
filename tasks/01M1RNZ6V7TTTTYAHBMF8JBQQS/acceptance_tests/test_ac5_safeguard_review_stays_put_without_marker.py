"""Зелёный с рождения: страховка от тавтологии (тот же принцип, что
`test_ac7_fixture_redness_safeguard.py` у `_pull_main_or_escalate`) — БЕЗ
неё `test_ac5_review_and_verifying_share_the_fix.py` доказывал бы только
«переход не падает», не «переход зависит от исхода приёмки»: реализация,
всегда прогоняющая review в verifying независимо от `acceptance.run`,
прошла бы её незамеченной. Поведение, которое здесь проверяется (переход
не двигается без зелёной планки), не меняется правкой регрессии №14 —
тест зелёный и до, и после.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (ExternalWorkspaceReviewSandbox,  # noqa: E402
                      MARKER_TEST_VIA_FILE)


class Ac5ReviewStaysPutWithoutMarkerTest(ExternalWorkspaceReviewSandbox):

    def test_ac5_review_stays_put_when_workspace_code_lacks_the_marker(self):
        """Без нового поведения в workspace внешнего target (`orchestrator/
        marker.py` не создан) переход обязан остаться в `review`, не
        пройти молчаливо."""
        self.commit_review_artifacts({"test_via_file.py": MARKER_TEST_VIA_FILE})

        self.run_review()

        self.assertEqual(self.state(), "review")


if __name__ == "__main__":
    unittest.main()
