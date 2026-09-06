"""Приёмочные тесты 01M1THKTJ7YT1K410G1KS17MK6 — AC-9 (`config.
SPLIT_SIGNAL_BUDGET_USD` пересчитан значением строго больше $45 и не
больше $70 (именованная константа с комментарием) — SPEC с
`budget_usd: 45` сигнал «подозрения на большой объём» не поднимает, SPEC
с `budget_usd: 70` — поднимает).

Числа 45/70 — литералы AC-9, не `config.*`: сама суть критерия — что
ИМЕННО эти два конкретных значения дают разные исходы, независимо от
того, какое ровно число из полуинтервала (45, 70] выберет разработчик
(тот же приём, что AC-9 задаёт SPEC буквально этими числами, не формулой
через порог).

Чёрный ящик над `guard.split_signal_names` — та же фикстура, что
`tests/test_guard_split_signals.py::BudgetSignalTest` уже держит для
сравнения с порогом (здесь — конкретные значения из AC-9, не сам порог).

Красен до реализации: сегодняшний `config.SPLIT_SIGNAL_BUDGET_USD == 30`
— сигнал «бюджет» уже поднимается и на 45, и на 70 (`budget >= 30` для
обоих), так что `test_ac9_budget_45_does_not_fire` красен именно потому,
что порог ещё не пересчитан.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, yamlmini  # noqa: E402
from scripts import guard  # noqa: E402
from _sandbox import spec_text  # noqa: E402


def _signal_names(text: str) -> list:
    return guard.split_signal_names(text, yamlmini.frontmatter(text))


class SplitSignalBudgetConstantRangeTest(unittest.TestCase):
    """Значение константы лежит в открыто-закрытом интервале (45, 70],
    как того требует AC-9.

    Ловит мутацию: константа пересчитана, но за пределы разрешённого
    диапазона (например, оставлена равной дефолту 50, что формально
    "строго больше 45", но округление до кратного пяти могло увести и
    ниже 46, и выше 70 при небрежной правке) — тест ловит оба края
    отдельными assert'ами.
    """

    def test_ac9_value_is_strictly_above_45(self):
        self.assertGreater(config.SPLIT_SIGNAL_BUDGET_USD, 45)

    def test_ac9_value_is_at_most_70(self):
        self.assertLessEqual(config.SPLIT_SIGNAL_BUDGET_USD, 70)


class SplitSignalBudgetConcreteValuesTest(unittest.TestCase):
    """SPEC c `budget_usd: 45` не поднимает сигнал «бюджет»; SPEC с
    `budget_usd: 70` — поднимает, независимо от того, какое именно
    число из (45, 70] выбрано порогом.

    Ловит мутацию: порог пересчитан НИЖЕ 46 (например, оставлен равным
    45 включительно, «не больше 70» перепутано с «не меньше 45») —
    тогда `budget_usd: 45` тоже поднимет сигнал, и первый тест упадёт.
    """

    def test_ac9_budget_45_does_not_fire(self):
        text = spec_text(schema_version=3, budget=45)

        names = _signal_names(text)

        self.assertNotIn("бюджет", names)

    def test_ac9_budget_70_fires(self):
        text = spec_text(schema_version=3, budget=70)

        names = _signal_names(text)

        self.assertIn("бюджет", names)


if __name__ == "__main__":
    unittest.main()
