"""AC-1 — 01M3GKJBXEBHB6ZA48J7VG8Z8W: один разбор строки мандата на три
потребителя.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. Разбор строки мандата живёт в одной функции модуля
`orchestrator/advance_gates/`; `orchestrator/answer.py`,
`orchestrator/advance_gates/zones.py` и
`orchestrator/advance_gates/test_integrity.py` зовут её и своего разбора
«маркер → элементы» не содержат. На одной и той же строке мандата все три
потребителя получают один и тот же список элементов.

Критерий проверяется двумя половинами, по одной на каждое его
предложение:

1. «своего разбора не содержат» — по AST исходников: шаг «отсечение
   префикса-маркера» (требование 1 SPEC) ищется как выражение, снимающее
   с строки префикс ИМЕНОВАННОГО маркера (`line[len(<…MARKER…>):]`,
   `.removeprefix(<…MARKER…>)`, `.split(<…MARKER…>)`/`.partition(…)`).
   Сегодня такое выражение несут три функции — по одной в каждом модуле
   (`answer._zones_mandate_marker_paths`, `zones._answer_zones_mandate`,
   `test_integrity._answer_mandate`); после правки его вправе нести
   РОВНО ОДНА функция, и не в `orchestrator/answer.py` (тот вне пакета
   `advance_gates`, а критерий требует общий узел именно там). Разбор по
   AST, не по тексту: упоминание маркера в комментарии или докстринге
   нарушением не является. Отсечение префикса по литералу (`line[len("Пути:"):]`
   раздела PLAN.md, `detail[len(prefix):]` журнала) под правило не
   подпадает — это не разбор строки мандата.
2. «все три получают один и тот же список» — прогоном: одна и та же
   строка элементов (с отступом, лишними пробелами и пустым элементом
   между запятыми) проходит через саму команду `answer`, через гейт зон
   (`zones._answer_zones_mandate`) и через гейт неослабления тестов
   (`test_integrity._answer_mandate`), и три списка сверяются между собой.

Красен до реализации: `orchestrator/answer.py:52-62` несёт собственное
отсечение префикса маркера, а с ним такие же выражения живут в
`zones.py:138` и `test_integrity.py:238` — трёх разборов вместо одного
`test_ac1_no_consumer_carries_its_own_mandate_parse` не принимает.
`test_ac1_three_consumers_parse_one_line_the_same_way` на сегодняшнем
коде зелёный — контроль, не молчаливый пропуск: три разбора СЕЙЧАС
совпадают только потому, что все зовут `_split_zone_paths`, и критерий
требует сохранить это совпадение после переноса разбора в общий узел.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

#: Потребители разбора, названные критерием.
CONSUMERS = ("orchestrator/answer.py",
             "orchestrator/advance_gates/zones.py",
             "orchestrator/advance_gates/test_integrity.py")

#: Модуль-потребитель, который общий узел нести НЕ вправе: он вне пакета
#: `orchestrator/advance_gates/`.
OUTSIDE_PACKAGE = "orchestrator/answer.py"

#: Имя переменной/константы маркера: отсечение префикса ПО ИМЕНИ маркера
#: (а не по строковому литералу) — признак разбора строки мандата.
MARKER_NAME = re.compile(r"marker", re.IGNORECASE)

#: Перечень элементов одной строки мандата: лишние пробелы вокруг
#: элементов и пустой элемент между запятыми — то, на чём разборы
#: расходятся, если их больше одного.
ELEMENTS_TAIL = f"  {_sandbox.TESTS_FILE} ,, {_sandbox.OTHER_TESTS_FILE}  "

#: Элементы, которые обязаны получить все три потребителя.
EXPECTED_ELEMENTS = [_sandbox.TESTS_FILE, _sandbox.OTHER_TESTS_FILE]


def _dotted(node) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _is_marker_name(node) -> bool:
    dotted = _dotted(node)
    return dotted is not None and bool(MARKER_NAME.search(dotted))


def _strips_marker_prefix(node) -> str | None:
    """Форма отсечения префикса-маркера, которую несёт узел; `None` — узел
    маркер не отсекает."""
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        lower = node.slice.lower
        if (isinstance(lower, ast.Call) and isinstance(lower.func, ast.Name)
                and lower.func.id == "len" and len(lower.args) == 1
                and _is_marker_name(lower.args[0])):
            return "срез по len(маркер)"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        attr = node.func.attr
        if (attr in ("removeprefix", "split", "rsplit", "partition")
                and node.args and _is_marker_name(node.args[0])):
            return f".{attr}(маркер)"
    return None


def _parsing_functions(rel_path: str) -> list:
    """«<файл>:<строка> <функция> (<форма>)» для каждой функции файла,
    отсекающей префикс именованного маркера."""
    source = (_sandbox.REPO_ROOT / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(func):
            form = _strips_marker_prefix(node)
            if form is not None:
                found.append(
                    f"{rel_path}:{node.lineno} {func.name} ({form})")
    return found


def _package_files() -> list:
    """Потребители плюс все модули пакета `orchestrator/advance_gates/` —
    общий узел ищется и там, где его мог поселить разработчик."""
    package = _sandbox.REPO_ROOT / "orchestrator" / "advance_gates"
    rels = {rel for rel in CONSUMERS}
    for path in sorted(package.glob("*.py")):
        rels.add(f"orchestrator/advance_gates/{path.name}")
    return sorted(rels)


class SingleMandateParseTest(unittest.TestCase):
    """AC-1, первая половина: разбор живёт в одной функции пакета
    `advance_gates`, и ни один из трёх потребителей своего не несёт."""

    def test_ac1_no_consumer_carries_its_own_mandate_parse(self):
        """Отсечение префикса-маркера во всём пакете `advance_gates` и в
        `orchestrator/answer.py` встречается не более чем в ОДНОЙ функции,
        и эта функция — не в `orchestrator/answer.py` (общий узел критерий
        требует в пакете `advance_gates`).

        Ловит мутацию: на общий узел переведён только `answer.py`, а
        `zones.py` (или `test_integrity.py`) оставлен со своим
        `line[len(_ZONES_MANDATE_MARKER):]` — получаются два разбора вместо
        одного, то есть ровно тот дефект, ради которого задача заведена:
        расхождение снова возможно, и второй разбор снова придётся
        править отдельно.
        """
        found = []
        for rel in _package_files():
            found.extend(_parsing_functions(rel))

        in_answer = [line for line in found
                     if line.startswith(OUTSIDE_PACKAGE + ":")]
        self.assertEqual(
            [], in_answer,
            f"{OUTSIDE_PACKAGE} по-прежнему сам отсекает префикс маркера — "
            f"критерий требует общий узел в orchestrator/advance_gates/: "
            + "; ".join(in_answer))
        self.assertLessEqual(
            len(found), 1,
            "разбор строки мандата обязан жить в ОДНОЙ функции, найдено "
            f"{len(found)}: " + "; ".join(found))


class ThreeConsumersAgreeTest(_sandbox.AnswerMandateSandbox):
    """AC-1, вторая половина: один и тот же список элементов у трёх
    потребителей на одной и той же строке мандата."""

    def test_ac1_three_consumers_parse_one_line_the_same_way(self):
        """Один и тот же перечень элементов («  a ,, b  »: отступ, пробелы
        вокруг элементов, пустой элемент между запятыми) в строке мандата
        зон и в строке мандата ослабления — команда `answer`, гейт зон и
        гейт неослабления тестов дают один и тот же список элементов.

        Ловит мутацию: общий узел появился, но один из потребителей зовёт
        его с уже обрезанной (или наоборот, не стрипнутой) строкой — и
        получает на том же мандате другой список: лишний пустой элемент,
        элемент с ведущим пробелом либо потерянный первый элемент. Именно
        такое расхождение трёх разборов задача и закрывает.
        """
        self.set_state("in_dev")
        self.succeed_answer(_sandbox.answer_text(
            _sandbox.zones_mandate_line(ELEMENTS_TAIL)))
        self.set_state("escalated")
        self.succeed_answer(_sandbox.answer_text(
            _sandbox.weakening_mandate_line(ELEMENTS_TAIL)))

        by_answer = self.journal_mandate_paths()
        self.assertEqual(1, len(by_answer),
                         f"ожидалась одна запись мандата в журнале: "
                         f"{self.journal()}")

        self.assertEqual(EXPECTED_ELEMENTS, sorted(by_answer[0]),
                         "команда answer разобрала строку иначе")
        self.assertEqual(EXPECTED_ELEMENTS, self.zones_mandate_elements(),
                         "гейт зон разобрал ту же строку иначе, чем answer")
        self.assertEqual(EXPECTED_ELEMENTS, self.weakening_mandate_elements(),
                         "гейт неослабления тестов разобрал ту же строку "
                         "иначе, чем answer")


if __name__ == "__main__":
    unittest.main()
