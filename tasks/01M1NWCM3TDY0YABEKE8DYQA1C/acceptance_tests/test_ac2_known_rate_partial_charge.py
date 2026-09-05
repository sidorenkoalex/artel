"""AC-2 (SPEC: «Стоимость частичного шага при таймауте: курс токенов
вместо тишины») — «Таймаут шага... с известным курсом роли и хотя бы
одним промежуточным usage-событием: частичная стоимость по счётчикам
токенов и курсу роли прибавлена к spent_usd задачи (не ноль); в журнал
шага записана строка «частичная стоимость по курсу» с суммой в $ и
числом токенов.»

Роль сценария — `test_author`, не `developer`: критерий не называет
конкретную роль, а `developer` — та самая роль, чей ИДЕНТИЧНЫЙ сценарий
(таймаут + usage-события) уже залочен существующим тестом
`tests/test_step_cost.py:319`
(`ChargeMissingResultTest.test_partial_tokens_are_journaled_without_touching_spent`)
с ПРОТИВОПОЛОЖНЫМ утверждением (spent_usd остаётся 0.0) — конфликт
между этим и требованием 1/AC-1 (курс обязателен для всех четырёх
ролей, включая developer) был эскалирован в `test_ac1_token_rate_table.py`
и разрешён Оператором в ANSWER-2.md (вариант A: курс заводится на все
четыре роли, T040-тесты роли `developer` переписывает разработчик в
`in_dev`, не test_author). Сам механизм требования 2 (начисление по
курсу при известной роли) проверяется здесь ролью, не участвующей в
правке T040 — она остаётся вне зоны этого файла.

Тест не фиксирует ТОЧНУЮ формулу пересчёта токенов в доллары (курс
несёт раздельную цену входного/выходного токена, а `partial_tokens` —
разбивка по видам счётчиков, тот же набор, что и сегодня отдают
`stream_usage_by_type`/`partial_tokens_from_log`) — только то, что
АС-2 требует буквально: сумма ненулевая и журнал несёт предписанный
текст с $ и числом токенов.

Правка формы (SPEC 01M1PP0VYRT55WN8GGVG66X89Y, требование 2/AC-2,
ADR-0012 п.1б): `partial_tokens` записывается литералом-разбивкой
`{"input_tokens": N}`, а не плоским `int` — новая сигнатура
`spend.charge_missing_result` требует словарь буквально (было решено
этой же SPEC намеренно, не косметика), проверяемое свойство (сумма
ненулевая, текст журнала) не меняется.

Красен до реализации: `spend.charge_missing_result` (orchestrator/
spend.py:143) сегодня НИКОГДА не зовёт `store.charge` — по докстрингу
функции, «store.charge здесь не зовётся ни в одной из веток» (SPEC T040,
сознательно, курс токена нигде не задан). До появления курса роль
"test_author" не может быть «известной ролью» ни в каком смысле — тест
падает на `self.assertGreater(row["spent_usd"], 0.0)` (получает 0.0).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import spend, store  # noqa: E402
from _sandbox import CostTmpRootTest  # noqa: E402


class KnownRatePartialChargeTest(CostTmpRootTest):

    def test_ac2_timeout_with_known_rate_charges_a_nonzero_partial_sum(self):
        """Таймаут роли с известным курсом и usage-событиями до обрыва
        прибавляет ненулевую сумму к `spent_usd` и оставляет в журнале
        строку «частичная стоимость по курсу» с $-суммой и числом
        токенов.

        Ловит мутацию: разработчик реализует требование 3 (алерт +
        верхняя оценка) для ЛЮБОЙ роли без ветвления по наличию курса —
        тогда `spent_usd` останется 0.0, тест покраснеет.
        """
        conn = store.db()

        spend.charge_missing_result(
            conn, self.TASK, "test_author", "попытка 1/3", "таймаут шага",
            partial_tokens={"input_tokens": 1000}, saw_usage_event=True)

        row = self.task_row()
        self.assertGreater(row["spent_usd"], 0.0,
                           "известный курс — сумма обязана быть ненулевой")
        detail = self.journal_rows()[-1][2]
        self.assertIn("частичная стоимость по курсу", detail)
        self.assertIn("1000", detail)
        self.assertIn("$", detail)

    def test_ac2_known_rate_branch_does_not_touch_the_upper_estimate(self):
        """Тот же сценарий не трогает `spent_estimate_usd` — требование 3
        (верхняя оценка) относится к ДРУГОЙ ветке (курс НЕ задан,
        AC-3), а не к этой.

        Ловит мутацию: разработчик по ошибке прибавляет верхнюю оценку
        константы `config.STEP_COST_ESTIMATE_USD` параллельно с точной
        суммой известного курса — `spent_estimate_usd` перестанет быть
        нулевым, тест покраснеет.
        """
        conn = store.db()

        spend.charge_missing_result(
            conn, self.TASK, "test_author", "попытка 1/3", "таймаут шага",
            partial_tokens={"input_tokens": 1000}, saw_usage_event=True)

        self.assertEqual(self.task_row()["spent_estimate_usd"] or 0.0, 0.0)
