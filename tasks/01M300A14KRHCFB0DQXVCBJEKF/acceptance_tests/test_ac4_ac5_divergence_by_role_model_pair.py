"""AC-4 и AC-5 — 01M300A14KRHCFB0DQXVCBJEKF: коэффициент расхождения
считается по паре (роль, модель), а строка без опознаваемой модели в
сверку не входит и расчёт не роняет.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Коэффициент расхождения считается по паре (роль, модель):
`spend.known_cost_pairs`/`spend.check_rate_divergence` берут строки
«agent cost KNOWN» этой роли с этой моделью (поле `model=`) не старше
даты калибровки тарифа модели; строка другой модели и строка старше этой
даты в коэффициент пары не входят.

AC-5. Строка «agent cost KNOWN», по которой модель не определяется (поля
`model=` нет либо оно не идентификатор модели), в сверку не входит и не
роняет расчёт: остальные строки пары посчитаны.

Строки журнала пишутся не вручную, а тем же вызовом `spend.charge_step` и
с тем же `numbered`, какой отдаёт ему `orchestrator/runner.py`
(`_numbered_with_model`, метка «дефолт CLI» — его же): формат строки
KNOWN и его разбор обязаны сойтись, а не совпасть с фантазией планки о
нём.

Коэффициент наблюдается через `report.token_rate_divergence` — это
единственная поверхность, на которой критерий называет его форму (AC-6,
ключ — идентификатор модели); внутри неё считают ровно те две функции,
которые называет AC-4. Состав выборки проверяется вдобавок прямо по
`spend.known_cost_pairs`: факт CLI отброшенной строки не должен
встретиться среди вошедших пар ни под каким ключом.

Красен до реализации: сверка идёт по роли (`_within_rate_period` и
`known_cost_pairs`, `orchestrator/spend.py:309-362`), поле `model=`
строки не читается вовсе, а `report.token_rate_divergence` отдаёт ключом
РОЛЬ — оба теста о коэффициенте падают на отсутствующем ключе модели.
Третий тест файла (`test_ac5_the_step_itself_is_still_charged`) зелён и
сейчас — намеренно: он фиксирует СУЩЕСТВУЮЩЕЕ поведение, которое
требование 3 обязано сохранить (пропуск строки в сверке тихий, шаг
всё равно учтён в `spent_usd`), и покраснеет ровно тогда, когда
реализация превратит пропуск в отказ или ранний выход до `store.charge`.
"""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402
from orchestrator import report, spend  # noqa: E402

#: Факт CLI строк, которые в сверку входить НЕ должны — нарочно далёкие
#: от расчётных сумм планки: попади любая из них в выборку, коэффициент
#: пары уедет далеко за пределы `places=6`.
STALE_ACTUAL_USD = 12.45
UNLABELLED_ACTUAL_USD = 7.77
DEFAULT_CLI_ACTUAL_USD = 8.88


class DivergenceIsCountedPerRoleModelPairTest(_tariff.TariffSandbox):
    """AC-4: чужая модель и строка старше даты калибровки тарифа модели в
    коэффициент пары не входят."""

    def setUp(self):
        super().setUp()
        # Дата тарифа модели — сегодня: строка, состаренная на день,
        # оказывается старше ТАРИФА МОДЕЛИ, оставаясь при этом свежее
        # даты калибровки удаляемого курса роли. Только так сценарий
        # различает две механики отсечения, а не совпадает с обеими.
        self.tariff_date = date.today().isoformat()
        self.use_catalog(price_date=self.tariff_date)
        self.calculated = _tariff.expected_cost_usd(_tariff.MODEL_ALFA)
        # Два шага пары (developer, model-alfa), каждый вдвое дешевле
        # расчёта: сумма расчёта вдвое выше суммы фактов, коэффициент 1.0.
        self.charge_known(_tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
                          self.calculated / 2, attempt=1)
        self.charge_known(_tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
                          self.calculated / 2, attempt=2)

    def test_ac4_only_fresh_steps_of_this_role_and_model_form_the_pair(self):
        """Строка той же роли с ДРУГОЙ моделью и строка той же модели,
        записанная РАНЬШЕ даты тарифа этой модели, не входят в пару
        (роль, модель): её коэффициент посчитан по двум свежим шагам, а
        факт CLI состаренной строки не встречается среди вошедших пар ни
        под каким ключом.

        Ловит мутацию: фильтр по дате остался привязан к роли, а поле
        `model=` не читается (или читается, но не фильтрует) — шаги
        старого тарифа и шаги другой модели складываются в одну сумму,
        коэффициент пары уезжает с 1.00 вниз, и `assertAlmostEqual`
        разойдётся; сама состаренная строка при этом всплывёт в выборке
        `spend.known_cost_pairs`.
        """
        older = (date.fromisoformat(self.tariff_date)
                 - timedelta(days=1)).isoformat()
        self.charge_known(_tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
                          STALE_ACTUAL_USD, attempt=3)
        self.backdate(3, older)
        self.charge_known(
            _tariff.ROLE_ON_BETA, _tariff.MODEL_BETA,
            _tariff.expected_cost_usd(_tariff.MODEL_BETA) / 4, attempt=4)

        divergence = report.token_rate_divergence(self.conn)
        actuals = _tariff.known_actuals(spend.known_cost_pairs(self.conn))

        self.assertIn(_tariff.MODEL_ALFA, divergence, sorted(divergence))
        self.assertAlmostEqual(divergence[_tariff.MODEL_ALFA], 1.0, places=6)
        self.assertNotIn(STALE_ACTUAL_USD, actuals)
        self.assertEqual(3, len(actuals), actuals)


