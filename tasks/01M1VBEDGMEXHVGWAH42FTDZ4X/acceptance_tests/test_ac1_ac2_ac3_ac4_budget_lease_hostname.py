"""Приёмочные тесты 01M1VBEDGMEXHVGWAH42FTDZ4X — AC-1, AC-2, AC-3, AC-4:
`budget <id> <usd>` под живым lease задачи (требование 1, SPEC.md).

Красен до реализации: `orchestrator/lease.py::acquire`, которую
`budget.cmd_budget` зовёт через `lease.run_locked`, отказывает ЛЮБОМУ
чужому session_id с живым heartbeat — hostname держателя не сравнивается
вовсе (прочитано в orchestrator/lease.py, строки 58-66). AC-1/AC-2
покраснеют: `cmd_budget` уйдёт в `sys.exit` вместо изменения потолка,
«во время шага» некому появиться в журнале. AC-3 покраснеет тем же путём
(без AC-1 значение не меняется, сверять после шага нечего). AC-4 —
исключение: разный hostname уже отказывает и сегодня (не предмет
требования 1), см. докстринг класса ниже.
"""
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutoCycleTest, insert_lease  # noqa: E402
from orchestrator import budget, config, store  # noqa: E402

FOREIGN_SESSION = "operator-second-terminal"
FOREIGN_HOST_SAME = socket.gethostname()
FOREIGN_HOST_OTHER = "some-other-operator-host.invalid"


class BudgetAcceptedUnderSameHostLiveLeaseTest(AutoCycleTest):
    """AC-1: lease живой (heartbeat свежий), принадлежит ДРУГОЙ session_id,
    но ТОМУ ЖЕ hostname, что и вызывающий процесс — `budget` обязан
    принять новый потолок немедленно, не дожидаясь освобождения lease."""

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=10.0, spent_usd=1.0)
        insert_lease(store.db(), self.TASK, FOREIGN_SESSION, FOREIGN_HOST_SAME)

    def test_ac1_budget_changes_ceiling_immediately_under_same_host_lease(self):
        """Живой lease того же hostname (чужая session_id) не блокирует
        `budget` — потолок задачи меняется тем же вызовом, без отказа.

        Ловит мутацию: сверка lease в `cmd_budget`/`acquire` остаётся
        привязанной только к session_id (без исключения по hostname) —
        `budget` уйдёт в `sys.exit` вместо изменения `tasks.budget_usd`,
        и это же исключение поймает тест.
        """
        self.capture(budget.cmd_budget, self.TASK, "40")

        row = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(row["budget_usd"], 40.0)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_OPERATOR)


class BudgetJournalsDuringStepMarkerTest(AutoCycleTest):
    """AC-2: журнальная запись «бюджет изменён», сделанная во время живого
    шага роли (условие AC-1), несёт в `detail` пометку «во время шага
    <роль>» с именем роли ТЕКУЩЕГО состояния задачи."""

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=10.0, spent_usd=1.0)
        insert_lease(store.db(), self.TASK, FOREIGN_SESSION, FOREIGN_HOST_SAME)

    def test_ac2_journal_names_the_current_role_during_the_live_step(self):
        """Detail записи «бюджет изменён» называет роль состояния `in_dev`
        (`developer`) — не просто факт изменения без пометки момента.

        Ловит мутацию: пометка «во время шага <роль>» не добавляется вовсе
        (журнал несёт только старое/новое значение, как до этой задачи) —
        `assertIn` не найдёт ни слова «шага», ни имени роли в detail.
        """
        self.capture(budget.cmd_budget, self.TASK, "40")

        details = [d for _, a, d in self.journal_rows() if a == "бюджет изменён"]
        self.assertEqual(len(details), 1, details)
        self.assertIn("во время шага", details[0])
        self.assertIn("developer", details[0])


class BudgetBlockSeesTheAppliedValueTest(AutoCycleTest):
    """AC-3: проверка потолка ПОСЛЕ шага (`budget.enforce_budget`) видит
    значение `tasks.budget_usd`, применённое во время самого шага (AC-1),
    а не значение, действовавшее на момент старта шага."""

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        # Расход уже выше СТАРОГО потолка — до подъёма следующий же
        # `enforce_budget` эскалировал бы задачу по старому значению.
        self.set_state("in_dev", budget_usd=10.0, spent_usd=12.0)
        insert_lease(store.db(), self.TASK, FOREIGN_SESSION, FOREIGN_HOST_SAME)

    def test_ac3_post_step_check_uses_the_ceiling_raised_mid_step(self):
        """Потолок, поднятый во время живого шага, снимает блокировку
        `enforce_budget` НЕМЕДЛЕННО после того же шага — без промежуточного
        возврата в escalated по устаревшему значению.

        Ловит мутацию: `enforce_budget`/`budget_block` кэшируют потолок,
        прочитанный на старте шага (или AC-1 не реализован вовсе) —
        расход $12 против старого потолка $10 уводит задачу в `escalated`
        несмотря на поднятый до $40 потолок.
        """
        self.capture(budget.cmd_budget, self.TASK, "40")

        escalated = budget.enforce_budget(store.db(), self.TASK, "in_dev")

        self.assertFalse(
            escalated, "enforce_budget эскалировал по значению до подъёма "
            "потолка")
        self.assertEqual(self.state(), "in_dev")


class BudgetStillRefusesForeignHostLiveLeaseTest(AutoCycleTest):
    """AC-4: живой lease с ДРУГИМ hostname по-прежнему отказывает `budget`
    тем же текстом, что и до этой задачи — исключение требования 1 не
    распространяется на межхостовый случай (инцидент 02.09.2026,
    докстринг `orchestrator/lease.py::foreign_live_lease`).

    Зелёный с рождения: `lease.acquire` уже сегодня отказывает любой чужой
    session_id с живым heartbeat, включая другой hostname (сверено
    прогоном ниже) — эта задача обязана СОХРАНИТЬ этот отказ, не ослабить
    его при введении исключения для своего hostname (AC-1).
    """

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=10.0, spent_usd=1.0)
        insert_lease(store.db(), self.TASK, FOREIGN_SESSION, FOREIGN_HOST_OTHER)

    def test_ac4_other_hostname_refuses_with_the_same_wording(self):
        """`budget` под живым lease чужого хоста завершается тем же
        `sys.exit`, что и любая другая мутирующая команда под чужим живым
        lease — потолок не меняется.

        Ловит мутацию: исключение AC-1 реализовано ПО session_id вместо
        hostname (сравнение «это не МОЯ сессия» вместо «это не МОЙ
        хост») — межхостовый чужой держатель ошибочно пропущен бы как
        «свой», и `sys.exit` здесь не случится.
        """
        with self.assertRaises(SystemExit) as exit_:
            self.capture(budget.cmd_budget, self.TASK, "40")

        message = str(exit_.exception)
        self.assertIn(FOREIGN_SESSION, message)
        self.assertIn(FOREIGN_HOST_OTHER, message)
        self.assertIn("подожди её или разберись", message)

        row = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(row["budget_usd"], 10.0,
                              "потолок изменился несмотря на отказ")


if __name__ == "__main__":
    import unittest
    unittest.main()
