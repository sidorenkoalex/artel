"""Адресные пробелы контракта ошибок общих примитивов.

Группа: долгоживущий
Зелёный с рождения: прежняя обработка ошибок ОС проверяется через публичные интерфейсы.
"""

import errno
import os
import random
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import liveness


class LivenessErrorsTest(unittest.TestCase):
    def test_ac11_liveness_pid_and_group_probe_errors(self):
        """Отказ доступа отличим от исчезновения PID и PGID.

        PID наблюдается через маркер владельца; PGID — через счётчик
        публичной остановки при недоступном ps и исчезновении на SIGTERM.
        Ловит мутацию: PermissionError проверки существования даёт False
        вместо True — владелец считается мёртвым либо счётчик группы равен нулю.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        cases = ((PermissionError(errno.EPERM, "probe denied"), True),
                 (ProcessLookupError(errno.ESRCH, "gone"), False),
                 (OSError(errno.EIO, "probe failed"), False))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pid in rng.sample(range(100000, 200000), 3):
                (root / liveness.CANARY_OWNER_MARKER).write_text(str(pid))
                for error, alive in cases:
                    with self.subTest(seed=seed, pid=pid, error=type(error).__name__):
                        with mock.patch.object(os, "kill", side_effect=error):
                            self.assertEqual(liveness.owner_alive(root), alive,
                                             f"зерно: {seed}")

                        def killpg(group, signum):
                            if signum == 0:
                                raise error
                            raise ProcessLookupError(errno.ESRCH, "gone on send")

                        with mock.patch.object(subprocess, "run", side_effect=OSError("ps unavailable")), \
                             mock.patch.object(os, "killpg", side_effect=killpg):
                            count = liveness.terminate_process_group(pid, grace_sec=0)
                        self.assertIsInstance(count, int, f"зерно: {seed}")
                        self.assertEqual(count > 0, alive, f"зерно: {seed}")

    def test_ac13_signal_send_errors_preserve_integer_result(self):
        """Исчезновение и отказ доступа на каждом сигнале не выходят к потребителю.

        Ловит мутацию: исключение SIGKILL или SIGTERM пробрасывается
        наружу вместо возврата числового счётчика.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for pgid in rng.sample(range(200000, 300000), 2):
            for failed_signal in (signal.SIGTERM, signal.SIGKILL):
                for error in (PermissionError, ProcessLookupError):
                    with self.subTest(seed=seed, pgid=pgid, signal=failed_signal, error=error):
                        calls = []

                        def killpg(group, signum):
                            calls.append((group, signum))
                            if signum == failed_signal:
                                raise error("send failed")

                        with mock.patch.object(subprocess, "run", return_value=
                                               subprocess.CompletedProcess([], 0, f"{pgid}\n", "")), \
                             mock.patch.object(os, "killpg", side_effect=killpg):
                            count = liveness.terminate_process_group(pgid, grace_sec=0)
                        self.assertIsInstance(count, int, f"зерно: {seed}")
                        self.assertIn((pgid, failed_signal), calls, f"зерно: {seed}")
