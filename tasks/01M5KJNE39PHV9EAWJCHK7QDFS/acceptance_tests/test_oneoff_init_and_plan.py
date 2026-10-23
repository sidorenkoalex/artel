"""Факты задачи: правка tests/__init__.py и замеры в PLAN.md.

Группа: разовый
Красен до реализации: на базе tests/__init__.py пуст и не тронут веткой, а PLAN.md задачи ещё нет — оба теста падают на отсутствии правки и плана.

Свойство проводки (`import tests` зовёт `prefer_direct_git(os.environ)`)
держит долгоживущий файл задачи в `tests/`; здесь — только факт этой
ветки: в `tests/__init__.py` нет другой правки, кроме вызова, и PLAN.md
(ссылка документов, через `artifact_text` помощника пульта) несёт замеры.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text, branch_diff  # noqa: E402

INIT = "tests/__init__.py"
ALLOWED_IMPORT_NAMES = {"prefer_direct_git", "direct_git", "environ"}


def file_diff(diff: str, rel: str) -> str:
    """Участок `diff` одного файла `rel` (от `diff --git` до следующего)."""
    for part in re.split(r"(?m)^(?=diff --git )", diff):
        if part.startswith(f"diff --git a/{rel} b/{rel}"):
            return part
    return ""


def is_environ(node) -> bool:
    """`os.environ` (или `environ`, импортированный из `os`)."""
    if isinstance(node, ast.Attribute):
        return node.attr == "environ" and isinstance(node.value, ast.Name)
    return isinstance(node, ast.Name) and node.id == "environ"


def foreign_statements(tree: ast.Module) -> list[str]:
    """Операторы модуля, не относящиеся к вызову `prefer_direct_git`."""
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(
            getattr(body[0], "value", None), ast.Constant):
        body = body[1:]  # докстринг модуля
    bad = []
    for node in body:
        text = ast.unparse(node)
        if isinstance(node, ast.Import):
            if all(a.name in ("os", "tests.direct_git") for a in node.names):
                continue
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = {a.name for a in node.names}
            if module in ("os",) and names <= {"environ"}:
                continue
            if module in ("tests.direct_git", "direct_git", "tests", "") and \
                    names <= ALLOWED_IMPORT_NAMES:
                continue
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if (len(targets) == 1 and isinstance(targets[0], ast.Name)
                    and targets[0].id == "DIRECT_GIT_DIR"
                    and isinstance(value, ast.Call)
                    and ast.unparse(value.func).split(".")[-1] == "prefer_direct_git"
                    and len(value.args) == 1 and not value.keywords
                    and is_environ(value.args[0])):
                continue
        elif isinstance(node, ast.Delete):
            if all(isinstance(t, ast.Name) and t.id in ALLOWED_IMPORT_NAMES | {"os"}
                   for t in node.targets):
                continue
        bad.append(text)
    return bad


class Ac6InitOnlyWiringTest(unittest.TestCase):
    def test_ac6_init_has_no_other_change(self):
        """В `tests/__init__.py` ветки — только вызов и его импорты.

        Дифф задачи (`branch_diff`) меняет `tests/__init__.py` без
        удалённых строк; файл рабочей копии, разобранный AST, кроме
        докстринга и комментариев содержит лишь импорт `os`/
        `prefer_direct_git` и присваивание
        `DIRECT_GIT_DIR = prefer_direct_git(os.environ)`.

        Ловит мутацию: в `tests/__init__.py` заодно добавлен посторонний
        код (например, `os.environ.setdefault(...)` или импорт
        `tests.sandbox`) — он попадает в перечень чужих операторов.
        """
        part = file_diff(branch_diff(), INIT)
        self.assertTrue(part, f"дифф задачи не меняет {INIT}")
        removed = [line for line in part.splitlines()
                   if line.startswith("-") and not line.startswith("---")]
        self.assertEqual(removed, [], f"удалённые строки {INIT}: {removed}")
        source = (Path(CODE_ROOT) / INIT).read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertEqual(foreign_statements(tree), [],
                         f"другая правка {INIT}:\n{source}")
        assigns = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
        self.assertEqual(len(assigns), 1, source)


class Ac9PlanMeasurementsTest(unittest.TestCase):
    def test_ac9_plan_has_alternating_measurements_with_load(self):
        """PLAN.md несёт попеременные замеры с загрузкой и счёт git.

        В PLAN.md задачи (ссылка документов) названы
        `Ac10EmptyPriorSetTest` файла `outcome_prior`, файл
        `outcome_components` и ещё один файл `tests/test_*.py`
        (наследник `TmpRootTest`); есть запись загрузки (`uptime`/
        `load average`), слова «база» и
        «ветка», подсчёт запусков git хуком аудита на `subprocess.Popen`.

        Ловит мутацию: PLAN.md без замеров (или без записи загрузки,
        или без счёта хуком аудита) — нужная строка не находится.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов")
        low = plan.lower()
        self.assertIn("test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior", plan)
        self.assertIn("Ac10EmptyPriorSetTest", plan)
        self.assertIn("test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components", plan)
        named = set(re.findall(r"tests/(test_\w+)\.py", plan))
        others = named - {"test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior",
                          "test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components",
                          "test_01m5kjne39phv9eawjchk7qdfs_direct_git"}
        self.assertTrue(others, f"третий файл наследников TmpRootTest не назван: {named}")
        self.assertTrue(re.search(r"uptime|load average", low),
                        "загрузка (uptime) у прогонов не записана")
        self.assertIn("база", low)
        self.assertIn("ветка", low)
        self.assertIn("subprocess.popen", low)
        self.assertTrue("audit" in low or "аудит" in low,
                        "подсчёт хуком аудита не описан")


if __name__ == "__main__":
    unittest.main()
