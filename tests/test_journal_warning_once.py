"""Юнит-тесты `orchestrator/budget.py::journal_warning_once` и трёх его
вызывающих мест (SPEC 01M3HP7WAXKFK3GYZ3T6HX08M0, требования 1-7).

Постоянная копия покрытия приёмочной планки задачи (`tasks/
01M3HP7WAXKFK3GYZ3T6HX08M0/acceptance_tests/`) — та планка уходит при
уборке каталога задачи, этот файл остаётся регрессией `tests/` (тот же
приём, что у `tests/test_runner_model_preflight.py`).

Песочницы берутся готовыми: `tests/sandbox.py::SchemaConnTmpRootTest` для
двух бюджетных мест (обоим нужна только БД) и `tests/
test_runner_model_preflight.py::_StepSandbox` для предполёта (настоящий
путь `runner.cmd_run` с подменённым процессом агента).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import budget, config, doctor, runner, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest, capture  # noqa: E402
from tests.test_runner_model_preflight import (TABLE_MODEL,  # noqa: E402
                                               _StepSandbox)

WARN_CHECK_NAME = "версия CLI"


def spend_levels(budget_usd: float, count: int) -> list:
    """`count` расходов СТРОГО между порогом предупреждения и потолком,
    возрастающих: пересечённый порог один, а текст предупреждения (он несёт
    текущие суммы) на каждом шаге свой. Считается от
    `config.BUDGET_ALERT_RATIO` — порог остаётся крутилкой Оператора."""
    threshold = budget_usd * config.BUDGET_ALERT_RATIO
    room = budget_usd - threshold
    return [threshold + room * (i + 1) / (count + 1) for i in range(count)]


class _TaskInDbTest(SchemaConnTmpRootTest):
    """Одна задача в `in_dev` без единой записи `state -> ...` в журнале —
    вырожденный случай «граница 0» (весь журнал = одно пребывание)."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, self.TASK, "Шум журнала", "in_dev",
                          "task/t001-shum", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def details(self, action: str) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]


