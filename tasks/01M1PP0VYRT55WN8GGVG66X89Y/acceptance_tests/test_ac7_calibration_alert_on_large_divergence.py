"""AC-7 (SPEC: «Частичная стоимость шага по видам токенов, калибровка
курса») — «Коэффициент расхождения калибровки требования 4 больше
именованного порога (константа config.py, по аналогии с
SPLIT_SIGNAL_*/STEP_COST_ESTIMATE_USD) поднимает алерт alerts с
kind=warning.»

Интерфейс, зафиксированный этим тестом:
- `config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD` — новая именованная
  константа (SPEC называет её только по аналогии, не по имени
  буквально — имя выбрано этим тестом по той же конвенции
  `<ОБЛАСТЬ>_<ЧТО>`, что уже принятые `SPLIT_SIGNAL_*`/
  `STEP_COST_ESTIMATE_USD`, orchestrator/config.py:286-291,336).
- `alerts.KINDS` обязан включать `"warning"` — сегодня
  (`orchestrator/alerts.py:31`) несёт только `("incident", "threshold",
  "trigger", "attention")`; `alerts.raise_alert(conn, ..., "warning",
  ...)` без этого расширения бросает `ValueError` изнутри
  `token_rate_divergence` раньше, чем дело дойдёт до самого алерта —
  это тоже часть требуемого поведения, не отдельный критерий.
- Вызывает `report.token_rate_divergence(conn)` — та же функция AC-6,
  сравнение и алерт совмещены одним вызовом (тот же приём, что уже
  сочетают `spend.charge_missing_result`/`budget.check_program_spend` в
  этой кодовой базе — вычисление и алерт в одной точке).

Значение порога тестом НЕ зафиксировано (конфиг — крутилка Оператора,
скил test-authoring): сценарии ниже читают
`config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD` динамически и строят
коэффициент заведомо выше/ниже него, а не сравнивают с зашитым числом.

Красен до реализации: `config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD` не
существует — `AttributeError` на первой строке `setUp`/теста, раньше,
чем дело дойдёт до `report.token_rate_divergence`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, report, spend  # noqa: E402
from _sandbox import TokenRateTmpRootTest  # noqa: E402

FAKE_RATES = {
    "input_usd_per_token": 0.000010,
    "output_usd_per_token": 0.000020,
    "cache_creation_usd_per_token": 0.000005,
    "cache_read_usd_per_token": 0.000001,
    "calibrated_at": "2026-09-04",
}

TOKENS_BY_TYPE = {
    "input_tokens": 100,
    "output_tokens": 50,
    "cache_creation_input_tokens": 10,
    "cache_read_input_tokens": 9000,
}
CALCULATED_USD = sum(
    TOKENS_BY_TYPE[k] * FAKE_RATES[rate_field] for k, rate_field in (
        ("input_tokens", "input_usd_per_token"),
        ("output_tokens", "output_usd_per_token"),
        ("cache_creation_input_tokens", "cache_creation_usd_per_token"),
        ("cache_read_input_tokens", "cache_read_usd_per_token"),
    ))


def _actual_usd_for_coefficient(coefficient: float) -> float:
    """`actual`, при котором |CALCULATED_USD - actual| / actual == coefficient."""
    return CALCULATED_USD / (1.0 + coefficient)


class CalibrationAlertOnLargeDivergenceTest(TokenRateTmpRootTest):

    def _seed_known_cost_step(self, role: str, actual_usd: float):
        cost = {"usd": actual_usd, "tokens": sum(TOKENS_BY_TYPE.values()),
               "tokens_by_type": dict(TOKENS_BY_TYPE)}
        spend.charge_step(self.conn, self.TASK, role, cost, "попытка 1/3")

    def test_ac7_coefficient_above_the_threshold_raises_a_warning_alert(self):
        """Роль с коэффициентом расхождения ЗАВЕДОМО выше именованного
        порога получает открытый алерт `kind=warning`.

        Ловит мутацию: реализация считает коэффициент, но не сверяет
        его с порогом (алерт не заводится вовсе, либо заводится другим
        `kind`) — список алертов `kind=warning` останется пустым,
        `assertEqual(len(...), 1)` провалится.
        """
        threshold = config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD
        over_threshold_coefficient = threshold * 3
        actual = _actual_usd_for_coefficient(over_threshold_coefficient)

        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            self._seed_known_cost_step("test_author", actual)
            report.token_rate_divergence(self.conn)

        warnings = self.alerts_of_kind("warning")
        self.assertEqual(len(warnings), 1)
        self.assertIn("test_author", warnings[0]["message"])

    def test_ac7_coefficient_below_the_threshold_raises_no_alert(self):
        """Роль с коэффициентом расхождения ЗАВЕДОМО ниже порога не
        получает алерта — калибровка не шумит на приемлемом отклонении.

        Ловит мутацию: алерт заводится безусловно при ЛЮБОМ ненулевом
        расхождении (порог не проверяется по существу, либо сравнение
        перевёрнуто `<` вместо `>`) — список `kind=warning` окажется
        непустым, `assertEqual(len(...), 0)` провалится.
        """
        threshold = config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD
        under_threshold_coefficient = threshold / 3
        actual = _actual_usd_for_coefficient(under_threshold_coefficient)

        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            self._seed_known_cost_step("test_author", actual)
            report.token_rate_divergence(self.conn)

        self.assertEqual(len(self.alerts_of_kind("warning")), 0)


if __name__ == "__main__":
    unittest.main()
