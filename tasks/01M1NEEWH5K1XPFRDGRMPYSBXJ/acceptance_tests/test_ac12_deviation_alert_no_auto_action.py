"""AC-12 (SPEC.md): отклонение метрик прогона от бейзлайна сверх порога
поднимает алерт Оператору — без автоматического исправления/действия.

Порог — `config.CANARY_DEVIATION_RATIO` (существующая константа v1,
`orchestrator/canary.py::_baseline_warnings`, дефолт 0.5) — читается
динамически, не литералом (тот же принцип, что у остальных порогов
`config.py`).

Красен до реализации: `canary --k` падает на разборе аргументов уже на первом (сеющем бейзлайн) прогоне — второй прогон и сверка вообще не достигаются, первая содержательная проверка (успешное завершение первого прогона) падает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox  # noqa: E402

POOL_TEMPLATES = {
    "malaya-pravka.md": "Добавь маленькую синтетическую фичу X с тестами.",
}


class DeviationAlertNoAutoActionTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)

    def test_ac12_deviation_beyond_threshold_raises_an_alert_without_auto_action(self):
        """Первый прогон (0 лишних ревью-раундов) пишет бейзлайн.
        Второй прогон того же единственного шаблона — с явно раздутым
        числом ревью-раундов (`config.LIMIT_REVIEW_ITERS`(3) − 1 = 2
        лишних раунда, держим ниже потолка, чтобы задача не ушла в
        escalated вместо штатного цикла) — гарантированно превышает
        `config.CANARY_DEVIATION_RATIO` по шагам. Обязан появиться
        открытый (не подтверждённый) алерт про отклонение канарейки; ни
        HEAD пульта (пин), ни живой журнал `tasks`/`steps` main
        (AC-3) при этом не меняются — реакция ограничена алертом, без
        какого-либо автоматического действия.

        Ловит мутацию: разработчик печатает предупреждение в stdout
        (буквальный перенос v1 `_baseline_warnings`, где реакция —
        только текст отчёта) вместо `alerts.raise_alert` — тогда
        `store.open_alerts(conn)` после второго прогона не содержит
        новой строки про канарейку, при этом сам текст в stdout мог бы
        быть, тест на него не смотрит и на него не купится.
        """
        from orchestrator import store

        sha_before = self._git("rev-parse", "HEAD").stdout.strip()
        alerts_before = store.open_alerts(store.db())

        out1 = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out1, out1)

        self.agent.extra_review_rounds_default = 2
        out2 = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out2, out2)

        alerts_after = store.open_alerts(store.db())
        new_alerts = [a for a in alerts_after
                     if a["id"] not in {b["id"] for b in alerts_before}]
        canary_alerts = [a for a in new_alerts
                        if "canary" in a["message"].lower()
                        or "канаре" in a["message"].lower()
                        or "отклонени" in a["message"].lower()]
        self.assertTrue(
            canary_alerts,
            f"второй прогон с явным отклонением не завёл открытый алерт "
            f"про канарейку: новые алерты {new_alerts}")

        sha_after = self._git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(
            sha_before, sha_after,
            "HEAD пульта (пин) сдвинулся сам по себе при отклонении "
            "канарейки — это не входит в реакцию (только алерт)")
        self.assertEqual(
            store.all_tasks(store.db()), [],
            "живой журнал main пульта не пуст после реакции на отклонение "
            "— похоже на автоматическое действие сверх алерта")


if __name__ == "__main__":
    unittest.main()
