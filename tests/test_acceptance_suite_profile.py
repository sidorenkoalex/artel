"""Юнит-тест `orchestrator/acceptance.py::acceptance_suite`: профиль проекта
задачи доходит до полного набора (SPEC 01M52EEFNA1WH31962HVNT0YZ9,
требование 1).
"""
import sqlite3
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, repo_context, store, targets
from tests import sandbox

OWN_VALUES = {
    "command": ["./run-tests"], "long_lived_dir": "backend/tests",
    "long_lived_name": "test_<id>_<name>.py",
    "weakening_scope": ["backend/tests/**"],
    "mutation_claim_scope": ["backend/tests/**"],
    "runner": targets.PROFILE_RUNNER_OWN, "workdir": "backend",
    "env": {"DJANGO_SETTINGS_MODULE": "app.settings"},
}


class AcceptanceSuiteProfileTest(unittest.TestCase):
    """Полный набор приёмки получает профиль `pytest-own` проекта задачи."""

    def call(self, answer, fresh: bool):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        result = acceptance.FullSuiteRun(
            True, acceptance.FULL_SUITE_GREEN, "зелёный", None, "зелёный")
        with sandbox.declared_without_profile("sled"), \
                mock.patch.object(store, "task_target", return_value="sled"), \
                mock.patch.object(repo_context, "profile_of",
                                  return_value=answer) as profile_of, \
                mock.patch.object(acceptance, "full_suite",
                                  return_value=result) as local, \
                mock.patch.object(store, "journal"):
            self.assertIs(acceptance.acceptance_suite(
                conn, Path("/tmp"), "T001", "task/t001", Path("/tmp"),
                actor="approve", fresh=fresh), result)
        profile_of.assert_called_with("sled")
        return local

    def test_own_profile_passed_other_profiles_keep_old_call(self):
        """`pytest-own` — `full_suite(..., command=<профиль>)`; `pult-pytest` и непрочитанный профиль — прежняя форма вызова.

        Проект задачи (`store.task_target`) — `sled`; профиль из
        `repo_context.profile_of`. С `fresh` и без.

        Ловит мутацию: `acceptance_suite` не читает профиль проекта задачи
        и зовёт `full_suite` без него (полный набор внешнего проекта идёт
        раннером пульта в корне), или передаёт профиль и при `pult-pytest`
        либо непрочитанном профиле — вызов расходится с ожидаемым.
        """
        own = repo_context.ProfileAnswer(repo_context.PROFILE_PRESENT,
                                         values=dict(OWN_VALUES))
        pult = repo_context.ProfileAnswer(repo_context.PROFILE_PRESENT, values={
            **OWN_VALUES, "runner": targets.PROFILE_RUNNER_DEFAULT})
        unread = repo_context.ProfileAnswer(repo_context.PROFILE_UNREAD,
                                            reason="битый targets.yaml")
        for fresh in (False, True):
            tail = {"fresh": True} if fresh else {}
            with self.subTest(runner="pytest-own", fresh=fresh):
                local = self.call(own, fresh)
                local.assert_called_once()
                self.assertEqual(local.call_args.args, (Path("/tmp"), "T001"))
                kwargs = dict(local.call_args.kwargs)
                profile = kwargs.pop("command")
                self.assertEqual(kwargs, tail)
                self.assertEqual(profile.runner, targets.PROFILE_RUNNER_OWN)
                self.assertEqual(profile.workdir, "backend")
                self.assertEqual(dict(profile.env), OWN_VALUES["env"])
            for name, answer in (("pult-pytest", pult), ("не прочитан", unread)):
                with self.subTest(runner=name, fresh=fresh):
                    self.call(answer, fresh).assert_called_once_with(
                        Path("/tmp"), "T001", **tail)


if __name__ == "__main__":
    unittest.main()
