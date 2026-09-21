"""Юнит-тесты сверки тарифа токенов с фактом CLI при записи шага
(SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требования 1-9; тариф на модель и пара
«роль, модель» — SPEC 01M300A14KRHCFB0DQXVCBJEKF, требования 1-4).

Действующий тариф (`spend.role_tariff`, каталог `models.yaml` плюс
локальный слой) и порог алерта
(`config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD`) — крутилки Оператора
(ADR-0002, класс «лимит»): тесты читают их из пульта, а расчёт по тарифу
— через `spend.partial_cost_usd`, и переживают поворот любой из крутилок.

Строки журнала пишутся тем же `numbered`, какой отдаёт `spend.py` сам
`orchestrator/runner.py` (`_numbered_with_model`): с 19.09 он несёт
`model=<идентификатор>`, и без этого поля строка в сверку не входит
вовсе (требование 3 SPEC 01M300A14KRHCFB0DQXVCBJEKF).
"""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, config, report, spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

ROLE = "developer"

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


class RoleTariffTest(TaskSeededTmpRootTest):
    """Требование 1 SPEC 01M300A14KRHCFB0DQXVCBJEKF: цена шага — тариф
    МОДЕЛИ роли, а не запись по роли."""

    def test_role_tariff_is_the_tariff_of_the_model_of_its_tier(self):
        """Тариф роли — тариф модели, на которую ведёт её ярус: тот же
        объект, что отдаёт разрешение цепочки, с той же датой.

        Ловит мутацию: цена снова ищется по имени роли (словарь «роль →
        тариф» переехал из `config` в другое место, но остался по роли) —
        смена модели яруса перестала бы менять цену шага, ровно как в
        инциденте 13.09-20.09."""
        from orchestrator import models

        resolved = models.resolve_role(ROLE)
        effective = spend.role_tariff(ROLE)

        self.assertEqual(effective.model, resolved.model)
        self.assertEqual(effective.tariff, resolved.tariff)
        self.assertEqual(spend.rate_calibrated_at(ROLE),
                         resolved.calibrated_at)

    def test_role_without_a_resolvable_chain_has_no_tariff(self):
        """Роль без яруса (`verifier`, `executor: none`) тарифа не имеет —
        `None`, а не нулевая цена.

        Ловит мутацию: неразрешимая цепочка деградирует в тариф из нулей
        — шаг такой роли считался бы бесплатным, и недоучёт снова копился
        бы молча (SPEC 01M1NWCM3TDY0YABEKE8DYQA1C, «Контекст»)."""
        self.assertIsNone(spend.role_tariff("verifier"))
        self.assertIsNone(spend.rate_calibrated_at("verifier"))


