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
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AgentStepSandbox, config, doctor, release,  # noqa: E402
                      wait_while_alive)
from tests.sandbox import claude_only_popen, claude_only_run  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]


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
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills",
                        dirs_exist_ok=True)
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates",
                        dirs_exist_ok=True)
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        config.TARGETS.write_text(
            "targets:\n  artel:\n    forge: github\n"
            "    url: https://example.invalid/artel\n    base: main\n"
            "    token_slot: artel-token\n    no_paths: []\n"
            "    project_skills: []\n    merge_gate: operator\n",
            encoding="utf-8")
        config.BACKUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
        config.BACKUP_MARKER.write_text("ok", encoding="utf-8")

        dead = self.dead_pid()
        self.install_dummy_lease(dead, session_id=self.SESSION)
        thread = self.run_step_in_background(self.agent_with_child_cmd(
            out_name="pids_fix.txt"))
        agent_pid, child_pid = self.read_agent_and_child_pid("pids_fix.txt")

        with mock.patch.object(doctor.shutil, "which",
                               lambda name: "/usr/bin/claude" if name == "claude" else None), \
             mock.patch.object(doctor.subprocess, "run",
                               side_effect=claude_only_run("0.0.1 (Claude Code)\n")), \
             mock.patch.object(doctor.subprocess, "Popen",
                               side_effect=claude_only_popen(_ok_live_smoke())):
            doctor.cmd_doctor(fix=False)
            still_alive = not wait_while_alive(child_pid, timeout=1.0)
            self.assertTrue(still_alive,
                            "потомок агентного шага снят ПРОСТЫМ `doctor` "
                            "(без --fix) — снятие мёртвого lease обязано "
                            "быть под флагом (ANSWER-1)")

            doctor.cmd_doctor(fix=True)
            thread.join(timeout=10)
            self.assertTrue(wait_while_alive(child_pid, timeout=5.0),
                            "потомок агентного шага пережил `doctor --fix`")


class _FakeLiveSmokeProc:
    """Замена `subprocess.Popen` для `doctor.live_smoke` — только
    `.communicate` (по образцу `tests/test_doctor.py::FakeLiveSmokeProc`,
    не общий `tests.sandbox` — определён локально там же, где и
    используется)."""

    def __init__(self, output: str, returncode: int = 0):
        self.output = output
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self.output, None

    def kill(self) -> None:
        pass

    def wait(self, timeout=None) -> int:
        return self.returncode


def _ok_live_smoke():
    return _FakeLiveSmokeProc('{"type":"result","total_cost_usd":0.0,"usage":{}}\n')


if __name__ == "__main__":
    unittest.main()