class JournalWarningOnceTest(_TaskInDbTest):
    """Сам узел подавления в изоляции — без бюджета и предполёта."""

    ACTION = "предупреждение теста"

    def write(self, detail: str, *, key) -> bool:
        return budget.journal_warning_once(self.conn, self.TASK, "fsm",
                                           self.ACTION, detail, key=key)

    def test_second_identical_warning_is_suppressed_and_reported_as_such(self):
        """Повтор с тем же ключом не пишется, и узел честно возвращает
        `False` — вызывающий код по этому ответу не судит о печати.

        Ловит мутацию: узел пишет запись всегда (подавления нет) или,
        наоборот, возвращает `True` на подавленном повторе — второй случай
        сделал бы ответ бесполезным для любого читателя.
        """
        self.assertTrue(self.write("текст", key="текст"))
        self.assertFalse(self.write("текст", key="текст"))

        self.assertEqual(self.details(self.ACTION), ["текст"])

    def test_a_different_text_key_gives_a_second_entry(self):
        """Другой текст — другое предупреждение (требование 3).

        Ловит мутацию: сверка идёт по одному `action`, без ключа —
        содержательно новое предупреждение с тем же действием потерялось бы.
        """
        self.write("первый", key="первый")
        self.write("второй", key="второй")

        self.assertEqual(self.details(self.ACTION), ["первый", "второй"])

    def test_key_none_suppresses_regardless_of_the_text(self):
        """`key=None` — ключ есть само действие: так подавляется «бюджет:
        предупреждение», чей текст меняется на каждом шаге (требование 3).

        Ловит мутацию: `None` трактуется как «ключ = текст» (например
        `key or detail`) — записей стало бы столько, сколько срабатываний.
        """
        self.write("суммы A", key=None)
        self.write("суммы B", key=None)

        self.assertEqual(self.details(self.ACTION), ["суммы A"])

    def test_state_entry_record_shifts_the_boundary(self):
        """Повторный вход в состояние (запись `state -> ...`) открывает
        журнал тому же предупреждению заново (требование 4).

        Ловит мутацию: сверка идёт по ВСЕЙ истории задачи, без отсечки по
        последней записи входа в состояние — предупреждение нового
        пребывания было бы проглочено навсегда.
        """
        self.write("текст", key="текст")
        store.journal(self.conn, self.TASK, "fsm",
                      f"{budget.STATE_ENTRY_ACTION_PREFIX}in_dev",
                      "повторный вход")

        self.write("текст", key="текст")

        self.assertEqual(self.details(self.ACTION), ["текст", "текст"])

    def test_a_foreign_tasks_warning_does_not_suppress_this_one(self):
        """Скоуп — журнал ЭТОЙ задачи: одинаковое предупреждение у соседа
        подавлением не является.

        Ловит мутацию: выборка журнала взята по всему пульту
        (`store.all_steps`/`steps_of_action`) вместо журнала задачи — одна
        задача глушила бы предупреждения всех остальных.
        """
        other = "T002"
        store.insert_task(self.conn, other, "Сосед", "in_dev",
                          "task/t002-sosed", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        budget.journal_warning_once(self.conn, other, "fsm", self.ACTION,
                                    "текст", key="текст")

        self.assertTrue(self.write("текст", key="текст"))


class BudgetWarningsDedupTest(_TaskInDbTest):
    """Оба бюджетных места требования 1 — на настоящих функциях."""

    def test_spec_budget_not_applied_is_journaled_once_but_printed_twice(self):
        """Два прохода гейта с «бюджет из SPEC не применён» — одна запись
        журнала и две печати (требования 1, 6).

        Ловит мутацию: подавление обёрнуто вокруг пары «журнал + print»
        целиком (или оформлено ранним `return` из ветки) — Оператор у
        терминала перестал бы видеть повторные срабатывания.
        """
        store.update_task(self.conn, self.TASK,
                          budget_usd=config.DEFAULT_BUDGET_USD,
                          budget_source=config.BUDGET_SOURCE_OPERATOR)
        meta = {"budget_usd": f"{config.DEFAULT_BUDGET_USD / 2:g}"}

        out = "".join(capture(budget.apply_spec_budget, self.conn,
                              store.get_task(self.conn, self.TASK), meta)
                      for _ in range(2))

        self.assertEqual(len(self.details(budget.SPEC_NOT_APPLIED_ACTION)), 1)
        self.assertEqual(out.count("бюджет из SPEC не применён"), 2, out)

    def test_both_not_applied_branches_share_the_suppression(self):
        """Ветка «уже применён» подавляется тем же узлом, что и ветка
        «потолок задан Оператором» — один класс, а не один экземпляр.

        Ловит мутацию: подавление поставлено только в первую ветку функции
        — вторая писала бы запись на каждый проход гейта, как до задачи.
        """
        store.update_task(self.conn, self.TASK, budget_usd=25.0,
                          budget_source=config.BUDGET_SOURCE_SPEC)
        meta = {"budget_usd": "25"}

        for _ in range(2):
            capture(budget.apply_spec_budget, self.conn,
                    store.get_task(self.conn, self.TASK), meta)

        self.assertEqual(self.details(budget.SPEC_NOT_APPLIED_ACTION),
                         ["$25.00 — уже применён, остаётся $25.00"])

    def test_budget_alert_is_journaled_once_despite_changing_sums(self):
        """Несколько шагов после порога `config.BUDGET_ALERT_RATIO` — одна
        запись «бюджет: предупреждение» и печать на каждое срабатывание
        (требования 1, 3, 6).

        Ловит мутацию: ключом подавления взят текст предупреждения — суммы
        в нём разные, и журнал получил бы запись на каждый шаг.
        """
        budget_usd = config.DEFAULT_BUDGET_USD
        store.update_task(self.conn, self.TASK, budget_usd=budget_usd)

        printed = []
        for spent in spend_levels(budget_usd, 3):
            store.update_task(self.conn, self.TASK, spent_usd=spent)
            printed.append(capture(budget.enforce_budget, self.conn,
                                   self.TASK, "in_dev"))

        self.assertEqual(len(set(printed)), 3, printed)
        self.assertEqual(len(self.details(budget.BUDGET_WARNING_ACTION)), 1)

    def test_exhaustion_escalates_even_after_a_suppressed_warning(self):
        """Исчерпание бюджета журналируется и эскалирует задачу независимо
        от предупреждения в том же пребывании (требование 5).

        Ловит мутацию: подавление навешено на `enforce_budget` целиком
        (один ключ на всю функцию) — запись об исчерпании и эскалация
        пропали бы вслед за предупреждением.
        """
        budget_usd = config.DEFAULT_BUDGET_USD
        store.update_task(self.conn, self.TASK, budget_usd=budget_usd,
                          spent_usd=spend_levels(budget_usd, 1)[0])
        capture(budget.enforce_budget, self.conn, self.TASK, "in_dev")
        store.update_task(self.conn, self.TASK, spent_usd=budget_usd)

        capture(budget.enforce_budget, self.conn, self.TASK, "in_dev")

        self.assertEqual(store.get_task(self.conn, self.TASK)["state"],
                         "escalated")
        self.assertEqual(len(self.details("state -> escalated")), 1)


class PreflightWarningDedupTest(_StepSandbox):
    """Шаг роли `developer`, чей предполёт отдаёт ровно одно управляемое
    предупреждение."""

    def setUp(self):
        super().setUp()
        self.set_model(TABLE_MODEL)
        self.set_cli_version("9.9.9")
        self.warn_detail = "claude 9.9.9 ≠ пин 2.1.251"
        self.patch(doctor, "preflight_checks", self._preflight_checks)

    def _preflight_checks(self, role: str, target: str) -> list:
        return [doctor.Check(WARN_CHECK_NAME, "warn", self.warn_detail)]

    def warning_details(self) -> list:
        return [r["detail"] for r in self.journal_rows()
                if r["action"] == runner.PREFLIGHT_WARNING_ACTION]

    def expected(self, warn_detail: str) -> str:
        return f"{WARN_CHECK_NAME}: {warn_detail}"

    def test_the_same_warning_on_two_steps_is_one_entry_and_two_prints(self):
        """Два шага роли в одном пребывании с одним и тем же текстом — одна
        запись журнала, две печати (требования 1, 6): именно этот класс дал
        162 записи об одной версии CLI за 13–27.09.

        Ловит мутацию: подавление к записи предполёта не подключено (или
        ключом взят номер шага/время вместо текста) — второй шаг допишет
        вторую запись с тем же текстом.
        """
        out = self.run_step() + self.run_step()

        self.assertEqual(self.warning_details(),
                         [self.expected(self.warn_detail)])
        self.assertEqual(out.count(self.warn_detail), 2, out)

    def test_a_different_warning_text_gives_a_second_entry(self):
        """Другой текст предупреждения в том же пребывании — вторая запись
        (требование 3, ключ — текст).

        Ловит мутацию: подавление написано по ВИДУ записи, без сверки
        текста — второе, содержательно новое предупреждение потерялось бы.
        """
        first = self.warn_detail
        self.run_step()
        second = "claude 9.9.9 ≠ пин 3.0.0"
        self.warn_detail = second

        self.run_step()

        self.assertEqual(self.warning_details(),
                         [self.expected(first), self.expected(second)])


if __name__ == "__main__":
    unittest.main()
