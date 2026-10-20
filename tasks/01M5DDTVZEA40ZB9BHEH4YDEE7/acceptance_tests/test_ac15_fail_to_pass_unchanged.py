"""AC-15: гейт FAIL_TO_PASS не меняется; правка `tests/test_component_report_gates.py` — только подмена нового шага в списке подмен помощника `merge`.

Группа: разовый
Зелёный с рождения: на базе ветки задачи `orchestrator/advance_gates/tests_writing.py` и `tests/test_component_report_gates.py` не тронуты, а `_check_failure_kind` даёт прежние виды — тесты держат, чтобы правка задачи их не изменила (классификатор берётся двусторонним прогоном отложенным импортом, без переноса).

Дифф задачи — помощник пульта `_pult.py` (`changed_paths`, `DIFF_BASE`,
`CODE_ROOT`): та же база, что у гейта зон. Тексты файла теста на базе и в
голове — `git show` в рабочей копии кода; сравниваются деревья разбора
`ast`, не строки (переносы и пробелы правки не различают).

Провалидировано временным стабом реализации (удалён, не закоммичен): стаб
не трогал `tests_writing.py`, двусторонний прогон звал `_check_failure_kind`
отложенным импортом — все методы файла зелёные. Сверка файла теста
провалидирована на синтетических текстах (функции `split`/`patches_list`
этого файла): добавленная подмена в `merge` — проходит; правка утверждения
другого метода и удаление прежней подмены — отказ.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

from orchestrator import project_profile  # noqa: E402
from orchestrator.advance_gates import tests_writing  # noqa: E402
from orchestrator.reporters import outcome  # noqa: E402

FAIL_TO_PASS_MODULE = "orchestrator/advance_gates/tests_writing.py"
GATES_TEST = "tests/test_component_report_gates.py"
HELPER_CLASS = "ChecksLocalFromRecordTest"
HELPER = "merge"


def profile(report: str) -> project_profile.Profile:
    return project_profile.Profile(
        command=("./run",), long_lived_dir="", long_lived_name="",
        weakening_scope=(), mutation_claim_scope=(), report=report,
        component="web", project="p", from_components=True,
        failure_errors=("AssertionError",))


def case(result: str, failure: str = "", retries: int = 0, fails: bool = False,
         mode: str = "run", skip_reason: str = "") -> outcome.CaseResult:
    return outcome.CaseResult("web:t.py::test_x", result, failure, skip_reason,
                              0.1, mode, fails, retries)


def show(rev: str, rel: str) -> str | None:
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show", f"{rev}:{rel}"],
                         capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else None


def patch_call(node) -> bool:
    """Элемент списка подмен — вызов `mock.patch.object(…)`/`mock.patch(…)`."""
    if not isinstance(node, ast.Call):
        return False
    name = ast.unparse(node.func)
    return name in ("mock.patch.object", "mock.patch")


class _Split(ast.NodeTransformer):
    """Вынимает помощник `merge` класса `HELPER_CLASS` из модуля; имена
    импорта `from orchestrator… import` — множеством, отдельно."""

    def __init__(self):
        self.helper = None
        self.imports: dict = {}

    def visit_ClassDef(self, node):
        if node.name == HELPER_CLASS:
            kept = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == HELPER:
                    self.helper = item
                else:
                    kept.append(item)
            node.body = kept
        return node

    def visit_ImportFrom(self, node):
        if (node.module or "").startswith("orchestrator"):
            self.imports.setdefault(node.module, set()).update(
                a.name for a in node.names)
            return None
        return node


def split(text: str) -> tuple:
    tree = ast.parse(text)
    splitter = _Split()
    tree = splitter.visit(tree)
    return ast.dump(tree), splitter.helper, splitter.imports


def patches_list(helper) -> tuple:
    """(элементы списка `patches = [...]`, тело помощника без этого
    присваивания) — оба дампами `ast`."""
    elements, rest = None, []
    for stmt in helper.body:
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == "patches"
                and isinstance(stmt.value, ast.List)):
            elements = list(stmt.value.elts)
        else:
            rest.append(ast.dump(stmt))
    return elements, rest


class Ac15FailToPassUnchangedTest(unittest.TestCase):

    def test_ac15_check_failure_kind_keeps_its_kinds(self):
        """Классификатор провала проверки даёт прежние виды на таблице записей `junit-xml` и `pult-vitest`.

        Сценарий: записи с повтором, `failed` с «assert …», с именем из
        списка и вне его, без имени, с `fails`, `error`, `skipped`,
        `passed` — для каждого вида отчёта; итог `_check_failure_kind`
        равен прежнему виду (пусто — провал проверки).

        Ловит мутацию: перенос классификатора в `two_sided.py` с правкой
        правила — у `junit-xml` «assert …» перестаёт быть проверкой либо
        повтор и `fails` перестают называться видом.
        """
        junit, vitest = profile("junit-xml"), profile("pult-vitest")
        table = (
            (junit, case("passed", retries=2), f"{outcome.RETRY_NOTE} внутри прогона: 2"),
            (junit, case("failed", "assert 1 == 2"), ""),
            (junit, case("failed", "AssertionError: boom"), ""),
            (junit, case("failed", "ValueError: boom"), "имя ошибки ValueError: boom"),
            (junit, case("failed", ""), "имя ошибки без имени"),
            (junit, case("failed", "assert x", fails=True), "fails (тест помечен it.fails)"),
            (junit, case("error", "TypeError"), "ошибка TypeError"),
            (junit, case("skipped", mode="", skip_reason="r"), "пропуск (r)"),
            (junit, case("passed"), "прошёл"),
            (vitest, case("failed", "AssertionError"), ""),
            (vitest, case("failed", "AssertionError: boom"), "имя ошибки AssertionError: boom"),
            (vitest, case("failed", "assert 1 == 2"), "имя ошибки assert 1 == 2"),
            (vitest, case("error", "timeout: x"), "таймаут теста (timeout: x)"),
            (vitest, case("passed", retries=1), f"{outcome.RETRY_NOTE} внутри прогона: 1"),
        )
        for prof, record, wanted in table:
            with self.subTest(report=prof.report, record=record):
                self.assertEqual(tests_writing._check_failure_kind(record, prof), wanted)

    def test_ac15_fail_to_pass_module_not_changed(self):
        """Модуль гейта FAIL_TO_PASS (`tests_writing.py`) в диффе задачи не тронут: классификатор не перенесён, вызывающий прежний.

        Ловит мутацию: `_check_failure_kind` перенесён из `tests_writing.py`
        в `two_sided.py` (или правлен его вызывающий) — путь модуля в
        диффе задачи.
        """
        self.assertNotIn(FAIL_TO_PASS_MODULE, changed_paths())

    def test_ac15_component_report_gates_only_new_patch_in_merge_helper(self):
        """В `tests/test_component_report_gates.py` правка — только новые подмены в списке `patches` помощника `merge`; утверждения и прочий текст файла прежние.

        Сценарий: тексты файла на базе диффа задачи и в голове рабочей
        копии кода. Файл не тронут — критерий выполнен. Тронут: модуль без
        помощника `merge` совпадает деревом разбора (имена импорта
        `from orchestrator… import` могут только добавиться); в помощнике
        тело вне списка `patches` прежнее; прежние элементы списка — на
        месте и в прежнем порядке, новые — только вызовы
        `mock.patch.object(…)`/`mock.patch(…)`.

        Ловит мутацию: правка утверждения любого метода файла (или
        удаление прежней подмены) — дерево модуля либо список подмен
        отличается от базы не только новой подменой.
        """
        if GATES_TEST not in changed_paths():
            return
        before, after = show(DIFF_BASE, GATES_TEST), show("HEAD", GATES_TEST)
        self.assertIsNotNone(before, f"{GATES_TEST} нет на базе {DIFF_BASE}")
        self.assertIsNotNone(after, f"{GATES_TEST} нет в голове")
        base_dump, base_helper, base_imports = split(before)
        head_dump, head_helper, head_imports = split(after)
        self.assertEqual(head_dump, base_dump,
                         "файл правлен вне помощника merge и импортов orchestrator")
        for module, names in base_imports.items():
            self.assertTrue(names <= head_imports.get(module, set()),
                            f"из импорта {module} убраны имена")
        self.assertIsNotNone(base_helper, "помощника merge на базе нет")
        self.assertIsNotNone(head_helper, "помощник merge удалён")
        self.assertEqual(ast.dump(head_helper.args), ast.dump(base_helper.args))
        base_items, base_rest = patches_list(base_helper)
        head_items, head_rest = patches_list(head_helper)
        self.assertIsNotNone(head_items, "списка patches в помощнике нет")
        self.assertEqual(head_rest, base_rest, "тело помощника правлено вне списка patches")
        old = [ast.dump(e) for e in base_items]
        kept = [ast.dump(e) for e in head_items if ast.dump(e) in old]
        self.assertEqual(kept, old, "прежние подмены убраны или переставлены")
        for element in head_items:
            if ast.dump(element) not in old:
                self.assertTrue(patch_call(element),
                                f"новый элемент не подмена: {ast.unparse(element)}")


if __name__ == "__main__":
    unittest.main()
