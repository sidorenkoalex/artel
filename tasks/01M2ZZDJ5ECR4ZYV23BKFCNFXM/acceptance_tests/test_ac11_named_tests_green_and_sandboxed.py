"""AC-11 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: названные наборы остаются
зелёными, новые тесты задачи живут на общей песочнице и не трогают
настоящий репозиторий пульта.

Источник — SPEC.md, «Критерии приёмки»:

AC-11. Прогон `tests/test_review_package.py`,
`tests/test_review_freshness.py`,
`tests/test_fsm_review_rework_sha_gate.py` — зелёный; новые тесты задачи
в `tests/` пользуются общей песочницей `tests/sandbox.py` и не меняют
настоящий репозиторий пульта.

Зелёный с рождения: три названных набора зелены и до правки (замер в
шаге автора планки: 113 passed), новых файлов `tests/test_*.py` у ветки
задачи пока нет — проверка использования `tests/sandbox.py` пройдёт по
пустому списку. Критерий сторожит РЕГРЕССИЮ: он обязан покраснеть ровно
тогда, когда правка разработчика ломает один из наборов (ожидания,
привязанные к «предпоследней записи») либо заводит в `tests/` тест,
собирающий свою песочницу мимо `tests/sandbox.py`.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

NAMED_TESTS = ("tests/test_review_package.py",
               "tests/test_review_freshness.py",
               "tests/test_fsm_review_rework_sha_gate.py")

SANDBOX_IMPORT_RE = re.compile(r"^\s*(from\s+tests\s+import\s+sandbox"
                               r"|from\s+tests\.sandbox\s+import"
                               r"|import\s+tests\.sandbox)", re.M)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT,
                          capture_output=True, text=True)


def _run_pytest(*paths: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-q", "-p", "no:cacheprovider"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=100)


def _integration_base() -> str:
    """Точка расхождения ветки задачи с главной — тем же приёмом, что и
    гейты пульта: сначала `origin/main`, при его отсутствии локальный
    `main`. Пустая строка — git не ответил ни на один из двух."""
    for base in ("origin/main", "main"):
        res = _git("merge-base", base, "HEAD")
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    return ""


def _changed_test_files() -> list:
    """Файлы `tests/test_*.py`, которые ветка задачи добавила или
    изменила — закоммиченные и ещё не закоммиченные."""
    base = _integration_base()
    changed: set = set()
    for args in ((["diff", "--name-only", base, "HEAD", "--", "tests/"]
                  if base else None),
                 ["diff", "--name-only", "HEAD", "--", "tests/"],
                 ["ls-files", "--others", "--exclude-standard", "--", "tests/"]):
        if args is None:
            continue
        res = _git(*args)
        if res.returncode == 0:
            changed.update(line.strip() for line in res.stdout.splitlines())
    return sorted(p for p in changed
                  if p.startswith("tests/test_") and p.endswith(".py"))


class NamedTestSuitesStayGreenTest(unittest.TestCase):

    def test_ac11_named_test_suites_are_green(self):
        """Три названных критерием набора прогоняются и обязаны быть
        зелёными после правки: именно в них живут ожидания, привязанные
        к прежней базе инкремента.

        Ловит мутацию: база инкремента переведена на якорь вердикта, а
        ожидания `IncrementalReviewPackageTest`/`PreviousVerdictShaTest`
        не обновлены (или обновлены ослаблением вместо перезаписи) —
        прогон вернёт ненулевой код, и тест покраснеет.
        """
        for path in NAMED_TESTS:
            with self.subTest(path=path):
                self.assertTrue((REPO_ROOT / path).is_file(),
                                f"{path} не существует — критерий называет "
                                f"его обязательным к прогону")
                res = _run_pytest(path)
                self.assertEqual(
                    res.returncode, 0,
                    f"{path} не зелёный:\n{res.stdout[-4000:]}\n{res.stderr[-2000:]}")


class NewTestsUseTheSharedSandboxTest(unittest.TestCase):

    def test_ac11_new_tests_import_the_shared_sandbox(self):
        """Каждый добавленный или изменённый веткой задачи файл
        `tests/test_*.py` импортирует общую песочницу `tests/sandbox.py`.

        Ловит мутацию: новый тест задачи собирает собственную копию
        песочницы (свой `tempfile` + свои патчи `config`) вместо импорта
        общей — ровно тот класс, из-за которого три планки разом упали
        на трёх независимых устаревших копиях одного набора патчей.
        """
        for path in _changed_test_files():
            with self.subTest(path=path):
                source = (REPO_ROOT / path).read_text(encoding="utf-8")
                self.assertRegex(
                    source, SANDBOX_IMPORT_RE,
                    f"{path} не пользуется общей песочницей tests/sandbox.py")

    def test_ac11_running_the_tests_leaves_the_pult_repo_unchanged(self):
        """Прогон названных и новых тестов задачи не меняет настоящий
        репозиторий пульта: `git status --porcelain` до и после совпадает,
        новых каталогов в `.artel/worktrees` не появляется.

        Ловит мутацию: новый тест задачи патчит не все пути `config`
        (например, забывает `WORKTREES` или `ROOT`) и пишет фикстуры в
        реальное дерево пульта — списки до и после разойдутся.
        """
        paths = sorted({*NAMED_TESTS, *_changed_test_files()})
        before_status = _git("status", "--porcelain").stdout
        worktrees = REPO_ROOT / ".artel" / "worktrees"
        before_dirs = sorted(p.name for p in worktrees.iterdir()) \
            if worktrees.is_dir() else []

        _run_pytest(*paths)

        self.assertEqual(before_status, _git("status", "--porcelain").stdout,
                         "прогон тестов изменил рабочее дерево пульта")
        after_dirs = sorted(p.name for p in worktrees.iterdir()) \
            if worktrees.is_dir() else []
        self.assertEqual(before_dirs, after_dirs,
                         "прогон тестов завёл каталог в .artel/worktrees")


if __name__ == "__main__":
    unittest.main()