class JournalModelTest(unittest.TestCase):
    """Требование 2-3 SPEC 01M300A14KRHCFB0DQXVCBJEKF: модель шага
    читается из поля `model=` строки журнала."""

    def test_identifier_is_read_without_the_trailing_colon(self):
        """`charge_step` приписывает к `numbered` двоеточие с пробелом —
        в идентификатор модели оно не входит.

        Ловит мутацию: разбор берёт всё до пробела вместе с двоеточием —
        `claude-opus-5:` не находится в каталоге, тариф не разрешается, и
        КАЖДАЯ строка журнала тихо выпадает из сверки: контур молчит не
        потому, что расхождения нет, а потому, что сверять стало нечего."""
        detail = "попытка 1/3, model=claude-opus-5: стоимость $1.0000"

        self.assertEqual(spend.journal_model(detail), "claude-opus-5")

    def test_identifier_with_colons_inside_survives(self):
        """Идентификатор, сам несущий двоеточия (arn у другого
        провайдера), читается целиком.

        Ловит мутацию: разбор рубит значение по первому двоеточию —
        модель другого провайдера опознавалась бы как `arn`, и её шаги
        считались бы по чужой цене или выпадали из сверки."""
        detail = "попытка 1/3, model=arn:aws:bedrock:model/x: стоимость"

        self.assertEqual(spend.journal_model(detail),
                         "arn:aws:bedrock:model/x")

    def test_line_written_before_the_model_field_has_no_model(self):
        """Строка до 19.09 поля `model=` не несёт вовсе — модели нет.

        Ловит мутацию: разбор отдаёт на строке без поля пустую строку
        (или саму `detail`) вместо `None` — старый журнал целиком завёл бы
        в сверке пару с пустым идентификатором модели, и её коэффициент
        считался бы по шагам неизвестно какой модели (AC-5)."""
        self.assertIsNone(spend.journal_model("попытка 1/3: стоимость"))

    def test_cli_default_label_is_parsed_but_the_catalog_rejects_it(self):
        """Метка «дефолт CLI» — не идентификатор модели, и отсекает её
        каталог, а не разбор поля: `journal_model` читает значение поля
        как есть («дефолт»), тариф по нему не разрешается, и строка
        выпадает из сверки на фильтре каталога (AC-5).

        Ловит мутацию: `model_tariff` деградирует в тариф по умолчанию
        вместо `None` на неизвестном каталогу идентификаторе — в отчёте
        завелась бы псевдомодель «дефолт», а её шаги считались бы по
        чужой цене."""
        self.assertEqual(spend.journal_model("попытка 1/3, model=дефолт CLI:"),
                         "дефолт")
        self.assertIsNone(spend.model_tariff("дефолт"))


class DivergenceMathTest(TaskSeededTmpRootTest):
    """`spend.check_rate_divergence` — единственная математика сверки
    (требование 6): сумма расчёта против суммы фактов.

    Песочница здесь не ради данных (пары считаются прямо в тестах), а
    ради `store.db()`: без подмены путей `config` соединение легло бы в
    настоящий `.artel/state.db` пульта."""

    def setUp(self):
        super().setUp()
        self.model = spend.role_tariff(ROLE).model

    def test_coefficient_is_the_sum_ratio_not_the_average_of_steps(self):
        """Ловит мутацию: расчёт усредняет коэффициенты шагов вместо
        деления суммы на сумму — на паре «крупный расходящийся шаг плюс
        мелкий точный» среднее даёт 0.125, а сумма против суммы —
        2.5/11 ≈ 0.227, и `assertAlmostEqual` разойдётся."""
        pairs = [(12.5, 10.0), (1.0, 1.0)]

        divergence = spend.check_rate_divergence(store.db(), self.model, pairs)

        self.assertAlmostEqual(divergence, 2.5 / 11.0)
        self.assertEqual(divergence.steps, 2)
        self.assertEqual(divergence.since, spend.rate_calibrated_at(ROLE))

    def test_nothing_to_compare_is_none_not_zero(self):
        """Ловит мутацию: пустая выборка трактуется как «расхождения
        нет» и возвращает 0.0 — модель без шагов попала бы в отчёт нулём,
        неотличимая от модели, чей тариф реально сошёлся с фактом."""
        self.assertIsNone(spend.check_rate_divergence(store.db(), self.model, []))

    def test_model_outside_the_catalog_is_not_compared(self):
        """Ловит мутацию: сверка идёт и для модели, которой нет в
        каталоге, — даты тарифа, с которой её считать, нет, и
        коэффициент считался бы по шагам неизвестного периода."""
        self.assertIsNone(spend.check_rate_divergence(
            store.db(), "model-which-is-not-in-the-catalog", [(1.0, 2.0)]))


