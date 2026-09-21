"""AC-10 и AC-11 — 01M300A14KRHCFB0DQXVCBJEKF: две новые проверки
`doctor` — свежесть действующего тарифа и его давность относительно
смены модели у роли.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. Проверка `doctor` «тариф свеж»: ok, когда дата действующего
тарифа не старше `config.MODEL_TARIFF_MAX_AGE_DAYS` (90 дней), и не-ok с
названной моделью и датой, когда старше.

AC-11. Проверка `doctor` «тариф не старше смены модели у роли»:
предупреждение, когда последняя строка «agent cost KNOWN» роли с другой
моделью новее даты действующего тарифа; ok, когда таких строк в журнале
нет.

Имён функций SPEC не называет — проверки названы по-русски. Планка
находит их по тому, что критерий называет дословно: потолок
`config.MODEL_TARIFF_MAX_AGE_DAYS` (AC-10) и действие журнала «agent cost
KNOWN» (AC-11), и требует, чтобы найденное было подключено к
`doctor.all_checks`: непровязанная проверка Оператору не видна вовсе.
Наблюдается результат — `doctor.Check` со статусом и текстом, — а не
внутреннее устройство.

Красен до реализации: `config.MODEL_TARIFF_MAX_AGE_DAYS` ещё нет
(`AttributeError` в первом же тесте), а среди проверок `doctor`
(`orchestrator/doctor/cli.py::all_checks`) нет ни одной, читающей
журнал «agent cost KNOWN», — выборка пуста, и `assertTrue` на ней
краснеет.
"""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402
from orchestrator import config  # noqa: E402

#: Потолок давности тарифа назван SPEC числом — 90 дней; сама граница
#: проверяется ОТ константы, чтобы поворот крутилки Оператора двигал
#: обе даты сценария вместе с ней.
DECLARED_MAX_AGE_DAYS = 90

FRESHNESS_NEEDLES = ("MODEL_TARIFF_MAX_AGE_DAYS",)
MODEL_CHANGE_NEEDLES = ("KNOWN_COST_JOURNAL_ACTION", "agent cost KNOWN")


class TariffFreshnessCheckTest(_tariff.TariffSandbox):
    """AC-10: дата действующего тарифа не старше потолка."""

    def freshness_results(self):
        checks = _tariff.doctor_checks_mentioning(*FRESHNESS_NEEDLES)
        self.assertTrue(
            checks,
            "ни одна проверка doctor, подключённая к all_checks, не "
            "читает config.MODEL_TARIFF_MAX_AGE_DAYS — проверки «тариф "
            "свеж» нет либо она не провязана")
        return _tariff.run_doctor_checks(checks, self.conn)

    def test_ac10_fresh_tariff_is_ok_and_stale_one_names_model_and_date(self):
        """Тариф моложе потолка не даёт ни одной красной/жёлтой строки о
        себе; тариф старше потолка даёт не-ok строку, называющую и
        модель, и дату этого тарифа.

        Ловит мутацию: сравнение с потолком перевёрнуто (или взято
        строгое «старше ИЛИ РАВНО нуля») — `doctor` либо молчит о
        протухшей цене, из-за которой учёт расхода расходится с фактом,
        либо орёт на свежий прейскурант в каждом прогоне, и Оператор
        перестаёт читать его строки.
        """
        self.assertEqual(DECLARED_MAX_AGE_DAYS,
                         config.MODEL_TARIFF_MAX_AGE_DAYS)
        horizon = config.MODEL_TARIFF_MAX_AGE_DAYS
        fresh = (date.today() - timedelta(days=max(1, horizon // 2))).isoformat()
        stale = (date.today() - timedelta(days=horizon + 5)).isoformat()

        self.use_catalog(price_date=fresh)
        fresh_results = self.freshness_results()

        self.use_catalog(price_date=stale)
        stale_results = self.freshness_results()

        self.assertEqual(
            [], [c for c in fresh_results
                 if c.status != "ok" and _tariff.MODEL_ALFA in (c.detail or "")],
            fresh_results)
        self.assertTrue(
            [c for c in stale_results if c.status != "ok"
             and _tariff.MODEL_ALFA in (c.detail or "")
             and stale in (c.detail or "")],
            stale_results)


class TariffOlderThanTheModelChangeCheckTest(_tariff.TariffSandbox):
    """AC-11: тариф старше смены модели у роли — предупреждение."""

    def model_change_results(self):
        checks = _tariff.doctor_checks_mentioning(*MODEL_CHANGE_NEEDLES)
        self.assertTrue(
            checks,
            "ни одна проверка doctor, подключённая к all_checks, не "
            "читает строки журнала «agent cost KNOWN» — проверки «тариф "
            "не старше смены модели у роли» нет либо она не провязана")
        return _tariff.run_doctor_checks(checks, self.conn)

    def test_ac11_journal_without_foreign_model_steps_stays_ok(self):
        """Журнал, где у роли есть только шаги на её текущей модели, не
        даёт предупреждения.

        Ловит мутацию: проверка предупреждает о любой строке KNOWN (не
        сверяя модель строки с моделью роли) — `doctor` жёлтый всегда, и
        реальная смена модели в нём неотличима от штатной работы.
        """
        self.charge_known(
            _tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
            _tariff.expected_cost_usd(_tariff.MODEL_ALFA), attempt=1)

        results = self.model_change_results()

        self.assertEqual([], [c for c in results if c.status == "warn"],
                         results)

    def test_ac11_step_of_another_model_newer_than_the_tariff_warns(self):
        """Строка KNOWN роли с ДРУГОЙ моделью, записанная позже даты
        действующего тарифа, даёт предупреждение, называющее эту модель.

        Ловит мутацию: сравнение с датой тарифа потеряно (сверяется факт
        наличия чужой модели когда-либо) либо наоборот — предупреждения
        нет вовсе: пульт снова молча считает деньги по тарифу модели,
        на которой роль уже не ходит, ровно как в инциденте 13.09-20.09.
        """
        self.charge_known(
            _tariff.ROLE_ON_ALFA, _tariff.MODEL_BETA,
            _tariff.expected_cost_usd(_tariff.MODEL_BETA), attempt=1)

        results = self.model_change_results()

        self.assertTrue(
            [c for c in results if c.status == "warn"
             and _tariff.MODEL_BETA in (c.detail or "")],
            results)


if __name__ == "__main__":
    unittest.main()
