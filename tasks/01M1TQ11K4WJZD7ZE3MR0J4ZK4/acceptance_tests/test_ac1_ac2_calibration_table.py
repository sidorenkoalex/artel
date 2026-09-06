"""Приёмочные тесты 01M1TQ11K4WJZD7ZE3MR0J4ZK4 — AC-1 (калибровочная
таблица по числу критериев приёмки и числу файлов зоны) и AC-2
(граничные значения таблицы на 5/6 и 10/11 критериев).

Интерфейс, который фиксируют эти тесты (`_sandbox.py`, докстрока):
`orchestrator.budget.recommended_budget_usd(ac_count, zone_files) ->
float`. SPEC требования 1 называет только СОСТАВ таблицы (пороги и
значения ADR-0014), не имя функции/константы — тот же приём, что уже
применён `config.TOKEN_RATES` (tasks/01M1NWCM3TDY0YABEKE8DYQA1C/
acceptance_tests/test_ac1_token_rate_table.py): разработчик реализует
под форму, заданную планкой.

Значения проверяются не прямым вызовом функции (она ещё не
существует), а ЧЕРЕЗ гейт SPEC (`fsm.cmd_approve` на `spec_gate`) с
намеренно заниженным `budget_usd = $1` — при таком потолке предупреждение
AC-6/AC-10 «рамка ниже калибровки: $N против ~$M» обязано сработать при
ЛЮБОМ ориентире таблицы ($35/$45/$70 — все они больше, чем 1 * 3, порог
срабатывания «ниже более чем на треть»), а `M` в этой строке и есть
искомое значение таблицы для заданных (число AC-n, число файлов zones).

Число файлов зоны фиксировано на 1 всюду, где интересен только разрез
по числу критериев приёмки, — таблица требования 1 не описывает
поведение на 4 файлах зоны (единственный зазор между «до 3» и «5 и
более»), тесты его не трогают.

Красен до реализации, по двум разным причинам:

- `CalibrationTableIsNamedInConfigTest` — `orchestrator.config` сегодня
  не несёт атрибут `BUDGET_CALIBRATION_TABLE` (grep по `orchestrator/
  config.py` на «CALIBRATION» пуст) — `hasattr` падает первым же
  `assertTrue`.
- Все остальные тесты файла (`CalibrationTableValuesTest`/
  `CalibrationBoundariesTest`) — `orchestrator/fsm.py::_cmd_approve` на
  `spec_gate` сегодня печатает только строку «дальше: …» (grep по
  `orchestrator/fsm.py` и `orchestrator/budget.py` на «калибровки»/
  «ориентир» пуст). `WARNING_RE.search(out)` вернёт `None` для КАЖДОГО
  сценария, `assertIsNotNone` упадёт на первой же строке тела
  `_orientir`, ни один тест не дойдёт до сравнения чисел.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import GateHintSandbox, WARNING_RE  # noqa: E402
from orchestrator import config  # noqa: E402


class CalibrationTableIsNamedInConfigTest(unittest.TestCase):
    """AC-1 (часть «именованная константа/структура ... в
    orchestrator/config.py»): проверка МЕСТА, а не значений — значения
    проверяет `CalibrationTableValuesTest`/`CalibrationBoundariesTest`
    ниже через реальных потребителей."""

    def test_ac1_config_carries_a_named_calibration_table(self):
        """`orchestrator.config.BUDGET_CALIBRATION_TABLE` существует и
        не пуст — требование 1 явно называет местом таблицы
        `orchestrator/config.py`, не `budget.py`/`catalog.py`/`fsm.py`
        (которые её ТОЛЬКО читают).

        Ловит мутацию: калибровочные пороги зашиты литералами прямо в
        `budget.recommended_budget_usd` (или дублируются в `catalog.py`
        и `fsm.py` порознь) без единого именованного источника в
        `config.py` — `hasattr` падает.
        """
        self.assertTrue(
            hasattr(config, "BUDGET_CALIBRATION_TABLE"),
            "orchestrator.config не несёт именованную калибровочную "
            "таблицу BUDGET_CALIBRATION_TABLE (AC-1)")
        self.assertTrue(
            config.BUDGET_CALIBRATION_TABLE,
            "orchestrator.config.BUDGET_CALIBRATION_TABLE пуст")


class _CalibrationViaGateTest(GateHintSandbox):
    """Общий узел: заводит задачу с занижённым `budget_usd=1`, approve
    на `spec_gate`, извлекает `M` из строки предупреждения."""

    def _orientir(self, task_id: str, *, ac_count: int,
                  zone_files: int) -> float:
        sha = self.enter_spec_gate(task_id, ac_count=ac_count,
                                   zone_files=zone_files, budget_usd=1.0)
        out = self.approve(task_id, sha)
        match = WARNING_RE.search(out)
        self.assertIsNotNone(
            match,
            f"не нашёл строку предупреждения «рамка ниже калибровки» "
            f"в выводе approve: {out!r}")
        return float(match.group("m"))


class CalibrationTableValuesTest(_CalibrationViaGateTest):
    """AC-1: значения таблицы по представителям каждого уровня."""

    def test_ac1_baseline_tier_up_to_5_ac_and_3_files(self):
        """До 5 критериев и до 3 файлов зоны — ориентир $35.

        Ловит мутацию: базовый уровень таблицы заменён единым числом для
        всех размеров (например всегда $45) — значение перестаёт быть
        35.0 при заведомо маленьком SPEC (3 критерия, 2 файла).
        """
        self.assertEqual(
            self._orientir("01BGTCALTAC1BASE00000001", ac_count=3,
                           zone_files=2),
            35.0)

    def test_ac1_mid_tier_6_to_10_ac(self):
        """6-10 критериев (файлов зоны меньше порога «5 и более») —
        ориентир $45.

        Ловит мутацию: средний уровень таблицы не выделен отдельной
        веткой и возвращает то же значение, что и базовый уровень (8
        критериев даёт $35 вместо $45).
        """
        self.assertEqual(
            self._orientir("01BGTCALTAC1MID000000001", ac_count=8,
                           zone_files=2),
            45.0)

    def test_ac1_high_tier_by_ac_count_over_10(self):
        """Больше 10 критериев — ориентир $70 (даже при одном файле
        зоны, то есть срабатывает именно счётчик критериев, не файлов).

        Ловит мутацию: верхний уровень таблицы применяется только по
        числу файлов зоны, не по числу критериев — 12 критериев даёт
        $45 вместо $70.
        """
        self.assertEqual(
            self._orientir("01BGTCALTAC1HIAC00000001", ac_count=12,
                           zone_files=1),
            70.0)

    def test_ac1_high_tier_by_zone_files_5_or_more(self):
        """5 и более файлов зоны — ориентир $70 независимо от числа
        критериев (здесь их всего 2 — заведомо «базовый» диапазон по
        одной только этой оси).

        Ловит мутацию: условие «5 и более файлов зоны» не реализовано —
        таблица смотрит только на число критериев, и при 2 критериях/5
        файлах ориентир остаётся $35.
        """
        self.assertEqual(
            self._orientir("01BGTCALTAC1HIFILE0000001", ac_count=2,
                           zone_files=5),
            70.0)

    def test_ac1_recommendation_never_below_25_floor(self):
        """Даже на минимальном размере (1 критерий, 1 файл) итоговая
        рекомендация не ниже $25 — самый нижний уровень таблицы уже $35,
        то есть пол $25 не должен быть пробит вниз ни одним уровнем.

        Ловит мутацию: разработчик вводит более мелкую градацию ниже
        текущего базового уровня (например «1 критерий -> $20») в
        нарушение явного требования «итоговая рекомендация не ниже $25».
        """
        self.assertGreaterEqual(
            self._orientir("01BGTCALTAC1FLOOR0000001", ac_count=1,
                           zone_files=1),
            25.0)


class CalibrationBoundariesTest(_CalibrationViaGateTest):
    """AC-2: граничные значения 5/6 и 10/11 критериев (файлы зоны
    фиксированы на 1, ниже порога «5 и более», чтобы разрез шёл только
    по числу критериев)."""

    def test_ac2_boundary_5_ac_stays_baseline(self):
        """5 критериев — ещё базовый уровень ($35), не средний.

        Ловит мутацию «на единицу»: сравнение `ac_count <= 5` заменено
        на `ac_count < 5` — 5 критериев уже попадает в средний уровень,
        ориентир становится $45.
        """
        self.assertEqual(
            self._orientir("01BGTCALTAC2FIVE0000001", ac_count=5,
                           zone_files=1),
            35.0)

    def test_ac2_boundary_6_ac_enters_mid_tier(self):
        """6 критериев — уже средний уровень ($45), не базовый.

        Ловит мутацию «на единицу»: сравнение `ac_count <= 6` вместо
        `ac_count <= 5` — 6 критериев остаётся в базовом уровне,
        ориентир не поднимается выше $35.
        """
        self.assertEqual(
            self._orientir("01BGTCALTAC2SIX00000001", ac_count=6,
                           zone_files=1),
            45.0)

    def test_ac2_boundary_10_ac_stays_mid_tier(self):
        """10 критериев — ещё средний уровень ($45), не верхний.

        Ловит мутацию «на единицу»: сравнение `ac_count <= 10` заменено
        на `ac_count < 10` — 10 критериев уже попадает в верхний
        уровень, ориентир становится $70.
        """
        self.assertEqual(
            self._orientir("01BGTCALTAC2TEN00000001", ac_count=10,
                           zone_files=1),
            45.0)

    def test_ac2_boundary_11_ac_enters_high_tier(self):
        """11 критериев — уже верхний уровень ($70), не средний.

        Ловит мутацию «на единицу»: сравнение `ac_count > 11` вместо
        `ac_count > 10` — 11 критериев остаётся в среднем уровне,
        ориентир не поднимается до $70.
        """
        self.assertEqual(
            self._orientir("01BGTCALTAC2ELEVEN000001", ac_count=11,
                           zone_files=1),
            70.0)


if __name__ == "__main__":
    unittest.main()
