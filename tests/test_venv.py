"""Юнит-тесты orchestrator/venv.py (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8,
требования 2, 6): `.artel/venv` пульта, создаётся идемпотентно.

Постоянная регрессия — переживает закрытие `tasks/
01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests/`, которая проверяла то же
самое подробнее, но живёт только пока задача открыта.

Сеть в тестах запрещена (docs/invariants.md, инвариант 35): подмена
`orchestrator.venv.subprocess.run` — только ветку `pip install`; ветка
`python -m venv` идёт к НАСТОЯЩЕМУ `subprocess.run` (стандартная
библиотека, офлайн) — только так можно честно наблюдать РЕАЛЬНЫЙ
артефакт venv на диске.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import venv as artel_venv  # noqa: E402

REAL_RUN = subprocess.run


def _is_venv_creation_call(args: list) -> bool:
    return len(args) >= 3 and args[1:3] == ["-m", "venv"]


def _make_fake_run(creation_calls: list, pip_calls: list):
    def fake_run(args, **kwargs):
        args = list(args)
        if _is_venv_creation_call(args):
            creation_calls.append(args)
            return REAL_RUN(args, **kwargs)
        pip_calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")
    return fake_run


class VenvSyncTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.target = root / ".artel" / "venv"
        self.lock_file = root / "requirements.lock"
        self.lock_file.write_text("pytest==7.4.4\n", encoding="utf-8")

    def _sync(self):
        creation_calls, pip_calls = [], []
        with mock.patch.object(artel_venv.subprocess, "run",
                               side_effect=_make_fake_run(creation_calls,
                                                          pip_calls)):
            artel_venv.sync(target=self.target, lock_file=self.lock_file)
        return creation_calls, pip_calls

    def test_sync_creates_a_real_venv_and_installs_from_the_lock_file(self):
        """AC-4: `sync()` создаёт `.artel/venv` НАСТОЯЩИМ `python -m venv`
        и ставит зависимости из файла закреплённых версий.

        Ловит мутацию: `sync()` не создаёт venv по-настоящему —
        `pyvenv.cfg` не появится на диске; либо установка не ссылается
        на файл закреплённых версий — `assertIn` откажет.
        """
        creation_calls, pip_calls = self._sync()

        self.assertTrue((self.target / "pyvenv.cfg").exists())
        self.assertTrue(creation_calls)
        self.assertTrue(pip_calls)
        install_call = pip_calls[0]
        self.assertIn("install", install_call)
        self.assertIn(str(self.lock_file), install_call)

    def test_second_call_on_an_existing_venv_is_idempotent(self):
        """AC-5: повторный вызов на уже созданном venv не пересоздаёт
        его.

        Ловит мутацию: `sync()` безусловно зовёт `python -m venv» заново
        — второй вызов добавит запись в `creation_calls`, `assertEqual`
        откажет.
        """
        first_creation, _ = self._sync()
        self.assertEqual(1, len(first_creation))

        second_creation, _ = self._sync()

        self.assertEqual(0, len(second_creation))

    def test_venv_is_created_with_the_pult_own_interpreter(self):
        """AC-6: интерпретатор `.artel/venv` — тот же `sys.executable`,
        которым запущен сам пульт, не `python3` из PATH.

        Ловит мутацию: команда создания собрана как `["python3", "-m",
        "venv", ...]` вместо `[sys.executable, ...]` — `assertEqual`
        откажет.
        """
        creation_calls, _ = self._sync()

        self.assertEqual(sys.executable, creation_calls[0][0])

    def test_install_command_is_exactly_pip_install_dash_r_lock_file(self):
        """AC-15: состав вызванной команды установки — `install -r
        <файл>`, `-r` непосредственно перед путём файла.

        Ловит мутацию: установка собрана без флага `-r`, либо `-r` не
        сопровождается путём файла тем же следующим аргументом —
        `assertIn`/`assertEqual` откажут.
        """
        _creation, pip_calls = self._sync()

        self.assertEqual(1, len(pip_calls))
        install_call = pip_calls[0]
        self.assertIn("install", install_call)
        self.assertIn("-r", install_call)
        r_index = install_call.index("-r")
        self.assertEqual(str(self.lock_file), install_call[r_index + 1])


if __name__ == "__main__":
    unittest.main()
