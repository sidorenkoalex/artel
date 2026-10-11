"""AC-3 (tasks/T056/SPEC.md): неослабляемый тест инварианта в
`test_invariants.py` зелёный; все существующие тесты зелёные, включая
тесты, использующие временные песочницы (не git-worktree) — их проверка
не задевает.

Требование 7 SPEC поручает сам неослабляемый тест разработчику —
`tests/test_invariants.py` вне зоны `tasks/T056/acceptance_tests/`
(правка кода/тестов репозитория вне `acceptance_tests/` этой роли
запрещена, скил test-authoring). Здесь — приёмочная сторона критерия:

1. тест действительно появился — структурная метка: разбор формата
   `gitdir: <main>/.git/worktrees/<id>` файла-ссылки `.git` (требование 2
   SPEC), до этой задачи в `tests/test_invariants.py` не встречавшийся;
2. весь набор `tests/` зелёный целиком, тем же вызовом, что и
   CI-джоб `python` (`.github/workflows`) — включая песочницы
   `tests/test_invariants.py`/`tests/test_multitarget_invariants.py`,
   патчащие `config.ROOT` на временный каталог БЕЗ файла-ссылки `.git`
   (требование 5 SPEC: их проверка новый guard не должна задевать).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


class InvariantLockedInTestSuiteTest(unittest.TestCase):

    def test_ac3_worktree_invariant_test_exists_and_full_suite_is_green(self):
        source = (REPO_ROOT / "tests" / "test_invariants.py").read_text(
            encoding="utf-8")
        self.assertIn(
            "gitdir", source,
            "tests/test_invariants.py не разбирает формат `gitdir:` "
            "файла-ссылки .git worktree (требование 2 SPEC) — "
            "неослабляемый тест инварианта (требование 7) не найден")

        result = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", "tests"],
            cwd=REPO_ROOT, timeout=180, capture_output=True, text=True,
            encoding="utf-8")

        self.assertEqual(
            result.returncode, 0,
            f"полный набор tests/ красный:\n{result.stdout[-3000:]}\n"
            f"{result.stderr[-3000:]}")


if __name__ == "__main__":
    unittest.main()
