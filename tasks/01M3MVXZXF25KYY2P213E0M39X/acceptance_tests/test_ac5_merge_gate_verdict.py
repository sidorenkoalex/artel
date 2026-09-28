"""AC-5 — гейт диффа на мерже даёт тот же вердикт на тех же трёх путях.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Гейт диффа на мерже даёт тот же вердикт на тех же трёх путях:
`fsm_merge_gate._touches_protected_path` истинна для каждого из них.

Критерий называет ровно одну функцию и ровно её вердикт — тест зовёт её
напрямую, без песочницы мержа: имя и сигнатура сохраняются требованием 5,
а состояние БД/git на вердикт этой функции не влияет.

Красен до реализации: `_touches_protected_path` сверяет путь префиксом, записи-маски в перечне ещё нет — вердикт на `conftest.py` и `tests/sub/conftest.py` ложный.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _protected  # noqa: E402
from orchestrator import fsm_merge_gate  # noqa: E402


class MergeGateTouchesProtectedPathTest(unittest.TestCase):

    def test_ac5_new_protected_paths_are_touched_on_the_merge_gate(self):
        """`fsm_merge_gate._touches_protected_path` истинна на
        `conftest.py`, `pyproject.toml` и `tests/sub/conftest.py` — тех же
        трёх путях, на которых отказывает гейт зон (AC-4).

        Ловит мутацию: помощника позвали только в гейте зон, а в
        `_touches_protected_path` оставили собственную префиксную формулу
        (правка «по одному месту за раз» — самый вероятный неполный
        вариант). Наблюдаемое расхождение: вердикт на `conftest.py` и
        `tests/sub/conftest.py` ложный, `_protected_path_diff_gate` не
        эскалирует, и ветка с подменённым окружением pytest доезжает до
        `done` — при том что гейт зон её на `review` не пустил, то есть
        разойтись эти два вердикта не имеют права.
        """
        for path in _protected.GATE_PATHS:
            with self.subTest(path=path):
                self.assertTrue(
                    fsm_merge_gate._touches_protected_path(path),
                    f"гейт диффа на мерже не считает {path} защищённым")


if __name__ == "__main__":
    unittest.main()
