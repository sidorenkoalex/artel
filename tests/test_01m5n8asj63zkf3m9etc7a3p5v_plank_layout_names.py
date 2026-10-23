"""Самодостаточная часть выкладки планки в `orchestrator.plank_layout` и
публичные имена `orchestrator.acceptance` для закрытых имён, которые берут
другие модули пульта.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/plank_layout.py нет (AC-1, AC-2, AC-3 падают на импорте), публичных имён `reported`, `own`, … в acceptance нет (AC-5), вызывающие модули обращаются к закрытым именам acceptance (AC-6).

Закрытые имена читаются только `getattr` по перечню строк: их
существование и тождество объектов — само проверяемое свойство (прежние
имена остаются совместимостью для кода и тестов). Обращения модулей
`orchestrator/` и `scripts/` к закрытым именам ищутся разбором `ast` по
формам импорта критерия; сам разбор сначала сверяется на синтетических
исходниках каждой формы.
"""
import ast
import random
import unittest
from pathlib import Path

import orchestrator
from orchestrator import acceptance

# Прежнее имя в acceptance -> имя в plank_layout (требование 1).
MOVED = {
    "PLANK_LAYOUT_DIR": "PLANK_LAYOUT_DIR",
    "PLANK_LAYOUT_EXCLUDE": "PLANK_LAYOUT_EXCLUDE",
    "LAYOUT_OUTSIDE_NOTE": "LAYOUT_OUTSIDE_NOTE",
    "PLANK_ABSENT_NOTE": "PLANK_ABSENT_NOTE",
    "NO_PLANK_LAYOUT": "NO_PLANK_LAYOUT",
    "LAYOUT_NOT_NORMAL": "LAYOUT_NOT_NORMAL",
    "LAYOUT_ID_NOT_LAST": "LAYOUT_ID_NOT_LAST",
    "LAYOUT_OUTSIDE_WORKDIR": "LAYOUT_OUTSIDE_WORKDIR",
    "LAYOUT_PARENT_NOT_HIDDEN": "LAYOUT_PARENT_NOT_HIDDEN",
    "LAYOUT_PARENT_TRACKED": "LAYOUT_PARENT_TRACKED",
    "_LAYOUT_ID": "_LAYOUT_ID",
    "_inside": "_inside",
    "_layout_mode": "layout_mode",
    "_layout_root": "layout_root",
    "_exclude_layout": "exclude_layout",
    "_exclude_pattern": "exclude_pattern",
    "_drop_layout": "drop_layout",
    "_plank_layout": "plank_layout",
    "_uses_plank_layout": "uses_plank_layout",
    "_layout_parent": "_layout_parent",
    "_drop_component_layout": "drop_component_layout",
    "_PlankPlan": "PlankPlan",
    "_Laid": "Laid",
}
PUBLIC_DEFS = ("exclude_layout", "exclude_pattern", "layout_mode",
               "layout_root", "drop_layout", "plank_layout",
               "uses_plank_layout", "drop_component_layout", "PlankPlan",
               "Laid")
CONSTANTS = ("PLANK_LAYOUT_DIR", "PLANK_LAYOUT_EXCLUDE", "LAYOUT_OUTSIDE_NOTE",
             "PLANK_ABSENT_NOTE", "NO_PLANK_LAYOUT", "LAYOUT_NOT_NORMAL",
             "LAYOUT_ID_NOT_LAST", "LAYOUT_OUTSIDE_WORKDIR",
             "LAYOUT_PARENT_NOT_HIDDEN", "LAYOUT_PARENT_TRACKED")
# Закрытое имя -> публичного двойника быть не должно.
PRIVATE_ONLY = {"_inside": "inside", "_layout_parent": "layout_parent",
                "_LAYOUT_ID": "LAYOUT_ID"}

# Закрытые имена acceptance, которые берут другие модули (требование 4).
CALLED_PRIVATE = ("_reported", "_own", "_full_suite_outcome", "_own_cwd",
                  "_own_target", "_place_command", "_place_env",
                  "_run_in_session", "_report_run",
                  "_report_suite_result_key", "_task_own_profile",
                  "_component_name", "_process_snapshot")
# Константа исключений критерия AC-6; подмен имён CALLED_PRIVATE тестами на
# базе ветки не найдено — исключений требования 5 нет.
EXCEPTIONS = frozenset({"_last_full_suite_metrics"})

ACCEPTANCE = ("orchestrator", "acceptance")
DOCTOR = ("orchestrator", "doctor")
PACKAGE = ("orchestrator",)


