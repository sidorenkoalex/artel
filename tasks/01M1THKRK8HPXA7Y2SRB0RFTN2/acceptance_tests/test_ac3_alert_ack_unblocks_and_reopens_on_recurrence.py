"""Приёмочные тесты 01M1THKRK8HPXA7Y2SRB0RFTN2 — AC-3 (SPEC.md).

Красен до реализации: `test_ac3_alert_ack_unblocks_the_next_run` падает
на первом же `popen.assert_not_called()` — требование 1 ещё не блокирует
`run` открытым алертом вовсе, детали в её докстринге. Второй тест класса
`Ac3RecurrenceAfterAckOpensNewAlertTest` (`test_ac3_new_occurrence_after_ack_is_a_new_open_alert`)
— исключение из этого же файла: зелёный с рождения, он проверяет уже
существующее поведение `alerts.py`, не код этой задачи (причина — в его
собственном докстринге).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (LightSandbox, RunPipelineSandbox,  # noqa: E402
                      alerts, mentions_stop_crane,
                      raise_stop_crane_alert, runner, store)

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class Ac3AlertAckUnblocksRunTest(RunPipelineSandbox):
    """AC-3: `alert-ack <id>` открытого алерта стоп-крана снимает
    блокировку — следующий `run` того же target стартует агентный шаг
    штатно."""

    def setUp(self):
        super().setUp()
        # См. tasks/.../test_ac1_run_auto_blocked_by_open_alert.py — без
        # SPEC.md на диске бриф developer отказывает до места, где
        # встанет проверка стоп-крана.
        self.write_spec("ready")
        self.write_plan("draft")
        self.set_state("in_dev")
        # См. tasks/.../test_ac1_run_auto_blocked_by_open_alert.py —
        # артефакт-минимум в рабочем каталоге роли, иначе успешный
        # (rc=0) прогон после ack честно ретраится «без артефакта».
        self.seed_worktree_plan()

    def test_ac3_alert_ack_unblocks_the_next_run(self):
        """`run`, отказавший из-за открытого алерта стоп-крана, начинает
        агентный шаг штатно сразу после `alert-ack` этого алерта — без
        второго срабатывания того же условия.

        Красен до реализации: сейчас первый `run` не отказывает вовсе
        (агент спавнится сразу) — требование 1 ещё не написано, поэтому
        `popen.assert_not_called()` первого прогона не совпадёт.

        Ловит мутацию: если `alert-ack` перестанет сниматься с реальной
        проверки блокировки (например, run продолжит смотреть на
        закешированный факт «алерт был» вместо текущего `ack_ts`),
        второй `run` тоже откажет вместо спавна агента.
        """
        alert_row = raise_stop_crane_alert(store.db())

        out_blocked, popen_blocked, code_blocked = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id="session-run-1"))
        popen_blocked.assert_not_called()
        # `sys.exit(текст)` кладёт причину отказа в `code`, не в stdout
        # (тот же приём, что и отказ по паузе) — см. первый тест
        # tasks/.../test_ac1_run_auto_blocked_by_open_alert.py.
        self.assertTrue(
            mentions_stop_crane(out_blocked) or
            mentions_stop_crane(str(code_blocked or "")),
            f"ни stdout, ни причина отказа не называют стоп-кран: "
            f"out={out_blocked!r}, code={code_blocked!r}")

        error = alerts.ack(store.db(), alert_row["id"], "operator", "")
        self.assertIsNone(error, f"alert-ack отказал: {error}")

        out_unblocked, popen_unblocked, code_unblocked = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id="session-run-2"))
        popen_unblocked.assert_called_once()
        self.assertFalse(mentions_stop_crane(out_unblocked))


class Ac3RecurrenceAfterAckOpensNewAlertTest(LightSandbox):
    """AC-3: повторное срабатывание того же класса ПОСЛЕ `ack` заводит
    НОВЫЙ алерт — не гасится прежним `ack` (автоматического снятия нет).

    Зелёный с рождения: это дословно существующее поведение
    `alerts.raise_alert`/`store.open_alert_exists` (дедуп только среди
    НЕподтверждённых строк — `orchestrator/alerts.py`, докстринг
    `raise_alert`) — эта задача его не меняет, стоп-кран лишь частный
    случай его применения (часть 1 заводит алерт этим же вызовом).
    Проверяется напрямую через `alerts.py`, а не через `run`/`auto`:
    предмет теста — поведение дедупа, не блокировка шага (та — AC-1).
    """

    def test_ac3_new_occurrence_after_ack_is_a_new_open_alert(self):
        """Второе срабатывание того же класса после `ack` первого —
        отдельная открытая строка `alerts`, а не молчаливо погашенная.

        Ловит мутацию: если дедуп `raise_alert` начнёт сверяться со
        ВСЕМИ строками (а не только с неподтверждёнными), второй вызов
        вернёт `False` (не заведён) вместо `True`, и `open_alerts`
        после него не покажет новую строку.
        """
        conn = store.db()
        message = "стоп-кран волны: класс 1б у 3 задач за 15 минут"
        first_opened = alerts.raise_alert(
            conn, self.row()["target"], "incident", "wave_breaker", message)
        self.assertTrue(first_opened)
        first_id = alerts.open_alerts(conn, "incident")[0]["id"]

        error = alerts.ack(conn, first_id, "operator", "")
        self.assertIsNone(error)
        self.assertEqual(alerts.open_alerts(conn, "incident"), [],
                         "после ack первый алерт не должен оставаться открытым")

        second_opened = alerts.raise_alert(
            conn, self.row()["target"], "incident", "wave_breaker", message)

        self.assertTrue(
            second_opened,
            "повторное срабатывание того же класса после ack обязано "
            "завести новый алерт, а не быть погашенным прежним ack")
        open_now = alerts.open_alerts(conn, "incident")
        self.assertEqual(len(open_now), 1)
        self.assertNotEqual(open_now[0]["id"], first_id)


if __name__ == "__main__":
    import unittest
    unittest.main()
