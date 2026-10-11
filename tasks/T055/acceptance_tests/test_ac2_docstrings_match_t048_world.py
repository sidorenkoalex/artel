"""AC-2 (tasks/T055/SPEC.md): докстринги `ensure()` и модуля
`orchestrator/workspace.py` приведены к миру T048: не описывают перенос
незакоммиченных артефактов главной копии в worktree и не упоминают
снятую функцию.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import workspace  # noqa: E402

REMOVED_NAME = "_seed_uncommitted_artifacts"
# "коммич" — общий корень слов, которыми удаляемая функция описывала
# перенос незакоммиченного/некоммиченного/закоммиченного содержимого
# (orchestrator/workspace.py, докстринг _seed_uncommitted_artifacts до
# этой задачи); в мире T048 докстринги ensure()/модуля этот язык не
# несут вовсе.
COMMIT_STATE_STEM = "коммич"


class DocstringsMatchT048WorldTest(unittest.TestCase):

    def test_ac2_module_docstring_does_not_name_the_removed_function(self):
        self.assertNotIn(REMOVED_NAME, workspace.__doc__ or "")

    def test_ac2_ensure_docstring_does_not_name_the_removed_function(self):
        self.assertNotIn(REMOVED_NAME, workspace.ensure.__doc__ or "")

    def test_ac2_module_docstring_does_not_describe_uncommitted_artifact_transfer(self):
        self.assertNotIn(COMMIT_STATE_STEM, workspace.__doc__ or "")

    def test_ac2_ensure_docstring_does_not_describe_uncommitted_artifact_transfer(self):
        self.assertNotIn(COMMIT_STATE_STEM, workspace.ensure.__doc__ or "")


if __name__ == "__main__":
    unittest.main()
