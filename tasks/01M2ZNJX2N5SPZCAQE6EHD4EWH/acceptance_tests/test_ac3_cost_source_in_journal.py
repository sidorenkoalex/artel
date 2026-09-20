"""AC-3: строка «agent cost KNOWN» несёт `источник=факт CLI`, строка
«agent cost PARTIAL» — `источник=расчёт по тарифу`, и разбивка по видам
с `actual_usd` в KNOWN читаются прежним `report._known_cost_breakdown`
без изменений.

Красен до реализации: `spend.charge_step`/`spend.charge_missing_result`
сегодня пишут детали без поля `источник=` вовсе (`orchestrator/spend.py`,
строки деталей KNOWN и PARTIAL) — обе проверки источника падают. Проверка
обратной читаемости строки KNOWN зелена уже сегодня и стоит здесь
барьером: источник обязан быть ДОБАВКОЙ к формату, а не его заменой.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import report, spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rates  # noqa: E402


class CostSourceTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.actual = _rates.actual_usd_for_coefficient(
            _rates.threshold() / 2)

    def test_ac3_known_line_names_the_cli_fact_as_its_source(self):
        """Завершённый шаг с фактом CLI: строка «agent cost KNOWN»
        называет источник стоимости — факт CLI.

        Ловит мутацию: разработчик добавляет источник только в ветку
        PARTIAL (там он «интереснее»: расчёт по тарифу), а строку KNOWN
        оставляет прежней — читатель журнала по-прежнему не отличает
        факт от расчёта именно там, где рядом теперь стоит и расчёт по
        курсу (AC-4).
        """
        spend.charge_step(self.conn, self.TASK, _rates.ROLE,
                          _rates.cost(self.actual), "попытка 1/3")

        known = _rates.details(self.conn, self.TASK, _rates.KNOWN_ACTION)
        self.assertEqual(len(known), 1, "AC-3: шаг обязан дать одну строку KNOWN")
        self.assertIn("источник=факт CLI", known[0])

    def test_ac3_partial_line_names_the_rate_calculation_as_its_source(self):
        """Шаг без финального события потока: строка «agent cost PARTIAL»
        называет источник стоимости — расчёт по тарифу.

        Ловит мутацию: разработчик пишет в обе строки одно и то же
        «источник=факт CLI» (копипаста ветки KNOWN) — тогда частичная
        сумма, посчитанная по курсу, выдаёт себя за факт CLI, и
        недоучёт шага PARTIAL (SPEC, «Контекст») снова нечем отличить
        от честной цены.
        """
        spend.charge_missing_result(
            self.conn, self.TASK, _rates.ROLE, "попытка 1/3", "таймаут шага",
            partial_tokens=_rates.TOKENS, saw_usage_event=True)

        partial = _rates.details(self.conn, self.TASK, _rates.PARTIAL_ACTION)
        self.assertEqual(len(partial), 1,
                         "AC-3: шаг обязан дать одну строку PARTIAL")
        self.assertIn("источник=расчёт по тарифу", partial[0])

    def test_ac3_known_line_is_still_read_back_by_known_cost_breakdown(self):
        """Строка KNOWN с новым источником и дописанным расчётом
        по-прежнему разбирается `report._known_cost_breakdown`: факт
        CLI и все четыре счётчика usage возвращаются без потерь.

        Ловит мутацию: дописывая источник и коэффициент, разработчик
        меняет форму уже существующих полей (переносит `actual_usd` в
        конец другим форматом, округляет его до центов, ставит пробелы
        вокруг `=` в счётчиках) — парсер отчёта вернёт `(None, None)`
        либо неполную разбивку, и вся сверка курса останется без
        данных, молча.
        """
        spend.charge_step(self.conn, self.TASK, _rates.ROLE,
                          _rates.cost(self.actual), "попытка 1/3")

        detail = _rates.details(self.conn, self.TASK, _rates.KNOWN_ACTION)[0]
        actual_usd, tokens_by_type = report._known_cost_breakdown(detail)
        self.assertIsNotNone(actual_usd,
                             "AC-3: факт CLI обязан читаться из строки KNOWN")
        self.assertAlmostEqual(actual_usd, self.actual, places=6)
        self.assertEqual(tokens_by_type, _rates.TOKENS)


if __name__ == "__main__":
    unittest.main()
