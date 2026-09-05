"""Юнит-тесты `orchestrator.liveness.terminate_process_group`/
`group_kill_detail` (SPEC 01M1PNBSHR2PMFECMP7C204MF1, требование 2):
общий примитив group-kill, которым пользуются `runner`/`cleanup`/
`pause`/`release`/`doctor` — сквозной путь через каждого из них уже
покрыт `tasks/01M1PNBSHR2PMFECMP7C204MF1/acceptance_tests/`; здесь —
сама функция в изоляции, реальными OS-процессами (SIGTERM/SIGKILL по
`os.killpg` заглушкой не проверить, тот же довод, что и у
`tests/test_pause_now.py`).
"""
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import liveness  # noqa: E402


def _wait_for(predicate, timeout: float = 2.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _spawn_group(sleep_sec: float = 5.0) -> subprocess.Popen:
    """Реальный процесс — лидер собственной сессии (pgid == pid), по
    образцу `runner.spawn_agent`. Поллинг после `Popen()`, не разовое
    чтение сразу за ним: `setsid()` новой сессии выполняется В САМОМ
    потомке до `exec` и не гарантированно завершается раньше, чем
    родительский `Popen()` вернёт управление (тот же довод, что и в
    `tasks/01M1PNBSHR2PMFECMP7C204MF1/acceptance_tests/
    test_ac1_spawn_agent_new_process_group.py`) — без ожидания
    `os.killpg(proc.pid, ...)` мог адресовать группу, которая на этот
    момент ещё не существует (`ProcessLookupError`, тихий no-op)."""
    proc = subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({sleep_sec})"],
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _wait_for(lambda: os.getpgid(proc.pid) == proc.pid)
    return proc


def _spawn_group_with_child(sleep_sec: float = 5.0) -> tuple:
    """Лидер + реальный потомок в ТОЙ ЖЕ группе (потомок не ставит
    свою сессию — наследует pgid лидера, как `pytest`/`unittest`,
    запущенные ролью)."""
    script = (
        "import subprocess, sys, time\n"
        f"c = subprocess.Popen([sys.executable, '-c', "
        f"'import time; time.sleep({sleep_sec})'], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "print(c.pid)\n"
        f"time.sleep({sleep_sec})\n"
    )
    leader = subprocess.Popen(
        [sys.executable, "-c", script], start_new_session=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    _wait_for(lambda: os.getpgid(leader.pid) == leader.pid)
    child_pid = int(leader.stdout.readline().strip())
    leader.stdout.close()
    return leader, child_pid


def _wait_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not liveness._pid_alive(pid):
            return True
        time.sleep(0.02)
    return not liveness._pid_alive(pid)


class TerminateProcessGroupTest(unittest.TestCase):

    def setUp(self):
        self._live = []
        self.addCleanup(self._reap_all)

    def _reap_all(self):
        for proc in self._live:
            if proc.poll() is None:
                proc.kill()
            proc.wait()

    def test_kills_the_leader_and_returns_a_positive_count(self):
        """Ловит мутацию: `terminate_process_group` не шлёт `SIGTERM`
        группе (например, шлёт `SIGTERM` только вызывающему процессу
        или не шлёт вовсе) — лидер переживёт вызов, `proc.wait` ниже
        упадёт по таймауту.

        `proc.wait(timeout=...)`, не поллинг `liveness._pid_alive` —
        тестовый процесс ЯВЛЯЕТСЯ родителем `proc`: не дожатый им
        зомби продолжает отвечать «жив» на `os.kill(pid, 0)` даже
        после успешного `SIGTERM` (тот же класс, что описывает
        докстринг `spawn_hung_test_run` в `_sandbox.py` этой задачи —
        там та же проблема решена нарочным осиротением через
        промежуточную оболочку)."""
        proc = _spawn_group()
        self._live.append(proc)

        count = liveness.terminate_process_group(proc.pid)

        self.assertGreaterEqual(count, 1)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.fail("лидер группы пережил terminate_process_group")

    def test_kills_every_member_of_the_group_not_just_the_leader(self):
        """Ловит мутацию: снятие адресует только найденный/переданный
        pid (`os.kill`), а не всю группу (`os.killpg`) — потомок
        переживёт вызов, хотя лидер корректно снят. Потомок не в
        прямом родительстве тестового процесса — он реально исчезает
        из таблицы процессов после смерти (реап ОС/launchd, не
        зомби), поэтому для него `_wait_dead`/`liveness._pid_alive`
        корректны (в отличие от `leader` выше)."""
        leader, child_pid = _spawn_group_with_child()
        self._live.append(leader)

        liveness.terminate_process_group(leader.pid)

        try:
            leader.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.fail("лидер группы пережил terminate_process_group")
        self.assertTrue(_wait_dead(child_pid),
                        "потомок пережил group-kill — снята не вся группа")

    def test_already_dead_group_returns_zero_without_raising(self):
        """Ловит мутацию: `os.killpg` на уже пустой группе не перехвачен
        (`ProcessLookupError` долетает наружу) — тогда любой путь
        AC-3..AC-6 падал бы на остаточной группе мёртвого lease вместо
        тихой деградации."""
        proc = subprocess.Popen([sys.executable, "-c", "pass"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        proc.wait()

        count = liveness.terminate_process_group(proc.pid)

        self.assertEqual(count, 0)

    def test_never_signals_the_caller_s_own_process_group(self):
        """Ловит мутацию: защитная проверка `pgid == os.getpgid(0)`
        убрана — вызов с pgid ЭТОГО ЖЕ тестового процесса дошёл бы до
        `os.killpg` и оборвал бы сам тестовый прогон сигналом `SIGTERM`/
        `SIGKILL` посреди выполнения."""
        own_pgid = os.getpgid(0)

        count = liveness.terminate_process_group(own_pgid)

        self.assertEqual(count, 0)


class GroupKillDetailTest(unittest.TestCase):

    def test_mentions_both_pgid_and_count(self):
        """Ловит мутацию: формулировка теряет число снятых процессов —
        приёмочный тест AC-7 ищет цифру рядом с корнем «групп» в этой
        же строке."""
        text = liveness.group_kill_detail(4242, 3)

        self.assertIn("4242", text)
        self.assertIn("3", text)
        self.assertIn("групп", text.lower())


if __name__ == "__main__":
    unittest.main()
