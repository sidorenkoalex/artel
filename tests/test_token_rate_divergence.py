"""Юнит-тесты сверки курса токенов с фактом CLI при записи шага
(SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требования 1-9).

Курс роли (`config.TOKEN_RATES`) и порог алерта
(`config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD`) — крутилки Оператора
(ADR-0002, класс «лимит»): кроме разбора самой таблицы курса (требование
1, где числа названы SPEC дословно), тесты читают их из `config`, а
расчёт по курсу — через `spend.partial_cost_usd`, и переживают поворот
любой из крутилок.
"""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, config, report, spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

ROLE = "developer"
AGENT_ROLES = ("analyst", "test_author", "developer", "reviewer")

# Прейскурант opus-5 за токен (требование 1) — числа SPEC дословно.
OPUS5_PRICES = {
    "input_usd_per_token": 0.000005,
    "output_usd_per_token": 0.000025,
    "cache_creation_usd_per_token": 0.00000625,
    "cache_read_usd_per_token": 0.0000005,
}
CALIBRATED_AT = "2026-09-20"

# Разбивка usage характерного шага: почти весь объём — чтения кэша.
TOKENS = {"input_tokens": 40_000,
          "output_tokens": 20_000,
          "cache_creation_input_tokens": 60_000,
          "cache_read_input_tokens": 2_000_000}


def cost(actual_usd: float, tokens: dict | None = TOKENS) -> dict:
    """Стоимость шага в форме `spend.parse_cost_event`."""
    return {"usd": actual_usd,
            "tokens": sum(tokens.values()) if tokens else None,
            "tokens_by_type": tokens}


class TokenRatesTableTest(unittest.TestCase):
    """Требование 1: курс всех четырёх agent-ролей — прейскурант opus-5."""

    def test_every_agent_role_carries_opus5_prices_and_the_september_date(self):
        """Ловит мутацию: цены подняты не во всех четырёх записях
        таблицы (копипаста трёх блоков из четырёх) либо подняты без
        сдвига `calibrated_at` — тогда сверка пошла бы с даты чужой
        модели, и `subTest` назвал бы отставшую роль поимённо."""
        for role in AGENT_ROLES:
            with self.subTest(role=role):
                rate = config.TOKEN_RATES[role]
                for field, price in OPUS5_PRICES.items():
                    self.assertEqual(rate[field], price)
                self.assertEqual(rate["calibrated_at"], CALIBRATED_AT)


class DivergenceMathTest(TaskSeededTmpRootTest):
    """`spend.check_rate_divergence` — единственная математика сверки
    (требование 6): сумма расчёта против суммы фактов.

    Песочница здесь не ради данных (пары считаются прямо в тестах), а
    ради `store.db()`: без подмены путей `config` соединение легло бы в
    настоящий `.artel/state.db` пульта."""

    def test_coefficient_is_the_sum_ratio_not_the_average_of_steps(self):
        """Ловит мутацию: расчёт усредняет коэффициенты шагов вместо
        деления суммы на сумму — на паре «крупный расходящийся шаг плюс
        мелкий точный» среднее даёт 0.25, а сумма против суммы — 0.099,
        и `assertAlmostEqual` разойдётся."""
        pairs = [(12.5, 10.0), (1.0, 1.0)]

        divergence = spend.check_rate_divergence(store.db(), ROLE, pairs)

        self.assertAlmostEqual(divergence["coefficient"], 2.5 / 11.0)
        self.assertEqual(divergence["steps"], 2)
        self.assertEqual(divergence["since"], config.TOKEN_RATES[ROLE]["calibrated_at"])

    def test_nothing_to_compare_is_none_not_zero(self):
        """Ловит мутацию: пустая выборка трактуется как «расхождения
        нет» и возвращает 0.0 — роль без шагов попала бы в отчёт нулём,
        неотличимая от роли, чей курс реально сошёлся с фактом."""
        self.assertIsNone(spend.check_rate_divergence(store.db(), ROLE, []))

    def test_role_without_a_rate_is_not_compared(self):
        """Ловит мутацию: сверка идёт и для роли без курса (`verifier`)
        — даты, с которой её считать, нет, и коэффициент считался бы по
        шагам неизвестного периода."""
        self.assertIsNone(spend.check_rate_divergence(
            store.db(), "verifier", [(1.0, 2.0)]))


