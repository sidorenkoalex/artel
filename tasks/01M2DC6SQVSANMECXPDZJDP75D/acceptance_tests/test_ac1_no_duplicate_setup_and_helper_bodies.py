"""AC-1 — 01M2DC6SQVSANMECXPDZJDP75D: ни один байтово идентичный `setUp`
или вспомогательная функция не остаются скопированными между файлами
`tests/*.py` (кроме `tests/test_invariants.py`) — общий код обязан жить
в базовом классе/функции `tests/sandbox.py`, остальные файлы наследуют.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. Байтово идентичные тела `setUp` и байтово идентичные тела
вспомогательных функций (`event`, `fake_git_config` и другие такие же
группы, кроме `tests/test_invariants.py`) заменены наследованием от
общих базовых классов `tests/sandbox.py`; ни один файл `tests/*.py`
(кроме `tests/test_invariants.py`) не содержит собственную копию тела,
байтово совпадающего с телом в другом файле или с телом нового
базового класса.

Проверка сканирует ИСХОДНЫЙ текст `tests/*.py` (AST + точная нарезка
источника по позиции узла — `ast.get_source_segment`, побайтовое
сравнение, не эвристика по имени) и группирует байтово одинаковые тела
`setUp`-методов и тела функций верхнего уровня модуля; для любой группы
размером ≥ 2 файл-нарушитель называется по имени. Сканирование включает
`tests/sandbox.py` в общий пул источников — совпадение тела файла с
телом БАЗОВОГО класса (наследование не случилось, тело просто
продублировано ещё раз рядом с базой) ловится тем же сравнением, что и
совпадение между двумя обычными файлами `tests/*.py`.

Красен до реализации: сегодня в `tests/*.py` (без `tests/test_invariants.
py`) 22 группы байтово идентичных `setUp` (например, `tests/
test_agent_log.py:_AgentLogTmpRootTest`, `tests/test_step_cost.py:
_StepCostTmpRootTest`, `tests/test_agent_failure.py:
_AgentFailureTmpRootTest` — все три несут один и тот же текст `setUp`, SPEC
«Контекст») и 1 группа идентичных вспомогательных функций (`event` в
`tests/test_agent_log.py` и `tests/test_step_cost.py`) — задача ещё не
перенесла ни одну из них в общий базовый класс/функцию, оба
`assertEqual({}, ...)` ниже находят непустой список нарушителей и
падают. Зелёный с рождения: `test_ac1_synthetic_duplicate_setup_bodies_
are_detected`/`test_ac1_synthetic_duplicate_helper_functions_are_detected`
— самопроверки самого сканера на подставных строках-модулях, не на
реальном дереве `tests/`; они подтверждают, что сравнение реагирует и на
дубль, и на различие корректно, независимо от того, сколько реальных
групп дублей сейчас не устранено — стаб корректной реализации
(временное удаление тела `setUp` из `_AgentFailureTmpRootTest`
(`tests/test_agent_failure.py`) — как выглядел бы переход на
наследование от общего базового класса без собственного `setUp` —
подтвердило, что группа-тройка с `test_agent_log.py`/`test_step_cost.py`
теряет этот файл среди нарушителей; правка отменена `git checkout` без
коммита).
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

REPO_ROOT = Path(__file__).resolve().parents[3]
TESTS_DIR = REPO_ROOT / "tests"
EXCLUDED_FILES = {"test_invariants.py"}


def _collect_setup_bodies(sources: dict) -> dict:
    """{текст тела setUp: [список меток "файл:класс"]} по словарю
    {имя_файла: исходный_текст}."""
    groups: dict = {}
    for relname, src in sources.items():
        tree = ast.parse(src, filename=relname)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "setUp":
                    seg = ast.get_source_segment(src, item)
                    groups.setdefault(seg, []).append(f"{relname}:{node.name}")
    return groups


def _collect_module_helper_bodies(sources: dict) -> dict:
    """{текст функции верхнего уровня: [список меток "файл:функция"]}."""
    groups: dict = {}
    for relname, src in sources.items():
        tree = ast.parse(src, filename=relname)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                seg = ast.get_source_segment(src, node)
                groups.setdefault(seg, []).append(f"{relname}:{node.name}")
    return groups


def _duplicates(groups: dict) -> dict:
    return {seg: locs for seg, locs in groups.items() if len(locs) > 1}


def _real_tests_sources() -> dict:
    return {
        str(p.relative_to(REPO_ROOT)): p.read_text(encoding="utf-8")
        for p in sorted(TESTS_DIR.glob("*.py"))
        if p.name not in EXCLUDED_FILES
    }


class NoDuplicateSetUpBodiesTest(unittest.TestCase):

    def test_ac1_no_byte_identical_setup_bodies_across_files(self):
        """Ни один `setUp`-метод в `tests/*.py` (кроме
        `test_invariants.py`) не байтово совпадает с телом `setUp` в
        другом классе/файле (включая классы `tests/sandbox.py`).

        Ловит мутацию: разработчик добавляет ещё одну копию уже
        существующего тела `setUp` в новый файл вместо наследования от
        общего базового класса `tests/sandbox.py` — новая копия образует
        группу размером ≥ 2 (или пополняет уже пойманную), и
        `assertEqual({}, ...)` красит тест по имени этого файла.
        """
        dups = _duplicates(_collect_setup_bodies(_real_tests_sources()))
        readable = {locs[0]: locs for locs in dups.values()}
        self.assertEqual(
            {}, readable,
            f"найдены байтово идентичные тела setUp в разных "
            f"файлах/классах tests/ (кроме test_invariants.py): "
            f"{list(dups.values())}")

    def test_ac1_synthetic_duplicate_setup_bodies_are_detected(self):
        """Сканер `_collect_setup_bodies` ловит подставной дубль тела
        `setUp` между двумя синтетическими модулями и НЕ путает его с
        двумя РАЗНЫМИ телами.

        Ловит мутацию: сравнение по ошибке нормализует пробелы/докстроки
        или сравнивает только сигнатуру (`def setUp(self):`), из-за чего
        разные по факту тела считались бы «одинаковыми», либо байтово
        одинаковые тела считались бы «разными» — оба конца проверяются
        раздельно ниже.
        """
        dirty_a = "class A(TmpRootTest):\n    def setUp(self):\n        super().setUp()\n        self.x = 1\n"
        dirty_b = "class B(TmpRootTest):\n    def setUp(self):\n        super().setUp()\n        self.x = 1\n"
        clean_c = "class C(TmpRootTest):\n    def setUp(self):\n        super().setUp()\n        self.x = 2\n"

        dups = _duplicates(_collect_setup_bodies({
            "synthetic_a.py": dirty_a,
            "synthetic_b.py": dirty_b,
            "synthetic_c.py": clean_c,
        }))

        self.assertEqual(1, len(dups), dups)
        (locs,) = dups.values()
        self.assertEqual(
            {"synthetic_a.py:A", "synthetic_b.py:B"}, set(locs))


class NoDuplicateModuleHelperBodiesTest(unittest.TestCase):

    def test_ac1_no_byte_identical_module_helper_functions_across_files(self):
        """Ни одна функция верхнего уровня модуля `tests/*.py` (кроме
        `test_invariants.py`) не байтово совпадает с одноимённой (или
        любой другой) функцией верхнего уровня в другом файле.

        Ловит мутацию: `event`/`fake_git_config`-подобный помощник
        копируется в третий файл вместо импорта из `tests/sandbox.py` —
        новая копия побайтно совпадает с уже существующей, группа растёт
        до ≥ 2, и `assertEqual({}, ...)` красит тест.
        """
        dups = _duplicates(_collect_module_helper_bodies(_real_tests_sources()))
        readable = {locs[0]: locs for locs in dups.values()}
        self.assertEqual(
            {}, readable,
            f"найдены байтово идентичные вспомогательные функции в "
            f"разных файлах tests/ (кроме test_invariants.py): "
            f"{list(dups.values())}")

    def test_ac1_synthetic_duplicate_helper_functions_are_detected(self):
        """Сканер `_collect_module_helper_bodies` ловит подставной дубль
        функции верхнего уровня между двумя синтетическими модулями и не
        путает его с функцией другого имени/тела.

        Ловит мутацию: сравнение сканирует и вложенные функции (методы
        класса) вместо только функций верхнего уровня модуля — тогда
        обычный метод класса дал бы ложное совпадение/несовпадение
        помимо цели проверки.
        """
        dirty_a = 'def helper():\n    return "same"\n'
        dirty_b = 'def helper():\n    return "same"\n'
        clean_c = 'def helper():\n    return "different"\n'

        dups = _duplicates(_collect_module_helper_bodies({
            "synthetic_a.py": dirty_a,
            "synthetic_b.py": dirty_b,
            "synthetic_c.py": clean_c,
        }))

        self.assertEqual(1, len(dups), dups)
        (locs,) = dups.values()
        self.assertEqual(
            {"synthetic_a.py:helper", "synthetic_b.py:helper"}, set(locs))


if __name__ == "__main__":
    unittest.main()
