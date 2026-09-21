"""AC-6 — 01M300A14KRHCFB0DQXVCBJEKF: отчёт группирует расхождение по
модели, значение остаётся числом, панель печатает строку на модель.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. `report.token_rate_divergence` возвращает `{идентификатор модели:
число}` — ключ модель, а не роль; значение сравнимо как число.
`report._divergence_html` печатает строку на модель.

Красен до реализации: `report.token_rate_divergence` собирает результат
по `spend.known_cost_pairs(conn).items()`, где ключ — РОЛЬ
(`orchestrator/report.py:364`), поэтому в ключах окажутся `developer`/
`test_author`, а не идентификаторы моделей.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402
from orchestrator import report  # noqa: E402


class DivergenceIsKeyedByModelTest(_tariff.TariffSandbox):

    def setUp(self):
        super().setUp()
        # По одному завершённому шагу на каждую из двух моделей: факт CLI
        # вдвое ниже расчёта, то есть коэффициент каждой модели — 1.00.
        self.alfa = _tariff.expected_cost_usd(_tariff.MODEL_ALFA)
        self.beta = _tariff.expected_cost_usd(_tariff.MODEL_BETA)
        self.charge_known(_tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
                          self.alfa / 2, attempt=1)
        self.charge_known(_tariff.ROLE_ON_BETA, _tariff.MODEL_BETA,
                          self.beta / 2, attempt=2)

    def test_ac6_keys_are_model_identifiers_and_values_are_numbers(self):
        """Ключи возврата — идентификаторы моделей каталога, имён ролей
        среди них нет, а значение участвует в обычной арифметике как
        число.

        Ловит мутацию: группировка осталась по роли (или ключом стала
        пара «роль/модель» строкой) — Оператор снова не видит, какой
        МОДЕЛИ принадлежит расхождение, а читатель, вычитающий
        коэффициент как число, падает `TypeError`.
        """
        divergence = report.token_rate_divergence(self.conn)

        self.assertEqual({_tariff.MODEL_ALFA, _tariff.MODEL_BETA},
                         set(divergence), sorted(divergence))
        for model_id, value in divergence.items():
            with self.subTest(model=model_id):
                self.assertIsInstance(value, float)
                self.assertAlmostEqual(value, 1.0, places=6)

    def test_ac6_panel_prints_a_row_per_model(self):
        """`report._divergence_html` печатает по строке на каждую модель
        выборки, называя её идентификатор.

        Ловит мутацию: панель склеивает все модели в одну строку (или
        печатает только первую) — в отчёте исчезает разрез, ради
        которого группировка и переносилась на модель.
        """
        divergence = report.token_rate_divergence(self.conn)

        html = report._divergence_html(divergence)

        self.assertIn(_tariff.MODEL_ALFA, html)
        self.assertIn(_tariff.MODEL_BETA, html)
        self.assertEqual(2, html.count("metric-row"), html)


if __name__ == "__main__":
    unittest.main()
