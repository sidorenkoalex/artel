"""Общий разбор предмета планки — тела `CmdModelsTest::
test_command_writes_nothing` из `tests/test_models.py`.

Модуль без префикса `test_` (skills/test-authoring.md, «Общий код планки
— только модули `_*.py`»): один и тот же разбор нужен файлам AC-1, AC-2 и
AC-4, а AC-3 берёт отсюда границы метода, чтобы прочитать в трассировке
падения, на какой именно строке теста оно случилось.

Источник разбора — `inspect.getsource` ИМПОРТИРОВАННОГО модуля
`tests.test_models`, а не чтение файла по пути: модуль приезжает в
процесс тем же путём, каким его видит прогон тестов, и разбор не зависит
ни от рабочего каталога pytest, ни от того, где материализована планка.
"""
import ast
import inspect
import io
import re
import textwrap
import tokenize
import unittest

from tests import test_models as target_module

TARGET_CLASS = "CmdModelsTest"
TARGET_METHOD = "test_command_writes_nothing"
TARGET_NAME = f"tests/test_models.py::{TARGET_CLASS}::{TARGET_METHOD}"


def target_callable():
    """Сам тестовый метод — предмет всех критериев задачи."""
    return getattr(getattr(target_module, TARGET_CLASS), TARGET_METHOD)


def source_and_start() -> tuple[str, int]:
    """(исходник метода без общего отступа, номер его первой строки в файле).

    Отступ снимается, чтобы `ast.parse` принял текст; нумерация строк
    разбора при этом относительная — строка `def` становится первой,
    перевод в абсолютные даёт `absolute()`.
    """
    lines, start = inspect.getsourcelines(target_callable())
    return textwrap.dedent("".join(lines)), start


def method_ast() -> ast.FunctionDef:
    """Разбор метода: корень — сам `FunctionDef`, строки относительные."""
    return ast.parse(source_and_start()[0]).body[0]


def absolute(lineno: int) -> int:
    """Относительная строка разбора -> строка в `tests/test_models.py`."""
    return source_and_start()[1] + lineno - 1


def method_line_range() -> tuple[int, int]:
    """(первая, последняя) строка метода в файле — рамка для трассировки."""
    source, start = source_and_start()
    return start, start + len(source.splitlines()) - 1


def iterdir_lines() -> list[int]:
    """Относительные строки всех вызовов `iterdir()` — обходы каталога."""
    return sorted(node.lineno for node in ast.walk(method_ast())
                  if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute)
                  and node.func.attr == "iterdir")


def first_snapshot_line() -> int | None:
    """Относительная строка первого `iterdir()` — граница «до снимка».

    `None` — вызова `iterdir()` в теле нет вовсе; такому телу критерии
    AC-1/AC-2 («до первого `iterdir()`») адресовать нечем, и тесты
    сообщают об этом отдельным сообщением, а не падают разбором.
    """
    lines = iterdir_lines()
    return lines[0] if lines else None


def iterdir_call_count() -> int:
    """Сколько раз тело зовёт `iterdir()` — снимки «до» и «после»."""
    return len(iterdir_lines())


def body_code() -> str:
    """Текст метода без комментариев и без докстринга — только код.

    Докстринг и комментарии здесь неизбежно называют и `del conn`, и
    `*-wal`/`*-shm` (этого требует заявка мутации), поэтому текстовые
    проверки планки обязаны смотреть на код, а не на весь исходник.
    """
    source = source_and_start()[0]
    lines = source.splitlines()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            row, col = token.start
            lines[row - 1] = lines[row - 1][:col]
    function = method_ast()
    if ast.get_docstring(function) is not None:
        doc = function.body[0]
        for row in range(doc.lineno, doc.end_lineno + 1):
            lines[row - 1] = ""
    return "\n".join(lines)


def nodes_before(line: int) -> list[ast.AST]:
    """Узлы разбора, начинающиеся строго ДО относительной строки `line`."""
    return [node for node in ast.walk(method_ast())
            if getattr(node, "lineno", None) is not None
            and node.lineno < line]


def assertion_calls(nodes) -> list[ast.Call]:
    """Вызовы утверждений (`self.assert*`) среди переданных узлов."""
    return [node for node in nodes
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")]


def run_target() -> unittest.TestResult:
    """Прогон настоящего `CmdModelsTest::test_command_writes_nothing` в
    этом же процессе — исход нужен и AC-3 (краснота на мутации), и AC-4
    (краснота на лишнем файле после команды)."""
    case_class = getattr(target_module, TARGET_CLASS)
    suite = unittest.TestSuite([case_class(TARGET_METHOD)])
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    return runner.run(suite)


def problem_reports(result: unittest.TestResult) -> list[str]:
    """Тексты трассировок падений и ошибок прогона — в порядке unittest."""
    return [report for _, report in result.failures + result.errors]


def lines_inside_method(report: str) -> list[int]:
    """Строки трассировки, попавшие в ТЕЛО предметного метода.

    Кадры того же файла вне тела (`run_cmd`, `setUp`) отбрасываются —
    иначе падение внутри команды выглядело бы как падение раньше снимка
    файлов только потому, что его строка меньше.
    """
    start, end = method_line_range()
    hits = [int(num) for num in re.findall(r'test_models\.py", line (\d+)',
                                           report)]
    return [num for num in hits if start <= num <= end]


def names_in(node: ast.AST) -> set[str]:
    """Имена и атрибуты поддерева — `weakref.ref` даёт {"weakref", "ref"}."""
    found: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            found.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            found.add(sub.attr)
    return found
