"""Юнит-тесты перефиксации sha на пути отклонённого перехода FSM (SPEC
T076): `gitcmd.commit_committer_dates`,
`fixation.refixate_after_rejected_transition`, `fsm._advance_with_refixation`.

Настоящий git (не заглушка `gitcmd.git`) — сама суть проверки в том, что
между зафиксированным и текущим sha реально произошёл коммит роли внутри
шага; заглушкой этого не изобразить (тот же довод, что у
`RealPultGitTest`, tests/test_git_fixation.py, и у
tests/test_step_autocommit.py/tests/test_timeout_checkpoint.py, которые
эту песочницу уже переиспользуют).
"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fixation, fsm, gitcmd, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

# SPEC schema_version 2 с AC-разметкой — spec_gate направляет approve в
# tests_writing (guard.requires_ac_markup), тот же приём, что
# tests/test_acceptance_tests_flow.py.
SPEC_V2 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: T076 — песочница перефиксации

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Единственный критерий, проверяемый тестом.

## Не входит
"""

# Полная трассируемость AC-1, но БЕЗ маркера красноты в докстринге модуля
# (SPEC T064) — guard отклоняет tests_writing -> in_dev именно по этой
# причине, хотя трассируемость сама по себе полная (сценарий T069/T073).
AC_TEST_NO_MARKER = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
"""

AC_TEST_NO_MARKER_V2 = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertEqual(1 + 1, 2)
"""

AC_TEST_WITH_MARKER = '''"""Красен до реализации: маркер красноты для прохождения guard'а T064."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
'''


class _RefixationTest(RealPultGitTest):

    def enter_tests_writing(self) -> str:
        (self.task_dir() / "SPEC.md").write_text(
            SPEC_V2.format(task=self.TASK), encoding="utf-8")
        self.commit_task_dir("SPEC.md ready")
        self.capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = self.head()
        self.capture(fsm.cmd_approve, self.TASK, sha)  # spec_gate -> tests_writing
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "tests_writing")
        return sha

    def write_ac_test(self, text: str) -> None:
        (self.task_dir() / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        (self.task_dir() / "acceptance_tests" / "test_ac.py").write_text(
            text, encoding="utf-8")

    def commit_as_role(self, message: str, role: str = "test_author") -> None:
        """Легитимный коммит роли ВНУТРИ шага — обрамлён теми же
        журнальными записями, что и настоящий `runner.run_agent_once`."""
        conn = store.db()
        store.journal(conn, self.TASK, role, "agent run started",
                      "шаг 1/1, лог: —, промпт: —")
        self.commit_task_dir(message)
        store.journal(conn, self.TASK, role, "agent run finished",
                      "rc=0, шаг 1/1")

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def journal_actions(self) -> list[str]:
        return [r["action"] for r in store.task_steps(store.db(), self.TASK)]


class OwnStepCommitRefixesWithoutIncidentTest(_RefixationTest):
    """Сценарий T069/T073: коммит роли ВНУТРИ шага, guard отклоняет
    переход по отсутствию маркера красноты — фиксация подтягивается,
    инцидент не поднимается."""

    def test_fixed_sha_moves_to_the_new_head(self):
        entry_sha = self.enter_tests_writing()
        self.write_ac_test(AC_TEST_NO_MARKER)
        self.commit_as_role("acceptance_tests от test_author")
        new_head = self.head()
        self.assertNotEqual(new_head, entry_sha)

        self.capture(fsm.cmd_advance, self.TASK)  # guard: нет маркера красноты

        conn = store.db()
        self.assertEqual(store.get_task(conn, self.TASK)["state"], "tests_writing")
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"], new_head)

    def test_refixation_is_journaled_with_both_shas(self):
        entry_sha = self.enter_tests_writing()
        self.write_ac_test(AC_TEST_NO_MARKER)
        self.commit_as_role("acceptance_tests от test_author")
        new_head = self.head()

        self.capture(fsm.cmd_advance, self.TASK)

        details = self.journal_details("sha перефиксирован после отклонённого перехода")
        self.assertEqual(len(details), 1)
        self.assertIn(entry_sha, details[0])
        self.assertIn(new_head, details[0])
        self.assertIn("коммиты шага", details[0])

    def test_no_integrity_incident_on_next_run(self):
        self.enter_tests_writing()
        self.write_ac_test(AC_TEST_NO_MARKER)
        self.commit_as_role("acceptance_tests от test_author")
        self.capture(fsm.cmd_advance, self.TASK)

        self.assertIsNone(fixation.check_integrity(store.db(), self.TASK))

        out, popen = self.run_faked()
        self.assertEqual(len(self.claude_launches(popen)), 1)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "tests_writing")
        self.assertNotIn("инцидент целостности", out)

    def test_ordinary_refusal_reason_is_kept(self):
        """Требование 2: обычная причина отказа гейта остаётся в журнале,
        перефиксация её не подменяет."""
        self.enter_tests_writing()
        self.write_ac_test(AC_TEST_NO_MARKER)
        self.commit_as_role("acceptance_tests от test_author")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertIn("маркера", out)
        self.assertTrue(
            self.journal_details("переход отклонён: трассируемость AC"))


