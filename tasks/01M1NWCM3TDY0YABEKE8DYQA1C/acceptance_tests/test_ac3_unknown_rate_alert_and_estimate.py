"""AC-3 (SPEC: «Стоимость частичного шага при таймауте: курс токенов
вместо тишины») — «Тот же случай, но курс для роли шага не задан:
spent_usd задачи не изменился; открыт алерт kind=threshold с текстом,
указывающим на неучтённую стоимость шага, роль, задачу и число токенов;
колонка tasks.spent_estimate_usd увеличилась на величину константы
верхней оценки; в журнал шага записана строка «верхняя оценка стоимости
шага» с суммой оценки.»

Роль сценария — `verifier` (roles.yaml её несёт, но `executor: none`,
и требование 1/AC-1 не называет её среди четырёх ролей с курсом) —
роль, для которой курс заведомо не задан ни при каком разрешении
эскалации test_ac1_token_rate_table.py (та эскалация — только про
analyst/test_author/developer/reviewer).

Красен до реализации: `spend.charge_missing_result` (orchestrator/
spend.py:143) сегодня для `saw_usage_event=True` пишет в журнал
«agent cost PARTIAL» с текстом «курс в доллары не задан» и НЕ заводит
алерт («AC-1/2 «либо…либо»» — алерт заводится только в ветке
`saw_usage_event=False`) и не трогает никакую колонку сверх `spent_usd`
— три теста ниже (алерт, верхняя оценка, накопление при повторе) падают
на этом уже сегодня. Один тест —
`test_ac3_timeout_with_unknown_rate_leaves_spent_usd_untouched` — уже
проходит сегодня «случайно»: он проверяет часть критерия, которую
требование 3 явно НЕ меняет («spent_usd задачи не изменился» — тот же
факт, что и до этой задачи), оставлен в файле как часть одного связного
сценария AC-3, не как отдельная приёмка.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, spend, store  # noqa: E402
from _sandbox import CostTmpRootTest  # noqa: E402


class UnknownRateAlertAndEstimateTest(CostTmpRootTest):

    def threshold_alerts(self) -> list:
        return store.db().execute(
            "SELECT * FROM alerts WHERE kind='threshold'").fetchall()

    def test_ac3_timeout_with_unknown_rate_leaves_spent_usd_untouched(self):
        """Таймаут роли БЕЗ курса, но с usage-событиями, не прибавляет
        ничего к `spent_usd` — та же гарантия, что уже даёт T040
        сегодня, теперь явно закреплённая критерием.

        Ловит мутацию: разработчик заводит курс «по умолчанию» для
        нераспознанной роли (fallback вместо явного отсутствия) —
        `spent_usd` перестанет быть 0.0, тест покраснеет.
        """
        conn = store.db()

        spend.charge_missing_result(
            conn, self.TASK, "verifier", "попытка 1/3", "обрыв stdout-пайпа",
            partial_tokens=777, saw_usage_event=True)

        self.assertEqual(self.task_row()["spent_usd"], 0.0)

    def test_ac3_timeout_with_unknown_rate_raises_a_threshold_alert(self):
        """Тот же сценарий заводит ровно один алерт `kind=threshold`,
        чей текст называет роль, задачу и число токенов.

        Ловит мутацию: алерт заводится с `kind=incident` вместо
        `kind=threshold` (перепутан с веткой AC-4/`saw_usage_event=
        False`) — фильтр по `kind='threshold'` не найдёт строку, тест
        покраснеет.
        """
        conn = store.db()

        spend.charge_missing_result(
            conn, self.TASK, "verifier", "попытка 1/3", "обрыв stdout-пайпа",
            partial_tokens=777, saw_usage_event=True)

        found = self.threshold_alerts()
        self.assertEqual(len(found), 1)
        message = found[0]["message"]
        self.assertIn(self.TASK, message)
        self.assertIn("verifier", message)
        self.assertIn("777", message)

    def test_ac3_timeout_with_unknown_rate_credits_the_upper_estimate(self):
        """Тот же сценарий прибавляет к `tasks.spent_estimate_usd` ровно
        именованную константу верхней оценки и оставляет в журнале
        строку «верхняя оценка стоимости шага» с суммой оценки.

        Ловит мутацию: константа читается, но не прибавляется к колонке
        (забыт `UPDATE`/аналог `store.charge`, только журнал) —
        `spent_estimate_usd` останется 0.0 вместо константы, тест
        покраснеет.
        """
        conn = store.db()

        spend.charge_missing_result(
            conn, self.TASK, "verifier", "попытка 1/3", "обрыв stdout-пайпа",
            partial_tokens=777, saw_usage_event=True)

        self.assertAlmostEqual(self.task_row()["spent_estimate_usd"],
                               config.STEP_COST_ESTIMATE_USD)
        detail = self.journal_rows()[-1][2]
        self.assertIn("верхняя оценка стоимости шага", detail)
        self.assertIn("$", detail)

    def test_ac3_repeated_identical_failure_does_not_duplicate_the_alert(self):
        """Повтор того же отказа не плодит вторую строку алерта (тот же
        дедуп `alerts.raise_alert`, что уже проверен T040 для ветки без
        usage-событий) — но КАЖДЫЙ повтор всё равно прибавляет верхнюю
        оценку к `spent_estimate_usd` заново: недоучёт не должен
        накапливаться молча только потому, что алерт уже открыт.

        Ловит мутацию: второй прогон не прибавляет оценку («алерт уже
        открыт — выходим раньше»/забыт вызов начисления до дедупа
        алерта) — колонка останется равна одной константе вместо двух,
        тест покраснеет.
        """
        conn = store.db()

        for _ in range(2):
            spend.charge_missing_result(
                conn, self.TASK, "verifier", "попытка 1/3",
                "обрыв stdout-пайпа", partial_tokens=777, saw_usage_event=True)

        self.assertEqual(len(self.threshold_alerts()), 1)
        self.assertAlmostEqual(self.task_row()["spent_estimate_usd"],
                               2 * config.STEP_COST_ESTIMATE_USD)
