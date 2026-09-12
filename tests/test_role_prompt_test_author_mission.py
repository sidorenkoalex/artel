"""Регресс-тест пункта 5 миссии test_author (SPEC 01M29BANMM8X8JWJ5GDTJWKB0Z,
требование 4, AC-3): команда прогона приёмочных тестов — pytest той же
формы, что `orchestrator/acceptance.py::_pytest_command`, со значением
таймаута из `stack.PER_TEST_TIMEOUT_SEC`, подставленным динамически, не
литералом; прежняя команда `unittest discover` в миссии не остаётся.
"""
import unittest
from unittest import mock

from orchestrator import brief, role_prompt, stack


class TestAuthorMissionPytestCommandRegressionTest(unittest.TestCase):

    TASK_ID = "01M00000000000000000000TT"

    def _mission(self):
        with mock.patch.object(brief, "test_author_answer_component",
                               return_value=None):
            mission, _, _ = role_prompt.mission_brief_package(
                None, self.TASK_ID, {"branch": "task/fixture-branch"},
                "test_author", "/tmp/fixture-cwd")
        return mission

    def test_mission_uses_pytest_with_constant_timeout(self):
        mission = self._mission()
        expected = (
            f"python3 -m pytest tasks/{self.TASK_ID}/acceptance_tests "
            f"-p no:cacheprovider -p timeout -o "
            f"timeout={stack.PER_TEST_TIMEOUT_SEC}")
        self.assertIn(expected, mission)

    def test_mission_no_longer_carries_unittest_discover(self):
        mission = self._mission()
        self.assertNotIn("unittest discover", mission)


if __name__ == "__main__":
    unittest.main()