def _plank_layout_module():
    import importlib
    return importlib.import_module("orchestrator.plank_layout")


def _is_private(name: str) -> bool:
    return name.startswith("_") and not (
        name.startswith("__") and name.endswith("__"))


def module_package(rel: Path) -> tuple:
    """Пакет файла `rel` (путь от корня репозитория) — точки отсчёта
    относительного импорта: `orchestrator/x.py` -> ("orchestrator",),
    `orchestrator/doctor/__init__.py` -> ("orchestrator", "doctor")."""
    return tuple(rel.parent.parts)


def import_target(node: ast.ImportFrom, package: tuple) -> tuple | None:
    """Полный путь модуля `from <…> import` с разрешением относительного
    импорта по пакету файла; `None` — уровень выше корня."""
    if node.level:
        if node.level - 1 > len(package):
            return None
        base = package[:len(package) - (node.level - 1)]
    else:
        base = ()
    return base + (tuple(node.module.split(".")) if node.module else ())


def private_accesses(source: str, rel: Path) -> list[tuple[int, str]]:
    """(строка, имя) обращений к закрытому имени модуля
    `orchestrator.acceptance` в исходнике файла `rel`: атрибут имени,
    привязанного к модулю импортом (абсолютным или относительным), атрибут
    `<doctor>.acceptance`/`orchestrator.acceptance`/
    `orchestrator.doctor.acceptance`, и импорт закрытого имени
    `from <orchestrator.acceptance> import _x`."""
    tree = ast.parse(source)
    package = module_package(rel)
    acc, doc, pkg = set(), set(), set()
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                full = tuple(alias.name.split("."))
                if alias.asname:
                    {ACCEPTANCE: acc, DOCTOR: doc, PACKAGE: pkg}.get(
                        full, set()).add(alias.asname)
                elif full[0] == "orchestrator":
                    pkg.add("orchestrator")
        elif isinstance(node, ast.ImportFrom):
            target = import_target(node, package)
            if target is None:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                full = target + (alias.name,)
                if full == ACCEPTANCE or (target == DOCTOR
                                          and alias.name == "acceptance"):
                    acc.add(local)
                elif full == DOCTOR:
                    doc.add(local)
                if target == ACCEPTANCE and _is_private(alias.name):
                    found.append((node.lineno, alias.name))

    def is_pkg(expr):
        return isinstance(expr, ast.Name) and expr.id in pkg

    def is_doc(expr):
        if isinstance(expr, ast.Name):
            return expr.id in doc
        return (isinstance(expr, ast.Attribute) and expr.attr == "doctor"
                and is_pkg(expr.value))

    def is_acc(expr):
        if isinstance(expr, ast.Name):
            return expr.id in acc
        return (isinstance(expr, ast.Attribute) and expr.attr == "acceptance"
                and (is_pkg(expr.value) or is_doc(expr.value)))

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and _is_private(node.attr) \
                and is_acc(node.value):
            found.append((node.lineno, node.attr))
    return found


