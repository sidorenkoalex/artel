"""Юнит-тесты корневого `conftest.py` (SPEC 01M2B6K3EM7F2J72RC2F520Y2K,
требования 2-4) — гейт сбора pytest по признаку роли в окружении
(`ARTEL_ROLE`), заменяющий снятый этой же задачей клиентский
PreToolUse-хук `docs/reference/role-home/claude/hooks/bash_guard.py`.

Прогон — subprocess (не вызов хуков pytest напрямую): `conftest.py`
смотрит на окружение и argv ЦЕЛОГО процесса, изнутри того же процесса
это не подделать надёжно.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

from orchestrator.config import ARTEL_ROLE_ENV

ROOT = Path(__file__).resolve().parents[1]
REASON_MARKER = "Сторож роли"


def _run_pytest(args, role):
    env = dict(os.environ)
    env.pop(ARTEL_ROLE_ENV, None)
    if role is not None:
        env[ARTEL_ROLE_ENV] = role
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=100)


class ConftestRoleGuardTest(unittest.TestCase):

    def test_bare_pytest_blocked_under_role(self):
        """Голый `pytest` без единого пути-аргумента отказывает под
        ARTEL_ROLE.

        Ловит мутацию: `conftest.py` не читает `ARTEL_ROLE` вовсе (либо
        читает, но не отказывает при пустом списке позиционных
        аргументов) — прогон вернул бы код 0 вместо отказа.
        """
        result = _run_pytest([], role="developer")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(REASON_MARKER, result.stdout + result.stderr)

    def test_tests_dir_blocked_under_role(self):
        """`pytest tests` (каталог целиком, не конкретный файл) отказывает
        под ARTEL_ROLE.

        Ловит мутацию: guard принимает буквальный токен `tests` как
        целевой путь наравне с `tests/test_x.py` — тогда весь каталог
        прошёл бы, хотя требование 2 называет его нецелевым явно.
        """
        result = _run_pytest(["tests"], role="developer")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(REASON_MARKER, result.stdout + result.stderr)

    def test_targeted_file_collects_under_role(self):
        """Путь к конкретному файлу под `tests/` собирается и прогоняется
        под ARTEL_ROLE без отказа.

        Ловит мутацию: перепутанное условие («если ARTEL_ROLE» без учёта
        наличия целевого пути) — тогда даже адресный прогон отказал бы.
        """
        result = _run_pytest(["tests/test_slugify.py", "-q"], role="developer")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(REASON_MARKER, result.stdout + result.stderr)

    def test_no_role_env_prior_behavior(self):
        """Без `ARTEL_ROLE` в окружении сбор идёт как обычно, даже для
        нецелевого запуска (`--collect-only`, без пути) — Оператор/CI не
        затронуты.

        Ловит мутацию: guard срабатывает независимо от присутствия
        `ARTEL_ROLE` — тогда обычный прогон Оператора отказал бы тем же
        REASON.
        """
        result = _run_pytest(["--collect-only", "-q"], role=None)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(REASON_MARKER, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
