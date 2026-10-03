"""Постоянные тесты задачи покрывают AC-1, AC-2, AC-4–AC-8 с заявками
мутаций; изменённые существующие тесты перечислены в PLAN.md.

Группа: разовый

Зелёный с рождения: до реализации ветка уже несёт долгоживущий файл планки `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py` (методы `test_ac1_…`, `test_ac2_…`, `test_ac4_…`–`test_ac8_…`, у каждого «Ловит мутацию»), а существующие тесты не тронуты — перечислять в PLAN нечего; тест сторожит, что правка существующих тестов не пройдёт без перечня в PLAN.

Группа «разовый»: предмет — дифф `tests/` этой ветки против базы и PLAN.md
задачи; после мержа их не на чем проверять.

Дифф — от точки расхождения HEAD рабочей копии кода с `origin/<основная>`
(`gitcmd.diff_base`), с рабочим деревом и неотслеживаемыми файлами `tests/`.
«Добавленный» файл — `tests/test_*.py`, которого нет в базе; «изменённый
существующий тест» — функция `test_*` файла базы, которой нет в HEAD или
чей текст в HEAD другой (удалённый файл — все его функции `test_*`).
Покрытие критерия — метод `test_ac<n>_…` в добавленном файле (имя метода —
единственная связь критерия с тестом, skills/test-authoring.md); заявка —
тем же узлом, что гейт выхода из `in_dev`
(`guard.test_functions_without_mutation_claim`). Перечень в PLAN — имя
функции (или имя класса, если класса в HEAD больше нет, или имя файла,
если файл удалён) в тексте PLAN.md, читаемого из ссылки документов, и
ссылка на ADR-0021 в нём.
"""
import ast
import re
import unittest

from _plank import CODE_ROOT, git, read_plan

from orchestrator import gitcmd
from scripts import guard

COVERED_ACS = (1, 2, 4, 5, 6, 7, 8)
TEST_FILE = re.compile(r"^tests/(.+/)?test_[^/]*\.py$")
ADR = "ADR-0021"


def diff_base() -> str | None:
    return gitcmd.diff_base("HEAD", repo=CODE_ROOT)


def changed_test_files(base: str) -> tuple[list, list, list]:
    """(добавленные, изменённые, удалённые) пути `tests/test_*.py` ветки от
    `base`: коммиты, рабочее дерево и неотслеживаемые файлы."""
    res = git("diff", "--name-status", "--no-renames", base, "--", "tests")
    assert res.returncode == 0, res.stderr
    added, modified, deleted = set(), set(), set()
    for line in res.stdout.splitlines():
        status, _, path = line.partition("\t")
        if not TEST_FILE.match(path):
            continue
        {"A": added, "M": modified, "D": deleted}.get(status[:1], modified).add(path)
    untracked = git("ls-files", "--others", "--exclude-standard", "--", "tests")
    assert untracked.returncode == 0, untracked.stderr
    added |= {p for p in untracked.stdout.split() if TEST_FILE.match(p)}
    return sorted(added), sorted(modified), sorted(deleted)


def show_base(base: str, path: str) -> str | None:
    res = git("show", f"{base}:{path}")
    return res.stdout if res.returncode == 0 else None


def collect_test_functions(source: str | None) -> dict:
    """{(класс или "", имя): текст сегмента} функций `test_*` модуля."""
    if source is None:
        return {}
    tree = ast.parse(source)
    found = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name.startswith("test")):
                    found[(node.name, item.name)] = ast.get_source_segment(
                        source, item)
        elif (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
              and node.name.startswith("test")):
            found[("", node.name)] = ast.get_source_segment(source, node)
    return found


def class_names(source: str | None) -> set:
    if source is None:
        return set()
    return {n.name for n in ast.parse(source).body if isinstance(n, ast.ClassDef)}


class PermanentTestsTest(unittest.TestCase):

    def setUp(self):
        self.base = diff_base()
        self.assertTrue(self.base, "база диффа ветки задачи не вычислена")
        self.added, self.modified, self.deleted = changed_test_files(self.base)

    def head_source(self, path: str) -> str:
        return (CODE_ROOT / path).read_text(encoding="utf-8")

    def test_ac11_added_tests_cover_criteria_with_mutation_claims(self):
        """Добавленные `tests/test_*.py` несут методы `test_ac<n>_…` для AC-1, AC-2, AC-4–AC-8, и у каждого метода есть «Ловит мутацию».

        Сценарий: собираются функции `test_*` всех файлов `tests/`,
        добавленных веткой; для каждого из AC-1, AC-2, AC-4…AC-8 среди них
        есть метод с префиксом `test_ac<n>_`; ни у одного метода
        добавленных файлов нет пропуска заявки «Ловит мутацию: …».

        Ловит мутацию: постоянный тест на один из критериев не добавлен
        (покрытие только разовой планкой) — префикса `test_ac<n>_` нет;
        добавленный метод без строки «Ловит мутацию» — узел гейта его
        называет.
        """
        names = []
        unclaimed = []
        for path in self.added:
            source = self.head_source(path)
            names += [name for _cls, name in collect_test_functions(source)]
            unclaimed += [f"{path}::{m}" for m in
                          guard.test_functions_without_mutation_claim(None, source)]
        missing = [n for n in COVERED_ACS
                   if not any(name.startswith(f"test_ac{n}_") for name in names)]
        self.assertEqual(missing, [], (
            f"нет постоянных тестов на AC {missing}; добавленные файлы: "
            f"{self.added}"))
        self.assertEqual(unclaimed, [], "методы без «Ловит мутацию»")

    def test_ac11_changed_existing_tests_listed_in_plan(self):
        """Каждый изменённый или удалённый существующий тест `tests/` назван в PLAN.md, и PLAN ссылается на ADR-0021.

        Сценарий: для изменённых и удалённых веткой `tests/test_*.py`
        собираются функции `test_*` базы, которых нет в HEAD или чей текст
        другой; каждая названа в PLAN.md из ссылки документов (имя
        функции; имя класса, если класс удалён; имя файла, если удалён
        файл), а в PLAN есть ссылка на ADR-0021. Ни одного такого теста —
        перечислять нечего.

        Ловит мутацию: разработчик правит или удаляет существующий тест
        (например, `ArtifactRepoInitTest` в `tests/test_git_fixation.py`)
        и не перечисляет его в PLAN — имя теста отсутствует в тексте PLAN.
        """
        changed = []
        for path in self.modified + self.deleted:
            base_src = show_base(self.base, path)
            head_src = None if path in self.deleted else self.head_source(path)
            head = collect_test_functions(head_src)
            head_classes = class_names(head_src)
            for (cls, name), segment in collect_test_functions(base_src).items():
                if head.get((cls, name)) == segment:
                    continue
                aliases = [name]
                if cls and cls not in head_classes:
                    aliases.append(cls)
                if head_src is None:
                    aliases.append(path.rsplit("/", 1)[-1])
                changed.append((f"{path}::{cls}::{name}", aliases))
        if not changed:
            return
        plan, reason = read_plan()
        self.assertIsNotNone(plan, f"PLAN.md не прочитан из ссылки: {reason}")
        self.assertIn(ADR, plan, "PLAN не обосновывает правку тестов ADR-0021")
        unlisted = [label for label, aliases in changed
                    if not any(alias in plan for alias in aliases)]
        self.assertEqual(unlisted, [],
                         "изменённые существующие тесты не перечислены в PLAN")


if __name__ == "__main__":
    unittest.main()
