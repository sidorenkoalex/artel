"""AC-1: исходный текст помощника и открытый набор выложенного `_pult.py`.

`orchestrator/plank_helper.py` импортирует только стандартную библиотеку и
ничего из пакета `orchestrator`; выложенный `_pult.py` даёт `TASK_ID`,
`CODE_ROOT`, базу диффа и её источник константами, функции
`artifact_text`, `branch_diff`, `changed_paths`, `apply_check`, а его
докстринг называет правило `changed_paths()`.

Группа: разовый
Красен до реализации: модуля `orchestrator/plank_helper.py` нет, а выкладка планки не кладёт `_pult.py` — файл не найден.
"""
import ast
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _scenario import TASK, PlankHelperSandbox, constant_values  # noqa: E402

import orchestrator  # noqa: E402

IMPORT_CALLS = ("__import__", "import_module", "importlib.import_module")


def _dotted(node) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def foreign_imports(source: str) -> list[str]:
    """Импорты текста `source`, не являющиеся стандартной библиотекой, и
    любое обращение к пакету `orchestrator` (`import`, `from … import`,
    относительный импорт, `__import__`/`importlib.import_module`)."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top == "orchestrator" or top not in sys.stdlib_module_names:
                    found.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            if node.level or top == "orchestrator" \
                    or top not in sys.stdlib_module_names:
                found.append(f"from {'.' * node.level}{module} import …")
        elif isinstance(node, ast.Call) and _dotted(node.func) in IMPORT_CALLS:
            for arg in node.args[:1]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                        and arg.value.split(".")[0] == "orchestrator":
                    found.append(f"{_dotted(node.func)}({arg.value!r})")
    return found


class HelperSourceImportsTest(unittest.TestCase):

    def test_ac1_plank_helper_module_imports_stdlib_only(self):
        """`orchestrator/plank_helper.py` есть и импортирует только stdlib.

        Сценарий: исходный текст модуля разбирается AST; каждый импорт —
        модуль стандартной библиотеки, ни одного обращения к `orchestrator`
        (ни прямого, ни относительного, ни через `importlib`).

        Ловит мутацию: помощник берёт `from orchestrator import gitcmd`
        (или `from . import config`) ради готовых примитивов — разбор
        называет этот импорт."""
        path = Path(orchestrator.__file__).resolve().parent / "plank_helper.py"
        self.assertTrue(path.is_file(), f"{path} нет")

        self.assertEqual(foreign_imports(path.read_text(encoding="utf-8")), [])


class MaterializedHelperSurfaceTest(PlankHelperSandbox):

    def setUp(self):
        super().setUp()
        self.helper = self.materialize()

    def test_ac1_materialized_helper_imports_stdlib_only(self):
        """Выложенный `_pult.py` тоже импортирует только stdlib.

        Ловит мутацию: подстановка значений при выкладке дописывает в
        текст импорт пакета `orchestrator` (например, для `config.
        MAIN_BRANCH`) — разбор выложенного файла его называет."""
        source = self.helper_path.read_text(encoding="utf-8")

        self.assertEqual(foreign_imports(source), [])

    def test_ac1_constants_name_task_code_root_base_and_source(self):
        """Константы помощника: id задачи, корень рабочей копии, база и источник.

        Сценарий: выкладка в рабочую копию кода задачи песочницы;
        `TASK_ID` — id задачи, `CODE_ROOT` — корень этой рабочей копии,
        среди открытых констант есть база диффа и источник базы — те же
        значения, что `gitcmd.diff_base`/`diff_base_source` ветки задачи.

        Ловит мутацию: `CODE_ROOT` подставляется корнем пульта
        (`config.ROOT`) вместо рабочей копии выкладки, либо база/источник
        не подставлены (остаются заглушкой шаблона) — сравнение
        расходится."""
        self.assertEqual(getattr(self.helper, "TASK_ID", None), TASK)
        self.assertTrue(hasattr(self.helper, "CODE_ROOT"))
        self.assertEqual(Path(self.helper.CODE_ROOT).resolve(), self.wt.resolve())
        values = constant_values(self.helper)
        self.assertIn(self.expected_base(), values)
        self.assertIn(self.expected_base_source(), values)

    def test_ac1_four_functions_with_reverse_flag(self):
        """Функции `artifact_text`, `branch_diff`, `changed_paths`, `apply_check`.

        Сценарий: все четыре — вызываемые объекты выложенного модуля;
        у `apply_check` есть параметр `reverse` со значением по умолчанию
        `False`.

        Ловит мутацию: функция переименована (`artifact`, `diff`) или
        обратная проверка вынесена в отдельную функцию без `reverse` —
        имени/параметра нет."""
        missing = [name for name in ("artifact_text", "branch_diff",
                                     "changed_paths", "apply_check")
                   if not callable(getattr(self.helper, name, None))]
        self.assertEqual(missing, [], "функций нет в выложенном помощнике")
        params = inspect.signature(self.helper.apply_check).parameters
        self.assertIn("reverse", params)
        self.assertIs(params["reverse"].default, False)

    def test_ac1_docstring_names_changed_paths_rule(self):
        """Докстринг помощника называет правило `changed_paths()`.

        Сценарий: в докстринге выложенного модуля (или `changed_paths`)
        названы три части правила — неотслеживаемые файлы включены,
        `tasks/<id>/` исключён, незакоммиченные правки отслеживаемых файлов
        не включены.

        Ловит мутацию: правило не записано (докстринг только «список путей
        задачи») — нет ни слова о неотслеживаемых и незакоммиченных."""
        doc = ((self.helper.__doc__ or "") + "\n"
               + (getattr(self.helper.changed_paths, "__doc__", "") or "")).lower()

        self.assertIn("неотслеживаем", doc)
        self.assertIn("tasks/", doc)
        self.assertIn("незакоммич", doc)


if __name__ == "__main__":
    unittest.main()
