"""AC-1 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): текст
`brief.developer_brief` и текст `review.review_package` несут опись —
для каждого включённого целиком компонента путь, размер в байтах и
sha256.

Красен до реализации: путь компонента уже виден в тексте сегодня (он
входит целиком), но байтовый размер и sha256 компонента нигде не
печатаются — опись как таковая ещё не существует ни у `developer_brief`,
ни у `review_package`.
"""
import hashlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BriefSandbox, FakeGitDiff, MAP_FRESH, PLAN_MD,  # noqa: E402
                      SPEC_MD, SPEC_SMALL, TASK, build_review_package,
                      standard_files)


class Ac1BriefManifestTest(BriefSandbox):

    def test_ac1_brief_manifest_has_path_size_sha256_for_spec(self):
        text = self.build_brief()

        rel = f"tasks/{TASK}/SPEC.md"
        expected_bytes = len(SPEC_SMALL.encode("utf-8"))
        expected_sha = hashlib.sha256(SPEC_SMALL.encode("utf-8")).hexdigest()

        self.assertIn(rel, text, "путь компонента отсутствует в описи")
        self.assertIn(str(expected_bytes), text,
                      "размер SPEC.md в байтах не найден в описи")
        self.assertIn(expected_sha, text, "sha256 SPEC.md не найден в описи")

    def test_ac1_brief_manifest_has_path_size_sha256_for_map(self):
        text = self.build_brief()

        expected_bytes = len(MAP_FRESH.encode("utf-8"))
        expected_sha = hashlib.sha256(MAP_FRESH.encode("utf-8")).hexdigest()

        self.assertIn("docs/codebase-map.md", text)
        self.assertIn(str(expected_bytes), text,
                      "размер карты в байтах не найден в описи")
        self.assertIn(expected_sha, text, "sha256 карты не найден в описи")


class Ac1ReviewPackageManifestTest(unittest.TestCase):
    """review_package не трогает config.ROOT/TASKS — TmpRootTest не нужен."""

    def test_ac1_review_package_manifest_has_path_size_sha256_for_spec(self):
        spec_text = SPEC_MD.format(task=TASK)
        git = FakeGitDiff(files=standard_files())

        package = build_review_package(git)

        rel = f"tasks/{TASK}/SPEC.md"
        expected_bytes = len(spec_text.encode("utf-8"))
        expected_sha = hashlib.sha256(spec_text.encode("utf-8")).hexdigest()

        self.assertIn(rel, package["text"])
        self.assertIn(str(expected_bytes), package["text"],
                      "размер SPEC.md в байтах не найден в описи пакета")
        self.assertIn(expected_sha, package["text"],
                      "sha256 SPEC.md не найден в описи пакета")

    def test_ac1_review_package_manifest_has_path_size_sha256_for_plan(self):
        plan_text = PLAN_MD.format(task=TASK)
        git = FakeGitDiff(files=standard_files())

        package = build_review_package(git)

        rel = f"tasks/{TASK}/PLAN.md"
        expected_bytes = len(plan_text.encode("utf-8"))
        expected_sha = hashlib.sha256(plan_text.encode("utf-8")).hexdigest()

        self.assertIn(rel, package["text"])
        self.assertIn(str(expected_bytes), package["text"])
        self.assertIn(expected_sha, package["text"])


if __name__ == "__main__":
    unittest.main()
