"""Приёмочные тесты AC-8, AC-9: четвёртый уровень и пересмотренные нижние
уровни калибровочной таблицы `config.BUDGET_CALIBRATION_TABLE`, плюс
комментарий над ней с датой пересчёта, выборкой и правилом выбора уровня
(SPEC, требования 6-7).

Текст `orchestrator/config.py` читается через `inspect.getsource` самого
импортированного модуля — без обращения к файловой системе рабочей копии.

Красен до реализации: таблица сегодня трёхуровневая ($35 / $45 / $70),
четвёртого уровня нет и рекомендации не совпадают ни с одним числом AC-8;
комментарий над таблицей не несёт ни даты пересчёта, ни выборки, ни
правила 80-го перцентиля.
"""
import inspect
import unittest

from orchestrator import budget, config

# Ожидания AC-8 дословно: (критериев приёмки, файлов зоны) -> рекомендация $.
EXPECTED_LEVELS = (
    ((5, 3), 25.0),
    ((10, 4), 40.0),
    ((15, 7), 45.0),
    ((20, 9), 85.0),
)


def comment_above(source: str, name: str) -> str:
    """Непрерывный блок комментариев непосредственно НАД присваиванием
    `name` в тексте модуля; пустая строка — присваивания нет."""
    lines = source.splitlines()
    at = next((i for i, line in enumerate(lines)
               if line.startswith(f"{name} =")), None)
    if at is None:
        return ""
    block = []
    cursor = at - 1
    while cursor >= 0 and lines[cursor].lstrip().startswith("#"):
        block.append(lines[cursor])
        cursor -= 1
    return "\n".join(reversed(block))


class BudgetCalibrationTest(unittest.TestCase):
    """Рекомендация потолка по новой таблице и её пол."""

    def test_ac8_each_level_and_the_floor_of_the_recommendation(self):
        """Четыре контрольные точки AC-8 — по одной на каждый уровень
        новой таблицы — и пол рекомендации на сетке входов.

        Рекомендация на любом входе не ниже
        `config.BUDGET_CALIBRATION_FLOOR_USD` (значение читается из
        config, а не литералом: пол — крутилка Оператора).

        Ловит мутацию: четвёртый уровень дописан в таблицу ПОСЛЕ
        неограниченного «всё остальное» — уровни проверяются по порядку,
        и вход (20, 9) добирает старые $70, так и не дойдя до $85.
        """
        for (ac_count, zone_files), expected in EXPECTED_LEVELS:
            with self.subTest(ac_count=ac_count, zone_files=zone_files):
                self.assertEqual(
                    budget.recommended_budget_usd(ac_count, zone_files),
                    expected,
                    f"({ac_count} критериев приёмки, {zone_files} файлов "
                    f"зоны) — ${expected:.2f} по новой таблице")

        for ac_count in range(0, 25):
            for zone_files in range(0, 15):
                self.assertGreaterEqual(
                    budget.recommended_budget_usd(ac_count, zone_files),
                    config.BUDGET_CALIBRATION_FLOOR_USD,
                    f"рекомендация на входе ({ac_count}, {zone_files}) ниже "
                    f"пола ${config.BUDGET_CALIBRATION_FLOOR_USD:.2f}")

    def test_ac9_comment_above_the_table_names_date_sample_and_rule(self):
        """Комментарий непосредственно над `BUDGET_CALIBRATION_TABLE` в
        `orchestrator/config.py`.

        Обязан нести дату пересчёта 21.09.2026, выборку (задачи done
        сентября со снятыми зонами) и правило выбора уровня по 80-му
        перцентилю факта своей группы.

        Ловит мутацию: числа таблицы пересчитаны, а комментарий над ней
        оставлен прежним — происхождение новых уровней перестаёт быть
        прослеживаемым, и следующий пересчёт снова идёт вслепую.
        """
        comment = comment_above(inspect.getsource(config),
                                "BUDGET_CALIBRATION_TABLE")

        self.assertTrue(comment,
                        "над BUDGET_CALIBRATION_TABLE нет блока комментариев")
        lowered = comment.lower()
        self.assertIn("21.09.2026", comment,
                      f"дата пересчёта не названа:\n{comment}")
        self.assertIn("done", lowered,
                      f"выборка не названа состоянием задач:\n{comment}")
        self.assertIn("сентябр", lowered,
                      f"выборка не названа месяцем:\n{comment}")
        self.assertIn("зон", lowered,
                      f"выборка не названа снятыми зонами:\n{comment}")
        self.assertIn("перцентил", lowered,
                      f"правило выбора уровня не названо:\n{comment}")
        self.assertIn("80", comment,
                      f"правило выбора уровня — 80-й перцентиль:\n{comment}")


if __name__ == "__main__":
    unittest.main()
