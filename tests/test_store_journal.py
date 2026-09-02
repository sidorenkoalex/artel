"""Юнит-тесты `orchestrator.store.journal` (SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC,
требования 1-2, AC-1/AC-2): identity сессии в каждой новой записи журнала.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

TASK = "T001"


class JournalSessionIdTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def last_step(self):
        return store.task_steps(store.db(), TASK)[-1]

    def test_default_resolves_the_current_session_from_the_environment(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-env"}):
            store.journal(store.db(), TASK, "operator", "тест")

        self.assertEqual(self.last_step()["session_id"], "sess-env")

    def test_explicit_session_id_wins_over_the_environment(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-env"}):
            store.journal(store.db(), TASK, "operator", "тест",
                          session_id="sess-explicit")

        self.assertEqual(self.last_step()["session_id"], "sess-explicit")

    def test_falls_back_to_parent_pid_without_env_var(self):
        env = dict(os.environ)
        env.pop("ARTEL_SESSION_ID", None)
        with mock.patch.dict(os.environ, env, clear=True):
            store.journal(store.db(), TASK, "operator", "тест")

        self.assertEqual(self.last_step()["session_id"], f"ppid-{os.getppid()}")


if __name__ == "__main__":
    unittest.main()