class PlankLayoutModuleTest(unittest.TestCase):
    """Состав и независимость модуля `orchestrator.plank_layout`."""

    def test_ac1_plank_layout_defines_public_constants_and_private_names(self):
        """В модуле есть публичные функции, классы и константы выкладки; закрытые три имени — без публичных двойников.

        Каждое из десяти публичных имён функций и классов определено в
        `orchestrator.plank_layout` (`__module__` — он сам), каждая из десяти
        констант — строка в нём; `_inside`, `_layout_parent`, `_LAYOUT_ID`
        есть, `inside`, `layout_parent`, `LAYOUT_ID` — нет.

        Ловит мутацию: функция перенесена под прежним закрытым именем
        (`_exclude_layout` без `exclude_layout`) — публичного имени нет;
        публичное имя — реэкспорт из acceptance, а не определение здесь —
        `__module__` равен `orchestrator.acceptance`; `_inside` получил
        публичный двойник `inside` — имя есть в модуле.
        """
        layout = _plank_layout_module()
        for name in PUBLIC_DEFS:
            with self.subTest(name=name):
                self.assertTrue(hasattr(layout, name), f"нет {name}")
                self.assertEqual(getattr(layout, name).__module__,
                                 "orchestrator.plank_layout", name)
        for name in CONSTANTS:
            with self.subTest(name=name):
                self.assertIsInstance(getattr(layout, name, None), str, name)
        for private, public in PRIVATE_ONLY.items():
            with self.subTest(name=private):
                self.assertTrue(hasattr(layout, private), f"нет {private}")
                self.assertFalse(hasattr(layout, public),
                                 f"у {private} публичный двойник {public}")
        for name in ("_inside", "_layout_parent"):
            self.assertEqual(getattr(layout, name).__module__,
                             "orchestrator.plank_layout", name)

    def test_ac2_plank_layout_does_not_import_acceptance(self):
        """Разбор `ast` файла модуля не находит импорта `acceptance` ни наверху, ни внутри функций.

        Проверяются все узлы `Import`/`ImportFrom` (в том числе ленивые в
        теле функций): ни сегмент пути модуля, ни импортируемое имя не
        равны `acceptance`; вызова `import_module`/`__import__` со строкой,
        содержащей `acceptance`, нет.

        Ловит мутацию: перенесённая функция зовёт `gitcmd` через ленивый
        `from . import acceptance` внутри тела или модуль берёт константу
        `from .acceptance import FULL_SUITE_GREEN` — узел импорта находится.
        """
        layout = _plank_layout_module()
        path = Path(layout.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "acceptance" in alias.name.split("."):
                        hits.append((node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if "acceptance" in (node.module or "").split(".") or any(
                        alias.name == "acceptance" for alias in node.names):
                    hits.append((node.lineno, node.module))
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else \
                    getattr(func, "id", "")
                if name in ("import_module", "__import__") and any(
                        isinstance(arg, ast.Constant)
                        and "acceptance" in str(arg.value)
                        for arg in node.args):
                    hits.append((node.lineno, name))
        self.assertEqual(hits, [], f"{path}: импорт acceptance")


class AcceptanceNamesTest(unittest.TestCase):
    """Прежние и публичные имена модуля `orchestrator.acceptance`."""

    def test_ac3_old_acceptance_names_are_plank_layout_objects(self):
        """Каждое прежнее имя перенесённой части в acceptance — тот же объект, что имя plank_layout.

        Перебор всего списка требования 1: функции, классы, константы и
        закрытые `_inside`, `_layout_parent`, `_LAYOUT_ID`; сверка `is`.

        Ловит мутацию: в acceptance оставлена прежняя копия функции рядом с
        перенесённой (`def _exclude_layout` не заменён реэкспортом) —
        объекты разные; константа переопределена тем же текстом заново —
        у строки, собранной f-строкой (`PLANK_LAYOUT_EXCLUDE`), другой
        объект; прежнее имя удалено — `getattr` не находит его.
        """
        layout = _plank_layout_module()
        for old, new in MOVED.items():
            with self.subTest(old=old, new=new):
                self.assertTrue(hasattr(acceptance, old),
                                f"acceptance.{old} нет")
                self.assertIs(getattr(acceptance, old), getattr(layout, new),
                              f"acceptance.{old} не plank_layout.{new}")

    def test_ac5_public_twins_of_called_private_names(self):
        """У каждого из тринадцати закрытых имён — публичный двойник без подчёркивания, тот же объект.

        Закрытое имя по-прежнему есть; публичное — `name.lstrip("_")`;
        `getattr(…, публичное) is getattr(…, закрытое)`. Публичного имени
        `last_full_suite_metrics` в модуле нет.

        Ловит мутацию: публичное имя объявлено обёрткой
        (`def reported(c): return _reported(c)`) — объекты разные; закрытое
        имя переименовано вместо добавления двойника — закрытого нет;
        одно имя списка пропущено — публичного нет; двойник заведён и
        изменяемой `_last_full_suite_metrics` — имя
        `last_full_suite_metrics` есть.
        """
        for private in CALLED_PRIVATE:
            public = private.lstrip("_")
            with self.subTest(private=private, public=public):
                self.assertTrue(hasattr(acceptance, private),
                                f"закрытого {private} нет")
                self.assertTrue(hasattr(acceptance, public),
                                f"публичного {public} нет")
                self.assertIs(getattr(acceptance, public),
                              getattr(acceptance, private),
                              f"{public} не тот же объект, что {private}")
        self.assertTrue(hasattr(acceptance, "_last_full_suite_metrics"))
        self.assertFalse(hasattr(acceptance, "last_full_suite_metrics"),
                         "у _last_full_suite_metrics публичный двойник")


class PrivateAccessScanTest(unittest.TestCase):
    """Обращения модулей пульта к закрытым именам `orchestrator.acceptance`."""

    # (путь файла, исходник, ожидаемые имена) — каждая форма критерия AC-6
    # и формы, которые не считаются.
    SYNTHETIC = (
        ("orchestrator/x.py", "from orchestrator import acceptance\n"
         "acceptance.{n}()\n", {"{n}"}),
        ("orchestrator/x.py", "import orchestrator.acceptance\n"
         "orchestrator.acceptance.{n}()\n", {"{n}"}),
        ("orchestrator/x.py", "import orchestrator.acceptance as acc\n"
         "acc.{n}()\n", {"{n}"}),
        ("orchestrator/x.py", "def f():\n    from . import acceptance as a\n"
         "    return a.{n}\n", {"{n}"}),
        ("orchestrator/advance_gates/x.py", "from .. import (config,\n"
         "    acceptance)\nacceptance.{n}(1)\n", {"{n}"}),
        ("orchestrator/doctor/x.py", "from .. import acceptance\n"
         "acceptance.{n}\n", {"{n}"}),
        ("orchestrator/doctor/x.py", "from orchestrator import doctor\n"
         "doctor.acceptance.{n}()\n", {"{n}"}),
        ("orchestrator/x.py", "from . import doctor\n"
         "doctor.acceptance.{n}()\n", {"{n}"}),
        ("orchestrator/x.py", "from .acceptance import {n}\n", {"{n}"}),
        ("orchestrator/x.py", "from . import acceptance\n"
         "acceptance._last_full_suite_metrics = None\n",
         {"_last_full_suite_metrics"}),
        # Не считаются: другой модуль advance_gates.acceptance, публичное
        # имя, dunder, однофамилец без импорта.
        ("orchestrator/advance_gates/x.py", "from . import acceptance\n"
         "acceptance.{n}()\n", set()),
        ("orchestrator/advance_gates/x.py", "from .acceptance import {n}\n",
         set()),
        ("orchestrator/x.py", "from .advance_gates import acceptance as g\n"
         "g.{n}()\n", set()),
        ("orchestrator/x.py", "from . import acceptance\n"
         "acceptance.reported(1)\nacceptance.__file__\n", set()),
        ("orchestrator/x.py", "acceptance = object()\nacceptance.{n}\n",
         set()),
    )

    def setUp(self):
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def test_ac6_no_pult_module_reaches_private_acceptance_names(self):
        """Ни один модуль `orchestrator/` и `scripts/` не берёт закрытое имя orchestrator.acceptance, кроме исключений.

        Сначала разбор сверяется на синтетических исходниках каждой формы
        импорта критерия (абсолютной, относительной от пути файла, через
        пакет `doctor`) со случайным закрытым именем, и на формах, которые
        не считаются (`advance_gates.acceptance`, публичное имя, dunder).
        Затем — все `*.py` под `orchestrator/` и `scripts/` репозитория,
        кроме самого `orchestrator/acceptance.py`: обращений к закрытым
        именам вне `EXCEPTIONS` нет.

        Ловит мутацию: вызывающий модуль оставлен на закрытом имени
        (`acceptance._reported(command)` в `suite_run.py`,
        `doctor.acceptance._process_snapshot()` в `doctor/machine_load.py`,
        `acceptance._report_run` в `advance_gates/two_sided.py`) — разбор
        находит обращение с файлом и строкой.
        """
        for index, (rel, template, want) in enumerate(self.SYNTHETIC):
            name = "_" + "".join(self.rng.choices("abcdefghij", k=6))
            source = template.replace("{n}", name)
            expected = {w.replace("{n}", name) for w in want}
            with self.subTest(case=index, seed=self.seed):
                got = {n for _line, n in private_accesses(source, Path(rel))}
                self.assertEqual(got, expected,
                                 f"зерно {self.seed}; {rel}:\n{source}")

        root = Path(orchestrator.__file__).resolve().parent.parent
        own = Path(acceptance.__file__).resolve()
        hits = []
        scanned = 0
        for folder in ("orchestrator", "scripts"):
            for path in sorted((root / folder).rglob("*.py")):
                if "__pycache__" in path.parts or path.resolve() == own:
                    continue
                scanned += 1
                rel = path.relative_to(root)
                for line, name in private_accesses(
                        path.read_text(encoding="utf-8"), rel):
                    if name not in EXCEPTIONS:
                        hits.append(f"{rel}:{line}: acceptance.{name}")
        self.assertGreater(scanned, 0, "модули пульта не найдены")
        self.assertEqual(hits, [], "обращения к закрытым именам acceptance:\n"
                         + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
