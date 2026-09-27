"""AC-12 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: метрики задачи-канарейки не
зависят от провайдера.

Источник — SPEC.md, «Критерии приёмки»:

AC-12. Метрики задачи-канарейки не зависят от провайдера: при одинаковых
`spent_usd`, числе шагов и итераций ревью сводка задачи совпадает для роли
на `claude` и на провайдере с `cost_from_cli: false`; собственного
пересчёта стоимости канарейка не делает (стоимость читается из `spent_usd`
задачи).

Два прогона по ОДНОМУ шаблону с одинаковыми `spent_usd`/шагами/итерациями
ревью: один по набору по умолчанию (роль на `claude`), другой по набору
Codex, чей раздел каталога помечен `cost_from_cli: false` — это и есть
«провайдер без стоимости из CLI» критерия (проверяется предпосылкой по
каталогу, а не литералом).

Красен до реализации: прогон по набору невозможен — у `canary.cmd_canary`
нет параметра набора.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import models  # noqa: E402

SPENT = 3.75
STEPS = 4
REVIEW_ITERS = 2

#: Колонки метрик, которые критерий называет «сводкой задачи».
METRIC_COLUMNS = ("steps", "cost_usd", "review_iterations", "escalations",
                  "outcome", "verdict")


class MetricsIndependentOfProviderTest(_util.CanarySetSandbox):

    def _rows(self):
        return self.conn.execute(
            "SELECT * FROM canary_runs ORDER BY id").fetchall()

    def test_ac12_same_metrics_for_claude_and_for_a_cost_from_cli_false_provider(self):
        """Сводка задачи совпадает у прогона по набору по умолчанию (роль
        на `claude`) и у прогона по Codex-набору при одинаковых
        `spent_usd`, шагах и итерациях ревью.

        Ловит мутацию: канарейка начинает считать стоимость шага сама
        (тарифом каталога — «у codex же `cost_from_cli: false`») — метрика
        прогона стала бы функцией провайдера, и бейзлайн одного набора
        нельзя было бы сравнить с прогоном того же набора после смены
        тарифа.
        """
        model = models.catalog_model(_util.SET_MODEL)
        self.assertFalse(
            model.cost_from_cli,
            "предпосылка сценария: провайдер модели набора не сообщает "
            "стоимость из CLI")

        self.run_canary(spent=SPENT, steps=STEPS, review_iters=REVIEW_ITERS)
        self.run_canary(set_name=_util.SET_NAME, spent=SPENT, steps=STEPS,
                        review_iters=REVIEW_ITERS)

        rows = self._rows()
        self.assertEqual(2, len(rows))
        claude_metrics, codex_metrics = (
            tuple(row[column] for column in METRIC_COLUMNS) for row in rows)
        self.assertEqual(claude_metrics, codex_metrics)

    def test_ac12_cost_is_the_task_spent_usd_without_any_recalculation(self):
        """Стоимость в строке прогона — ровно `spent_usd` задачи, ни
        центом больше: канарейка стоимость не пересчитывает.

        Ловит мутацию: стоимость прогона собирается из токенов журнала по
        тарифу модели набора вместо `spent_usd` задачи — на модели с
        другим тарифом то же самое прохождение конвейера давало бы другую
        метрику, и «отклонение сверх порога» сообщало бы о смене тарифа, а
        не о регрессии конвейера.
        """
        self.run_canary(set_name=_util.SET_NAME, spent=SPENT, steps=STEPS,
                        review_iters=REVIEW_ITERS)

        row = self._rows()[0]

        self.assertEqual(SPENT, row["cost_usd"])
        self.assertEqual(STEPS, row["steps"])
        self.assertEqual(REVIEW_ITERS, row["review_iterations"])


if __name__ == "__main__":
    unittest.main()
