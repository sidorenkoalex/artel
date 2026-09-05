"""Приёмочные тесты 01M1SC40NT8T1WFKKKJ67CK96Z — AC-1, AC-2 (структура
`orchestrator/auto.py::_cmd_auto` после разбора на именованные шаги).

Красен до реализации: на коде ДО этой задачи `_cmd_auto` — один блок на
~266 строк (прочитано перед написанием этого файла), несущий литералом
и вызов `runner.cmd_run(` (шаг роли), и имя `_REWORK_GATE_STATES` (решение
о пред-advance), и сравнения `steps >= config.AUTO_MAX_STEPS` /
`idle_steps >= config.AUTO_STALL_STEPS_LIMIT` (стоп-краны) прямо в своём
теле — ни один из структурных запретов ниже не выполняется, и явного
типа исхода шага (перечисление/dataclass с вариантами AC-2) в модуле нет
вовсе (`class` в `orchestrator/auto.py` сегодня отсутствует, проверено
`grep -n "^class " orchestrator/auto.py`). Оба теста написаны по
буквальной формулировке критериев (SPEC «Критерии приёмки» AC-1, AC-2),
не по имени функций, которых до реализации не существует: тест не
называет конкретные имена новых функций/класса — сама SPEC их тоже не
называет, оставляя выбор разработчику, — а проверяет НАБЛЮДАЕМОЕ
СЛЕДСТВИЕ декомпозиции (тело `_cmd_auto` короче и не несёт литералов
шагов (в)/(г) напрямую; в модуле явно живёт тип исхода с нужными
вариантами; тело `_cmd_auto` не читает/не пишет `idle_steps`/
`prev_refusal` как голые локальные имена).

Обе проверки провалидированы временным стабом (декомпозиция тела
`_cmd_auto` в отдельную функцию + перечисление исходов шага) прямо в
`orchestrator/auto.py`, прогоном этого файла и последующим `git checkout
-- orchestrator/auto.py` — репозиторий не тронут, инструкция test-authoring
соблюдена.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
AUTO_PY = REPO_ROOT / "orchestrator" / "auto.py"

# Имена функций модуля ДО этой задачи (зафиксированы на момент написания
# теста, `grep -n "^def " orchestrator/auto.py`) — базовая линия для
# AC-1: разбор обязан завести НОВЫЕ функции, а не просто переименовать
# существующие в одну (вырожденный случай «переложил весь блок в один
# новый метод» не размножает имена и ловится порогом ниже).
_BASELINE_FUNCTIONS = frozenset({
    "_run_paused_refusal", "_run_zone_wait_refusal", "_advance_refusal",
    "_is_legit_first_entry_detail", "_role_step_since_state_entry",
    "_rework_not_addressed_reason", "_verifying_poll_note",
    "_advance_verifying_poll", "_final_stop_raises_alert",
    "auto_stop_advice", "auto_stop", "cmd_auto", "_cmd_auto",
})

# «Короткая композиция» (AC-1): нижняя граница взята с большим запасом
# от исходных ~266 строк — не требует конкретной цифры декомпозиции,
# только явного, кратного сокращения тела координирующей функции.
_MAX_CMD_AUTO_LINES = 100


def _module_ast():
    return ast.parse(AUTO_PY.read_text(encoding="utf-8"))


def _cmd_auto_node(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_cmd_auto":
            return node
    raise AssertionError("orchestrator/auto.py: функция _cmd_auto не найдена")


def _source_segment(node):
    return ast.get_source_segment(AUTO_PY.read_text(encoding="utf-8"), node)


def _top_level_function_names(tree):
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def _top_level_class_names(tree):
    return [node for node in tree.body if isinstance(node, ast.ClassDef)]


def _normalize_identifier(name):
    return "".join(ch for ch in name.lower() if ch.isalpha())


class CmdAutoIsAShortCompositionOfNamedStepsTest(unittest.TestCase):
    """AC-1: `_cmd_auto` разобрана на именованные функции по шагам цикла,
    сама функция после разбора — короткая композиция их вызовов."""

    def test_ac1_cmd_auto_delegates_role_run_gate_decision_and_stop_cranks(self):
        """Тело `_cmd_auto` короче исходного и не несёт литералом код шагов
        (б)/(в)/(г) АТ СИТУ — эти решения обязаны жить в отдельных
        именованных функциях, вызываемых из короткой композиции.

        Ловит мутацию: разработчик передвинул часть логики в новые
        функции, но оставил вызов `runner.cmd_run(...)` (шаг роли, AC-1в)
        или сравнение `steps >= config.AUTO_MAX_STEPS`/`idle_steps >=
        config.AUTO_STALL_STEPS_LIMIT` (стоп-краны, AC-1г) прямо в теле
        `_cmd_auto` — тест покраснеет на конкретной оставленной строке,
        не на всём диффе разом.
        """
        tree = _module_ast()
        node = _cmd_auto_node(tree)
        source = _source_segment(node)

        line_count = node.end_lineno - node.lineno + 1
        self.assertLessEqual(
            line_count, _MAX_CMD_AUTO_LINES,
            f"_cmd_auto занимает {line_count} строк — короткой композицией "
            f"после разбора на шаги (AC-1) это не назвать (порог "
            f"{_MAX_CMD_AUTO_LINES})")

        self.assertNotIn(
            "runner.cmd_run(", source,
            "_cmd_auto зовёт runner.cmd_run напрямую — запуск шага роли и "
            "разбор его исхода (AC-1в) обязаны жить в отдельной функции")
        self.assertNotIn(
            "_REWORK_GATE_STATES", source,
            "_cmd_auto проверяет _REWORK_GATE_STATES напрямую — решение "
            "«нужен ли пред-advance» (AC-1а) обязано жить в отдельной "
            "функции, не инлайном в теле цикла")
        self.assertNotIn(
            ">= config.AUTO_MAX_STEPS", source,
            "_cmd_auto сравнивает счётчик шагов с лимитом напрямую — "
            "стоп-кран лимита шагов (AC-1г) обязан жить в отдельной функции")
        self.assertNotIn(
            ">= config.AUTO_STALL_STEPS_LIMIT", source,
            "_cmd_auto сравнивает счётчик холостых шагов с порогом "
            "напрямую — стоп-кран буксования (AC-1г) обязан жить в "
            "отдельной функции")

    def test_ac1_decomposition_introduces_more_than_one_new_named_function(self):
        """Разбор заводит НЕСКОЛЬКО новых функций модуля, не одну —
        вырожденный «перенос всего блока в один новый метод» не
        удовлетворяет «по одной на каждый из пяти шагов».

        Ловит мутацию: весь код тела `_cmd_auto`, ранее инлайновый,
        механически завёрнут в ОДНУ новую функцию без дальнейшего
        разделения по шагам — новых имён на верхнем уровне модуля
        прибавится только одно, порог ниже это отличит от разбора на
        несколько именованных шагов.
        """
        tree = _module_ast()
        current = _top_level_function_names(tree)
        new_functions = current - _BASELINE_FUNCTIONS

        self.assertGreaterEqual(
            len(new_functions), 2,
            f"после разбора в модуле новых функций: {sorted(new_functions)} "
            f"— по одной на каждый из пяти шагов цикла (AC-1) не сводится "
            f"к переносу всего тела в единственную новую функцию")


class StepOutcomesAreExplicitValuesTest(unittest.TestCase):
    """AC-2: исходы шагов — явные значения (перечисление либо dataclass) с
    именованными вариантами advanced/role_ran/refused/stop; состояние
    итерации не передаётся локальными флагами тела `_cmd_auto`."""

    def test_ac2_module_defines_outcome_type_with_the_named_variants(self):
        """В модуле заведён класс (Enum либо dataclass), чьи имя класса и
        имена членов/вложенных классов вместе покрывают как минимум
        варианты advanced, role_ran, refused, stop — литерально названные
        в AC-2.

        Ловит мутацию: цикл продолжает разбирать исход шага ветками
        if/elif по сырым булевым флагам без единого именованного типа —
        `orchestrator/auto.py` сегодня не содержит ни одного `class`
        (проверено `grep -n "^class "`), и тест не найдёт ни одного
        варианта.
        """
        tree = _module_ast()
        class_nodes = _top_level_class_names(tree)
        self.assertTrue(
            class_nodes,
            "в orchestrator/auto.py нет ни одного class верхнего уровня — "
            "исходы шага (AC-2) обязаны быть перечислением либо dataclass")

        tokens = set()
        for cls in class_nodes:
            tokens.add(_normalize_identifier(cls.name))
            for item in ast.walk(cls):
                if isinstance(item, (ast.Assign, ast.AnnAssign)):
                    targets = (item.targets if isinstance(item, ast.Assign)
                              else [item.target])
                    for t in targets:
                        if isinstance(t, ast.Name):
                            tokens.add(_normalize_identifier(t.id))

        required = {"advanced": "advanced", "roleran": "role_ran",
                    "refused": "refused", "stop": "stop"}
        missing = [label for key, label in required.items() if key not in tokens]
        self.assertEqual(
            [], missing,
            f"среди классов/вариантов модуля не найдены исходы {missing} "
            f"(AC-2 требует как минимум advanced, role_ran, refused(<причина>), "
            f"stop(<причина>)); найденные токены: {sorted(tokens)}")

    def test_ac2_cmd_auto_body_does_not_carry_the_old_scattered_flags(self):
        """Тело `_cmd_auto` не читает и не пишет `idle_steps`/`prev_refusal`
        как голые локальные имена — состояние итерации цикла обязано
        передаваться явным значением исхода, не флагами, разбросанными по
        телу функции (буквальная вторая половина AC-2).

        Ловит мутацию: рефакторинг завёл тип исхода (первая проверка выше
        зеленеет), но `_cmd_auto` по-прежнему сама держит `idle_steps = 0`
        и инкрементирует её внутри своего тела — тест находит `ast.Name`
        с этим именем внутри `_cmd_auto` и краснеет, даже если тип исхода
        формально существует.
        """
        tree = _module_ast()
        node = _cmd_auto_node(tree)
        banned = {"idle_steps", "prev_refusal"}
        offenders = sorted({
            n.id for n in ast.walk(node)
            if isinstance(n, ast.Name) and n.id in banned})
        self.assertEqual(
            [], offenders,
            f"_cmd_auto всё ещё держит голые локальные флаги {offenders} — "
            f"AC-2 требует передавать состояние итерации явным значением "
            f"исхода, не разбросанными по телу функции переменными")


if __name__ == "__main__":
    unittest.main()
