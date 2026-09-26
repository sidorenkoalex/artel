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
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config  # noqa: E402
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
        """Ловит мутацию: `map_stats` читает файл с диска или зовёт
        subprocess (например, ходит в git за sha) вместо разбора только
        переданного текста карты (AC-1: чистая функция)."""
        def boom(*a, **kw):
            raise AssertionError("не должна трогать диск/subprocess")

        with mock.patch.object(Path, "read_text", side_effect=boom), \
                mock.patch("subprocess.run", side_effect=boom):
            result = codebase_map.map_stats(MAP_TEXT)

        self.assertIsInstance(result, dict)

    def test_bytes_total_and_sections_total(self):
        """Ловит мутацию: `bytes_total` считается по числу символов, а не
        байт utf-8 входного текста; `sections_total` считает не секции
        верхнего уровня (например, все `##`-заголовки без разбора уровня
        вложенности) — на фикстуре из трёх секций дал бы иное число."""
        result = codebase_map.map_stats(MAP_TEXT)
        self.assertEqual(result["bytes_total"], len(MAP_TEXT.encode("utf-8")))
        self.assertEqual(result["sections_total"], 3)

    def test_bytes_by_dir_covers_three_directories(self):
        """Ловит мутацию: `bytes_by_dir` пропускает один из трёх каталогов
        перечня (`orchestrator/`, `scripts/`, `tests/`) или приписывает
        секцию не тому каталогу — размер по каталогу останется нулевым."""
        result = codebase_map.map_stats(MAP_TEXT)
        self.assertEqual(set(result["bytes_by_dir"]),
                         {"orchestrator", "scripts", "tests"})
        self.assertTrue(all(v > 0 for v in result["bytes_by_dir"].values()))

    def test_top_sections_sorted_descending_with_name_and_bytes(self):
        """Ловит мутацию: `top_sections` не отсортирован по убыванию
        размера (например, по порядку появления в карте) или несёт не
        все секции карты с их именами/размерами."""
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
        """Ловит мутацию: результат несёт значение, несериализуемое в
        компактный однострочный JSON (например, `set` вместо списка в
        `top_sections`), или сериализация с дефолтными разделителями
        `json.dumps` вносит переносы строк/лишние пробелы (AC-4)."""
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


# --- подпакеты (01M3FTQ16M3VVXPPFCC0BGA39V, требования 1-4) ------------
#
# Залоченная планка задачи гоняет те же свойства на дереве-фикстуре
# целиком; здесь — юниты на отдельные функции обхода и разбора имён,
# плюс единственная проверка, которую фикстурой не собрать: размер
# проекции РЕАЛЬНОЙ карты против порога переполнения брифа.
SUBPACKAGE_TREE = {
    "orchestrator/__init__.py": '"""Пакет."""\n',
    "orchestrator/config.py": '"""Конфиг."""\n\nLIMIT = 1\n',
    "orchestrator/doctor/__init__.py": '"""Подпакет."""\n',
    "orchestrator/doctor/checks.py": '"""Сосед по подпакету."""\n',
    "orchestrator/doctor/preflight.py": (
        '"""Модуль подпакета."""\n'
        "from . import checks\n"
        "from .. import config\n"
    ),
    "orchestrator/doctor/__pycache__/preflight.py": '"""Мусор."""\n',
    "tests/test_x.py": '"""Тест."""\n',
}


def write_tree(root: Path, files: dict) -> None:
    for rel, source in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")


class DiscoverModulePathsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        write_tree(self.root, SUBPACKAGE_TREE)
        self.found = [p.relative_to(self.root).as_posix()
                      for p in codebase_map.discover_module_paths(self.root)]

    def test_subpackage_modules_are_discovered(self):
        """Ловит мутацию: обход снова нерекурсивный (`glob("*.py")`) или
        рекурсия заведена только для `__init__.py` подпакета — модулей
        `orchestrator/doctor/*.py` в перечне не будет."""
        self.assertEqual(
            ["orchestrator/__init__.py", "orchestrator/config.py",
             "orchestrator/doctor/__init__.py",
             "orchestrator/doctor/checks.py",
             "orchestrator/doctor/preflight.py",
             "tests/test_x.py"],
            self.found)

    def test_service_directories_are_skipped(self):
        """Ловит мутацию: `rglob("*.py")` без фильтра служебных каталогов
        — байткод-кэш подпакета (`__pycache__/preflight.py`) и содержимое
        скрытого каталога попадут в перечень модулей карты."""
        self.assertEqual([], [rel for rel in self.found
                              if "__pycache__" in rel])
        write_tree(self.root, {"orchestrator/.venv/lib/mod.py": "x = 1\n"})
        again = [p.relative_to(self.root).as_posix()
                 for p in codebase_map.discover_module_paths(self.root)]
        self.assertEqual(self.found, again)

    def test_subpackage_sections_stay_contiguous(self):
        """Сортировка по сегментам пути, а не по имени файла: модули
        подпакета идут подряд.

        Ловит мутацию: ключ сортировки вернулся к `p.name` — `checks.py`
        подпакета встанет по алфавиту между `__init__.py` и `config.py`
        верхнего уровня, и блок подпакета разорвётся."""
        write_tree(self.root, {"orchestrator/zeta.py": '"""Z."""\n'})
        found = [p.relative_to(self.root).as_posix()
                 for p in codebase_map.discover_module_paths(self.root)]
        positions = [i for i, rel in enumerate(found)
                     if rel.startswith("orchestrator/doctor/")]
        self.assertEqual(3, len(positions))
        self.assertEqual(list(range(positions[0], positions[0] + 3)), positions)


class SubpackageDottedNamesTest(unittest.TestCase):
    def test_module_of_subpackage_named_by_full_path(self):
        """Ловит мутацию: имя собрано из первого сегмента пути и `stem`
        (`orchestrator.preflight`) — оно не совпадёт с абсолютным
        импортом `orchestrator.doctor.preflight`, и зависимость потеряется."""
        self.assertEqual(
            "orchestrator.doctor.preflight",
            codebase_map.module_dotted_name(
                Path("orchestrator/doctor/preflight.py")))

    def test_init_of_subpackage_named_by_the_subpackage(self):
        """Ловит мутацию: ветка `__init__.py` возвращает `parts[0]`
        (`orchestrator`) — `__init__.py` подпакета перекроет в словаре
        имён `orchestrator/__init__.py` пакета верхнего уровня."""
        self.assertEqual(
            "orchestrator.doctor",
            codebase_map.module_dotted_name(
                Path("orchestrator/doctor/__init__.py")))

    def test_package_name_of_module(self):
        """`module_package_name` — база относительных импортов модуля.

        Ловит мутацию: функция возвращает dotted-имя самого модуля, а не
        его пакета (`orchestrator.doctor.preflight` вместо
        `orchestrator.doctor`) — `from . import checks` резолвился бы в
        несуществующий `orchestrator.doctor.preflight.checks`."""
        self.assertEqual(
            "orchestrator.doctor",
            codebase_map.module_package_name(
                Path("orchestrator/doctor/preflight.py")))
        self.assertEqual(
            "orchestrator",
            codebase_map.module_package_name(Path("orchestrator/config.py")))


class RelativeImportLevelsTest(unittest.TestCase):
    def test_parent_level_import_resolves_above_the_subpackage(self):
        """Ловит мутацию: уровень 2 по-прежнему отбрасывается ветвью
        `else: continue` — `from .. import config` внутри
        `orchestrator.doctor` не даст `orchestrator.config`."""
        tree = parse("from .. import config\n")
        names = codebase_map.extract_imported_dotted_names(
            tree, "orchestrator.doctor")
        self.assertIn("orchestrator.config", names)
        self.assertIn("orchestrator", names)

    def test_own_level_import_resolves_inside_the_subpackage(self):
        """Ловит мутацию: уровень 1 отсчитывается на сегмент выше, чем
        надо (`orchestrator.checks` вместо
        `orchestrator.doctor.checks`) — сосед по подпакету не найдётся."""
        tree = parse("from . import checks\n")
        names = codebase_map.extract_imported_dotted_names(
            tree, "orchestrator.doctor")
        self.assertIn("orchestrator.doctor.checks", names)

    def test_import_above_the_package_root_is_skipped(self):
        """Ловит мутацию: глубина уровня не сверяется с числом сегментов
        пакета — `from .. import y` в модуле верхнего уровня даст пустой
        или обрезанный якорь вроде `.y`, то есть мусорное имя в перечне."""
        tree = parse("from .. import y\n")
        names = codebase_map.extract_imported_dotted_names(tree, "orchestrator")
        self.assertEqual(set(), {n for n in names if n.endswith("y")})


class SubpackageDependencyListsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        write_tree(self.root, SUBPACKAGE_TREE)
        self.modules, self.imports, self.imported_by = \
            codebase_map.build_modules(self.root)

    def test_relative_targets_land_in_both_directions(self):
        """Ловит мутацию: разрешённые относительные импорты кладутся
        только в `resolved_imports`, а обратный индекс `imported_by`
        наполняется по прежнему набору — «Импортируется» соседа по
        подпакету останется пустым."""
        sub = "orchestrator/doctor/preflight.py"
        self.assertEqual(["orchestrator/config.py",
                          "orchestrator/doctor/checks.py"],
                         self.imports[sub])
        self.assertEqual([sub], self.imported_by["orchestrator/config.py"])
        self.assertEqual([sub],
                         self.imported_by["orchestrator/doctor/checks.py"])

    def test_subpackage_init_is_not_a_dependency_target(self):
        """`__init__.py` исключён как цель и у подпакета — иначе
        `from . import checks`, попутно называющий сам пакет, приписал бы
        зависимость от `orchestrator/doctor/__init__.py` почти каждому
        модулю подпакета.

        Ловит мутацию: исключение сужено до `__init__.py` каталога
        верхнего уровня (сверка по полному пути вместо имени файла) — в
        «Импортирует» модуля подпакета появится его собственный
        `__init__.py`."""
        self.assertEqual(
            [], self.imported_by["orchestrator/doctor/__init__.py"])


class SubpackageProjectionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        write_tree(self.root, SUBPACKAGE_TREE)
        modules, imports, imported_by = codebase_map.build_modules(self.root)
        self.map_text = codebase_map.render(modules, imports, imported_by,
                                            "0" * 40)
        self.projected = codebase_map.project_for_brief(self.map_text)

    def _labels(self, map_text: str, rel: str) -> list:
        marker = f"## {rel}\n"
        start = map_text.index(marker)
        rest = map_text[start + len(marker):]
        nxt = rest.find("\n## ")
        section = rest if nxt == -1 else rest[:nxt]
        return re.findall(r"^\*\*([^:*]+):\*\*", section, re.M)

    def test_subpackage_section_projected_like_top_level(self):
        """Ловит мутацию: `_section_kind` начинает выбирать правило по
        полному пути секции, а не по первому сегменту — секция
        `orchestrator/doctor/preflight.py` вернётся из проекции как есть,
        вместе с блоком «Импортируется»."""
        self.assertEqual(
            ["Назначение", "Публичные функции", "Импортирует",
             "Импортируется"],
            self._labels(self.map_text, "orchestrator/doctor/preflight.py"))
        self.assertEqual(
            ["Назначение", "Публичные функции", "Импортирует"],
            self._labels(self.projected,
                         "orchestrator/doctor/preflight.py"))
        self.assertEqual(
            self._labels(self.projected, "orchestrator/config.py"),
            self._labels(self.projected, "orchestrator/doctor/preflight.py"))

    def test_tests_sections_still_keep_only_purpose(self):
        """Ловит мутацию: правило подпакетов заведено расширением
        `_KEPT_FIELDS_BY_KIND` с сохранением всех полей по умолчанию —
        секции `tests/*` начнут носить «Публичные функции»/«Импортирует»
        и проекция раздуется."""
        self.assertEqual(["Назначение"],
                         self._labels(self.projected, "tests/test_x.py"))


class RealMapProjectionSizeTest(unittest.TestCase):
    def test_projection_of_committed_map_fits_the_brief_threshold(self):
        """Проекция закоммиченной карты реального дерева умещается в
        `config.CONTEXT_FILE_MAX_BYTES` — порог, за которым
        `orchestrator/brief.py` поднимает алерт переполнения и выкидывает
        карту из брифа роли.

        Ловит мутацию: секциям подпакетов оставлены все четыре поля (или
        проекция перестала снимать «Импортируется») — карта из 281 секции
        перерастает порог, и бриф разработчика молча остаётся без карты."""
        root = Path(__file__).resolve().parent.parent
        map_text = (root / codebase_map.OUTPUT_PATH).read_text(encoding="utf-8")
        size = len(codebase_map.project_for_brief(map_text).encode("utf-8"))
        self.assertLessEqual(
            size, config.CONTEXT_FILE_MAX_BYTES,
            f"проекция карты — {size} байт при потолке "
            f"{config.CONTEXT_FILE_MAX_BYTES}: уточняй правило проекции, "
            f"не порог")


if __name__ == "__main__":
    unittest.main()
