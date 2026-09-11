"""Приёмочные тесты 01M1THKRK8HPXA7Y2SRB0RFTN2 — AC-1 (SPEC.md).

Красен до реализации: сейчас НИЧЕГО в `runner._cmd_run` не читает
`alerts.open_alerts(conn, "incident")` в поисках стоп-крана — открытый
алерт не мешает старту шага вовсе, поэтому `test_ac1_...blocks...`
падает на `assertIn(STOP_CRANE_WORD, ...)`/`popen.assert_not_called()`
(агент реально спавнится), а не на отсутствии модуля: код требования 1
этой задачи ещё не написан.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (RunPipelineSandbox, mentions_stop_crane,  # noqa: E402
                      raise_stop_crane_alert, runner, store)

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import auto  # noqa: E402


class Ac1RunBlockedByOpenAlertTest(RunPipelineSandbox):
    """AC-1: пока по target self открыт алерт стоп-крана, `run` любой
    задачи этого target отказывает начать НОВЫЙ агентный шаг с причиной,
    называющей стоп-кран — в stdout вызова и в журнале задачи."""

    def setUp(self):
        super().setUp()
        # `write_spec`/`write_plan` — те же артефакты-минимум, что
        # `tests/test_invariants.py::AgentRunsOnlyFromRunTest` заводит
        # перед тем, как `run` реально доходит до `spawn_agent` (без
        # SPEC.md на диске бриф developer отказывает раньше, с текстом
        # «бриф не собран», ещё до места, где встанет проверка стоп-крана).
        self.write_spec("ready")
        self.write_plan("draft")
        self.set_state("in_dev")
        # Артефакт-минимум В РАБОЧЕМ КАТАЛОГЕ роли (не там же, куда пишет
        # `write_plan` выше — см. докстринг `seed_worktree_plan`): без
        # него успешный (rc=0) прогон честно ретраится «без артефакта»,
        # маскируя собой предмет теста этого файла.
        self.seed_worktree_plan()

    def test_ac1_open_alert_blocks_run_with_reason_in_stdout_and_journal(self):
        """Открытый алерт стоп-крана self блокирует `run` этой же задачи:
        агент не спавнится, причина отказа называет стоп-кран и в stdout,
        и в журнале задачи.

        Ловит мутацию: если проверку открытого алерта уберут (или
        поставят её ПОСЛЕ спавна агента), `popen` окажется вызванным и
        `stop-кран` не появится ни в выводе, ни в журнале.
        """
        raise_stop_crane_alert(store.db())

        out, popen, code = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id="session-run"))

        popen.assert_not_called()
        # Отказ `run` уходит `sys.exit(текст)` (тем же приёмом, что и
        # отказ по паузе) — текст осядет в `code` исключения, не в stdout;
        # причина теста — «стоп-кран назван в выводе ВЫЗОВА», обе части
        # вместе и есть этот вывод для человека, запустившего `run`.
        self.assertTrue(
            mentions_stop_crane(out) or mentions_stop_crane(str(code or "")),
            f"ни stdout, ни причина отказа не называют стоп-кран: "
            f"out={out!r}, code={code!r}")
        journal_text = self.journal_tail_text()
        self.assertTrue(mentions_stop_crane(journal_text),
                       f"причина отказа не попала в журнал задачи: {journal_text!r}")

    def test_ac1_alert_opened_mid_step_does_not_interrupt_running_step(self):
        """Алерт, заведённый уже ПОСЛЕ старта агентного шага (симуляция —
        `spawn_agent` сам заводит алерт перед тем, как отдать управление),
        не прерывает этот уже идущий шаг: он дорабатывает штатно, а вот
        следующий шаг цикла `auto` — уже нет, ровно как алерт, увиденный
        ДО старта, блокирует его в первом тесте этого файла.

        Ловит мутацию: если отказ проверялся бы не один раз перед стартом,
        а опросом состояния уже во время шага, `spawn_agent` был бы вызван
        меньше или процесс шага не дописал бы «agent run finished» —
        сигнал, что шаг оборвали, а не дали ему закончиться.
        """
        # `spawn_agent` — фейковый, но зовётся РЕАЛЬНЫМ циклом `auto`
        # столько раз, сколько тот решит сам; событие «алерт завёлся
        # прямо во время шага» по смыслу теста происходит РОВНО один раз
        # — второй и далее вызов `spawn_agent` (если цикл всё же сделает
        # их, потому что блокировки требования 1 ещё нет) не должны
        # повторно заводить тот же алерт.
        opened = False

        def open_alert_mid_step() -> None:
            nonlocal opened
            if not opened:
                raise_stop_crane_alert(store.db())
                opened = True

        out, popen, code = self.run_with_mid_step_side_effect(
            lambda: auto.cmd_auto(self.TASK, session_id="session-auto"),
            open_alert_mid_step)

        self.assertEqual(
            popen.call_count, 1,
            f"алерт, заведённый во время первого шага, не должен был ни "
            f"оборвать его, ни разрешить второй — агент спавнился "
            f"{popen.call_count} раз(а). Вывод auto: {out!r}")
        journal_text = self.journal_tail_text()
        self.assertIn("agent run finished", journal_text,
                     f"уже стартовавший шаг обязан был доработать штатно: "
                     f"{journal_text!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
