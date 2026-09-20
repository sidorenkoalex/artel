"""AC-8: расчёт «сумма расчёта против суммы фактов» — один на обе точки
вызова: `report.token_rate_divergence` даёт тот же коэффициент, что
`charge_step` дописал в журнал, по умолчанию считает с даты
`calibrated_at` роли, и строка отчёта называет эту дату и число вошедших
в сверку шагов.

Форму возврата `token_rate_divergence` планка не диктует (числа роли
берутся через `_rates.numbers_in`) — критерий говорит о величине и о
строке отчёта, не о структуре словаря.

Красен до реализации: `report.token_rate_divergence` сегодня считает по
ВСЕМ строкам KNOWN роли без фильтра по дате, `charge_step` коэффициента
вовсе не пишет (сверять не с чем), а строка отчёта (`report.
_divergence_html`) несёт только сам коэффициент — ни даты, ни числа
шагов в ней нет.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import report, spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rates  # noqa: E402

# Шаги фикстуры: четыре — до даты калибровки (другая модель), два — после.
STALE_STEPS = 4
FRESH_STEPS = 2

DIV_RE = re.compile(r"<div[^>]*>(.*?)</div>", re.S)
# Целое число, стоящее в тексте само по себе: соседние цифры и точка
# исключены, чтобы под «число шагов» не попали куски даты (2026-09-20),
# суммы ($1.24) и коэффициента (0.26).
STANDALONE_INT_RE = re.compile(r"(?<![\d.])(\d+)(?![\d.])")


class OneCalculationTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.calculated = _rates.calculated_usd()

    def charge(self, actual: float, numbered: str) -> None:
        spend.charge_step(self.conn, self.TASK, _rates.ROLE,
                          _rates.cost(actual), numbered)

    def seed_stale_and_fresh_steps(self) -> None:
        """Шаги другой модели (состаренные до даты калибровки) и свежие
        шаги, чей факт CLI равен расчёту по курсу. Расхождение старых
        шагов — ниже порога алерта: панель алертов отчёта в этом
        сценарии обязана остаться пустой, иначе она сама заговорит о
        коэффициенте."""
        stale_actual = _rates.actual_usd_for_coefficient(
            _rates.threshold() / 2)
        for step in range(STALE_STEPS):
            self.charge(stale_actual, f"попытка {step + 1}/9")
        _rates.backdate_known_rows(self.conn)
        for step in range(FRESH_STEPS):
            self.charge(self.calculated, f"попытка {STALE_STEPS + step + 1}/9")

    def divergence_line(self) -> str:
        """Строка отчёта о расхождении курса для роли фикстуры."""
        self.capture(report.cmd_report)
        html = (self.root / ".artel" / "report.html").read_text(encoding="utf-8")
        found = [m.group(1) for m in DIV_RE.finditer(html)
                 if _rates.ROLE in m.group(1) and "коэффициент" in m.group(1)]
        self.assertEqual(
            len(found), 1,
            f"AC-8: отчёт обязан нести ровно одну строку расхождения "
            f"роли {_rates.ROLE!r}; найдено: {found}")
        return found[0]

    def test_ac8_report_line_names_the_calibration_date_and_step_count(self):
        """Строка отчёта о расхождении называет дату `calibrated_at`
        курса роли и число шагов, вошедших в сверку, — вошли только
        свежие шаги, не все записанные.

        Ловит мутацию: разработчик оставляет строку отчёта прежней
        (только коэффициент) или называет в ней ОБЩЕЕ число строк
        KNOWN роли вместо числа вошедших в сверку — читатель отчёта
        снова не может сказать, по какому периоду и по скольким шагам
        посчитана цифра, и молчаливое смешение двух моделей повторится
        незамеченным.
        """
        self.seed_stale_and_fresh_steps()

        line = self.divergence_line()
        self.assertIn(_rates.rate_date(), line,
                      "AC-8: строка отчёта обязана называть дату калибровки")
        numbers = STANDALONE_INT_RE.findall(line)
        self.assertIn(
            str(FRESH_STEPS), numbers,
            f"AC-8: строка отчёта обязана называть число шагов сверки "
            f"({FRESH_STEPS}); строка: {line}")
        self.assertNotIn(
            str(STALE_STEPS + FRESH_STEPS), numbers,
            f"AC-8: в сверку входят только шаги с даты калибровки — "
            f"общее число строк KNOWN роли не то же самое; строка: {line}")

    def test_ac8_divergence_defaults_to_steps_since_the_calibration_date(self):
        """`report.token_rate_divergence` по умолчанию (без аргументов)
        считает только с даты `calibrated_at` роли: свежие шаги идут
        ровно по курсу, поэтому коэффициент нулевой, а не тот, что дали
        бы все шесть шагов вместе.

        Ловит мутацию: фильтр по дате разработчик заводит только на
        пути `charge_step`, а отчёт оставляет считать по всем строкам
        KNOWN — две точки начинают показывать разные цифры по одним и
        тем же данным, и алерт отчёта снова срабатывает на смеси
        моделей.
        """
        self.seed_stale_and_fresh_steps()
        stale_actual = _rates.actual_usd_for_coefficient(
            _rates.threshold() / 2)
        everything = (STALE_STEPS + FRESH_STEPS) * self.calculated
        actual_sum = STALE_STEPS * stale_actual + FRESH_STEPS * self.calculated
        with_stale = abs(everything - actual_sum) / actual_sum
        self.assertGreater(
            with_stale, 0.05,
            "фикстура бессмысленна: со старыми шагами коэффициент обязан "
            "заметно отличаться от нуля")

        divergence = report.token_rate_divergence(self.conn)

        self.assertIn(_rates.ROLE, divergence,
                      "AC-8: роль со свежими шагами KNOWN обязана быть в сверке")
        numbers = _rates.numbers_in(divergence[_rates.ROLE])
        self.assertTrue(
            any(abs(number) <= 0.01 for number in numbers),
            f"AC-8: коэффициент роли обязан быть нулевым (в сверку вошли "
            f"только шаги по курсу); числа роли: {numbers}")
        self.assertFalse(
            any(abs(number - with_stale) <= 0.01 for number in numbers),
            f"AC-8: коэффициент {with_stale:.2f} — это сверка ВМЕСТЕ со "
            f"старыми шагами, она по умолчанию не считается; числа роли: "
            f"{numbers}")

    def test_ac8_charge_step_and_report_agree_on_one_coefficient(self):
        """Коэффициент, дописанный `charge_step` в строку KNOWN, и
        коэффициент, который по тем же данным даёт `report.
        token_rate_divergence`, — одно и то же число: расчёт живёт в
        одной функции, вторую математику никто не завёл.

        Ловит мутацию: разработчик пишет в `charge_step` собственный
        расчёт (например, среднее по шагам вместо суммы расчёта против
        суммы фактов), оставив `token_rate_divergence` как есть — две
        цифры по одним данным разойдутся, и Оператор не сможет сказать,
        какой из них верить.
        """
        expected = _rates.threshold() / 2
        self.charge(_rates.actual_usd_for_coefficient(expected), "попытка 1/3")
        journal_coefficient = _rates.coefficient_in(
            _rates.details(self.conn, self.TASK, _rates.KNOWN_ACTION)[-1])
        self.assertIsNotNone(
            journal_coefficient,
            "AC-8: сверить нечего — `charge_step` не дописал коэффициент "
            "(см. AC-4)")

        divergence = report.token_rate_divergence(self.conn)

        numbers = _rates.numbers_in(divergence.get(_rates.ROLE))
        self.assertTrue(
            any(abs(number - journal_coefficient) <= 0.01 for number in numbers),
            f"AC-8: отчёт обязан дать тот же коэффициент "
            f"{journal_coefficient}, что и строка журнала; числа роли: "
            f"{numbers}")


if __name__ == "__main__":
    unittest.main()
