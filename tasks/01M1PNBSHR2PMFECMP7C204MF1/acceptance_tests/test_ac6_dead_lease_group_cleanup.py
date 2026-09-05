"""AC-6 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Снятие мёртвого lease
(release мёртвого lease требования 2 — путь doctor.check_leases/
orchestrator/release.py::cmd_release для уже неживого держателя) добивает
остаточную группу процессов, если она ещё жива, в рамках снятия lease.»

ANSWER-1 (tasks/01M1PNBSHR2PMFECMP7C204MF1/ANSWER-1.md), Вопрос 2,
вариант B, разводит два анкера AC-6 по немедленности:

- `release.cmd_release` — немедленный путь требования 2: бьёт остаточную
  группу БЕЗ флага, как и остальные пути AC-3..AC-5.
- `doctor.check_leases` — снятие остаточной группы ТОЛЬКО под
  `doctor --fix`; обычный `doctor` остаётся наблюдательным (алерт,
  существующее поведение `check_leases`, не предмет этой задачи).

Оба сценария используют тот же приём, что AC-4/AC-5: агентный шаг
заводится РЕАЛЬНЫМ `run_agent_once` в фоне (пишет свой pgid туда, откуда
его прочитает адресующий путь, — независимо от того, lease это или
журнал, AC-2), а «мёртвый держатель» — реальный, уже завершённый процесс
(`dead_pid`), а не сам заведённый шаг: инцидент как раз про то, что
ПУЛЬТ-обёртка умерла, а потомки агентного шага — нет.

Красен до реализации: `release.cmd_release` сегодня снимает только
строку `leases`, не трогая ни один OS-процесс; `doctor.check_leases` не
трогает OS-процессы вовсе (только incident-алерт) ни с `--fix`, ни без.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AgentStepSandbox, fake_claude_cli, release,  # noqa: E402
                      run_doctor, wait_while_alive)


class DeadLeaseGroupCleanupTest(AgentStepSandbox):

    SESSION = "dead-lease-test-session"

    def test_ac6_release_kills_residual_group_of_a_dead_lease(self):
        """`release <id>` на задаче с мёртвым держателем лизы (пульт-
        обёртка уже завершилась) добивает остаточный потомок агентного
        шага — «без флага», немедленный путь (ANSWER-1).

        Ловит мутацию: если `cmd_release` продолжает только удалять
        строку `leases` (сегодняшнее поведение) и не находит записанную
        AC-2 группу шага — потомок останется жив после `release`,
        несмотря на то что сама строка lease корректно снимается уже
        сегодня (это НЕ то, что здесь проверяется).
        """
        dead = self.dead_pid()
        self.install_dummy_lease(dead, session_id=self.SESSION)

        thread = self.run_step_in_background(self.agent_with_child_cmd())
        agent_pid, child_pid = self.read_agent_and_child_pid()

        release.cmd_release(self.TASK)
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive(), "фоновый шаг не завершился "
                         "после release")

        self.assertTrue(wait_while_alive(child_pid, timeout=5.0),
                        "потомок агентного процесса (аналог pytest/"
                        "unittest) пережил release мёртвого lease")

    def test_ac6_doctor_check_leases_group_kill_gated_by_fix(self):
        """`doctor` (без `--fix`) на той же мёртвой лизе — только алерт,
        группа НЕ трогается (ANSWER-1, вариант B: «обычный doctor
        остаётся наблюдательным»); `doctor --fix` — та же ситуация,
        группа снимается.

        Ловит мутацию: если снятие остаточной группы `check_leases`
        сделать БЕЗУСЛОВНЫМ (без гейта `--fix`) — потомок погибнет уже на
        первом, «наблюдательном» прогоне, и первый `assertTrue` (потомок
        жив после прогона без `--fix`) покраснеет вместо ожидаемого
        сценария «жив -> снят только после --fix».
        """
        self.bootstrap_doctor_environment()

        dead = self.dead_pid()
        self.install_dummy_lease(dead, session_id=self.SESSION)
        thread = self.run_step_in_background(self.agent_with_child_cmd(
            out_name="pids_fix.txt"))
        agent_pid, child_pid = self.read_agent_and_child_pid("pids_fix.txt")

        with fake_claude_cli():
            # `run_doctor` глотает `SystemExit` — на этой мёртвой лизе
            # `check_leases` честно и легитимно возвращает `fail`
            # (существующее поведение, не предмет AC-6), а `cmd_doctor`
            # завершается `sys.exit(1)` на ЛЮБОМ провале; здесь важны
            # только побочные эффекты (живость потомка), не код возврата
            # всей команды `doctor`.
            run_doctor(fix=False)
            still_alive = not wait_while_alive(child_pid, timeout=1.0)
            self.assertTrue(still_alive,
                            "потомок агентного шага снят ПРОСТЫМ `doctor` "
                            "(без --fix) — снятие мёртвого lease обязано "
                            "быть под флагом (ANSWER-1)")

            run_doctor(fix=True)
            thread.join(timeout=10)
            self.assertTrue(wait_while_alive(child_pid, timeout=5.0),
                            "потомок агентного шага пережил `doctor --fix`")


if __name__ == "__main__":
    unittest.main()
