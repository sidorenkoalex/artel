"""AC-2 (tasks/01M1SD5RHTJ0H0SR0615SVCJM5/SPEC.md): шаги-функции
возвращают явный исход (`ok`/`refused(...)`/`escalate(...)` либо
специфичный аналог существующего протокола) без булевых флагов и без
новой вложенности условий поверх текущей.

Красен до реализации: НЕТ для этого конкретного индикатора — сегодняшний
модуль уже проходит собственный порог (замерено `ast`: максимальная
глубина вложенности `if`/`for`/`while`/`try`/`with` внутри любой
top-level функции `orchestrator/fsm_merge_gate.py` сегодня равна 2, у
`_cmd_approve_merge_gate` и `_cmd_approve_merge_gate_cycle`). Зелёный с
рождения: тест проверяет буквально «не выросло» — то же свойство,
которым уже обладает сегодняшний код; рефакторинг обязан его СОХРАНИТЬ,
не создать заново, поэтому тест зелёный уже сегодня и обязан остаться
зелёным после разбора на шаги.

Часть AC-2 про явный тип исхода (`ok`/`refused`/`escalate`/протокольный
аналог) и отсутствие булевых флагов сигнатурно привязана к именам и
сигнатурам новых шаг-функций, которых SPEC не фиксирует (декомпозицию
предлагает исполнитель, правила фазы R роадмапа, прецедент T091) —
не проверяется здесь тем же доводом, что и в `test_ac1_short_
composition_and_new_step_functions.py`; это предмет ревью diff'а на
review_gate.
"""
import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm_merge_gate  # noqa: E402

# Замерено на сегодняшнем orchestrator/fsm_merge_gate.py: максимум по
# всем top-level функциям модуля. Порог — «не больше», не «меньше»:
# AC-2 запрещает НОВУЮ вложенность, не требует уменьшения существующей.
MAX_NESTING_DEPTH_BASELINE = 2

_NESTING_NODES = (ast.If, ast.For, ast.While, ast.Try, ast.With)


def _max_nesting_depth(node: ast.AST, depth: int = 0) -> int:
    best = depth
    for child in ast.iter_child_nodes(node):
        child_depth = depth + 1 if isinstance(child, _NESTING_NODES) else depth
        best = max(best, _max_nesting_depth(child, child_depth))
    return best


class NoNewNestingTest(unittest.TestCase):

    def test_ac2_no_step_function_nests_deeper_than_the_baseline(self):
        """Ни одна top-level функция модуля не вложена условиями глубже,
        чем сегодняшний максимум (2) — декомпозиция на шаги не заводит
        НОВУЮ вложенность поверх текущей (AC-2).

        Ловит мутацию: разработчик выносит шаги в отдельные функции, но
        внутри каждой копирует условную развилку старого монолита ещё на
        один уровень глубже (например, оборачивает уже вложенный `if
        merge_res...` в дополнительный `if step_kind == ...`) — максимум
        вырастет с 2 до 3+, и `assertLessEqual` здесь покраснеет.
        """
        src = Path(fsm_merge_gate.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)

        depths = {
            node.name: _max_nesting_depth(node)
            for node in tree.body if isinstance(node, ast.FunctionDef)
        }

        worst = max(depths.values(), default=0)
        self.assertLessEqual(
            worst, MAX_NESTING_DEPTH_BASELINE,
            f"вложенность условий выросла выше сегодняшнего максимума "
            f"({MAX_NESTING_DEPTH_BASELINE}): {depths}")


if __name__ == "__main__":
    unittest.main()