class ChargeStepJournalTest(TaskSeededTmpRootTest):
    """Требования 2-5: источник стоимости, расчёт, дата тарифа и
    коэффициент в строке KNOWN, фильтр по дате, тихий пропуск без usage."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.effective = spend.role_tariff(ROLE)
        self.model = self.effective.model
        self.since = self.effective.calibrated_at
        self.calculated = spend.partial_cost_usd(ROLE, TOKENS)
        self.threshold = config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD

    def numbered(self, attempt: int = 1, model_id: str = None) -> str:
        """`numbered` в том виде, в каком его отдаёт `runner`: с `model=`."""
        model_id = self.model if model_id is None else model_id
        return f"попытка {attempt}/3, model={model_id}"

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
        действующего тарифа — «шаги, посчитанные по другой цене»."""
        day = date.fromisoformat(self.since) - timedelta(days=1)
        self.conn.execute("UPDATE steps SET ts=? WHERE action=?",
                          (f"{day} 12:00:00Z", spend.KNOWN_COST_JOURNAL_ACTION))
        self.conn.commit()

    def test_known_line_names_the_fact_and_carries_calculation_and_coefficient(self):
        """Ловит мутацию: строка KNOWN остаётся прежней (без источника,
        расчёта, даты тарифа и коэффициента) — читатель журнала снова не
        отличает факт CLI от расчёта по тарифу, не видит расхождения до
        запуска отчёта и не знает, по какой цене шаг посчитан."""
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.actual_for(self.threshold / 2)),
                          self.numbered())

        detail = self.details(spend.KNOWN_COST_JOURNAL_ACTION)[-1]
        self.assertIn("источник=факт CLI", detail)
        self.assertIn(f"расчёт по тарифу=${self.calculated:.4f}", detail)
        self.assertIn(f"тариф модели с {self.since}", detail)
        self.assertIn(f"коэффициент пары с {self.since}="
                      f"{self.threshold / 2:.2f}", detail)

    def test_partial_line_names_the_rate_as_its_source(self):
        """Ловит мутацию: источник дописан только в ветку KNOWN —
        частичная сумма по тарифу (шаг без финального события потока)
        продолжает выдавать себя за счёт CLI."""
        spend.charge_missing_result(
            self.conn, self.TASK, ROLE, self.numbered(), "таймаут шага",
            partial_tokens=TOKENS, saw_usage_event=True)

        detail = self.details("agent cost PARTIAL")[-1]
        self.assertIn("источник=расчёт по тарифу", detail)
        self.assertIn(f"тариф модели с {self.since}", detail)

    def test_spent_usd_gets_the_cli_fact_not_the_calculation(self):
        """Ловит мутацию: начисление подменяется расчётом по тарифу (или
        расчёт прибавляется вторым `store.charge`) — `spent_usd`
        разъедется со счётом CLI, и весь бюджетный контур станет считать
        деньги по калибровочной таблице."""
        actual = self.actual_for(2 * self.threshold)
        self.assertGreater(abs(self.calculated - actual), 0.01)

        spend.charge_step(self.conn, self.TASK, ROLE, cost(actual),
                          self.numbered())

        row = self.conn.execute("SELECT * FROM tasks WHERE id=?",
                                (self.TASK,)).fetchone()
        self.assertAlmostEqual(row["spent_usd"], actual, places=6)

    def test_steps_older_than_the_tariff_date_stay_out_of_the_check(self):
        """Ловит мутацию: сверка идёт по всем строкам KNOWN пары без
        фильтра по дате — шаги старой и новой цены складываются в одну
        сумму, и коэффициент свежей строки уедет с нуля."""
        self.charge_stale_then_fresh()

        coefficient = self.details(spend.KNOWN_COST_JOURNAL_ACTION)[-1]
        self.assertIn(f"коэффициент пары с {self.since}=0.00", coefficient)

    def charge_stale_then_fresh(self) -> None:
        """Один сильно расходящийся шаг, состаренный до даты тарифа, и
        один свежий шаг ровно по тарифу."""
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.actual_for(4 * self.threshold)),
                          self.numbered(1))
        self.backdate_known_rows()
        spend.charge_step(self.conn, self.TASK, ROLE, cost(self.calculated),
                          self.numbered(2))

    def test_step_of_another_model_stays_out_of_the_pair(self):
        """Строка той же роли с ДРУГОЙ моделью в коэффициент пары не
        входит (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 2).

        Ловит мутацию: поле `model=` не фильтрует выборку — шаг чужой
        модели, посчитанный по её цене, лёг бы в коэффициент этой пары, и
        расхождение показало бы разницу прейскурантов двух моделей вместо
        расхождения тарифа с фактом."""
        other = next(model_id for model_id in _catalog_models()
                     if model_id != self.model)
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.actual_for(4 * self.threshold)),
                          self.numbered(1, other))
        spend.charge_step(self.conn, self.TASK, ROLE, cost(self.calculated),
                          self.numbered(2))

        detail = self.details(spend.KNOWN_COST_JOURNAL_ACTION)[-1]
        self.assertIn(f"коэффициент пары с {self.since}=0.00", detail)

    def test_step_without_usage_breakdown_is_charged_silently(self):
        """Ловит мутацию: сверка считается до проверки пустой разбивки —
        расчёт по пустому usage равен нулю, коэффициент выходит 1.0
        («расхождение на все сто»), и каждый такой шаг открывал бы
        ложный алерт."""
        note = spend.charge_step(self.conn, self.TASK, ROLE,
                                 cost(3.75, tokens={}), self.numbered())

        self.assertIn("стоимость", note)
        self.assertEqual(self.details(spend.KNOWN_COST_JOURNAL_ACTION), [])
        self.assertEqual(self.divergence_alerts(), [])

    def test_coefficient_above_the_threshold_raises_the_alert_at_charge_step(self):
        """Ловит мутацию: коэффициент считается, но алерт остаётся за
        отчётом — сигнал снова ждёт запуска `report`, которого может не
        быть неделями (SPEC, «Контекст»)."""
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.actual_for(2 * self.threshold)),
                          self.numbered())

        raised = self.divergence_alerts()
        self.assertEqual(len(raised), 1)
        self.assertIsNone(raised[0]["target"])
        self.assertIn(self.model, raised[0]["message"])

    def test_coefficient_below_the_threshold_raises_nothing(self):
        """Ловит мутацию: алерт заводится на любое ненулевое
        расхождение (сравнение с порогом потеряно при переносе расчёта
        из отчёта в запись шага) — порог перестаёт значить что-либо."""
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.actual_for(self.threshold / 2)),
                          self.numbered())

        self.assertEqual(self.divergence_alerts(), [])

    def test_repeated_divergence_of_the_same_model_keeps_one_alert(self):
        """Ловит мутацию: алерт заводится через `alerts.raise_alert`
        напрямую — дедуп там по точному тексту, а текст несёт растущие
        суммы и число шагов, так что каждый шаг плодил бы копию одного
        сигнала."""
        for attempt in (1, 2):
            spend.charge_step(self.conn, self.TASK, ROLE,
                              cost(self.actual_for(2 * self.threshold)),
                              self.numbered(attempt))

        self.assertEqual(len(self.divergence_alerts()), 1)


