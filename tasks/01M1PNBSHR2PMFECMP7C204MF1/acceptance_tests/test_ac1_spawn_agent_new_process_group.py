"""AC-1 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Агентный шаг роли
(orchestrator/runner.py) запускается в новой группе процессов (сессии) —
так что pgid дочернего процесса отличается от pgid пульта.»

Красен до реализации: `runner.spawn_agent` сегодня — голый
`subprocess.Popen(cmd, **kwargs)` без выставления новой сессии/группы,
поэтому у спавненного процесса тот же pgid, что и у пульта (процесс
наследует группу вызывающего) — `assertNotEqual` ниже падает, сравнивая
равные числа.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import runner, wait_for  # noqa: E402


class SpawnAgentNewProcessGroupTest(unittest.TestCase):
    """Проверяет САМУ точку спавна (`runner.spawn_agent`), в обход всей
    остальной механики шага (lease/бюджет/git) — предмет AC-1 это
    исключительно то, в какой группе процессов оказывается спавненный
    процесс."""

    def setUp(self):
        self._live = []
        self.addCleanup(self._reap_all)

    def _reap_all(self):
        for proc in self._live:
            if proc.poll() is None:
                proc.kill()
            proc.wait()

    def test_ac1_agent_process_gets_a_pgid_different_from_the_pult(self):
        """Реальный дочерний процесс, заведённый `runner.spawn_agent`, —
        новая сессия (сам себе pgid), не унаследованная группа вызывающего.

        Ловит мутацию: если из будущей реализации убрать флаг новой
        сессии (`start_new_session=True`/эквивалент) у вызова
        `subprocess.Popen` внутри `spawn_agent`, дочерний процесс снова
        унаследует pgid этого тестового процесса («пульта») — сравнение
        ниже перестанет ловить разницу и тест покраснеет.
        """
        import os
        pult_pgid = os.getpgid(0)

        proc = runner.spawn_agent(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._live.append(proc)

        # Поллинг, не разовое чтение сразу после Popen(): `setsid()`
        # новой сессии выполняется в САМОМ потомке до `exec`, и в общем
        # случае не гарантированно завершается раньше, чем родительский
        # `Popen()` вернёт управление — короткое окно опроса вместо
        # гонки на «правильной» реализации.
        wait_for(lambda: os.getpgid(proc.pid) != pult_pgid, timeout=2.0)
        child_pgid = os.getpgid(proc.pid)
        self.assertNotEqual(child_pgid, pult_pgid,
                            "pgid спавненного агентного процесса совпал с "
                            "pgid пульта — новая группа процессов не заведена")


if __name__ == "__main__":
    unittest.main()
