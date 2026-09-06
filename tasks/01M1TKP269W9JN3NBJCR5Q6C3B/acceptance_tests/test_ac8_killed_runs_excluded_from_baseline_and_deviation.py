"""AC-8 (SPEC.md): строки `canary_runs` с исходом `killed` сохраняются в
таблице, но не участвуют ни в обновлении `canary_baseline`, ни в
вычислении предупреждений об отклонении текущего прогона от бейзлайна.

Контекст — оба наблюдения копилки 06.09: `canary_baseline` дважды за
день (20260905T175403Z, 20260905T191514Z) принял шаги/стоимость задачи
с исходом `killed`, из-за чего бейзлайн, построенный на незавершённом
прогоне, стал несравним с последующими зелёными прогонами. Буквально —
`store.canary_baseline(title)` был `None` (ни разу не был бейзлайна для
этого шаблона), и ИМЕННО killed-прогон стал тем, из которого бейзлайн
завёлся (`orchestrator/canary.py::_run_one_task`: `if baseline is None:
store.set_canary_baseline(...)` — сегодня без всякого условия на
`outcome`).

Сценарий — тот же класс «не сошлась», что и `test_ac1_ac2_ac3_
diagnostics_on_inconclusive_outcome.py`: ревью один раз запрашивает
доработку, каждый следующий вход в `in_dev` эскалирует по-настоящему
(`_sandbox._EscalatesOnReworkAgent`, `PLAN.md status: escalate`) —
задача убивается «не сошлась» реальным исчерпанием `config.
CANARY_MAX_ESCALATION_CYCLES` (`orchestrator/canary.py::_drive_task`).

Красен до реализации: сегодняшний код создаёт `canary_baseline` из
ПЕРВОГО прогона шаблона независимо от его исхода — `store.canary_
baseline(conn, TITLE)` после единственного killed-прогона вернул бы
НЕ `None` (первый тест), и алерт отклонения появился бы там, где его
быть не должно, при заранее известном бейзлайне (второй тест).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, _EscalatesOnReworkAgent  # noqa: E402

from orchestrator import store  # noqa: E402

TITLE_NO_PRIOR_BASELINE = "killed-ne-dolzhen-zavodit-bazu"
TITLE_WITH_PRIOR_BASELINE = "killed-ne-dolzhen-trogat-bazu"


class KilledRunDoesNotCreateBaselineTest(CanarySandbox):
    """Ни разу не было бейзлайна для этого шаблона (`store.canary_
    baseline` — `None`) — ровно сценарий реального инцидента: первый
    прогон шаблона оказался killed."""

    AGENT_CLASS = _EscalatesOnReworkAgent

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            f"{TITLE_NO_PRIOR_BASELINE}.md":
                "Синтетическая правка, ревью которой никогда не "
                "одобряется.",
        })
        self.agent.extra_review_rounds_default = 1
        self.conn = store.db()

    def test_ac8_first_killed_run_does_not_create_a_baseline(self):
        """Строка метрик прогона попадает в `canary_runs` с `outcome ==
        "killed"` (сохранение таблицы, первая половина AC-8), но
        `canary_baseline` для этого `title` остаётся `None` — killed не
        заводит бейзлайн, даже если это первый прогон шаблона вообще
        (буквально сценарий копилки 06.09: 20260905T175403Z,
        20260905T191514Z).

        Ловит мутацию: `_run_one_task` заводит `canary_baseline` из
        ЛЮБОГО первого прогона (буквальный сегодняшний код: `if
        baseline is None: store.set_canary_baseline(...)`, без условия
        на `outcome`) — `store.canary_baseline(conn, TITLE)` после
        прогона вернул бы строку вместо `None`.
        """
        out = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out, out)

        rows = self.conn.execute(
            "SELECT * FROM canary_runs WHERE title=?",
            (TITLE_NO_PRIOR_BASELINE,)).fetchall()
        self.assertEqual(
            len(rows), 1,
            f"прогон не записал строку canary_runs для "
            f"{TITLE_NO_PRIOR_BASELINE}: {rows}")
        self.assertEqual(rows[0]["outcome"], "killed", dict(rows[0]))

        baseline_after = store.canary_baseline(self.conn, TITLE_NO_PRIOR_BASELINE)
        self.assertIsNone(
            baseline_after,
            f"killed-прогон завёл бейзлайн вопреки AC-8/AC-7: "
            f"{dict(baseline_after) if baseline_after is not None else None}")


class KilledRunDoesNotRaiseDeviationAlertTest(CanarySandbox):
    """Бейзлайн для этого шаблона УЖЕ существует (заведён заранее — как
    если бы более ранний прогон был зелёным) — заведомо маленькие
    значения, чтобы метрики killed-прогона гарантированно
    превышали `config.CANARY_DEVIATION_RATIO`, будь сравнение
    включено."""

    AGENT_CLASS = _EscalatesOnReworkAgent

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            f"{TITLE_WITH_PRIOR_BASELINE}.md":
                "Синтетическая правка, ревью которой никогда не "
                "одобряется.",
        })
        self.agent.extra_review_rounds_default = 1

        self.conn = store.db()
        store.set_canary_baseline(self.conn, TITLE_WITH_PRIOR_BASELINE,
                                  steps=1, cost_usd=0.01,
                                  review_iterations=0)
        self.baseline_before = dict(
            store.canary_baseline(self.conn, TITLE_WITH_PRIOR_BASELINE))
        self.alerts_before_ids = {a["id"] for a in store.open_alerts(self.conn)}

    def test_ac8_killed_run_does_not_raise_a_deviation_alert(self):
        """Несмотря на заведомо огромное отклонение раздутых метрик от
        уже существующего маленького бейзлайна (многократно превышает
        `config.CANARY_DEVIATION_RATIO`), killed-прогон не заводит новый
        алерт отклонения, не печатает предупреждение и не трогает сам
        бейзлайн — killed-строка исключена из СРАВНЕНИЯ.

        Ловит мутацию: `_run_one_task` продолжает сравнивать метрики
        killed-исхода с бейзлайном (`_task_deviation_warnings` вызывается
        безусловно) — новый открытый алерт `kind=threshold,
        source=canary` появился бы, и в выводе — «[ВНИМАНИЕ».
        """
        out = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out, out)

        alerts_after = store.open_alerts(self.conn)
        new_alerts = [a for a in alerts_after
                     if a["id"] not in self.alerts_before_ids]
        canary_deviation_alerts = [
            a for a in new_alerts
            if a["source"] == "canary" and TITLE_WITH_PRIOR_BASELINE in a["message"]]
        self.assertEqual(
            canary_deviation_alerts, [],
            f"killed-прогон завёл алерт отклонения от бейзлайна вопреки "
            f"AC-8: {canary_deviation_alerts}")
        self.assertNotIn(
            "[ВНИМАНИЕ", out,
            f"вывод команды несёт предупреждение об отклонении для "
            f"killed-исхода:\n{out}")

        baseline_after = dict(
            store.canary_baseline(self.conn, TITLE_WITH_PRIOR_BASELINE))
        self.assertEqual(
            baseline_after["steps"], self.baseline_before["steps"],
            f"killed-прогон переписал существующий бейзлайн по шагам: "
            f"было {self.baseline_before}, стало {baseline_after}")


if __name__ == "__main__":
    unittest.main()
