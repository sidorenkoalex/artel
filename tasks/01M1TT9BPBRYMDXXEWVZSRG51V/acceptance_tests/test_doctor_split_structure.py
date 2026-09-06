"""Приёмочные тесты задачи 01M1TT9BPBRYMDXXEWVZSRG51V: структурная часть
разреза `orchestrator/doctor.py` на пакет (AC-1, AC-3, AC-9). AC-8/AC-12 —
пометки в самом низу файла.

Красен до реализации: `orchestrator/doctor.py` сегодня — плоский файл
(`orchestrator/doctor` как каталог не существует), поэтому все три теста
падают на самой первой структурной проверке (`DOCTOR_PKG_DIR.is_dir()`)
ещё до того, как дойти до сверки имён/разделителей/логики — это и есть
единственная причина красноты, не опечатка теста.

Стаб для самопроверки (SPEC-обязательный прогон перед сдачей, решение
Оператора 03.09): каталог `orchestrator/doctor/` с `__init__.py`,
ре-экспортирующим ВСЕ имена из скопированного `orchestrator/doctor.py`
(`from ._orig import *`-подобный приём) плюс 17 файлов-пустышек
`section_01.py`..`section_17.py`, каждый из которых содержит РОВНО один
из 17 комментариев-разделителей (переписанных дословно) — прогнан
локально, все три теста дали PASS, стаб удалён без коммита.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import doctor  # noqa: E402

from _sandbox import (ALL_REQUIRED_FACADE_NAMES, DOCTOR_PKG_DIR,  # noqa: E402
                     FUNCTION_LOGIC_HASHES, SECTION_MARKERS, logic_hash,
                     package_py_files)


class PackageExistsAndExportsTest(unittest.TestCase):
    """AC-1: пакет `orchestrator/doctor/` существует и его `__init__.py`
    экспортирует полный перечень публичных имён/коллаборантов/приватных
    помощников, на которые ссылаются tests/orchestrator/scripts."""

    def test_ac1_package_exists_with_init_and_exports_all_collected_names(self):
        """Каталог `orchestrator/doctor/` — пакет с `__init__.py`, и на
        фасаде `orchestrator.doctor` присутствуют все имена из
        ALL_REQUIRED_FACADE_NAMES.

        Ловит мутацию: разработчик оставил `orchestrator/doctor.py` файлом
        (не разрезал) — первая же проверка `is_dir()` красит тест; либо
        разрезал, но забыл прокинуть в `__init__.py` реэкспорт одного из
        коллаборантов/приватных помощников (например, `canary` или
        `_auto_ack_gone`) — `hasattr` находит недостачу.
        """
        self.assertTrue(
            DOCTOR_PKG_DIR.is_dir(),
            f"{DOCTOR_PKG_DIR} должен быть пакетом-каталогом с __init__.py, "
            f"а не файлом doctor.py")
        init_path = DOCTOR_PKG_DIR / "__init__.py"
        self.assertTrue(init_path.is_file(), f"{init_path} отсутствует")

        missing = [n for n in ALL_REQUIRED_FACADE_NAMES if not hasattr(doctor, n)]
        self.assertEqual(
            missing, [],
            f"фасад orchestrator.doctor не экспортирует: {missing}")


class SectionSplitPreservesLogicTest(unittest.TestCase):
    """AC-3: разделы перенесены по границам комментариев-разделителей
    (один раздел — один файл), тело функций не переписано."""

    def test_ac3_sections_map_one_to_one_to_files_and_function_bodies_unchanged(self):
        """Каждый из 17 разделительных комментариев встречается ровно в
        одном файле пакета (не в нескольких, и не по два в одном файле),
        число файлов-разделов (без `__init__.py`) равно числу разделителей,
        а AST каждой перенесённой функции совпадает с деревом, снятым до
        переноса.

        Ловит мутацию: два раздела слиты в один файл (пропадает 1:1),
        либо тело функции подправлено «по пути» (переставлено условие,
        добавлена строка) — оба случая меняют проверяемое здесь свойство
        и красят тест.
        """
        self.assertTrue(
            DOCTOR_PKG_DIR.is_dir(),
            f"{DOCTOR_PKG_DIR} должен быть пакетом-каталогом — раздела ещё нет")

        files = package_py_files()
        self.assertEqual(
            len(files), len(SECTION_MARKERS),
            f"ожидалось {len(SECTION_MARKERS)} файлов-разделов (без "
            f"__init__.py), нашли {len(files)}: {[p.name for p in files]}")

        contents = {p: p.read_text(encoding="utf-8") for p in files}
        owner_by_marker = {}
        for marker in SECTION_MARKERS:
            owners = [p for p, text in contents.items() if marker in text]
            self.assertEqual(
                len(owners), 1,
                f"разделитель {marker!r} должен встретиться ровно в одном "
                f"файле пакета, встретился в {[p.name for p in owners]}")
            owner_by_marker[marker] = owners[0]

        counts = {}
        for p in owner_by_marker.values():
            counts[p] = counts.get(p, 0) + 1
        duplicated = {p.name: c for p, c in counts.items() if c > 1}
        self.assertEqual(
            duplicated, {},
            f"в одном файле пакета более одного раздела: {duplicated}")

        mismatched = [
            name for name, expected in FUNCTION_LOGIC_HASHES.items()
            if logic_hash(getattr(doctor, name)) != expected
        ]
        self.assertEqual(
            mismatched, [],
            f"AST-дерево этих функций изменилось при переносе: {mismatched}")


class NoDirectCollaboratorImportTest(unittest.TestCase):
    """AC-9: ни один файл пакета (кроме `__init__.py`) не импортирует
    `subprocess`/`shutil`/`gitcmd` напрямую — только через фасад."""

    FORBIDDEN_PATTERNS = [
        re.compile(r"^\s*import subprocess\b", re.M),
        re.compile(r"^\s*import shutil\b", re.M),
        re.compile(r"^\s*from orchestrator import gitcmd\b", re.M),
    ]

    def test_ac9_submodules_have_no_direct_collaborator_import(self):
        """Сканирует все `orchestrator/doctor/*.py` кроме `__init__.py` на
        буквальные `import subprocess`, `import shutil`,
        `from orchestrator import gitcmd`.

        Ловит мутацию: вернули прямой `import subprocess` (или `shutil`,
        или `from orchestrator import gitcmd`) в один подмодуль вместо
        ленивого чтения через `doctor.subprocess`/`doctor.shutil`/
        `doctor.gitcmd` — сканер находит совпадение и красит тест.
        """
        self.assertTrue(
            DOCTOR_PKG_DIR.is_dir(),
            f"{DOCTOR_PKG_DIR} должен быть пакетом-каталогом — раздела ещё нет")

        violations = {}
        for p in package_py_files():
            text = p.read_text(encoding="utf-8")
            hits = [pat.pattern for pat in self.FORBIDDEN_PATTERNS
                   if pat.search(text)]
            if hits:
                violations[p.name] = hits
        self.assertEqual(
            violations, {},
            f"прямой импорт коллаборанта в подмодулях пакета: {violations}")


# AC-8: skip — критерий требует прогона ВСЕГО существующего tests/, но
# skill test-authoring этой роли прямо запрещает гонять полный набор
# tests/ в шаге («Полный набор tests/ в шаге не запускай (его гоняет
# CI): только планка по одному файлу и тесты затронутых модулей»,
# решение Оператора 05.09) — юнит-тест, вызывающий здесь полный прогон,
# я не могу ни включить в планку (нечем его провалидировать стабом, не
# нарушив то же правило), ни просто написать «на будущее»: он обязан
# быть исполним прямо сейчас тем же способом, каким гоняются остальные
# тесты планки. Фактическая проверка AC-8 — уже существующий CI-прогон
# полного tests/ на ветке разработчика; частичное покрытие уже даёт
# AC-2/AC-4/AC-5/AC-9/AC-10/AC-11 этой же планки (мокинг `doctor.*`,
# порядок all_checks, отсутствие прямых импортов).
# AC-12: manual — критерий описывает процессное поведение разработчика
# («не гонять и не править планки закрытых задач; при конфликте живой
# планки эскалировать с перечнем имён/задач, а не править планку») — это
# дисциплина исполнителя шага, а не свойство кода или его вывода,
# автоматической проверке не поддаётся. Оператор сверяет это на приёмке
# по PLAN.md/REVIEW.md разработчика (упомянул ли он такие планки и как
# поступил).
