"""AC-8 (tasks/T052/SPEC.md): все существующие тесты пакета остаются
зелёными; единственное допустимое изменение существующего теста —
`test_merge_failure_leaves_the_task_in_the_gate` (`tests/test_invariants.py`).

«Все существующие тесты пакета остаются зелёными» эти акцептансы
дословно не перепрогоняют: полный `unittest discover -s tests` уже
исполняет штатный CI-гейт на каждый коммит ветки
(`.github/workflows/ci.yml`, джоб `python`) — тот же довод и прецедент,
что AC-4 в `tasks/T036/acceptance_tests/test_merge_gitcmd.py` (там —
явный `manual`; повтор здесь подпроцессом ловил бы экологию машины
разработчика, не дефект T052). Вторая половина критерия — КАКОЙ именно
существующий тест разрешено менять — содержательно проверяема реальным
диффом ветки относительно `main`, без единого мока (тем же приёмом, что
`tasks/T049/acceptance_tests/test_ac6_ac7_regression_and_protected_paths.py`
AC-7): поэтому вся AC-8 в `manual` целиком не уводится.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

ALLOWED_MODIFIED_EXISTING_TEST = "tests/test_invariants.py"


class OnlyOneExistingTestFileMayChangeTest(unittest.TestCase):
    """Реальный дифф текущей ветки относительно `main`, без моков."""

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout

    def test_ac8_diff_touches_at_most_the_permitted_existing_test_file(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD").strip()
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch).strip()

        existing_before = set(self._git(
            "ls-tree", "-r", "--name-only", merge_base,
            "tests").splitlines())
        changed = set(self._git(
            "diff", "--name-only", merge_base, branch, "--",
            "tests").splitlines())

        offending = sorted(
            (existing_before & changed) - {ALLOWED_MODIFIED_EXISTING_TEST})
        self.assertEqual(
            offending, [],
            f"дифф ветки {branch} правит существующие тесты вне "
            f"{ALLOWED_MODIFIED_EXISTING_TEST}: {offending} (SPEC T052, "
            f"AC-8 — единственное допустимое изменение существующего "
            f"теста — test_merge_failure_leaves_the_task_in_the_gate)")


if __name__ == "__main__":
    unittest.main()
