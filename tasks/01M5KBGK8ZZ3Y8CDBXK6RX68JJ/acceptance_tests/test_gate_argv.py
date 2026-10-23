"""Планка AC-1…AC-6: тест argv гейта полного набора в `tests/test_suite_run.py`.

Группа: разовый
Красен до реализации: в tests/test_suite_run.py метод test_gate_call_argv_unchanged ещё собирает ожидание вызовом acceptance._pytest_command вне подмены, а новых тестов требований 2 и 3 нет.

Предмет планки — сам файл `tests/test_suite_run.py` ветки задачи: его
устройство разбирается `ast`, а поведение методов проверяется их запуском
через `unittest.TestResult` — с подменой `acceptance._pytest_command`
мутантом общей части команды либо с подменой тела
`GateArgvTest.test_gate_call_argv_unchanged` прежним телом метода (копия
ниже, `_old_gate_call_argv_body`).
"""
import ast
import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

ROOT = Path(CODE_ROOT or ".").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import subprocess  # noqa: E402

from orchestrator import acceptance, config  # noqa: E402

SUITE_FILE = ROOT / "tests" / "test_suite_run.py"
GATE_CLASS = "GateArgvTest"
GATE_METHOD = "test_gate_call_argv_unchanged"
FAKE_PY = "/fake/venv/bin/python3"
EXPECTED_LITERAL = (
    '["/fake/venv/bin/python3", "-m", "pytest", "tests", "-p", '
    '"no:cacheprovider", "-p", "timeout", "-o", '
    'f"timeout={stack.PER_TEST_TIMEOUT_SEC}", "-n", '
    'str(config.FULL_SUITE_WORKERS), "-p", "xdist"]')


def _old_gate_call_argv_body(self):
    """Тело метода до задачи: ожидание через `_pytest_command` вне подмены."""
    (self.root / "tests").mkdir()
    done = subprocess.CompletedProcess([], 0, "1 passed in 0.1s", "")
    with mock.patch.object(acceptance.subprocess, "run",
                           return_value=done) as run:
        acceptance.run_full_suite(self.root)
    argv = run.call_args.args[0]
    self.assertEqual(argv, acceptance._pytest_command("tests") + [
        "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"])


def _suite_module():
    return importlib.import_module("tests.test_suite_run")


def _source():
    return SUITE_FILE.read_text(encoding="utf-8")


def _methods(tree):
    """{(класс, метод): узел} всех методов классов модуля."""
    found = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found[(node.name, item.name)] = item
    return found


def _gate_node(tree):
    return _methods(tree).get((GATE_CLASS, GATE_METHOD))


def _run(cls, name):
    result = unittest.TestResult()
    cls(name).run(result)
    return result


def _report(result):
    parts = [f"{test}: {text}" for test, text in
             result.failures + result.errors]
    return "\n".join(parts) or "(нет сообщений)"


def _is_executable_patch(call):
    """Вызов `mock.patch.object(<stack>, "pytest_python_executable",
    return_value="/fake/venv/bin/python3")`."""
    if not isinstance(call, ast.Call):
        return False
    if not ast.unparse(call.func).endswith("patch.object"):
        return False
    if len(call.args) < 2:
        return False
    if ast.unparse(call.args[0]) not in ("acceptance.stack", "stack"):
        return False
    attr = call.args[1]
    if not (isinstance(attr, ast.Constant)
            and attr.value == "pytest_python_executable"):
        return False
    for kw in call.keywords:
        if (kw.arg == "return_value" and isinstance(kw.value, ast.Constant)
                and kw.value.value == FAKE_PY):
            return True
    return False


def _first_element_mutant(first):
    """Мутант `_pytest_command`: первый элемент — `first` в обход
    `stack.pytest_python_executable`."""
    original = acceptance._pytest_command

    def mutated(*args, **kwargs):
        argv = original(*args, **kwargs)
        return [first(), *argv[1:]]
    return mutated


