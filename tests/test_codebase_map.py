"""Юнит-тесты функций scripts/codebase_map.py (tasks/T027/SPEC.md).

Поведение генератора целиком (запуск процессом, файл на диске, CI-джоб)
уже покрыто локальными приёмочными тестами задачи
(tasks/T027/acceptance_tests/test_codebase_map.py, AC-1..9) — это её
залоченный контракт, дублировать его тут смысла нет. Здесь — юниты на
отдельные функции разбора, которые эти приёмочные тесты проверяют только
косвенно (через итоговый markdown), напрямую на входах, которые сложно
собрать через фикстуру целого дерева: докстринг с внутренними пустыми
строками, импорт под `if`, относительный `from . import x`.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import codebase_map  # noqa: E402


def parse(source: str) -> ast.Module:
    return ast.parse(source)


class ExtractPurposeTest(unittest.TestCase):
    def test_first_line_of_multiline_docstring(self):
        tree = parse('"""Первая строка.\n\nВторая строка, не входит."""\n')
        self.assertEqual(codebase_map.extract_purpose(tree), "Первая строка.")

    def test_no_docstring_marker(self):
        tree = parse("x = 1\n")
        self.assertEqual(codebase_map.extract_purpose(tree),
                         codebase_map.NO_DOCSTRING_MARK)

    def test_blank_docstring_falls_back_to_marker(self):
        tree = parse('"""   """\n')
        self.assertEqual(codebase_map.extract_purpose(tree),
                         codebase_map.NO_DOCSTRING_MARK)


class ExtractPublicFunctionsTest(unittest.TestCase):
    def test_only_top_level_public_functions_sorted(self):
        tree = parse(
            "def zeta(): pass\n"
            "def _hidden(): pass\n"
            "async def alpha(): pass\n"
            "class C:\n"
            "    def method_not_top_level(self): pass\n"
            "def inner_holder():\n"
            "    def nested(): pass\n"
        )
        self.assertEqual(codebase_map.extract_public_functions(tree),
                         ["alpha", "inner_holder", "zeta"])

    def test_no_public_functions(self):
        tree = parse("def _only_private(): pass\n")
        self.assertEqual(codebase_map.extract_public_functions(tree), [])


class ExtractImportedDottedNamesTest(unittest.TestCase):
    def test_absolute_import_statement(self):
        tree = parse("import orchestrator.config\n")
        self.assertIn("orchestrator.config",
                      codebase_map.extract_imported_dotted_names(tree, "scripts"))

    def test_absolute_from_import(self):
        tree = parse("from scripts import guard\n")
        names = codebase_map.extract_imported_dotted_names(tree, "orchestrator")
        self.assertIn("scripts.guard", names)
        self.assertIn("scripts", names)

    def test_relative_from_import_resolves_against_own_package(self):
        tree = parse("from . import config, gitcmd\n")
        names = codebase_map.extract_imported_dotted_names(tree, "orchestrator")
        self.assertIn("orchestrator.config", names)
        self.assertIn("orchestrator.gitcmd", names)

    def test_import_inside_conditional_is_still_found(self):
        tree = parse(
            "if True:\n"
            "    from . import store\n"
        )
        names = codebase_map.extract_imported_dotted_names(tree, "orchestrator")
        self.assertIn("orchestrator.store", names)

    def test_import_of_unrelated_third_party_module_is_kept_unresolved(self):
        tree = parse("import json\n")
        names = codebase_map.extract_imported_dotted_names(tree, "scripts")
        self.assertIn("json", names)


class ModuleDottedNameTest(unittest.TestCase):
    def test_regular_module(self):
        self.assertEqual(
            codebase_map.module_dotted_name(Path("orchestrator/alpha.py")),
            "orchestrator.alpha")

    def test_package_init_named_after_directory(self):
        self.assertEqual(
            codebase_map.module_dotted_name(Path("orchestrator/__init__.py")),
            "orchestrator")


# --- map_stats (01M1RFVWV6WWTXRC5F40K61632, требование 1, AC-1..AC-4) ---
#
# Планка приёмки (tasks/01M1RFVWV6WWTXRC5F40K61632/acceptance_tests/
# test_map_stats.py) уже покрывает эти критерии исчерпывающе на карте,
# построенной настоящим `render()`; здесь — компактный юнит на карте
# трёх каталогов ровно по тексту требования 5 SPEC, без дублирования
# всего объёма приёмочной планки.
MAP_TEXT = (
    "---\nbuilt_at_sha: " + "a" * 40 + "\n---\n\n"
    "# Карта кодовой базы\n\n"
    "## orchestrator/aaa.py\n\n**Назначение:** А.\n\n"
    "**Публичные функции:** (нет)\n\n**Импортирует:** —\n\n"
    "**Импортируется:** —\n\n"
    "## scripts/bbb.py\n\n**Назначение:** Б, подлиннее описание модуля.\n\n"
    "**Публичные функции:**\n- `f`\n- `g`\n\n**Импортирует:** —\n\n"
    "**Импортируется:** —\n\n"
    "## tests/ccc.py\n\n**Назначение:** Ц.\n\n"
    "**Публичные функции:** (нет)\n\n**Импортирует:** —\n\n"
    "**Импортируется:** —\n"
)


class MapStatsTest(unittest.TestCase):
    def test_is_pure_no_disk_or_subprocess(self):
        def boom(*a, **kw):
            raise AssertionError("не должна трогать диск/subprocess")

        with mock.patch.object(Path, "read_text", side_effect=boom), \
                mock.patch("subprocess.run", side_effect=boom):
            result = codebase_map.map_stats(MAP_TEXT)

        self.assertIsInstance(result, dict)

    def test_bytes_total_and_sections_total(self):
        result = codebase_map.map_stats(MAP_TEXT)
        self.assertEqual(result["bytes_total"], len(MAP_TEXT.encode("utf-8")))
        self.assertEqual(result["sections_total"], 3)

    def test_bytes_by_dir_covers_three_directories(self):
        result = codebase_map.map_stats(MAP_TEXT)
        self.assertEqual(set(result["bytes_by_dir"]),
                         {"orchestrator", "scripts", "tests"})
        self.assertTrue(all(v > 0 for v in result["bytes_by_dir"].values()))

    def test_top_sections_sorted_descending_with_name_and_bytes(self):
        result = codebase_map.map_stats(MAP_TEXT)
        top = result["top_sections"]
        self.assertEqual(len(top), 3, "меньше пяти секций всего — все войдут")
        sizes = [entry["bytes"] for entry in top]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        self.assertEqual({entry["name"] for entry in top},
                         {"orchestrator/aaa.py", "scripts/bbb.py", "tests/ccc.py"})

    def test_bytes_projection_key_present_with_project_for_brief(self):
        """После подтяжки main `project_for_brief` существует (задача
        01M1RFQ52S0VD22J628TXX96XS) — ключ обязан быть и равняться байтам
        проекции (AC-3, вторая половина условия). Ловит мутацию: ключ
        считается от полного текста, а не от проекции."""
        self.assertTrue(hasattr(codebase_map, "project_for_brief"))
        result = codebase_map.map_stats(MAP_TEXT)
        self.assertEqual(
            result["bytes_projection"],
            len(codebase_map.project_for_brief(MAP_TEXT).encode("utf-8")))

    def test_result_is_compact_single_line_json_serializable(self):
        result = codebase_map.map_stats(MAP_TEXT)
        compact = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        self.assertNotIn("\n", compact)
        self.assertEqual(json.loads(compact), result)
class RepoRootTest(unittest.TestCase):
    """`codebase_map.repo_root` (SPEC 01M1SAA01YRRTWAVADT2F81RRQ, AC-4/AC-7):
    приёмочные тесты залоченной планки уже гоняют её через `main()` на
    двух глубинах подкаталога — здесь юниты на саму функцию, изолированно
    от записи файла на диск и от `git_head_sha`."""

    def test_resolves_to_git_top_level_not_the_given_subdir(self):
        """Ловит мутацию: `repo_root` возвращает переданный `cwd` напрямую
        вместо результата `git rev-parse --show-toplevel` — запуск из
        подкаталога тогда пишет карту не в корень репозитория."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subdir = root / "a" / "b"
            subdir.mkdir(parents=True)
            self.assertEqual(codebase_map.repo_root(subdir), root)

    def test_raises_when_cwd_is_outside_any_git_repository(self):
        """Ловит мутацию: ошибка git-процесса подавляется (например,
        `subprocess.run(..., check=False)`), и функция молча возвращает
        некорректный путь вместо падения.

        `GIT_CEILING_DIRECTORIES` — иначе git продолжил бы искать `.git`
        выше по дереву и мог бы найти настоящий репозиторий пульта,
        если временный каталог ОС окажется внутри его рабочей копии.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with mock.patch.dict(os.environ,
                                 {"GIT_CEILING_DIRECTORIES": str(root)}):
                with self.assertRaises(subprocess.CalledProcessError):
                    codebase_map.repo_root(root)


if __name__ == "__main__":
    unittest.main()
