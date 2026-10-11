"""Приёмочные тесты T083 — AC-3 (SPEC.md, «Критерии приёмки»):

Полный набор `tests/` зелёный при прогоне в копии репозитория с
произвольными ветками/worktree и не зависит от состояния реального git
пульта.

Не `manual` (в отличие от прецедента `tasks/T037/acceptance_tests/
test_manual_criteria.py`, AC-5 «полный прогон зелёный», размеченного
`manual`, потому что этот же прогон и так гоняет CI на каждый пуш): CI
чистого раннера здесь ничего не докажет — фактура части 2 (приёмка T048,
28.08) прямым текстом говорит «на CI (detached HEAD) зелено, на живой
копии с ветками задач — 16 ложных падений полного набора». Сам предмет
AC-3 — поведение именно в живой копии с произвольными ветками, которую
чистый раннер CI не воспроизводит никогда.

Красен до реализации: тест ниже создаёт ИЗОЛИРОВАННУЮ копию репозитория
(не трогает настоящий пульт — только что скопированное дерево в
tempfile), заводит в ней реальную ветку `task/t001-byudzhet` — тем самым
именем, которое `tests/test_spec_budget.py::LegacyDbMigrationTest`
подставляет в БД напрямую (без `fake_git`, AC-2) — плюс несколько
случайных посторонних веток и worktree поверх этой же копии, и гоняет
полный `python3 -m unittest discover -s tests` внутри worktree. Подход
эмпирически перепроверен перед записью этого файла: с сегодняшним кодом
(`LegacyDbMigrationTest` без `fake_git`) эта постановка даёт ровно 16
провалов — то же число, что в фактуре части 2 SPEC; с тем же временным
стабом, что и AC-2 (не закоммичен), — 0.

Тяжёлый тест (копирует дерево, поднимает временный git, гоняет ~1000
тестов подпроцессом — порядка двух минут): осознанно, это буквальное
прочтение критерия, не сокращение до подмножества — «Полный набор
tests/».
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Ветка, которую `tests/test_spec_budget.py::LegacyDbMigrationTest`
# вписывает в БД напрямую, в обход `catalog.cmd_new`/`fake_git` (AC-2,
# смотри tasks/T083/acceptance_tests/test_ac2_no_real_pult_git.py) —
# реальное совпадение имени с существующей веткой пульта и есть источник
# «16 ложных падений» из фактуры части 2 SPEC.
COLLIDING_BRANCH = "task/t001-byudzhet"

DECOY_BRANCHES = (
    COLLIDING_BRANCH,
    "task/tzzz1-proizvolnaya-vetka-postoronney-zadachi",
    "task/tzzz2-eshcho-odna-postoronnyaya-vetka",
    "feature/nikak-ne-svyazannaya-s-testami-vetka",
)


class FullSuiteGreenInCopyWithArbitraryBranchesTest(unittest.TestCase):
    """AC-3."""

    def test_ac3_full_tests_suite_is_green_in_a_repo_copy_with_arbitrary_branches_and_a_worktree(self):
        tmp_root = Path(tempfile.mkdtemp(prefix="t083-ac3-"))
        try:
            copy_dir = tmp_root / "repo"
            shutil.copytree(
                REPO_ROOT, copy_dir,
                ignore=shutil.ignore_patterns(
                    ".git", ".artel", "__pycache__", "*.pyc", ".pytest_cache"))

            def git(*args, cwd=copy_dir):
                res = subprocess.run(["git", *args], cwd=cwd,
                                     capture_output=True, text=True)
                self.assertEqual(
                    res.returncode, 0,
                    f"подготовка фабрикованной копии: git {args} упал: "
                    f"{res.stderr}")
                return res

            git("init", "-q", "-b", "main")
            git("config", "user.email", "t083-ac3@example.invalid")
            git("config", "user.name", "T083 AC-3 acceptance")
            git("add", "-A")
            git("commit", "-q", "-m", "снимок дерева для AC-3")
            for branch in DECOY_BRANCHES:
                git("branch", branch)

            # Второй кусок формулировки критерия — «...веток/worktree»:
            # рабочее дерево ЗАДАЧИ поверх той же фабрикованной копии, а не
            # сама копия на main/detached HEAD.
            worktree_dir = tmp_root / "worktree"
            git("worktree", "add", "-q", "-b",
                "task/tzzz3-worktree-samoy-zadachi", str(worktree_dir))

            result = subprocess.run(
                [sys.executable, "-m", "unittest", "discover",
                 "-s", "tests", "-p", "test_*.py"],
                cwd=worktree_dir, capture_output=True, text=True)

            self.assertEqual(
                result.returncode, 0,
                "полный набор tests/ не зелёный в копии репозитория с "
                "произвольными ветками/worktree (AC-3) — не независим от "
                "состояния git:\n"
                f"{result.stdout[-6000:]}\n{result.stderr[-6000:]}")
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
