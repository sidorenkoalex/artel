"""Юнит-тесты `orchestrator.catalog._tz_calibration_inputs`/`_TZ_ZONES_RE`
(SPEC 01M1TQ11K4WJZD7ZE3MR0J4ZK4, требование 2; регрессия REVIEW.md
итерации 1, R1-F1): разбор строки «Зоны:» устойчив к прозаическому
упоминанию слова «Зоны:» раньше самой строки и к переносу строки
«Зоны: ...» на вторую физическую строку — оба свойства несёт РЕАЛЬНОЕ
ТЗ этой же задачи (`tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/TZ.md`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog  # noqa: E402

TZ_WITH_PROSE_MENTION_AND_WRAPPED_ZONES = """Контекст фикстуры.

Требуется:
1. Пункт один.
2. Пункт два.

Печатает ориентир (число путей в «Зоны:») и разницу с рамкой.

Зоны: orchestrator/config.py, orchestrator/catalog.py,
orchestrator/budget.py, orchestrator/fsm.py, tests/.
Порядок: после мержа ещё не влитых задач.

Рамка: $20.
"""


class TzZonesParsingTest(unittest.TestCase):

    def test_prose_mention_of_zony_before_real_line_is_ignored(self):
        """Первое по тексту вхождение «Зоны:» — в прозе требования, не в
        самой строке зон; regexp обязан пропустить его и найти реальную
        строку (заякорена на начало строки)."""
        rama, ac_count, zone_files = catalog._tz_calibration_inputs(
            TZ_WITH_PROSE_MENTION_AND_WRAPPED_ZONES)

        self.assertEqual(zone_files, 5)

    def test_wrapped_zones_line_without_blank_line_before_next_label(self):
        """Строка «Зоны: ...» перенесена на вторую физическую строку, а
        сразу за ней (без пустой строки-разделителя) идёт следующая метка
        «Порядок:» — захват обязан остановиться перед ней, не поглотить
        её текст."""
        rama, ac_count, zone_files = catalog._tz_calibration_inputs(
            TZ_WITH_PROSE_MENTION_AND_WRAPPED_ZONES)

        self.assertEqual(rama, 20.0)
        self.assertEqual(ac_count, 2)
        self.assertEqual(zone_files, 5)


if __name__ == "__main__":
    unittest.main()
