"""AC-6 (tasks/01M1TKNXX5YN5KT4WHG4T44JWV/SPEC.md): тела `in_dev`/`review`
после рефакторинга — короткие композиции (≤ 40 строк каждая), без НОВЫХ
уровней вложенности условий относительно кода до правки; публичные
сигнатуры и имена модульных функций-гейтов (`_capacity_gate_refuses`/
`_zones_gate_refuses`/`_review_rework_gate_refuses`, чьи вызовы и
сигнатуры дословно фиксируют `tests/test_capacity_gate.py`/
`tests/test_zones_gate.py`/`tests/test_fsm_review_rework_gate.py`)
сохранены.

Красен до реализации: сегодняшние тела `in_dev` (126 строк без строки
`def`)/`review` (172 строки) далеко превышают потолок 40 строк —
рефакторинг ещё не сократил их до композиций вызовов.

Зелёный с рождения: сигнатуры `in_dev(conn, task_id, t, tdir, target,
state)`/`review(conn, task_id, t, tdir, target, state)` и имена
`_capacity_gate_refuses`/`_zones_gate_refuses`/`_review_rework_gate_
refuses` уже сегодня ровно такие, какими их фиксирует AC-6 — эта часть
проверки не должна была сломаться рефакторингом, но фиксируется как
планка, чтобы падение здесь было видно отдельно от падения по длине тела.
"""
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox as gate_ast  # noqa: E402
from orchestrator import fsm_advance  # noqa: E402

# Базовая (снятая ДО правки кода) глубина вложенности `if` — «без новых
# уровней» буквально значит «не глубже, чем было» (SPEC требование 4/AC-6),
# не абсолютное число: `orchestrator/fsm_advance.py::in_dev`/`review`
# сегодня несут это значение вложенности.
_BASELINE_IF_NESTING = {"in_dev": 4, "review": 3}

_EXPECTED_SIGNATURES = {
    "in_dev": ["conn", "task_id", "t", "tdir", "target", "state"],
    "review": ["conn", "task_id", "t", "tdir", "target", "state"],
}

_PRESERVED_GATE_FUNCTION_NAMES = (
    "_capacity_gate_refuses", "_zones_gate_refuses",
    "_review_rework_gate_refuses",
)


class Ac6EntryPointSignaturesPreservedTest(unittest.TestCase):

    def test_ac6_in_dev_and_review_keep_their_public_parameter_names_and_order(self):
        """`in_dev`/`review` сохраняют сигнатуру `(conn, task_id, t, tdir,
        target, state)` — буквально из AC-6.

        Ловит мутацию: параметр переставлен местами или переименован
        (например `target`/`state` поменяны местами) — код, который зовёт
        точку входа позиционно (диспетчер `fsm.py::_cmd_advance`),
        передал бы значения не туда без единого исключения на этом
        уровне.
        """
        for name, expected in _EXPECTED_SIGNATURES.items():
            with self.subTest(func=name):
                func = getattr(fsm_advance, name)
                actual = list(inspect.signature(func).parameters.keys())
                self.assertEqual(actual, expected)


class Ac6GateFunctionNamesPreservedTest(unittest.TestCase):

    def test_ac6_the_three_gate_functions_used_by_existing_tests_still_exist(self):
        """Модульные функции-гейты, чьи вызовы дословно фиксируют
        `tests/test_capacity_gate.py`/`tests/test_zones_gate.py`/
        `tests/test_fsm_review_rework_gate.py`, остаются доступны как
        `fsm_advance.<имя>` и остаются вызываемыми.

        Ловит мутацию: одна из трёх функций переименована или удалена в
        пользу нового имени внутри рефакторинга — `hasattr` вернёт
        `False` для неё.
        """
        missing = [name for name in _PRESERVED_GATE_FUNCTION_NAMES
                  if not callable(getattr(fsm_advance, name, None))]

        self.assertEqual(
            missing, [],
            f"эти функции обязаны остаться доступны по имени: {missing!r}")


class Ac6ShortBodyCompositionTest(unittest.TestCase):

    def test_ac6_in_dev_and_review_bodies_are_at_most_40_lines(self):
        """Тело каждой из `in_dev`/`review` — не более 40 строк (без
        строки `def ...:`), буквально по AC-6.

        Ловит мутацию: гейты собраны в общий каркас, но тело точки входа
        всё ещё несёт старую предварительную логику построчно (чтение
        PLAN/REVIEW, разбор статуса) вперемешку с вызовом каркаса вместо
        вынесения её в отдельные функции — счётчик строк останется
        далеко за 40.
        """
        for name in ("in_dev", "review"):
            with self.subTest(func=name):
                lines = gate_ast.function_body_line_count(name)
                self.assertLessEqual(
                    lines, 40,
                    f"тело {name} несёт {lines} строк — обязано быть ≤ 40")

    def test_ac6_in_dev_and_review_introduce_no_new_if_nesting_levels(self):
        """Глубина вложенности `if` в `in_dev`/`review` не превышает
        значение ДО рефакторинга (снято с сегодняшнего кода:
        `in_dev`=4, `review`=3) — «без новых уровней вложенности условий»
        буквально из AC-6.

        Ловит мутацию: цепочка гейтов реализована как вложенные `if`
        (`if not gate1(...): if not gate2(...): ...`) вместо плоской
        композиции/цикла по списку — глубина вложенности выросла бы
        относительно этой же функции до правки.
        """
        for name, baseline in _BASELINE_IF_NESTING.items():
            with self.subTest(func=name):
                depth = gate_ast.function_if_nesting_depth(name)
                self.assertLessEqual(
                    depth, baseline,
                    f"вложенность if в {name} выросла до {depth} "
                    f"(было {baseline} до рефакторинга)")


if __name__ == "__main__":
    unittest.main()
