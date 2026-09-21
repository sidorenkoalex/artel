"""Юнит-тесты четырёхуровневой калибровочной таблицы
`config.BUDGET_CALIBRATION_TABLE` и её читателя
`budget.recommended_budget_usd` (SPEC 01M31DRD81092HB69J0MAKZMGH,
требования 6-7).

Планка задачи (`tasks/01M31DRD81092HB69J0MAKZMGH/acceptance_tests/
test_ac8_ac9_budget_calibration.py`) проверяет четыре контрольные точки и
пол рекомендации. Здесь — свойства самой таблицы, которые ни одна
контрольная точка не ловит: порядок уровней, ограниченность всех, кроме
последнего, и монотонность ответа по обеим осям. Именно эти свойства
делают «первый подошедший уровень побеждает» осмысленным правилом: без
них дописанный не туда уровень тихо перехватывает чужие входы, оставаясь
зелёным на любых четырёх точках.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import budget, config  # noqa: E402


class CalibrationTableShapeTest(unittest.TestCase):
    """Форма таблицы: уровни, их порядок и замыкающий уровень."""

    def test_only_the_last_level_is_unbounded_and_it_is_the_last(self):
        """Неограниченный уровень (`None` по обеим осям) в таблице ровно
        один и стоит последним.

        Ловит мутацию: новый уровень дописан ПОСЛЕ неограниченного «всё
        остальное» — до него не доходит ни один вход, и таблица молча
        продолжает работать по-старому, оставаясь внешне четырёхуровневой.
        """
        table = config.BUDGET_CALIBRATION_TABLE
        unbounded = [i for i, (_, max_ac, max_files) in enumerate(table)
                     if max_ac is None and max_files is None]

        self.assertEqual(len(table), 4, "таблица четырёхуровневая")
        self.assertEqual(unbounded, [len(table) - 1],
                         f"неограниченный уровень обязан быть ровно один и "
                         f"последним: {table}")

    def test_bounded_levels_widen_strictly_from_first_to_last(self):
        """Потолки осей у ограниченных уровней строго растут сверху вниз.

        Ловит мутацию: уровни переставлены местами (или потолок сужен) —
        более широкий уровень оказывается выше более узкого и перехватывает
        его входы первым, а узкий становится мёртвым кодом.
        """
        bounded = [lvl for lvl in config.BUDGET_CALIBRATION_TABLE
                   if lvl[1] is not None and lvl[2] is not None]

        for earlier, later in zip(bounded, bounded[1:]):
            self.assertLess(earlier[1], later[1],
                            f"ось критериев приёмки не растёт: {bounded}")
            self.assertLess(earlier[2], later[2],
                            f"ось файлов зоны не растёт: {bounded}")

    def test_no_level_sits_below_the_floor_of_the_recommendation(self):
        """Ни один уровень таблицы не ниже
        `config.BUDGET_CALIBRATION_FLOOR_USD`.

        Ловит мутацию: уровень пересчитан ниже пола — `max(...)` в
        `recommended_budget_usd` молча вытягивает ответ обратно к полу, и
        заявленное число таблицы перестаёт что-либо значить, не сломав ни
        одного теста рекомендации.
        """
        for amount, max_ac, max_files in config.BUDGET_CALIBRATION_TABLE:
            with self.subTest(level=(amount, max_ac, max_files)):
                self.assertGreaterEqual(amount,
                                        config.BUDGET_CALIBRATION_FLOOR_USD)


class RecommendationMonotonicityTest(unittest.TestCase):
    """Ответ `recommended_budget_usd` на сетке входов."""

    GRID_AC = range(0, 26)
    GRID_FILES = range(0, 16)

    def test_recommendation_never_falls_when_a_task_grows(self):
        """Рост числа критериев приёмки или числа файлов зоны не может
        УМЕНЬШИТЬ рекомендацию.

        Ловит мутацию: значения уровней перепутаны местами (скажем, $45
        оказалось выше $40 по таблице) — более крупная задача получает
        ориентир ниже, чем более мелкая, и предупреждение «рамка ниже
        калибровки» начинает срабатывать наоборот.
        """
        for ac_count in self.GRID_AC:
            for files in self.GRID_FILES:
                here = budget.recommended_budget_usd(ac_count, files)
                self.assertLessEqual(
                    here, budget.recommended_budget_usd(ac_count + 1, files),
                    f"рост критериев приёмки уронил ориентир на "
                    f"({ac_count}, {files})")
                self.assertLessEqual(
                    here, budget.recommended_budget_usd(ac_count, files + 1),
                    f"рост файлов зоны уронил ориентир на "
                    f"({ac_count}, {files})")

    def test_every_level_of_the_table_is_reachable_on_the_grid(self):
        """Каждый уровень таблицы кто-то из сетки входов действительно
        получает.

        Ловит мутацию: уровень перекрыт соседом по обеим осям и
        недостижим — таблица выглядит четырёхуровневой, а раздаёт три
        значения, и пересчёт «поднял потолок для крупных задач», ничего не
        изменив.
        """
        reachable = {budget.recommended_budget_usd(ac, files)
                     for ac in self.GRID_AC for files in self.GRID_FILES}
        levels = {max(amount, config.BUDGET_CALIBRATION_FLOOR_USD)
                  for amount, _, _ in config.BUDGET_CALIBRATION_TABLE}

        self.assertEqual(levels - reachable, set(),
                         f"недостижимые уровни таблицы: {levels - reachable}")

    def test_the_spec_of_this_task_lands_on_its_own_new_level(self):
        """Сама эта задача (9 критериев приёмки, 5 путей зоны) по новой
        таблице получает ориентир $45 — ровно свою рамку, без
        предупреждения «рамка ниже калибровки».

        Ловит мутацию: границы третьего уровня заданы уже заявленных (15
        критериев приёмки / 7 файлов зоны) — типовая задача этого размера
        снова проваливается в верхний уровень, и предупреждение калибровки
        возвращается там, где расхождения нет.
        """
        orientir = budget.recommended_budget_usd(9, 5)

        self.assertEqual(orientir, 45.0)
        self.assertIsNone(budget.calibration_warning(45.0, orientir))


if __name__ == "__main__":
    unittest.main()
