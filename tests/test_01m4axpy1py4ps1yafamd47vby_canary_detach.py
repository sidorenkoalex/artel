"""Публичная команда canary: отвязанный запуск, результат и справка.
Группа: долгоживущий
Красен до реализации: --detach ещё не запускает процесс и не печатает файл результата.
"""

import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, config, runner, store
from tests.sandbox import TmpRootTest, capture


class CanaryDetachTest(TmpRootTest):
    """Процесс канарейки подменён объектом, который сам не заканчивается."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.launches = []

    def invoke(self, k, launcher):
        with mock.patch.object(runner, "in_role_environment", return_value=False), \
             mock.patch.object(sys, "argv", ["artel.py", "canary", "--k", str(k),
                                            "--detach"]), \
             mock.patch.object(artel.subprocess, "Popen", launcher):
            return capture(artel.main)

    def paths_in(self, output):
        return [Path(word.strip("'\"(),;")) for word in re.findall(
            re.escape(str(self.root)) + r"[^\s]*", output)]

    def test_ac11_detach_returns_pid_log_result_and_new_session(self):
        """Два размера выборки возвращают управление сразу, сообщая pid и оба пути.

        Ловит мутацию: команда ждёт завершения дочернего процесса или запускает его в сессии вызывающего.
        """
        real_popen = subprocess.Popen
        for k in (1, 2):
            with self.subTest(k=k):
                def launch(argv, *args, **kwargs):
                    proc = real_popen([sys.executable, "-c",
                                       "import time; time.sleep(5)"],
                                      *args, **kwargs)
                    self.launches.append((list(argv), kwargs, proc))
                    return proc

                started = time.monotonic()
                output = self.invoke(k, launch)
                self.assertTrue(self.launches, f"зерно: {self.seed}; {output}")
                argv, _kwargs, proc = self.launches[-1]
                self.addCleanup(lambda p=proc: (p.kill() if p.poll() is None else None,
                                                p.wait()))
                self.assertLess(time.monotonic() - started, 3,
                                f"зерно: {self.seed}; команда ждала дочерний процесс")
                self.assertIsNone(proc.poll(), f"зерно: {self.seed}; child уже закончил")
                self.assertIn(str(proc.pid), output,
                              f"зерно: {self.seed}; {output}")
                log_lines = [line for line in output.splitlines()
                             if "лог" in line.lower()]
                result_lines = [line for line in output.splitlines()
                                if "результат" in line.lower()]
                self.assertTrue(any(self.paths_in(line) for line in log_lines),
                                f"зерно: {self.seed}; {output}")
                self.assertTrue(any(self.paths_in(line) for line in result_lines),
                                f"зерно: {self.seed}; {output}")
                self.assertNotEqual(os.getsid(proc.pid), os.getsid(0),
                                    f"зерно: {self.seed}; child унаследовал сессию")
                self.assertIn(str(k), argv,
                              f"зерно: {self.seed}; аргументы потеряли --k")

    def test_ac12_completed_detached_run_has_visible_row_and_result_file(self):
        """Подменённый дочерний прогон заканчивается зелёной строкой и файлом по выданному пути.

        Ловит мутацию: родитель сообщает путь результата, но дочерний путь завершения не создаёт файл — после окончания файла нет.
        """
        child_args = []

        class Pending:
            pid = 70017

            def wait(self, *args, **kwargs):
                raise AssertionError("родитель не ждёт")

        def launch(argv, *args, **kwargs):
            child_args.extend(argv)
            return Pending()

        output = self.invoke(1, launch)
        self.assertIn(str(Pending.pid), output, f"зерно: {self.seed}; {output}")
        result_paths = [p for line in output.splitlines()
                        if "результат" in line.lower() for p in self.paths_in(line)]
        self.assertTrue(result_paths, f"зерно: {self.seed}; {output}")
        result_path = result_paths[0]
        self.assertFalse(result_path.exists(), f"зерно: {self.seed}; прогон ещё идёт")

        def finished_canary(**kwargs):
            store.insert_canary_run(store.db(), "fixture", "fixture", "01FIXTURE",
                                    1, 0.0, 0, 0, "killed", None, False, False,
                                    main_sha="f" * 40, verdict="green")

        # Исполняем тот же вход CLI, который родитель передал дочернему
        # процессу. Ведение подменено, запись результата остаётся кодом CLI.
        start = child_args.index("canary")
        with mock.patch.object(runner, "in_role_environment", return_value=False), \
             mock.patch.object(sys, "argv", ["artel.py", *child_args[start:]]), \
             mock.patch.object(canary, "cmd_canary", finished_canary):
            capture(artel.main)
        rows = store.green_canary_runs(store.db())
        self.assertTrue(any(row["task_id"] == "01FIXTURE" for row in rows),
                        f"зерно: {self.seed}; {rows}")
        self.assertTrue(result_path.is_file(), f"зерно: {self.seed}; {result_path}")


class CanaryHelpTest(TmpRootTest):
    def test_ac13_help_names_detach_and_operator_session_default(self):
        """Справка публичной команды содержит флаг и его штатность для сессии Оператора.

        Ловит мутацию: флаг работает, но строка справки не обновлена — Оператор не увидит штатный способ запуска.
        """
        help_text = artel.__doc__ or ""
        positions = [match.start() for match in re.finditer("--detach", help_text)]
        self.assertTrue(positions, "справка не называет --detach")
        self.assertTrue(any(all(fragment in help_text[max(0, at - 220):at + 220].lower()
                                for fragment in ("canary", "отвяз", "штатн",
                                                 "сесси", "оператор"))
                            for at in positions),
                        "справка не называет отвязанный запуск штатным для сессии Оператора")
