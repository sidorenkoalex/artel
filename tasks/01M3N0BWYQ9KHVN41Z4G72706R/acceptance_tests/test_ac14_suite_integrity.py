"""AC-14 — ни один существующий тест, гейт или проверка guard не удалены;
каждый новый тестовый метод в `tests/` несёт «Ловит мутацию: …».

Дифф задачи считается от точки расхождения с `origin` (`gitcmd.
diff_base`, skills/test-authoring.md) — тем же приёмом, что гейт зон.
Часть критерия «полный набор `tests/` зелёный» этим файлом не
исполняется: полный прогон `tests/` не укладывается в таймаут одного
теста планки и уже исполняется штатно — CI ветки и полный прогон на
мерже; «ослаблен» (а не удалён) сверяет ревьюер по диффу. Здесь —
механически различимые части: удаление имён и заявка мутации.

Группа: разовый
Зелёный с рождения: до реализации дифф задачи по `tests/`, `scripts/guard.py` и гейтам пуст — удалённых имён и новых методов без заявки нет; файл сторожит, что реализация их не внесёт (сверка — по голове ветки задачи, закоммиченный код).
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
from scripts import guard  # noqa: E402


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT,
                          capture_output=True, text=True)


def show(rev: str, path: str) -> str | None:
    """Текст `path` на ревизии `rev`; `None` — файла там нет."""
    res = git("show", f"{rev}:{path}")
    return res.stdout if res.returncode == 0 else None


def files_at(rev: str, prefix: str) -> list[str]:
    res = git("ls-tree", "-r", "--name-only", rev, "--", prefix)
    return [p for p in res.stdout.splitlines() if p.endswith(".py")]


def defined_names(source: str, predicate) -> set[str]:
    """`Класс.метод` и имена функций уровня модуля, удовлетворяющие
    `predicate(имя)`."""
    names = set()
    tree = ast.parse(source)
    for node in tree.body:
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

    def test_ac14_no_existing_test_is_removed(self):
        """Каждый тестовый метод `Класс.test_*` из `tests/test_*.py` базы
        есть в `tests/` головы ветки задачи (в любом файле `tests/`).

        Ловит мутацию: разработчик удалил существующий тест, мешавший
        новому гейту (например, тест, чья фикстура без строки группы
        теперь не проходит выход из `tests_writing`), вместо того чтобы
        дописать фикстуре строку — имени метода нет в голове ветки.
        """
        is_test = lambda name: name.startswith("test_")  # noqa: E731
        before = names_under(self.base, "tests", is_test)
        after = names_under("HEAD", "tests", is_test)
        self.assertEqual(sorted(before - after), [],
                         "из tests/ удалены тестовые методы")

    def test_ac14_no_guard_check_or_gate_is_removed(self):
        """Каждая функция `scripts/guard.py` базы и каждый гейт
        (`*_gate`) `orchestrator/advance_gates/` базы есть в голове
        ветки задачи.

        Ловит мутацию: `guard.scan_artifact_disk_reads` «поглощён» новой
        проверкой долгоживущего файла и удалён, либо
        `_tests_writing_artifact_source_gate` снят как дублирующий —
        имени нет в голове ветки.
        """
        before = names_under(self.base, "scripts/guard.py", lambda n: True)
        after = names_under("HEAD", "scripts/guard.py", lambda n: True)
        self.assertEqual(sorted(before - after), [],
                         "из scripts/guard.py удалены функции")
        is_gate = lambda name: name.endswith("_gate")  # noqa: E731
        before = names_under(self.base, "orchestrator/advance_gates", is_gate)
        after = names_under("HEAD", "orchestrator/advance_gates", is_gate)
        self.assertEqual(sorted(before - after), [], "удалены гейты")

    def test_ac14_every_new_test_method_in_tests_has_mutation_claim(self):
        """Для каждого `tests/test_*.py` головы ветки: новые и
        изменённые против базы тестовые методы несут «Ловит мутацию: …»
        (тот же узел `guard.test_functions_without_mutation_claim`, что
        рубеж выхода из `in_dev`).

        Ловит мутацию: новый метод `tests/` (например, проверка признака
        «sys.path») написан с докстрингом без заявки или с «Зелёный с
        рождения» — он окажется в перечне нарушителей.
        """
        offenders = []
        for path in files_at("HEAD", "tests"):
            if not Path(path).name.startswith("test_"):
                continue
            head = show("HEAD", path)
            missing = guard.test_functions_without_mutation_claim(
                show(self.base, path), head)
            offenders.extend(f"{path}::{name}" for name in missing)
        self.assertEqual(offenders, [],
                         "новые методы tests/ без «Ловит мутацию: …»")


if __name__ == "__main__":
    unittest.main()
