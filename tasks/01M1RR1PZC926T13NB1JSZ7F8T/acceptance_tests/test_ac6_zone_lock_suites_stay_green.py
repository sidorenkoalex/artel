"""AC-6 (SPEC 01M1RR1PZC926T13NB1JSZ7F8T): «`tests/test_zone_lock.py` и
`tests/test_zones_gate.py` в текущем виде — без правки существующих
ассертов — остаются зелёными после фикса».

Зелёный с рождения: обе планки уже зелёные СЕГОДНЯ, до единой строчки кода
этой задачи — критерий охраняет РЕГРЕССИЮ будущей правки
`orchestrator/zone_lock.py` (сужение фильтра по актору не задело бы
существующие тесты, которые журналируют `"agent run started"` актором
`"developer"` явно — SPEC, «Материалы»), а не описывает новую
функциональность. Тот же приём, что `tasks/01M1KVG3KSCY47HWXWF5HM0E76/
acceptance_tests/test_ac6_existing_plankas_stay_green.py`: `subprocess`
прогон реальным интерпретатором против ТЕКУЩЕГО кода `orchestrator/`, не
зафиксированной копии.
"""
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))


def _run_module(dotted: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "unittest", dotted, "-v"],
        cwd=_REPO_ROOT, capture_output=True, text=True, timeout=600)


class ZoneLockAndZonesGateSuitesStayGreenTest(unittest.TestCase):

    def test_ac6_test_zone_lock_suite_stays_green(self):
        """`python3 -m unittest tests.test_zone_lock` (реальное дерево
        `orchestrator/`) — код 0, ни одного `FAILED`/`ERROR`.

        Ловит мутацию: фикс требования 1 меняет сигнатуру/поведение
        `_occupies`/`_visit_has_action` так, что существующие сценарии
        файла (например `test_agent_started_after_in_dev_boundary_lifts_
        conflict`, журналирующий старт актором `"developer"` явно)
        перестают проходить — `returncode` станет ненулевым, `stderr`
        понесёт `FAILED`.
        """
        self.assertTrue((_REPO_ROOT / "tests/test_zone_lock.py").is_file())

        result = _run_module("tests.test_zone_lock")

        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        self.assertNotIn("FAILED", result.stderr)

    def test_ac6_test_zones_gate_suite_stays_green(self):
        """`python3 -m unittest tests.test_zones_gate` (реальное дерево
        `orchestrator/`) — код 0, ни одного `FAILED`/`ERROR`.

        Ловит мутацию: фикс требования 1 задевает `fsm_advance.py`/общий
        код гейта зон (например правкой сигнатуры функции, которую
        `_zones_gate_refuses` переиспользует) — `returncode` станет
        ненулевым, хотя SPEC, «Не входит», не предполагает такого
        пересечения.
        """
        self.assertTrue((_REPO_ROOT / "tests/test_zones_gate.py").is_file())

        result = _run_module("tests.test_zones_gate")

        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        self.assertNotIn("FAILED", result.stderr)


if __name__ == "__main__":
    unittest.main()
