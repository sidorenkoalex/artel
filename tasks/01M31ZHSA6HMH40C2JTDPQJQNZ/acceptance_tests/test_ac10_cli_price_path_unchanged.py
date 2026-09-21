"""AC-10 — 01M31ZHSA6HMH40C2JTDPQJQNZ: провайдер с `cost_from_cli: true`
и ценой в итоге запуска идёт прежним путём, а отсутствие итога запуска
даёт прежние UNKNOWN/PARTIAL/ESTIMATED/LOST.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. Провайдер с `cost_from_cli: true` и ценой в итоге даёт прежнюю
строку «agent cost KNOWN» с `источник=факт CLI`, полем `actual_usd=`,
разбивкой по видам, датой тарифа и коэффициентом сверки; отсутствие итога
запуска даёт прежние «agent cost UNKNOWN»/«agent cost PARTIAL»/«agent
cost ESTIMATED»/«agent cost LOST» с прежними алертами.

Зелёный с рождения: это тест сохранения существующего поведения — путь
факта CLI сегодня работает именно так (провайдер репозитория `claude`
помечен в каталоге `cost_from_cli: true`). Красным он станет, если
переезд разбора к провайдеру уведёт шаг с ценой от CLI на расчёт по
тарифу или потеряет одну из четырёх веток учёта без финального события.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _run  # noqa: E402
import _sample  # noqa: E402
from orchestrator import config, spend  # noqa: E402


class CliPricePathTest(_run.StepRunSandbox):

    def test_ac10_price_from_cli_gives_the_known_line(self):
        """Шаг с ценой в итоге запуска списывается фактом CLI: строка
        KNOWN с источником, полной ценой, разбивкой по видам, датой
        тарифа и коэффициентом сверки.

        Ловит мутацию: ветка расчёта по тарифу (требование 4) написана
        так, что забирает и шаг с ценой от CLI — `spent_usd` начинает
        расходиться с фактическим счётом провайдера, а сверка тарифа с
        фактом теряет свой единственный источник.
        """
        self.run_stream(_sample.STREAM)

        self.assertAlmostEqual(self.task_row()["spent_usd"],
                               _sample.EXPECTED_COST_USD)
        detail = self.details(_run.KNOWN)[-1]
        self.assertIn(_run.SOURCE_CLI, detail)
        self.assertIn("actual_usd=", detail)
        self.assertIn(spend.role_tariff(self.ROLE).calibrated_at, detail)
        self.assertIn("коэффициент", detail)
        actual_usd, tokens_by_type = spend.known_cost_breakdown(detail)
        self.assertAlmostEqual(actual_usd, _sample.EXPECTED_COST_USD)
        self.assertEqual(_sample.normalized(tokens_by_type),
                         _sample.EXPECTED_COST_BY_KIND)

    def test_ac10_stream_without_a_result_event_stays_unknown(self):
        """Поток, завершившийся без финального события (и без таймаута),
        по-прежнему даёт «agent cost UNKNOWN» и не трогает `spent_usd`.

        Ловит мутацию: «итога запуска нет» и «итог есть, но без цены»
        слиты в одну ветку — шаг, чей вывод вовсе не дошёл, начинает
        списываться расчётом по тарифу по обрывкам usage, и недоучёт
        превращается в переучёт.
        """
        self.run_stream(_sample.STREAM_WITHOUT_RESULT)

        self.assertEqual(self.task_row()["spent_usd"], 0.0)
        self.assertEqual(len(self.details(_run.UNKNOWN)), 1,
                         self.journal_text())
        self.assertEqual(self.details(_run.KNOWN), [])

    def test_ac10_timeout_with_usage_events_still_gives_partial(self):
        """Таймаут шага с usage-событиями в потоке по-прежнему даёт
        «agent cost PARTIAL» с суммой по тарифу и без алерта неизвестной
        стоимости.

        Ловит мутацию: ветка «финального события нет» перестаёт получать
        накопленные вживую токены (их разбор переехал к провайдеру, а
        путь таймаута остался на старом) — прерванный шаг снова стоит
        ноль.
        """
        self.run_timeout(_sample.STREAM_WITHOUT_RESULT)

        self.assertGreater(self.task_row()["spent_usd"], 0.0)
        detail = self.details(_run.PARTIAL)[-1]
        self.assertIn(_run.SOURCE_TARIFF, detail)
        self.assertEqual(
            [a for a in self.alerts() if a["source"] == "spend.unknown_cost"],
            [], "usage-события были — алерт неизвестной стоимости не нужен")

    def test_ac10_estimated_and_lost_paths_keep_their_alerts(self):
        """Роль без разрешимого тарифа даёт «agent cost ESTIMATED» с
        верхней оценкой и алертом `threshold`, а попытка вовсе без
        usage-событий — «agent cost LOST» с алертом `incident`.

        Ловит мутацию: обе ветки схлопнуты в одну (или алерт заводится
        только у одной из них) — шаг, о котором нечего сказать вовсе,
        перестаёт отличаться от шага, чью стоимость просто не по чему
        посчитать, и один из двух сигналов Оператору исчезает.
        """
        spend.charge_missing_result(
            self.conn, self.TASK, "verifier", "попытка 1/3", "таймаут шага",
            partial_tokens={"input_tokens": 42}, saw_usage_event=True)
        spend.charge_missing_result(
            self.conn, self.TASK, self.ROLE, "попытка 1/3",
            "обрыв stdout-пайпа", partial_tokens={}, saw_usage_event=False)

        row = self.task_row()
        self.assertEqual(row["spent_usd"], 0.0)
        self.assertAlmostEqual(row["spent_estimate_usd"],
                               config.STEP_COST_ESTIMATE_USD)
        self.assertEqual(len(self.details(_run.ESTIMATED)), 1,
                         self.journal_text())
        self.assertEqual(len(self.details(_run.LOST)), 1, self.journal_text())
        kinds = {alert["kind"] for alert in self.alerts()}
        self.assertIn("threshold", kinds)
        self.assertIn("incident", kinds)


if __name__ == "__main__":
    unittest.main()
