"""Юнит-тест края подтяжки ссылок документов при заведении клона (SPEC
01M446WV7S94FTZGJCGMPJ667F, требование 1): `git clone` ответил успехом, а
каталога клона нет (так отвечают заглушки git песочниц) — fetch ссылок
не идёт, клон всё равно заведён, причина — одной строкой.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artifact_branch, gitcmd, targets, workspace
from tests.sandbox import capture_new_task_id


class MissingCloneDirTest(unittest.TestCase):

    def test_no_docs_fetch_into_missing_clone_dir(self):
        """Ловит мутацию: `_fetch_docs_refs` без проверки каталога клона —
        `fetch_all_from_origin` зовётся для несуществующего каталога (в
        песочницах это лишний `git -C <клон> fetch` первым в списке
        вызовов), и `assert_not_called` покраснеет."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        clone = Path(tmp.name) / "acme" / "repo"
        ok = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(workspace, "repo", return_value=clone), \
                mock.patch.object(workspace, "area_consistent",
                                  return_value=True), \
                mock.patch.object(targets, "target",
                                  return_value={"url": "file:///nowhere"}), \
                mock.patch.object(gitcmd, "in_repo", return_value=ok), \
                mock.patch.object(workspace, "inherit_identity"), \
                mock.patch.object(artifact_branch,
                                  "fetch_all_from_origin") as fetch:
            out, (path, reason) = capture_new_task_id(workspace.ensure_clone, "acme")
        fetch.assert_not_called()
        self.assertEqual(path, clone)
        self.assertIsNone(reason)
        self.assertEqual(
            sum("refs/artifacts/*" in line for line in out.splitlines()), 1,
            out)


if __name__ == "__main__":
    unittest.main()
