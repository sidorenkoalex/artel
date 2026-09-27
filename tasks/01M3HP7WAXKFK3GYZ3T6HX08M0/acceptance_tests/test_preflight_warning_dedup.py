"""Планка AC-1, AC-2, AC-3, AC-6: дедупликация записи `pre-flight WARNING`
в журнале задачи по ключу «текст предупреждения + пребывание в состоянии»
и неприкосновенность вывода в stdout у всех трёх подавляемых мест.

Красен до реализации: подавления повторов в `orchestrator/runner.py:354`
ещё нет — второй шаг роли с тем же предупреждением пишет вторую запись
журнала, поэтому AC-1 видит 2 записи вместо 1, а AC-6 не находит
подавленного повтора, за печатью которого он и следит. AC-2/AC-3 (там,
где записей обязано быть две) на сегодняшнем коде зелены с рождения и
охраняют реализацию от пересола — подавления там, где его быть не должно.

Песочница — `_StepSandbox` из `tests/test_runner_model_preflight.py`
(своей копии здесь нет, скил test-authoring): настоящий путь
`runner.cmd_run` во временном `config`-корне с подменённым процессом
агента, `roles.yaml`/каталогом моделей/ответом `claude --version` под
управлением теста. Набор предполётных проверок подменён на управляемый
(`doctor.preflight_checks`) — предмет критериев не в том, ОТКУДА взялось
предупреждение, а в том, сколько раз оно попадает в журнал.

Пребывание в состоянии здесь одно по построению: `_StepSandbox` ставит
задаче `in_dev` прямой записью в БД, минуя `store.set_state`, поэтому
записи `state -> in_dev` в журнале нет — вырожденный случай «граница 0»
из `store.refusal_history`. AC-3 добавляет её сам: именно эта запись, по
требованию 4 SPEC и по тексту самого критерия, и есть граница пребывания.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import budget, config, doctor, store  # noqa: E402
from tests.test_runner_model_preflight import (TABLE_MODEL,  # noqa: E402
                                               _StepSandbox)

from _util import (BUDGET_WARNING_ACTION, PREFLIGHT_WARNING_ACTION,  # noqa: E402
                   SPEC_NOT_APPLIED_ACTION, capture_value, spend_levels)

WARN_CHECK_NAME = "версия CLI"


class PreflightWarningDedupTest(_StepSandbox):
    """Шаг роли `developer`, у которого предполёт всегда отдаёт ровно одно
    предупреждение с управляемым текстом."""

    def setUp(self):
        super().setUp()
        self.set_model(TABLE_MODEL)
        self.set_cli_version("9.9.9")
        self.warn_detail = "claude 9.9.9 ≠ пин 2.1.251"
        self.patch(doctor, "preflight_checks", self._preflight_checks)

    # ------------------------------------------------------------ утилиты

    def _preflight_checks(self, role: str, target: str) -> list:
        """Предполёт из одного warn с текущим `self.warn_detail` — блокирующих
        проверок нет, шаг обязан доходить до агента."""
        return [doctor.Check(WARN_CHECK_NAME, "warn", self.warn_detail)]

    def warning_details(self) -> list[str]:
        """Детали записей `pre-flight WARNING` журнала задачи, по порядку."""
        return [r["detail"] for r in self.journal_rows()
                if r["action"] == PREFLIGHT_WARNING_ACTION]

    def expected_detail(self, warn_detail: str) -> str:
        """Деталь записи журнала так, как её собирает `runner.py`:
        `"<имя проверки>: <текст>"` — текст самого предупреждения эта
        задача не меняет (требование 7)."""
        return f"{WARN_CHECK_NAME}: {warn_detail}"

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in self.journal_rows()
                if r["action"] == action]

    def journal_state_reentry(self, state: str = "in_dev") -> None:
        """Запись `state -> <состояние>` в журнал задачи — та самая граница
        пребывания, которой требование 4 SPEC и текст AC-3 определяют
        повторный вход (`store.set_state` пишет её на каждом переходе;
        здесь она кладётся напрямую, чтобы сценарий не тащил за собой
        побочные эффекты перехода — фиксацию sha и паспорт задачи)."""
        store.journal(store.db(), self.TASK, "fsm", f"state -> {state}",
                      "повторный вход в состояние")

    # ----------------------------------------------------------- сценарии

    def test_ac1_same_preflight_warning_twice_is_one_journal_entry(self):
        """Два шага роли подряд в одном пребывании в состоянии, оба с
        совпадающим текстом предупреждения pre-flight — в журнале ровно
        одна запись `pre-flight WARNING`.

        Ловит мутацию: подавление не подключено к записи предполёта вовсе
        (или подключено, но ключом взят номер шага/время, а не текст
        предупреждения) — второй шаг допишет вторую запись с тем же
        текстом, и счёт даст 2.
        """
        self.run_step()
        self.run_step()

        self.assertEqual(self.warning_details(),
                         [self.expected_detail(self.warn_detail)])

    def test_ac2_a_different_preflight_text_gives_a_second_entry(self):
        """В том же пребывании в состоянии предупреждение pre-flight с
        ДРУГИМ текстом даёт вторую запись `pre-flight WARNING`: ключ
        подавления — текст, а не вид записи.

        Первый шаг предупреждает об одной версии CLI, второй — о другой
        (сменился текст, состояние то же).

        Ловит мутацию: подавление написано по ВИДУ записи («такая запись у
        задачи в этом пребывании уже есть — молчим»), без сверки текста —
        второе, содержательно новое предупреждение потерялось бы, и в
        журнале осталась бы одна запись вместо двух.
        """
        first = self.warn_detail
        self.run_step()
        second = "claude 9.9.9 ≠ пин 3.0.0"
        self.warn_detail = second

        self.run_step()

        self.assertEqual(self.warning_details(),
                         [self.expected_detail(first),
                          self.expected_detail(second)])

    def test_ac3_reentering_the_state_journals_the_same_warning_again(self):
        """После повторного входа задачи в то же состояние (новая запись
        `state -> in_dev`) то же самое предупреждение pre-flight
        журналируется снова: одна запись в прошлом пребывании, одна в новом.

        Ловит мутацию: подавление считает «уже журналировали» по ВСЕЙ
        истории задачи, без отсечки по последней записи `state -> in_dev`
        — повторный вход не сдвинул бы границу, и вторая запись не
        появилась бы (в журнале осталась бы одна).
        """
        self.run_step()
        self.journal_state_reentry()

        self.run_step()

        expected = self.expected_detail(self.warn_detail)
        self.assertEqual(self.warning_details(), [expected, expected])

    def test_ac6_every_trigger_of_all_three_warnings_reaches_stdout(self):
        """Число печатей равно числу срабатываний у всех трёх
        предупреждений, включая те повторы, которые в журнале подавлены.

        Разыгрываются все три места требования 1 на одной задаче: два шага
        роли с одним и тем же текстом предполёта, два прохода
        `apply_spec_budget` с «бюджет из SPEC не применён» и три вызова
        `enforce_budget` после порога `config.BUDGET_ALERT_RATIO`. Печати
        считаются по тексту каждого срабатывания, записи журнала — по
        действию: печатей столько же, сколько срабатываний, записей — по
        одной на место.

        Ловит мутацию: подавление поставлено ВЫШЕ печати — например,
        ранним `return` из ветки предупреждения или проверкой вокруг пары
        «журнал + print» целиком, — и Оператор у терминала перестаёт видеть
        повторные срабатывания, хотя требование 6 их сокращать запрещает.
        """
        conn = store.db()
        budget_usd = config.DEFAULT_BUDGET_USD
        store.update_task(conn, self.TASK, budget_usd=budget_usd,
                          budget_source=config.BUDGET_SOURCE_OPERATOR)
        meta = {"budget_usd": f"{budget_usd / 2:g}"}
        spec_detail = f"${budget_usd / 2:.2f} — потолок задан Оператором"

        preflight_out = self.run_step() + self.run_step()
        spec_out = ""
        for _ in range(2):
            _, printed = capture_value(budget.apply_spec_budget, conn,
                                       store.get_task(conn, self.TASK), meta)
            spec_out += printed
        alert_out = ""
        levels = spend_levels(budget_usd, 3)
        for spent in levels:
            store.update_task(conn, self.TASK, spent_usd=spent)
            _, printed = capture_value(budget.enforce_budget, conn, self.TASK,
                                       "in_dev")
            alert_out += printed

        self.assertEqual(preflight_out.count(self.warn_detail), 2,
                         preflight_out)
        self.assertEqual(spec_out.count(spec_detail), 2, spec_out)
        # Доля порога — от `config.BUDGET_ALERT_RATIO`, не литералом «70%»:
        # порог остаётся крутилкой Оператора.
        threshold_words = f"больше {int(config.BUDGET_ALERT_RATIO * 100)}% бюджета"
        printed_alerts = [line for line in alert_out.splitlines()
                          if threshold_words in line]
        self.assertEqual(len(printed_alerts), 3, alert_out)
        self.assertEqual(len(set(printed_alerts)), 3,
                         "фикстура: суммы в тексте каждого срабатывания свои")
        self.assertEqual(len(self.warning_details()), 1)
        self.assertEqual(len(self.journal_details(SPEC_NOT_APPLIED_ACTION)), 1)
        self.assertEqual(len(self.journal_details(BUDGET_WARNING_ACTION)), 1)


if __name__ == "__main__":
    unittest.main()