def _catalog_models() -> list:
    """Идентификаторы моделей боевого каталога, отсортированные."""
    from orchestrator import models
    return sorted(models.load_catalog().models)


class ReportDivergenceTest(TaskSeededTmpRootTest):
    """Требования 6-7: отчёт считает тем же расчётом, с той же даты, и
    называет дату и число вошедших шагов; ключ — МОДЕЛЬ (SPEC
    01M300A14KRHCFB0DQXVCBJEKF, требование 4)."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.effective = spend.role_tariff(ROLE)
        self.model = self.effective.model
        self.calculated = spend.partial_cost_usd(ROLE, TOKENS)

    def numbered(self, attempt: int = 1) -> str:
        return f"попытка {attempt}/3, model={self.model}"

    def test_report_agrees_with_the_journal_line_on_one_coefficient(self):
        """Ловит мутацию: в `charge_step` заведён собственный расчёт
        (например, среднее по шагам), а `token_rate_divergence` оставлен
        прежним — две цифры по одним данным разойдутся, и Оператор не
        сможет сказать, какой верить."""
        threshold = config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD
        spend.charge_step(self.conn, self.TASK, ROLE,
                          cost(self.calculated / (1.0 + threshold / 2)),
                          self.numbered())

        divergence = report.token_rate_divergence(self.conn)

        self.assertAlmostEqual(divergence[self.model], threshold / 2, places=2)
        self.assertEqual(divergence[self.model].steps, 1)
        self.assertEqual(divergence[self.model].since,
                         self.effective.calibrated_at)

    def test_coefficient_of_a_model_stays_a_plain_number(self):
        """Возврат `token_rate_divergence` по модели — число: его
        вычитают и сравнивают как число (`assertAlmostEqual`), а период
        сверки едет атрибутами.

        Ловит мутацию: дата и число шагов заезжают в возврат так, что
        значение перестаёт быть числом (словарь, кортеж) — арифметика
        читателя падает с `TypeError`, а контракт `dict[str, float]`
        ломается молча."""
        spend.charge_step(self.conn, self.TASK, ROLE, cost(self.calculated),
                          self.numbered())

        value = report.token_rate_divergence(self.conn)[self.model]

        self.assertIsInstance(value, float)
        self.assertAlmostEqual(value, 0.0, places=6)

    def test_report_line_names_the_date_and_the_number_of_steps(self):
        """Ловит мутацию: строка отчёта остаётся прежней (только
        коэффициент) — читатель не может сказать, по какому периоду и по
        скольким шагам посчитана цифра."""
        line = report._divergence_html(
            {self.model: spend.RateDivergence(0.12, 7, "2026-09-20")})

        self.assertIn(self.model, line)
        self.assertIn("коэффициент расхождения 0.12", line)
        self.assertIn("по 7 шагам", line)
        self.assertIn("2026-09-20", line)

    def test_model_without_fresh_steps_is_absent_from_the_result(self):
        """Ловит мутацию: модель без шагов с даты тарифа попадает в
        результат нулём — отчёт заявлял бы сошедшийся тариф там, где его
        вообще не с чем сверять."""
        self.assertEqual(report.token_rate_divergence(self.conn), {})


class BreakdownNameFormsTest(unittest.TestCase):
    """`spend.known_cost_breakdown` на обеих формах имён видов токенов
    (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требование 7).

    Планка задачи сверяет ЧИСЛА двух форм; здесь — перекрытие самих
    имён, которого она не проверяет: прежние имена начинаются с общих
    (`input` — префикс `input_tokens`), и разбор обязан не спутать их."""

    @staticmethod
    def line(breakdown: str) -> str:
        return (f"попытка 1/3, model=m: стоимость $0.5000, "
                f"разбивка по видам: {breakdown} | actual_usd=0.5")

    def test_common_name_is_not_found_inside_a_legacy_one(self):
        """Строка прежней формы читается прежними именами — общее имя
        внутри длинного счётчика не подхватывается.

        Ловит мутацию: шаблон общего имени собран без отсечки границы —
        `cache_read=` находится внутри `cache_read_input_tokens=`, и
        чтения кэша считаются дважды (или вид перетирается чужим
        числом), отчего расчёт по тарифу на старом журнале уезжает в
        полтора раза.
        """
        _, breakdown = spend.known_cost_breakdown(self.line(
            "input_tokens=1, output_tokens=2, "
            "cache_creation_input_tokens=3, cache_read_input_tokens=4"))

        self.assertEqual(breakdown, {"input": 1, "output": 2,
                                     "cache_write": 3, "cache_read": 4})

    def test_both_forms_give_the_same_breakdown_for_the_same_numbers(self):
        """Одни и те же числа, записанные двумя формами имён, дают одну
        и ту же разбивку общими видами.

        Ловит мутацию: разбор переведён на общие имена без поддержки
        прежних — весь журнал до задачи читается пустым, и калибровка
        тарифа молча начинается с нуля.
        """
        legacy = spend.known_cost_breakdown(self.line(
            "input_tokens=1, output_tokens=2, "
            "cache_creation_input_tokens=3, cache_read_input_tokens=4"))
        common = spend.known_cost_breakdown(self.line(
            "input=1, output=2, cache_write=3, cache_read=4"))

        self.assertEqual(legacy, common)


if __name__ == "__main__":
    unittest.main()
