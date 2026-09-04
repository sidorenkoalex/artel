"""Приёмочные тесты 01M1KS8K9RXWHX2PW3ZKB0P903 — AC-1 (пороги сигналов
«подозрения на большой объём» заданы именованными константами в
`orchestrator/config.py`).

AC-1 сам по себе не называл имена констант — test_author эскалировал
именно этот пробел (см. историю `test_ac_manual_and_escalate_markers.py`
до правки этим коммитом), Оператор ответил ANSWER-1: имена и значения
четырёх констант зафиксированы буквально —
`SPLIT_SIGNAL_ZONE_FILES = 5`, `SPLIT_SIGNAL_AC_COUNT = 10`,
`SPLIT_SIGNAL_BUDGET_USD = 30`, `SPLIT_SIGNAL_DIFF_FORECAST_RATIO = 0.5`.
С названными именами проверка «константа существует под ЭТИМ именем и
несёт ЭТО значение» уже отличает новую константу от случайных совпадений
по значению с существующими `AUTO_STALL_STEPS_LIMIT=5`/
`MAX_PARALLEL_TASKS=10`/`AUTO_MAX_STEPS=30` — трюк, который ставил в
тупик test_author до ответа (проверка по значению без имени была бы
зелёной уже сегодня, до реализации задачи).

Красен до реализации: ни одно из четырёх имён не существует сегодня в
`orchestrator/config.py` (проверено `grep -n "SPLIT_SIGNAL" -r
orchestrator` — пусто) — `getattr(config, name, _MISSING)` возвращает
`_MISSING` для каждого имени, `assertEqual` падает на сравнении с
ожидаемым числом.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

_MISSING = object()

# Имена и значения — буквально из ANSWER-1 (ответ на эскалацию AC-1).
EXPECTED_SPLIT_SIGNAL_CONSTANTS = {
    "SPLIT_SIGNAL_ZONE_FILES": 5,
    "SPLIT_SIGNAL_AC_COUNT": 10,
    "SPLIT_SIGNAL_BUDGET_USD": 30,
    "SPLIT_SIGNAL_DIFF_FORECAST_RATIO": 0.5,
}


class SplitSignalConstantsTest(unittest.TestCase):
    """Каждая из четырёх названных ANSWER-1 констант существует в
    `orchestrator/config.py` под своим именем и несёт заданное значение.

    Ловит мутацию: константа заведена под другим именем (опечатка,
    сокращение), значение сдвинуто на единицу (например
    `SPLIT_SIGNAL_AC_COUNT = 9` вместо `10` — «≥10» перестаёт совпадать
    с границей, названной ANSWER-1), либо порог продолжает жить
    захардкоженным числом внутри `scripts/guard.py` без одноимённой
    константы в `config.py` вовсе — соответствующий subTest покраснеет
    отдельно от остальных.
    """

    def test_ac1_named_constants_have_answer1_values(self):
        for name, expected in EXPECTED_SPLIT_SIGNAL_CONSTANTS.items():
            with self.subTest(constant=name):
                actual = getattr(config, name, _MISSING)

                self.assertNotEqual(
                    actual, _MISSING,
                    f"orchestrator/config.py не содержит константу "
                    f"'{name}' (ANSWER-1, AC-1)")
                self.assertEqual(
                    actual, expected,
                    f"orchestrator/config.{name} = {actual!r}, ожидалось "
                    f"{expected!r} (ANSWER-1, AC-1)")


if __name__ == "__main__":
    unittest.main()
