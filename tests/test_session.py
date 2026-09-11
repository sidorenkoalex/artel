"""Юнит-тесты orchestrator/session.py (SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC,
требование 1, AC-1; SPEC 01M290PP4KBTG1KYS1PWKQJH6T, требование 2 —
identity сессии из файла `.artel/session-id`, не только `ppid`-fallback).

`ResolveSessionIdTest`/`SessionIdentityFileTest` наследуют `tests.sandbox.
TmpRootTest`, не голый `unittest.TestCase`, как раньше: с этой задачи
`resolve_session_id` при отсутствии аргумента/переменной окружения читает
(и при первом обращении заводит) файл в `.artel/` реального `config.ROOT`
— непропатченный `config.ROOT` означал бы, что тест на «ppid-fallback»
зависит от того, остался ли на диске файл сессии от ПРЕДЫДУЩЕГО прогона
этого же файла юнит-тестов (или от любого прежнего вызова CLI на этой
машине), тот же класс утечки в реальное дерево пульта, которого избегает
вся остальная песочница (`tests/sandbox.py`).
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, lease, session  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


def _env_without_session_var() -> dict:
    env = dict(os.environ)
    env.pop("ARTEL_SESSION_ID", None)
    return env


class ResolveSessionIdTest(TmpRootTest):

    def test_explicit_argument_wins(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-sess"}):
            self.assertEqual(session.resolve_session_id("explicit"), "explicit")

    def test_env_var_wins_over_ppid_fallback(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-sess"}):
            self.assertEqual(session.resolve_session_id(None), "env-sess")

    def test_falls_back_to_parent_pid_when_no_var_and_no_file_yet(self):
        with mock.patch.dict(os.environ, _env_without_session_var(),
                             clear=True):
            self.assertEqual(session.resolve_session_id(None),
                             f"ppid-{os.getppid()}")

    def test_no_argument_defaults_to_none(self):
        with mock.patch.dict(os.environ, _env_without_session_var(),
                             clear=True):
            self.assertEqual(session.resolve_session_id(),
                             f"ppid-{os.getppid()}")

    def test_lease_module_re_exports_the_same_function_object(self):
        """AC-1: `lease.resolve_session_id` — тот же объект функции, не
        вторая копия, которая могла бы разойтись именем источника."""
        self.assertIs(lease.resolve_session_id, session.resolve_session_id)


class SessionIdentityFileTest(TmpRootTest):
    """SPEC 01M290PP4KBTG1KYS1PWKQJH6T, требование 2, AC-4/AC-5.

    Независимое от `tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/`
    покрытие: та планка — гейт приёмки задачи, не часть `tests/`, которую
    CI гоняет на каждый пуш ветки (`.github/workflows/ci.yml`).
    """

    def test_first_access_creates_session_file_under_dot_artel(self):
        session_file = config.ROOT / ".artel" / "session-id"
        self.assertFalse(session_file.exists())

        with mock.patch.dict(os.environ, _env_without_session_var(),
                             clear=True):
            result = session.resolve_session_id(None)

        self.assertEqual(result, f"ppid-{os.getppid()}")
        self.assertTrue(session_file.exists())

    def test_second_call_reads_persisted_identity_despite_ppid_change(self):
        """Ровно механизм, которым отвязанный `auto` (другой `ppid` после
        репарентинга на init) и `watch --mine`, вызванный из той же
        сессии, видят одну и ту же identity (AC-5): второй вызов читает
        уже записанное значение, не пересчитывает живой `os.getppid()`."""
        with mock.patch.dict(os.environ, _env_without_session_var(),
                             clear=True):
            with mock.patch("os.getppid", return_value=111):
                first = session.resolve_session_id(None)
            with mock.patch("os.getppid", return_value=222):
                second = session.resolve_session_id(None)

        self.assertEqual(first, "ppid-111")
        self.assertEqual(second, first)

    def test_explicit_argument_and_env_var_still_beat_the_file(self):
        """Порядок приоритета не меняется — файл только последний источник
        ПЕРЕД `ppid`-fallback'ом, не первый."""
        with mock.patch.dict(os.environ, _env_without_session_var(),
                             clear=True):
            file_identity = session.resolve_session_id(None)
            self.assertEqual(session.resolve_session_id("явный-аргумент"),
                             "явный-аргумент")

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-value"}):
            self.assertEqual(session.resolve_session_id(None), "env-value")

        self.assertNotEqual(file_identity, "явный-аргумент")
        self.assertNotEqual(file_identity, "env-value")


if __name__ == "__main__":
    unittest.main()
