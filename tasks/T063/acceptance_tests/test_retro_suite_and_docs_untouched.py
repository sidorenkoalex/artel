"""Приёмочные тесты T063 — AC-4 (полный набор тестов остаётся зелёным) и
AC-5 (`docs/retro/` не переписывается этой задачей)."""
# AC-4: manual — критерий уже покрыт `.github/workflows/ci.yml` (джоб
# `python`, `unittest discover -s tests -v` на каждый пуш в чистом
# раннере); повтор прогона всего набора подпроцессом внутри
# acceptance_tests ловил бы экологические условия машины разработчика, а
# не дефект этой задачи (прецедент tasks/T036 AC-4, tasks/T042 AC-5).

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


class Ac5RetroDirUntouchedTest(unittest.TestCase):
    """AC-5: реальная проверка диффа текущей ветки задачи относительно
    `main` — без единого мока, тем же принципом, что `ProtectedPathsUntouchedTest`
    в tasks/T042/acceptance_tests/test_map_regen_on_merge.py."""

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def test_ac5_branch_diff_does_not_touch_docs_retro(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        offending = [p for p in changed if p.startswith("docs/retro/")]
        self.assertEqual(
            offending, [],
            f"дифф ветки {branch} относительно main переписывает "
            f"уже сгенерированные RETRO-файлы: {offending}")


if __name__ == "__main__":
    unittest.main()