def _drop_timeout_mutant():
    original = acceptance._pytest_command

    def mutated(*args, **kwargs):
        argv = list(original(*args, **kwargs))
        for i in range(len(argv) - 1):
            if argv[i] == "-p" and argv[i + 1] == "timeout":
                del argv[i:i + 2]
                break
        return argv
    return mutated


def _reorder_mutant():
    original = acceptance._pytest_command

    def mutated(*args, **kwargs):
        argv = list(original(*args, **kwargs))
        for i in range(len(argv) - 1):
            if argv[i] == "-p" and argv[i + 1] == "no:cacheprovider":
                pair = argv[i:i + 2]
                del argv[i:i + 2]
                return argv + pair
        return argv
    return mutated


def _interpreter_test_names(module, tree):
    """Новые методы требования 2: запускают гейтовый метод через
    `TestResult` и утверждают `wasSuccessful`."""
    src = _source()
    names = []
    for (cls_name, meth), node in _methods(tree).items():
        if (cls_name, meth) == (GATE_CLASS, GATE_METHOD):
            continue
        if not meth.startswith("test"):
            continue
        text = ast.get_source_segment(src, node) or ""
        if GATE_METHOD in text and "wasSuccessful" in text:
            names.append((cls_name, meth))
    return names


class GateArgvPlankTest(unittest.TestCase):

    def setUp(self):
        self.src = _source()
        self.tree = ast.parse(self.src)
        self.module = _suite_module()

    def test_ac1_single_patch_covers_call_and_literal_expectation(self):
        """Метод гейта подменяет интерпретатор одним патчем и сверяет argv
        со списком-литералом.

        Разбирается тело `GateArgvTest.test_gate_call_argv_unchanged`: нет
        обращения к `_pytest_command`; есть список-литерал ровно из
        критерия; подмена `stack.pytest_python_executable` значением
        `"/fake/venv/bin/python3"` (декоратор либо `with`, в теле которого
        и вызов `acceptance.run_full_suite`, и литерал); `assertEqual`
        сравнивает литерал (или имя, связанное с ним) с argv целиком, без
        среза. Сам метод при этом проходит.

        Ловит мутацию: ожидание оставлено вызовом
        `acceptance._pytest_command("tests") + [...]` либо собрано вне
        `with` подмены, либо сравнивается срез `argv[1:]` — разбор
        находит вызов/литерал вне подмены/подскрипт и тест краснеет.
        """
        node = _gate_node(self.tree)
        self.assertIsNotNone(node, f"нет метода {GATE_CLASS}.{GATE_METHOD}")
        for sub in ast.walk(node):
            name = (sub.attr if isinstance(sub, ast.Attribute)
                    else sub.id if isinstance(sub, ast.Name) else None)
            self.assertNotEqual(
                name, "_pytest_command",
                f"метод всё ещё зовёт _pytest_command: строка "
                f"{getattr(sub, 'lineno', '?')}")

        expected_dump = ast.dump(ast.parse(EXPECTED_LITERAL, mode="eval").body)
        literals = [sub for sub in ast.walk(node)
                    if isinstance(sub, ast.List)
                    and ast.dump(sub) == expected_dump]
        self.assertTrue(literals,
                        f"в методе нет списка-литерала {EXPECTED_LITERAL}")
        literal = literals[0]

        decorated = any(_is_executable_patch(d) for d in node.decorator_list)
        covered = decorated
        if not decorated:
            for sub in ast.walk(node):
                if not isinstance(sub, (ast.With, ast.AsyncWith)):
                    continue
                if not any(_is_executable_patch(item.context_expr)
                           for item in sub.items):
                    continue
                inner = [n for stmt in sub.body for n in ast.walk(stmt)]
                calls_suite = any(
                    isinstance(n, ast.Call)
                    and ast.unparse(n.func).endswith("run_full_suite")
                    for n in inner)
                if calls_suite and any(n is literal for n in inner):
                    covered = True
        self.assertTrue(
            covered,
            "подмена stack.pytest_python_executable значением "
            f"{FAKE_PY!r} не охватывает и run_full_suite, и литерал ожидания")

        bound = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign) and sub.value is literal:
                bound |= {t.id for t in sub.targets
                          if isinstance(t, ast.Name)}
        compared = False
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "assertEqual"
                    and len(sub.args) >= 2):
                continue
            first, second = sub.args[0], sub.args[1]
            for exp, act in ((first, second), (second, first)):
                is_expected = exp is literal or (
                    isinstance(exp, ast.Name) and exp.id in bound)
                if is_expected and not isinstance(act, ast.Subscript):
                    compared = True
        self.assertTrue(compared,
                        "нет assertEqual всего argv со списком-литералом")

        result = _run(self.module.GateArgvTest, GATE_METHOD)
        self.assertTrue(result.wasSuccessful(), _report(result))

    def test_ac2_docstring_names_both_mutations(self):
        """Докстринг метода гейта называет обе ловимые мутации.

        Читается докстринг `GateArgvTest.test_gate_call_argv_unchanged`:
        в нём есть мутация прогона гейта (`suite-run` и порядок) и мутация
        общей части команды (`_pytest_command`).

        Ловит мутацию: докстринг оставлен прежним — в нём только флаги
        `suite-run`/порядок путей, без упоминания `_pytest_command`.
        """
        node = _gate_node(self.tree)
        self.assertIsNotNone(node, f"нет метода {GATE_CLASS}.{GATE_METHOD}")
        doc = ast.get_docstring(node) or ""
        for needle in ("suite-run", "порядок", "_pytest_command"):
            with self.subTest(needle=needle):
                self.assertIn(needle, doc)

    def test_ac3_common_part_change_turns_gate_test_red(self):
        """Мутант общей части `_pytest_command` краснит метод гейта.

        `acceptance._pytest_command` подменяется мутантом — без пары
        `-p timeout` либо с `-p no:cacheprovider`, переставленной в конец, —
        и `GateArgvTest.test_gate_call_argv_unchanged` запускается через
        `unittest.TestResult`: обязан упасть. Без мутанта тот же метод
        проходит.

        Ловит мутацию: ожидание метода снова собрано той же
        `_pytest_command` — мутант попадает в обе стороны сравнения, метод
        зелёный, и этот тест краснеет.
        """
        cls = self.module.GateArgvTest
        clean = _run(cls, GATE_METHOD)
        self.assertTrue(clean.wasSuccessful(), _report(clean))
        for label, mutant in (("без -p timeout", _drop_timeout_mutant),
                              ("иной порядок флагов", _reorder_mutant)):
            with self.subTest(mutant=label):
                with mock.patch.object(acceptance, "_pytest_command",
                                       mutant()):
                    result = _run(cls, GATE_METHOD)
                self.assertFalse(result.wasSuccessful(),
                                 f"мутант «{label}» не покраснил метод гейта")

    def test_ac4_interpreter_independence_test_exists_and_passes(self):
        """Новый тест воспроизводит условие ревизии и зелёный.

        В `tests/test_suite_run.py` ищется тестовый метод (кроме метода
        гейта), который запускает `test_gate_call_argv_unchanged` и
        утверждает `wasSuccessful`; файл несёт подмены `_MODULE_ROOT`,
        `VENV_DIR`, `executable` (`stack.sys`) значением `/fake/bin/python`,
        `git worktree add` и `.artel/venv/bin/python3`, без сетевых
        адресов. Найденный метод запускается и обязан пройти.

        Ловит мутацию: новый тест не добавлен либо проверяет вызов без
        `wasSuccessful` — поиск пуст; либо добавлен, но красный на
        исправленном методе гейта — запуск не успешен.
        """
        names = _interpreter_test_names(self.module, self.tree)
        self.assertTrue(
            names, "нет нового теста, запускающего test_gate_call_argv_"
            "unchanged через TestResult с проверкой wasSuccessful")
        for needle in ("_MODULE_ROOT", "VENV_DIR", "executable",
                       "/fake/bin/python", "worktree", ".artel"):
            with self.subTest(needle=needle):
                self.assertTrue(needle in self.src,
                                f"в {SUITE_FILE.name} нет {needle!r}")
        for scheme in ("http://", "https://", "git@"):
            self.assertFalse(scheme in self.src,
                             f"в {SUITE_FILE.name} сетевой адрес {scheme!r}")
        for cls_name, meth in names:
            with self.subTest(test=f"{cls_name}.{meth}"):
                result = _run(getattr(self.module, cls_name), meth)
                self.assertTrue(result.wasSuccessful(), _report(result))

    def test_ac5_interpreter_test_red_on_old_gate_body(self):
        """Тест требования 2 краснеет на прежнем теле метода гейта.

        Тело `GateArgvTest.test_gate_call_argv_unchanged` подменяется
        прежним (ожидание через `_pytest_command` вне подмены), и каждый
        найденный тест требования 2 запускается: обязан упасть. С текущим
        телом он же проходит.

        Ловит мутацию: новый тест не подменяет `_MODULE_ROOT`/`VENV_DIR`/
        `sys.executable` (или подменяет не тот модуль) — прежнее тело в нём
        зелёное, и этот тест краснеет.
        """
        names = _interpreter_test_names(self.module, self.tree)
        self.assertTrue(names, "нет нового теста требования 2")
        for cls_name, meth in names:
            cls = getattr(self.module, cls_name)
            with self.subTest(test=f"{cls_name}.{meth}", body="текущее"):
                result = _run(cls, meth)
                self.assertTrue(result.wasSuccessful(), _report(result))
            with self.subTest(test=f"{cls_name}.{meth}", body="прежнее"):
                with mock.patch.object(self.module.GateArgvTest, GATE_METHOD,
                                       _old_gate_call_argv_body):
                    result = _run(cls, meth)
                self.assertFalse(result.wasSuccessful(),
                                 "тест требования 2 зелёный на прежнем теле")

    def test_ac6_first_argv_element_comes_from_selector(self):
        """Новый тест ловит интерпретатор в обход
        `stack.pytest_python_executable`.

        Кандидаты — тестовые методы файла (кроме метода гейта и тестов
        требования 2), чей текст называет `pytest_python_executable` и
        `run_full_suite`. Хотя бы один кандидат зелёный на текущем коде и
        красный под каждым мутантом `_pytest_command`, ставящим первым
        элементом голый `python3` либо `sys.executable`.

        Ловит мутацию: охранный тест не добавлен либо сверяет argv без
        первого элемента — ни один кандидат не краснеет под мутантами.
        """
        excluded = set(_interpreter_test_names(self.module, self.tree))
        excluded.add((GATE_CLASS, GATE_METHOD))
        candidates = []
        for key, node in _methods(self.tree).items():
            if key in excluded or not key[1].startswith("test"):
                continue
            text = ast.get_source_segment(self.src, node) or ""
            if "pytest_python_executable" in text and "run_full_suite" in text:
                candidates.append(key)
        self.assertTrue(candidates, "нет нового теста требования 3")
        mutants = (("python3", lambda: "python3"),
                   ("sys.executable", lambda: sys.executable))
        verdicts = {}
        for cls_name, meth in candidates:
            cls = getattr(self.module, cls_name)
            clean = _run(cls, meth)
            reds = []
            for label, first in mutants:
                with mock.patch.object(acceptance, "_pytest_command",
                                       _first_element_mutant(first)):
                    reds.append(not _run(cls, meth).wasSuccessful())
            verdicts[f"{cls_name}.{meth}"] = (clean.wasSuccessful(), reds)
        self.assertTrue(
            any(ok and all(reds) for ok, reds in verdicts.values()),
            f"ни один кандидат не зелёный и не красный под обоими "
            f"мутантами: {verdicts}")


if __name__ == "__main__":
    unittest.main()
