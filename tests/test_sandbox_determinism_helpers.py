"""Помощники песочницы детерминизма тестов (SPEC 01M4G8MNEPECNX1TCEDW4T4RPX):
`PollGate` — ожидание итераций цикла опроса вместо срока по часам,
`TempfileInTestRoot` — уборка сирот теста в своём временном каталоге.
"""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import doctor, liveness
from orchestrator.doctor import orphans
from tests.sandbox import (PollGate, TempfileInTestRoot, TmpRootTest,
                           isolate_orphan_sweep, wait_processes_gone)


class PollGateTest(unittest.TestCase):

    def start_loop(self, gate: PollGate, iterations: int) -> list:
        """Цикл в своём потоке: запись итерации, затем пауза `gate`."""
        seen = []

        def loop():
            try:
                for number in range(iterations):
                    seen.append(number)
                    gate.sleep(0.2)
            finally:
                gate.finish()

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5.0)
        self.addCleanup(gate.release)
        return seen

    def test_step_runs_exactly_the_granted_iterations(self):
        """`step(n)` возвращается, когда цикл прошёл ровно n итераций сверх
        первой и стоит на паузе.

        Ловит мутацию: пауза не держит цикл (`sleep` сразу возвращается) —
        к возврату `step` итераций больше разрешённых; `step` не ждёт конца
        итерации — итераций меньше.
        """
        gate = PollGate()
        seen = self.start_loop(gate, 50)
        self.assertTrue(gate.step())
        self.assertEqual(len(seen), 2)
        self.assertTrue(gate.step(3))
        self.assertEqual(len(seen), 5)
        self.assertEqual(gate.polls, 5)

    def test_step_reports_loop_that_ended(self):
        """Цикл завершился раньше — `step` отвечает `False`, а не ждёт.

        Ловит мутацию: `finish` не будит ожидающий `step` — тест виснет до
        таймаута pytest; `step` отвечает `True` на завершённый цикл.
        """
        gate = PollGate()
        seen = self.start_loop(gate, 2)
        self.assertFalse(gate.step(5))
        self.assertEqual(seen, [0, 1])

    def test_release_lets_loop_run_on_its_own(self):
        """После `release` пауза больше не держит цикл.

        Ловит мутацию: `release` не будит цикл — поток так и стоит на паузе,
        `join` возвращается с живым потоком.
        """
        gate = PollGate()
        done = threading.Event()

        def loop():
            for _ in range(20):
                gate.sleep(0.2)
            done.set()

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        gate.release()
        thread.join(5.0)
        self.assertTrue(done.is_set())


class WaitProcessesGoneTest(unittest.TestCase):

    def test_answers_when_processes_are_gone_or_polls_run_out(self):
        """Ответ — сразу, когда процессов нет; `False` — исчерпав проверки.

        Ловит мутацию: помощник отвечает по первой проверке, не дожидаясь
        (живой процесс — `True`); число проверок не ограничено — тест висит.
        """
        states = iter([True, True, False])
        self.assertTrue(wait_processes_gone([1], lambda _pid: next(states),
                                            polls=5, pause=0))
        self.assertFalse(wait_processes_gone([1], lambda _pid: True,
                                             polls=3, pause=0))


class TempfileInTestRootTest(unittest.TestCase):

    def test_system_temp_is_replaced_by_own_directory(self):
        """Системный временный каталог процесса подменён своим каталогом
        теста; каталог убирается вместе с тестом.

        Ловит мутацию: заместитель отдаёт `tempfile.gettempdir()` как есть —
        уборка сирот снова идёт по системному каталогу.
        """
        proxy = TempfileInTestRoot(self)
        own = Path(proxy.gettempdir())
        self.assertNotEqual(own.resolve(),
                            Path(tempfile.gettempdir()).resolve())
        self.assertTrue(own.is_dir())
        self.assertEqual(proxy.gettempdir(), str(own))
        self.doCleanups()
        self.assertFalse(own.exists())

    def test_temp_directory_chosen_by_test_is_kept(self):
        """Тест, сам уведший `tempfile.tempdir`, видит свой каталог.

        Ловит мутацию: заместитель подменяет любой каталог, не только
        системный, — уборка теста канарейки не видит его каталогов.
        """
        with tempfile.TemporaryDirectory() as own, \
                mock.patch.object(tempfile, "tempdir", own):
            self.assertEqual(TempfileInTestRoot(self).gettempdir(), own)


class OrphanSweepStaysInTestRootTest(TmpRootTest):

    def test_sweep_under_sandbox_keeps_system_temp_canary_directory(self):
        """`doctor` под песочницей не удаляет каталог канарейки в системном
        временном каталоге, даже без маркера владельца.

        Ловит мутацию: `TmpRootTest.setUp` не изолирует уборку сирот
        (`isolate_orphan_sweep` не зовётся) — уборка удаляет каталог
        `artel-canary-origin-*` чужого процесса без маркера.
        """
        system = tempfile.mkdtemp(prefix="artel-canary-origin-",
                                  dir=os.path.realpath(tempfile.gettempdir()))
        self.addCleanup(lambda: os.path.isdir(system) and os.rmdir(system))
        doctor._fix_orphan_temp_dirs()
        self.assertTrue(os.path.isdir(system))

    def test_sweep_still_removes_orphans_in_own_root(self):
        """В своём каталоге теста уборка действует: каталог origin мёртвого
        владельца удалён.

        Ловит мутацию: заместитель отдаёт пустой или несуществующий путь —
        уборка ничего не видит, и сам `doctor --fix` не проверяется
        тестами песочницы.
        """
        root = Path(orphans.tempfile.gettempdir())
        dead = root / "artel-canary-origin-dead"
        dead.mkdir()
        (dead / liveness.CANARY_OWNER_MARKER).write_text("99999999",
                                                         encoding="utf-8")
        doctor._fix_orphan_temp_dirs()
        self.assertFalse(dead.exists())


class IsolateOrphanSweepTest(unittest.TestCase):

    def test_patch_is_lifted_after_test(self):
        """Подмена снимается вместе с тестом.

        Ловит мутацию: патчер не снимается — модуль уборки остаётся с
        заместителем чужого, уже завершённого теста.
        """
        isolate_orphan_sweep(self)
        self.assertIsInstance(orphans.tempfile, TempfileInTestRoot)
        self.doCleanups()
        self.assertIs(orphans.tempfile, tempfile)


if __name__ == "__main__":
    unittest.main()