class StepsWithoutAModelStayOutOfTheCheckTest(_tariff.TariffSandbox):
    """AC-5: строка, по которой модель не определяется, пропускается
    тихо — остальные строки пары посчитаны."""

    def setUp(self):
        super().setUp()
        self.calculated = _tariff.expected_cost_usd(_tariff.MODEL_ALFA)
        self.charge_known(_tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
                          self.calculated / 2, attempt=1)
        self.charge_known(_tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
                          self.calculated / 2, attempt=2)
        # Старый формат до 19.09: поля `model=` в строке нет вовсе.
        self.charge_known(_tariff.ROLE_ON_ALFA, None,
                          UNLABELLED_ACTUAL_USD, attempt=3)
        # Поле есть, но это не идентификатор модели — метку «дефолт CLI»
        # пишет сам `orchestrator/runner.py`, когда цепочка не разрешилась.
        self.charge_known(_tariff.ROLE_ON_ALFA, "дефолт CLI",
                          DEFAULT_CLI_ACTUAL_USD, attempt=4)

    def test_ac5_unidentified_model_lines_are_skipped_and_the_rest_counted(self):
        """Две строки без опознаваемой модели не входят в сверку, а
        коэффициент пары по двум оставшимся строкам посчитан.

        Ловит мутацию: строка без `model=` относится к ТЕКУЩЕЙ модели
        роли «по умолчанию» (или метка «дефолт CLI» заводит собственную
        псевдомодель, попадающую в отчёт) — шаги неизвестного тарифа
        снова смешиваются с парой, и коэффициент 1.00 уезжает.
        """
        divergence = report.token_rate_divergence(self.conn)
        actuals = _tariff.known_actuals(spend.known_cost_pairs(self.conn))

        self.assertIn(_tariff.MODEL_ALFA, divergence, sorted(divergence))
        self.assertAlmostEqual(divergence[_tariff.MODEL_ALFA], 1.0, places=6)
        self.assertNotIn(UNLABELLED_ACTUAL_USD, actuals)
        self.assertNotIn(DEFAULT_CLI_ACTUAL_USD, actuals)
        self.assertEqual(2, len(actuals), actuals)

    def test_ac5_the_step_itself_is_still_charged(self):
        """Шаг, по которому модель не определяется, всё равно учтён:
        `spent_usd` задачи несёт сумму всех четырёх фактов CLI.

        Ловит мутацию: пропуск сделан отказом (исключением) или ранним
        возвратом ДО `store.charge` — строка, не годная для сверки,
        перестала бы попадать в расход, и деньги шага утекли бы мимо
        бюджета, как в инциденте с недоучётом PARTIAL.
        """
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?",
                                (self.TASK,)).fetchone()

        self.assertAlmostEqual(
            row["spent_usd"],
            self.calculated + UNLABELLED_ACTUAL_USD + DEFAULT_CLI_ACTUAL_USD,
            places=6)


if __name__ == "__main__":
    unittest.main()
