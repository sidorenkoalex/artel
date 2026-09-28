"""AC-23 — ни один существующий тест и гейт не ослаблен: тестовые методы
`tests/` базы, функции `scripts/guard.py`, гейты
`orchestrator/advance_gates/` и сверка лока `_acceptance_lock_refuses`
базы есть в голове ветки задачи.

Дифф задачи считается от точки расхождения с `origin` (`gitcmd.
diff_base`, skills/test-authoring.md). Часть критерия «полный набор
`tests/` зелёный» этим файлом не исполняется: полный прогон `tests/` не
укладывается в таймаут одного теста планки (`-o timeout=120` раннера
планки) и уже исполняется штатно — CI ветки, полный прогон `approve` из
`acceptance` и прогон на мерже; «ослаблен» (а не удалён) сверяет ревьюер
по диффу и гейт неослабления тестов на `in_dev -> verifying`. Здесь —
механически различимая часть: удаление имён.

Группа: разовый
Зелёный с рождения: до реализации дифф задачи по `tests/`, `scripts/guard.py` и гейтам пуст — удалённых имён нет; файл сторожит, что реализация их не внесёт (сверка — по голове ветки задачи, закоммиченный код).
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import gitcmd  # noqa: E402


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT,
                          capture_output=True, text=True)


def show(rev: str, path: str) -> str | None:
    res = git("show", f"{rev}:{path}")
    return res.stdout if res.returncode == 0 else None


def files_at(rev: str, prefix: str) -> list[str]:
    res = git("ls-tree", "-r", "--name-only", rev, "--", prefix)
    return [p for p in res.stdout.splitlines() if p.endswith(".py")]


def defined_names(source: str, predicate) -> set[str]:
    """`Класс.метод` и функции уровня модуля, удовлетворяющие `predicate`."""
    names = set()
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if predicate(node.name):
                names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and predicate(item.name)):
                    names.add(f"{node.name}.{item.name}")
    return names


def names_under(rev: str, prefix: str, predicate) -> set[str]:
    names = set()
    for path in files_at(rev, prefix):
        source = show(rev, path)
        if source is not None:
            names |= defined_names(source, predicate)
    return names


class SuiteIntegrityTest(unittest.TestCase):

    def setUp(self):
        self.base = gitcmd.diff_base("HEAD", repo=REPO_ROOT)
        self.assertTrue(self.base, "база диффа задачи не вычислена")

    def test_ac23_no_existing_test_method_is_removed(self):
        """Каждый тестовый метод `Класс.test_*` из `tests/` базы есть в
        `tests/` головы ветки задачи (в любом файле `tests/`).

        Ловит мутацию: разработчик удалил существующий тест чекпоинта,
        утверждавший «test_author ничего не коммитит в кодовую ветку»,
        вместо того чтобы сузить его до путей без префикса задачи — имени
        метода нет в голове ветки.
        """
        is_test = lambda name: name.startswith("test_")  # noqa: E731
        before = names_under(self.base, "tests", is_test)
        after = names_under("HEAD", "tests", is_test)
        self.assertEqual(sorted(before - after), [],
                         "из tests/ удалены тестовые методы")

    def test_ac23_no_guard_check_or_gate_is_removed(self):
        """Каждая функция `scripts/guard.py` базы и каждый гейт (`*_gate`,
        `*_refuses`) `orchestrator/advance_gates/` базы есть в голове ветки
        задачи.

        Ловит мутацию: `_acceptance_lock_refuses` «поглощён» новым общим
        узлом сверки и удалён, либо `_tests_writing_test_groups_gate`
        снят как дублирующий проверки файлов `tests/` — имени нет в
        голове ветки.
        """
        before = names_under(self.base, "scripts/guard.py", lambda n: True)
        after = names_under("HEAD", "scripts/guard.py", lambda n: True)
        self.assertEqual(sorted(before - after), [],
                         "из scripts/guard.py удалены функции")
        is_gate = lambda name: name.endswith(("_gate", "_refuses"))  # noqa: E731
        before = names_under(self.base, "orchestrator/advance_gates", is_gate)
        after = names_under("HEAD", "orchestrator/advance_gates", is_gate)
        self.assertEqual(sorted(before - after), [], "удалены гейты")


if __name__ == "__main__":
    unittest.main()
