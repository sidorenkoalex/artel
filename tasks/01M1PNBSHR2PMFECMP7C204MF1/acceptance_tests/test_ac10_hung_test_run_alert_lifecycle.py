"""AC-10 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Найденный сторожем
(AC-8, AC-9) процесс поднимает алерт kind=incident с pid, возрастом и
путём worktree в сообщении; открытый алерт авто-ack'ается, когда процесс
исчезает (тем же приёмом, что _auto_ack_gone для check_leases).»

Два наблюдения одного сценария: (1) форма алерта — открыт, kind=incident,
сообщение несёт pid и путь worktree подставного процесса; (2) жизненный
цикл — когда процесс исчезает МИМО сторожа (внешний kill, не
`doctor --fix`), следующий прогон `doctor` подтверждает (auto-ack) ранее
открытый алерт по этому источнику, а не оставляет его висеть вечно.

Красен до реализации: `config.HUNG_TEST_RUN_AGE_SEC` — то же допущение
имени, что в AC-8/AC-9 (`_sandbox.py`), которого пока нет —
`AttributeError` на подмене. Реализована константа под другим именем —
падает содержательно: сторож не существует, ни (1), ни (2) не находят
алерта вовсе.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AgentStepSandbox, alerts, config, fake_claude_cli,  # noqa: E402
                      run_doctor, store)


class HungTestRunAlertLifecycleTest(AgentStepSandbox):

    TASK_HUNG = "T-AC10-HUNG"

    def test_ac10_raises_incident_alert_and_auto_acks_when_process_is_gone(self):
        """Алерт открытого incident по подставному прогону несёт pid и
        путь worktree; после того как процесс исчезает (внешний kill),
        следующий прогон doctor его авто-ack'ает.

        Ловит мутацию: если алерт заводится другим `kind` (например,
        `warning`, которого вовсе нет в `alerts.KINDS` — см. ANSWER-1,
        Вопрос 1) — первый `assertTrue` (открытый incident с pid/путём)
        не найдёт подходящую строку; если авто-ack не реализован (алерт
        остаётся открытым навсегда) — второй `assertFalse` (алерт всё ещё
        среди открытых incident) покраснеет.
        """
        self.bootstrap_doctor_environment()
        self.ensure_task(self.TASK_HUNG)
        workdir = self.worktree_dir(self.TASK_HUNG)
        proc = self.spawn_hung(self.TASK_HUNG, sleep_sec=60)

        with mock.patch.object(config, "HUNG_TEST_RUN_AGE_SEC", 1), \
             fake_claude_cli():
            # Целые секунды: `ps`/`etime` (BSD/macOS) — разрешение в
            # целую секунду, см. `test_ac8_hung_test_run_age_threshold.py`.
            time.sleep(1.5)
            run_doctor(fix=False)

            open_incidents = alerts.open_alerts(store.db(), "incident")
            matching = [r for r in open_incidents
                       if str(proc.pid) in r["message"]
                       and str(workdir) in r["message"]]
            self.assertTrue(
                matching,
                "нет открытого incident-алерта с pid и путём worktree "
                "подставного зависшего прогона")

            proc.kill()
            proc.wait()
            run_doctor(fix=False)

            still_open = alerts.open_alerts(store.db(), "incident")
            still_matching = [r for r in still_open
                              if str(proc.pid) in r["message"]]
            self.assertFalse(
                still_matching,
                "алерт по исчезнувшему процессу остался открытым — "
                "авто-ack не сработал")


if __name__ == "__main__":
    unittest.main()