class ChargeStepJournalTest(TaskSeededTmpRootTest):
    """Требования 2-5: источник стоимости, расчёт и коэффициент в строке
    KNOWN, фильтр по дате калибровки, тихий пропуск без usage."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.calculated = spend.partial_cost_usd(ROLE, TOKENS)
        self.threshold = config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD

    def actual_for(self, coefficient: float) -> float:
        """Факт CLI, дающий ровно заданный коэффициент расхождения."""
        return self.calculated / (1.0 + coefficient)

    def details(self, action: str) -> list:
        return [row["detail"] for row in store.task_steps(self.conn, self.TASK)
                if row["action"] == action]

    def divergence_alerts(self) -> list:
        return [row for row in alerts.open_alerts(self.conn, "warning")
                if row["source"] == alerts.TOKEN_RATE_DIVERGENCE_SOURCE]

    def backdate_known_rows(self) -> None:
        """Состаривает записанные строки KNOWN на день раньше даты
        калибровки курса — «шаги другой модели»."""
        day = date.fromisoformat(
            config.TOKEN_RATES[ROLE]["calibrated_at"]) - timedelta(days=1)
        self.conn.execute("UPDATE steps SET ts=? WHERE action=?",
                          (f"{day} 12:00:00Z", spend.KNOWN_COST_JOURNAL_ACTION))
        self.conn.commit()

    def test_known_line_names_the_fact_and_carries_calculation_and_coefficient(self):
        """Ловит мутацию: строка KNOWN остаётся прежней (без источника,
        расчёта и коэффициента) — читатель журнала снова не отличает
        факт CLI от расчёта по тарифу и не видит расхождения до запуска
        отчёта."""
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.actual_for(self.threshold / 2)),
                          "попытка 1/3")

        detail = self.details(spend.KNOWN_COST_JOURNAL_ACTION)[-1]
        self.assertIn("источник=факт CLI", detail)
        self.assertIn(f"расчёт по курсу=${self.calculated:.4f}", detail)
        self.assertIn(f"коэффициент роли с {CALIBRATED_AT}="
                      f"{self.threshold / 2:.2f}", detail)

    def test_partial_line_names_the_rate_as_its_source(self):
        """Ловит мутацию: источник дописан только в ветку KNOWN —
        частичная сумма по курсу (шаг без финального события потока)
        продолжает выдавать себя за счёт CLI."""
        spend.charge_missing_result(
            self.conn, self.TASK, ROLE, "попытка 1/3", "таймаут шага",
            partial_tokens=TOKENS, saw_usage_event=True)

        self.assertIn("источник=расчёт по тарифу",
                      self.details("agent cost PARTIAL")[-1])

    def test_spent_usd_gets_the_cli_fact_not_the_calculation(self):
        """Ловит мутацию: начисление подменяется расчётом по курсу (или
        расчёт прибавляется вторым `store.charge`) — `spent_usd`
        разъедется со счётом CLI, и весь бюджетный контур станет считать
        деньги по калибровочной таблице."""
        actual = self.actual_for(2 * self.threshold)
        self.assertGreater(abs(self.calculated - actual), 0.01)

        spend.charge_step(self.conn, self.TASK, ROLE, cost(actual),
                          "попытка 1/3")

        row = self.conn.execute("SELECT * FROM tasks WHERE id=?",
                                (self.TASK,)).fetchone()
        self.assertAlmostEqual(row["spent_usd"], actual, places=6)

    def test_steps_older_than_the_calibration_date_stay_out_of_the_check(self):
        """Ловит мутацию: сверка идёт по всем строкам KNOWN роли без
        фильтра по дате — шаги Sonnet и opus-5 складываются в одну
        сумму, и коэффициент свежей строки уедет с нуля."""
        self.charge_stale_then_fresh()

        coefficient = self.details(spend.KNOWN_COST_JOURNAL_ACTION)[-1]
        self.assertIn(f"коэффициент роли с {CALIBRATED_AT}=0.00", coefficient)

    def charge_stale_then_fresh(self) -> None:
        """Один сильно расходящийся шаг, состаренный до даты калибровки,
        и один свежий шаг ровно по курсу."""
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.actual_for(4 * self.threshold)),
                          "попытка 1/3")
        self.backdate_known_rows()
        spend.charge_step(self.conn, self.TASK, ROLE, cost(self.calculated),
                          "попытка 2/3")

    def test_step_without_usage_breakdown_is_charged_silently(self):
        """Ловит мутацию: сверка считается до проверки пустой разбивки —
        расчёт по пустому usage равен нулю, коэффициент выходит 1.0
        («расхождение на все сто»), и каждый такой шаг открывал бы
        ложный алерт."""
        note = spend.charge_step(self.conn, self.TASK, ROLE,
                                 cost(3.75, tokens={}), "попытка 1/3")

        self.assertIn("стоимость", note)
        self.assertEqual(self.details(spend.KNOWN_COST_JOURNAL_ACTION), [])
        self.assertEqual(self.divergence_alerts(), [])

    def test_coefficient_above_the_threshold_raises_the_alert_at_charge_step(self):
        """Ловит мутацию: коэффициент считается, но алерт остаётся за
        отчётом — сигнал снова ждёт запуска `report`, которого может не
        быть неделями (SPEC, «Контекст»)."""
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.actual_for(2 * self.threshold)),
                          "попытка 1/3")

        raised = self.divergence_alerts()
        self.assertEqual(len(raised), 1)
        self.assertIsNone(raised[0]["target"])
        self.assertIn(ROLE, raised[0]["message"])

    def test_coefficient_below_the_threshold_raises_nothing(self):
        """Ловит мутацию: алерт заводится на любое ненулевое
        расхождение (сравнение с порогом потеряно при переносе расчёта
        из отчёта в запись шага) — порог перестаёт значить что-либо."""
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.actual_for(self.threshold / 2)),
                          "попытка 1/3")

        self.assertEqual(self.divergence_alerts(), [])

    def test_repeated_divergence_of_the_same_role_keeps_one_alert(self):
        """Ловит мутацию: алерт заводится через `alerts.raise_alert`
        напрямую — дедуп там по точному тексту, а текст несёт растущие
        суммы и число шагов, так что каждый шаг плодил бы копию одного
        сигнала."""
        for numbered in ("попытка 1/3", "попытка 2/3"):
            spend.charge_step(self.conn, self.TASK, ROLE,
                              cost(self.actual_for(2 * self.threshold)),
                              numbered)

        self.assertEqual(len(self.divergence_alerts()), 1)


class ReportDivergenceTest(TaskSeededTmpRootTest):
    """Требования 6-7: отчёт считает тем же расчётом, с той же даты, и
    называет дату и число вошедших шагов."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.calculated = spend.partial_cost_usd(ROLE, TOKENS)

    def test_report_agrees_with_the_journal_line_on_one_coefficient(self):
        """Ловит мутацию: в `charge_step` заведён собственный расчёт
        (например, среднее по шагам), а `token_rate_divergence` оставлен
        прежним — две цифры по одним данным разойдутся, и Оператор не
        сможет сказать, какой верить."""
        threshold = config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.calculated / (1.0 + threshold / 2)),
                          "попытка 1/3")

        divergence = report.token_rate_divergence(self.conn)

        self.assertAlmostEqual(divergence[ROLE]["coefficient"], threshold / 2,
                               places=2)
        self.assertEqual(divergence[ROLE]["steps"], 1)
        self.assertEqual(divergence[ROLE]["since"], CALIBRATED_AT)

    def test_report_line_names_the_date_and_the_number_of_steps(self):
        """Ловит мутацию: строка отчёта остаётся прежней (только
        коэффициент) — читатель не может сказать, по какому периоду и по
        скольким шагам посчитана цифра."""
        line = report._divergence_html(
            {ROLE: {"coefficient": 0.12, "steps": 7, "since": CALIBRATED_AT}})

        self.assertIn("коэффициент расхождения 0.12", line)
        self.assertIn("по 7 шагам", line)
        self.assertIn(CALIBRATED_AT, line)

    def test_role_without_fresh_steps_is_absent_from_the_result(self):
        """Ловит мутацию: роль без шагов с даты калибровки попадает в
        результат нулём — отчёт заявлял бы сошедшийся курс там, где его
        вообще не с чем сверять."""
        self.assertEqual(report.token_rate_divergence(self.conn), {})


if __name__ == "__main__":
    unittest.main()
