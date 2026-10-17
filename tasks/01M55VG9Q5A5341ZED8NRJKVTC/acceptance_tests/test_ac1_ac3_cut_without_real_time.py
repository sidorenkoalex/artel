"""Обрыв фонового `suite-run` в целевом тесте — настоящей строкой
`proc.wait(timeout=limit[0])` копии пульта и без N секунд реального времени.

Группа: разовый
Красен до реализации: целевой тест держит обрыв на реальных часах — между разметкой «до» и «обрыв» вызова proc.wait копии проходит N = 11–13 с реального времени (AC-1); AC-3 на сегодняшнем тесте зелён (обрыв уже делает настоящая строка :1598).

Целевой тест (`tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py::
SuiteRunProfileLimitTest::test_ac5_…`) прогоняется вложенным pytest во
временной копии рабочей копии кода, где вокруг строки
`proc.wait(timeout=limit[0])` в `_run_full_suite_to_log` дописана разметка
(`_mutant.py`): файл-метка до вызова, после возврата и в ветке
`TimeoutExpired`. Реальное время вызова — по mtime файлов-меток.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mutant  # noqa: E402

# Ожидание по реальным часам, от которого зависит исход (AC-1), — не длиннее.
REAL_WAIT_CEILING = 5.0


class CutWithoutRealTimeTest(unittest.TestCase):

    def test_ac1_cut_happens_without_n_real_seconds(self):
        """Обрыв прогона ветки наступает раньше N секунд реального времени.

        Сценарий: целевой тест в размеченной копии; он обязан быть зелёным, а
        у каждого вызова `proc.wait(timeout=limit[0])` копии, кончившегося
        `TimeoutExpired`, между меткой «до» и меткой «обрыв» прошло меньше
        переданного предела N и не больше 5 с реального времени.

        Ловит мутацию: тест оставлен на реальных часах (обрыв по истечении
        настоящих N = 11–13 с при пробнике на 100 с) — у вызова с обрывом
        реальное время ≥ N, метод красен.
        """
        run = _mutant.instrumented_run()
        self.assertTrue(run.green, run.context("целевой тест не зелёный"))
        cuts = [c for c in run.calls if c.end == "timeout"]
        self.assertTrue(cuts, run.context("обрыва строкой proc.wait копии нет"))
        for call in cuts:
            self.assertLess(call.elapsed, call.limit, run.context(
                f"обрыв по пределу {call.limit} с занял {call.elapsed:.2f} с "
                f"реального времени — не меньше самого предела"))
            self.assertLessEqual(call.elapsed, REAL_WAIT_CEILING, run.context(
                f"ожидание обрыва {call.elapsed:.2f} с реального времени "
                f"длиннее {REAL_WAIT_CEILING} с"))

    def test_ac3_cut_is_made_by_real_wait_line_of_copy(self):
        """Обрыв выполняет настоящая строка `proc.wait(timeout=limit[0])` копии.

        Сценарий: целевой тест в размеченной копии зелёный (отчёт «не
        уложился» с N получен), и среди вызовов размеченной строки
        `_run_full_suite_to_log` копии есть вызов, кончившийся
        `TimeoutExpired` (метка «обрыв» после метки «до»).

        Ловит мутацию: тест подменяет заглушкой `acceptance.run_full_suite`,
        `_run_full_suite_now` или `_run_full_suite_to_log` копии (отчёт о
        таймауте выдаётся без настоящего ожидания) — размеченную строку
        никто не исполняет, меток «до»/«обрыв» нет, метод красен.
        """
        run = _mutant.instrumented_run()
        self.assertTrue(run.green, run.context("целевой тест не зелёный"))
        self.assertTrue(run.calls, run.context(
            "строка proc.wait(timeout=limit[0]) копии не исполнялась"))
        self.assertTrue(
            any(c.end == "timeout" for c in run.calls),
            run.context("ни один вызов размеченной строки не кончился "
                        "TimeoutExpired — обрыв сделан не ею"))


if __name__ == "__main__":
    unittest.main()
