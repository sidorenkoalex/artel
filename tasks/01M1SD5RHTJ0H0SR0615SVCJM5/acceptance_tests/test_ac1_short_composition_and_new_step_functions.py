"""AC-1 (tasks/01M1SD5RHTJ0H0SR0615SVCJM5/SPEC.md): `_cmd_approve_merge_
gate`/`_cmd_approve_merge_gate_cycle` разложены на именованные функции-
шаги, `_cmd_approve_merge_gate` — короткая композиция вызовов этих шагов.

Красен до реализации: до разбора `_cmd_approve_merge_gate` несёт 35
top-level операторов на 184 строки одной функции (замерено `ast` на
сегодняшнем `orchestrator/fsm_merge_gate.py`), а модуль целиком — 10
top-level функций; оба порога ниже подобраны так, чтобы монолит их не
проходил и тест падал именно из-за отсутствия декомпозиции задачи, не по
другой причине.

SPEC не фиксирует ни конкретные имена новых шагов, ни их количество
(«декомпозицию предлагает исполнитель», формулировка требования 1 и
правила фазы R роадмапа — прецедент T091) — явное перечисление всех
8 ответственностей из формулировки AC-1 (мьютекс, подтяжка/свежесть,
CI, защищённые пути, merge+push, снапшот/RETRO, уборка, журнал/печать)
поимённо поэтому НЕ проверяется здесь: это предмет ревью diff'а на
review_gate (тот же класс отступления, что и `tasks/T036/acceptance_
tests/test_merge_gitcmd.py::test_ac1...`, тоже AST-проверка структурного
факта без знания будущих имён). Здесь — два объективных, не зависящих
от выбора имён индикатора самого факта декомпозиции: тело `_cmd_approve_
merge_gate` стало короткой композицией (мало top-level операторов), и
модуль обзавёлся новыми именованными функциями сверх сегодняшних 10.
"""
import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm_merge_gate  # noqa: E402

# Замерено на сегодняшнем orchestrator/fsm_merge_gate.py (до рефакторинга
# задачи): `_cmd_approve_merge_gate` — 35 top-level операторов, модуль —
# 10 top-level функций. Пороги ниже — заведомо ниже сегодняшних чисел,
# так что монолит (или косметическая правка без реальной декомпозиции)
# их не проходит.
MAX_BODY_STATEMENTS = 20
MIN_NEW_TOP_LEVEL_FUNCTIONS = 12


def _module_tree() -> ast.Module:
    src = Path(fsm_merge_gate.__file__).read_text(encoding="utf-8")
    return ast.parse(src)


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"функция {name} не найдена в модуле")


class ShortCompositionTest(unittest.TestCase):

    def test_ac1_cmd_approve_merge_gate_is_a_short_composition(self):
        """`_cmd_approve_merge_gate` несёт немного top-level операторов —
        признак того, что тело стало композицией вызовов шагов, а не
        клубком инлайн-логики.

        Ловит мутацию: разработчик оставляет всю логику мержа/публикации/
        уборки инлайн (сегодняшние 35 операторов на 184 строки) вместо
        выноса в отдельные шаг-функции — счётчик останется выше
        `MAX_BODY_STATEMENTS`, и `assertLessEqual` здесь покраснеет.
        """
        tree = _module_tree()
        node = _top_level_function(tree, "_cmd_approve_merge_gate")

        self.assertLessEqual(
            len(node.body), MAX_BODY_STATEMENTS,
            f"_cmd_approve_merge_gate несёт {len(node.body)} top-level "
            f"операторов — не похоже на короткую композицию шагов (AC-1)")

    def test_ac1_module_gains_new_named_step_functions(self):
        """Модуль обзаводится новыми именованными функциями сверх
        сегодняшних 10 — decomposition действительно произошла, а не
        только переименование существующих узлов.

        Ловит мутацию: разработчик разбирает функцию на замыкания/лямбды
        внутри тела или переставляет код без выноса в top-level функции —
        число top-level `FunctionDef` в модуле не вырастет, и
        `assertGreaterEqual` здесь покраснеет.
        """
        tree = _module_tree()
        function_count = sum(
            1 for node in tree.body if isinstance(node, ast.FunctionDef))

        self.assertGreaterEqual(
            function_count, MIN_NEW_TOP_LEVEL_FUNCTIONS,
            f"модуль несёт {function_count} top-level функций — "
            f"декомпозиция на именованные шаги (AC-1) не видна")


if __name__ == "__main__":
    unittest.main()
