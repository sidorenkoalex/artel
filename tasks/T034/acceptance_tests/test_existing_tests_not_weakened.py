"""Приёмочные тесты T034: AC-15 — существующие тесты не ослаблены.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 12
(принцип целостности, ADR-0002): ни один тест из существующих
(`tests/*.py`) не удалён и не ослаблен (не превращён в `skip`, не
потерял тестовые методы) в ходе исправления пунктов 1–10.

Приём — тот же, что у `tasks/T031/acceptance_tests/test_branch_correct_reads.py`
(`Ac8ExistingAdvanceTestsNotWeakenedTest`, T033), применённый ко ВСЕМ
файлам `tests/*.py`, а не только к именованным в SPEC: сравнение
рабочего дерева с `main` по множеству имён тестовых методов и по
новым `@unittest.skip*`.

Покрытие поведенческих правок (AC-1, AC-2, AC-3, AC-5, AC-7, AC-9)
новым тестом — по построению этой задачи: каждая из них уже получила
собственный `test_ac<n>_...` в tasks/T034/acceptance_tests/ (см. файлы
рядом), проверять это отдельным тестом было бы тавтологией.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

TEST_METHOD_DEF = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.M)
SKIP_DECORATED_METHOD = re.compile(
    r"@unittest\.skip\w*\([^)]*\)\s*\n\s*def\s+(test_\w+)\s*\(", re.M)


class Ac15ExistingTestsNotWeakenedTest(unittest.TestCase):
    """Реальный репозиторий (не песочница): рабочее дерево против `main`."""

    def _git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def _tests_py_files_on_main(self) -> list:
        listing = self._git("ls-tree", "-r", "--name-only", "main", "--", "tests")
        return sorted(p for p in listing.splitlines()
                     if p.startswith("tests/") and p.endswith(".py")
                     and "/" not in p[len("tests/"):])

    def test_ac15_no_test_method_removed_or_newly_skipped_in_tests_dir(self):
        removed: list[str] = []
        newly_skipped: list[str] = []

        for path in self._tests_py_files_on_main():
            before = self._git("show", f"main:{path}")
            after_file = REPO_ROOT / path
            if not after_file.exists():
                removed.append(f"{path}: файл удалён целиком")
                continue
            after = after_file.read_text(encoding="utf-8")

            missing = (set(TEST_METHOD_DEF.findall(before))
                      - set(TEST_METHOD_DEF.findall(after)))
            if missing:
                removed.append(f"{path}: {sorted(missing)}")

            newly = (set(SKIP_DECORATED_METHOD.findall(after))
                    - set(SKIP_DECORATED_METHOD.findall(before)))
            if newly:
                newly_skipped.append(f"{path}: {sorted(newly)}")

        self.assertEqual(
            removed, [],
            f"тестовые методы tests/*.py удалены по сравнению с main "
            f"(SPEC T034 AC-15, принцип целостности ADR-0002): {removed}")
        self.assertEqual(
            newly_skipped, [],
            f"тестовые методы tests/*.py заскипаны по сравнению с main "
            f"(SPEC T034 AC-15, принцип целостности ADR-0002): {newly_skipped}")


if __name__ == "__main__":
    unittest.main()