class ForeignCommitKeepsIncidentTest(_RefixationTest):
    """Требование 3: коммит вне окна шага (не обёрнут «agent run
    started»/«agent run finished») по-прежнему эскалирует инцидент."""

    def test_fixed_sha_is_not_touched(self):
        entry_sha = self.enter_tests_writing()
        self.write_ac_test(AC_TEST_NO_MARKER)
        self.commit_task_dir("посторонний коммит вне окна шага")
        new_head = self.head()
        self.assertNotEqual(new_head, entry_sha)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            store.get_task(store.db(), self.TASK)["fixed_sha"], entry_sha)
        self.assertEqual(
            self.journal_details("sha перефиксирован после отклонённого перехода"),
            [])

    def test_integrity_incident_still_raised(self):
        entry_sha = self.enter_tests_writing()
        self.write_ac_test(AC_TEST_NO_MARKER)
        self.commit_task_dir("посторонний коммит вне окна шага")
        new_head = self.head()
        self.capture(fsm.cmd_advance, self.TASK)

        incident = fixation.check_integrity(store.db(), self.TASK)

        self.assertIsNotNone(incident)
        self.assertIn(entry_sha, incident)
        self.assertIn(new_head, incident)

        out, popen = self.run_faked()
        self.assertEqual(self.claude_launches(popen), [])
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        self.assertIn("инцидент целостности", out)


class UnclosedRunWindowNotCountedTest(_RefixationTest):
    """Прогон «agent run started» без парного «agent run finished» — окно
    не закрыто, доказательства завершённого шага нет: коммит внутри него
    сверка обязана трактовать как непроверенный (fail-closed)."""

    def test_commit_inside_unfinished_run_still_escalates(self):
        entry_sha = self.enter_tests_writing()
        self.write_ac_test(AC_TEST_NO_MARKER)
        conn = store.db()
        store.journal(conn, self.TASK, "test_author", "agent run started",
                      "шаг 1/1")
        self.commit_task_dir("коммит без agent run finished")
        # Нарочно нет "agent run finished".

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            store.get_task(conn, self.TASK)["fixed_sha"], entry_sha,
            "незакрытое окно не должно давать право на перефиксацию")
        self.assertIsNotNone(fixation.check_integrity(conn, self.TASK))


class MultipleOwnStepWindowsAccumulateTest(_RefixationTest):
    """Несколько отклонённых попыток подряд, каждая — свой закрытый
    прогон: перефиксация обновляется на каждой, инцидент не копится."""

    def test_two_rounds_of_rejection_each_refixate(self):
        self.enter_tests_writing()
        conn = store.db()

        self.write_ac_test(AC_TEST_NO_MARKER)
        self.commit_as_role("первая попытка test_author")
        first_head = self.head()
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"], first_head)

        self.write_ac_test(AC_TEST_NO_MARKER_V2)
        self.commit_as_role("вторая попытка test_author")
        second_head = self.head()
        self.assertNotEqual(second_head, first_head)
        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"], second_head)
        self.assertEqual(
            len(self.journal_details("sha перефиксирован после отклонённого перехода")),
            2)
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))


class SuccessfulTransitionUnaffectedTest(_RefixationTest):
    """Требование 5: успешный переход не порождает никакой перефиксации
    отдельно от обычной `record_fixation` — обёртка не вмешивается."""

    def test_no_extra_refixation_journal_on_success(self):
        self.enter_tests_writing()
        self.write_ac_test(AC_TEST_WITH_MARKER)
        self.commit_as_role("test_author закончил")

        self.capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "in_dev")
        self.assertEqual(
            self.journal_details("sha перефиксирован после отклонённого перехода"),
            [])
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["fixed_sha"], self.head())


class CommitCommitterDatesTest(RealPultGitTest):

    def test_returns_one_iso_date_per_commit_in_range(self):
        before = self.head()
        (self.task_dir()).mkdir(parents=True, exist_ok=True)
        (self.task_dir() / "note.txt").write_text("x", encoding="utf-8")
        self.commit_task_dir("заметка")
        after = self.head()

        dates = gitcmd.commit_committer_dates(before, after)

        self.assertEqual(len(dates), 1)
        datetime.fromisoformat(dates[0])  # не падает — валидный ISO8601

    def test_empty_range_is_an_empty_list_not_none(self):
        head = self.head()

        self.assertEqual(gitcmd.commit_committer_dates(head, head), [])

    def test_unreachable_range_returns_none(self):
        self.assertIsNone(
            gitcmd.commit_committer_dates("0" * 40, self.head()))


if __name__ == "__main__":
    unittest.main()
