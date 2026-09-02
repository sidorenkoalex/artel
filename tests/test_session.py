"""Юнит-тесты orchestrator/session.py (SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC,
требование 1, AC-1): единая функция identity сессии, вынесенная из
`orchestrator/lease.py` в отдельный лист графа импортов.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import lease, session  # noqa: E402


class ResolveSessionIdTest(unittest.TestCase):

    def test_explicit_argument_wins(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-sess"}):
            self.assertEqual(session.resolve_session_id("explicit"), "explicit")

    def test_env_var_wins_over_ppid_fallback(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-sess"}):
            self.assertEqual(session.resolve_session_id(None), "env-sess")

    def test_falls_back_to_parent_pid(self):
        env = dict(os.environ)
        env.pop("ARTEL_SESSION_ID", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(session.resolve_session_id(None),
                             f"ppid-{os.getppid()}")

    def test_no_argument_defaults_to_none(self):
        env = dict(os.environ)
        env.pop("ARTEL_SESSION_ID", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(session.resolve_session_id(),
                             f"ppid-{os.getppid()}")

    def test_lease_module_re_exports_the_same_function_object(self):
        """AC-1: `lease.resolve_session_id` — тот же объект функции, не
        вторая копия, которая могла бы разойтись именем источника."""
        self.assertIs(lease.resolve_session_id, session.resolve_session_id)


if __name__ == "__main__":
    unittest.main()
