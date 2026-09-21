"""AC-3 — 01M300A14KRHCFB0DQXVCBJEKF: `spend.rate_calibrated_at` отдаёт
дату действующего тарифа МОДЕЛИ.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. `spend.rate_calibrated_at` отдаёт дату действующего тарифа модели:
`calibrated_at` переопределения локального слоя, если оно есть, иначе
`price_date` каталога.

Красен до реализации: `spend.rate_calibrated_at` читает
`config.TOKEN_RATES[role]["calibrated_at"]` (`orchestrator/spend.py:302`)
— дата одна на роль и не меняется ни от модели яруса, ни от появления
собственного тарифа в локальном слое.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402
from orchestrator import spend  # noqa: E402


class RateCalibratedAtFollowsTheModelTariffTest(_tariff.TariffSandbox):

    def test_ac3_catalog_price_date_when_there_is_no_override(self):
        """Без переопределения дата действующего тарифа — `price_date`
        записи модели в каталоге, одинаковая для обеих ролей этой модели
        и своя у модели другого яруса.

        Ловит мутацию: дата берётся не из разрешения цепочки, а остаётся
        привязанной к роли (одна на всех) — сверка расхождения пошла бы
        с даты, не имеющей отношения к тарифу модели шага, и строки
        чужой модели снова попали бы в коэффициент.
        """
        self.assertEqual(spend.rate_calibrated_at(_tariff.ROLE_ON_ALFA),
                         _tariff.CATALOG_PRICE_DATE)
        self.assertEqual(spend.rate_calibrated_at(_tariff.OTHER_ROLE_ON_ALFA),
                         _tariff.CATALOG_PRICE_DATE)
        self.assertEqual(spend.rate_calibrated_at(_tariff.ROLE_ON_BETA),
                         _tariff.CATALOG_PRICE_DATE)

    def test_ac3_override_calibration_date_wins_over_the_catalog(self):
        """Собственный тариф локального слоя приносит свою дату
        калибровки — и только модели, у которой он заведён: роль на
        другой модели продолжает жить по дате каталога.

        Ловит мутацию: дата всегда берётся из каталога (`price_date`),
        даже когда действует переопределение — Оператор, откалибровавший
        собственный тариф сегодня, получал бы сверку с даты прейскуранта
        и вместе с ней шаги, записанные до его калибровки.
        """
        self.use_local(overrides={_tariff.MODEL_ALFA:
                                  _tariff.scaled(_tariff.MODEL_ALFA, 1.5)})

        self.assertEqual(spend.rate_calibrated_at(_tariff.ROLE_ON_ALFA),
                         _tariff.OVERRIDE_CALIBRATED_AT)
        self.assertEqual(spend.rate_calibrated_at(_tariff.OTHER_ROLE_ON_ALFA),
                         _tariff.OVERRIDE_CALIBRATED_AT)
        self.assertEqual(spend.rate_calibrated_at(_tariff.ROLE_ON_BETA),
                         _tariff.CATALOG_PRICE_DATE)


if __name__ == "__main__":
    unittest.main()
