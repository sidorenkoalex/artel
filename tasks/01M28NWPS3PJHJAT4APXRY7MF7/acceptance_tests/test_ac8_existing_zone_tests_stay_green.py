"""Приёмочный тест 01M28NWPS3PJHJAT4APXRY7MF7 — AC-8 (SPEC.md).

«Существующие тесты `tests/test_zone_lock.py` и `tests/test_zones_gate.py`
остаются зелёными без правки существующих утверждений» — критерий не о
НОВОМ поведении этой задачи, а о том, что реализация требований 1-3 НЕ
задевает уже застолблённые тесты `_occupies`/`blocking_conflict`/
`refusal`/`queue_order`/`queue_position` частей 1-3 (`tests/
test_zone_lock.py`) и разбора гейта зон `in_dev -> review` (`tests/
test_zones_gate.py`, задача 01M1P9QCHPHSCEA6TK13PV85SP — отдельная
механика, эта задача её не трогает вовсе). Проверяется буквально —
прогоном обоих файлов дочерним процессом `python3 -m unittest`, тем же
интерпретатором, что гоняет их же в CI.

Зелёный с рождения: до правки `orchestrator/zone_lock.py`/`orchestrator/
runner.py` этой задачей оба файла УЖЕ проходят (48 тестов, `python3 -m
unittest tests.test_zone_lock tests.test_zones_gate` — OK, проверено
вручную при написании этой планки) — критерий фиксирует, что реализация
требований 1-3 не сломает это состояние, не создаёт его заново. Красный
здесь был бы дефектом ЭТОЙ планки (например, неверный путь запуска), не
ожидаемым состоянием «до реализации».
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


class Ac8ExistingZoneLockAndZonesGateTestsStayGreenTest(unittest.TestCase):
    """Прогон `tests/test_zone_lock.py`/`tests/test_zones_gate.py` тем же
    интерпретатором, что и сама эта планка — независимый процесс, не
    делящий состояние БД/патчи с остальными тестами этого каталога.

    Ловит мутацию: правка `_occupies`/`blocking_conflict`/диапазона
    `BLOCKING_STATES`/фильтра актора `developer` под давлением требований
    1-3 этой задачи задевает существующее поведение частей 1-3 (например
    ослабляет сверку актора `"agent run started"`, что мгновенно рушит
    `tests/test_zone_lock.py::ZoneLockTest.
    test_non_developer_agent_start_in_same_stay_does_not_occupy`) —
    `returncode` дочернего прогона станет ненулевым."""

    def test_ac8_existing_zone_lock_and_zones_gate_suites_pass(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_zone_lock", "tests.test_zones_gate"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=180)

        self.assertEqual(
            result.returncode, 0,
            f"tests/test_zone_lock.py и/или tests/test_zones_gate.py "
            f"больше не зелёные:\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
