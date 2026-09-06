"""Юнит-тесты гейта ёмкости diff снимка — fail-closed на сбое git
(R1-F2, REVIEW.md итерация 1, major, tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X):
git не ответил на diff снимка (`git diff MAIN_BRANCH...ветка`) обязан
отказать переходу, а не измерять байты короткой строки-причины сбоя
(`"(не собран: <reason>)"`, которую в этом случае отдаёт
`review.git_diff_part`) вместо фактического diff — иначе гейт молча
пропускает переход, так и не выяснив реальный размер снимка.

Приёмочные тесты задачи (`tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/
acceptance_tests/test_ac12_ac16_capacity_gate.py`) закрывают AC-12..
AC-16 на успешном пути git и намеренно не бьют по сбою git — этот файл
закрывает именно его, тем же fail-closed приёмом, что уже применён в
`orchestrator/fsm_advance.py::in_dev` для лока `acceptance_tests/`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_advance, gitcmd, review, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class CapacityGateGitFailureTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.t = {"title": "Тест гейта ёмкости", "branch": "task/t001-x"}

    def _refuses(self, git_diff) -> bool:
        with mock.patch.object(gitcmd, "git", git_diff):
            return fsm_advance._capacity_gate_refuses(
                self.conn, self.task_id, self.t, "in_dev")

    def journal_details(self) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,))]

    @staticmethod
    def _failing_diff(*args) -> subprocess.CompletedProcess:
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(
                list(args), 128, "", "fatal: bad revision 'main...task/t001-x'")
        return subprocess.CompletedProcess(list(args), 0, "", "")

    def test_git_diff_failure_refuses_the_transition_fail_closed(self):
        refused = self._refuses(self._failing_diff)

        self.assertTrue(
            refused, "git не ответил на diff снимка — гейт обязан "
            "отказать переходу, не измерять байты строки-причины сбоя")

    def test_git_diff_failure_is_journaled_with_the_reason(self):
        self._refuses(self._failing_diff)

        details = self.journal_details()
        self.assertTrue(
            any("git не ответил" in d and "bad revision" in d
               for d in details),
            f"отказ обязан назвать причину сбоя git в журнале: {details}")

    def test_git_diff_unicode_failure_also_refuses_fail_closed(self):
        """`gitcmd.git` бросает `UnicodeDecodeError` на бинарном diff —
        тот же случай, что и обычный ненулевой код возврата: причина
        непустая, гейт обязан отказать, а не пропустить переход."""
        def raising_git(*args):
            if args and args[0] == "diff":
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        refused = self._refuses(raising_git)

        self.assertTrue(refused)

    def test_git_diff_success_under_the_cap_is_unaffected(self):
        def ok_git(*args) -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(
                list(args), 0, "diff --git a b\n+маленький diff", "")

        refused = self._refuses(ok_git)

        self.assertFalse(
            refused, "успешный diff под потолком обязан пройти гейт, "
            "как и раньше (AC-16 не регрессирует)")


class CapacityGateTwoNumbersMessageTest(TmpRootTest):
    """tasks/01M1RA0N6FCFEQBB82K58GM12X, AC-1/AC-3: гейт мерит diff кода
    БЕЗ `tasks/<id>/` (mock различает вызов по pathspec-хвосту команды)
    и, при отказе, называет обе цифры — код и исключённые артефакты."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.t = {"title": "Тест двух цифр", "branch": "task/t001-x"}

    def journal_details(self) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,))]

    def _refuses_with(self, git_diff) -> bool:
        with mock.patch.object(gitcmd, "git", git_diff):
            return fsm_advance._capacity_gate_refuses(
                self.conn, self.task_id, self.t, "in_dev")

    def test_refusal_message_names_code_size_and_artifacts_size_separately(self):
        code_body = "x" * (config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES + 37_856)
        artifacts_body = "y" * 500

        def git_diff(*args) -> subprocess.CompletedProcess:
            if args and args[0] == "diff":
                if f":!tasks/{self.task_id}/" in args:
                    return subprocess.CompletedProcess(
                        list(args), 0, code_body, "")
                if f"tasks/{self.task_id}/" in args:
                    return subprocess.CompletedProcess(
                        list(args), 0, artifacts_body, "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        refused = self._refuses_with(git_diff)

        self.assertTrue(refused)
        details = "\n".join(self.journal_details())
        self.assertIn(
            str(len(code_body)), details,
            "журнал обязан назвать размер diff кода (без tasks/<id>/)")
        self.assertIn(
            str(len(artifacts_body)), details,
            "журнал обязан назвать размер diff артефактов (tasks/<id>/)")

    def test_empty_artifacts_diff_reports_zero_bytes_not_placeholder_size(self):
        """R1-F1, REVIEW.md итерации 1-3: `tasks/<id>/` реально не менялся
        — git отвечает пустым stdout, `git_diff_part` подставляет для показа
        строку-плейсхолдер `review.EMPTY_DIFF_TEXT`. Вторая цифра сообщения
        обязана быть 0, а не байтовым размером этого плейсхолдера."""
        code_body = "x" * (config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES + 37_856)

        def git_diff(*args) -> subprocess.CompletedProcess:
            if args and args[0] == "diff":
                if f":!tasks/{self.task_id}/" in args:
                    return subprocess.CompletedProcess(
                        list(args), 0, code_body, "")
                if f"tasks/{self.task_id}/" in args:
                    return subprocess.CompletedProcess(list(args), 0, "", "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        refused = self._refuses_with(git_diff)

        self.assertTrue(refused)
        details = "\n".join(self.journal_details())
        self.assertIn(
            "0 байт", details,
            "diff артефактов реально пуст — вторая цифра обязана быть 0, "
            "не размер строки-плейсхолдера")
        placeholder_size = len(review.EMPTY_DIFF_TEXT.encode("utf-8"))
        self.assertNotIn(
            f"{placeholder_size} байт", details,
            "вторая цифра не имеет права быть байтовым размером строки "
            "«(изменений нет)» — это плейсхолдер для показа, не diff")

    def test_artifacts_diff_failure_does_not_invent_a_number(self):
        """Второй diff (только `tasks/<id>/`) не отвечает — отказ уже
        решён первой цифрой (код выше потолка), гейт не выдаёт вымышленное
        число вместо честного «неизвестен»."""
        code_body = "x" * (config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES + 37_856)

        def git_diff(*args) -> subprocess.CompletedProcess:
            if args and args[0] == "diff":
                if f":!tasks/{self.task_id}/" in args:
                    return subprocess.CompletedProcess(
                        list(args), 0, code_body, "")
                if f"tasks/{self.task_id}/" in args:
                    return subprocess.CompletedProcess(
                        list(args), 128, "", "fatal: bad revision")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        refused = self._refuses_with(git_diff)

        self.assertTrue(
            refused, "первая цифра (код) уже выше потолка — отказ не "
            "имеет права зависеть от сбоя второго diff'а")
        details = "\n".join(self.journal_details())
        self.assertIn("неизвестен", details)


class CapacityGateExternalTargetTest(TmpRootTest):
    """Гейт ёмкости не применяется к внешнему (не self) target —
    `tests.test_git_fixation.ExternalTargetAdvanceIgnoresDirtyCheckTest.
    test_uncommitted_plan_still_advances_for_external_target` уже
    фиксирует, что `tasks/<id>/` внешнего target до перехода не
    закоммичен в свою ветку (коммитит `fixation._fix_external` уже ПОСЛЕ
    решения перейти) — `git diff` на такую ветку не отвечает не из-за
    сбоя git, а по архитектуре внешнего target; fail-closed здесь
    заблокировал бы КАЖДЫЙ переход внешнего target навсегда."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        store.insert_task(self.conn, self.task_id, "Задача внешнего target",
                          "in_dev", "task/t001-x", "sled", 25.0)
        self.t = {"title": "Задача внешнего target", "branch": "task/t001-x"}

    @staticmethod
    def _no_such_branch(*args) -> subprocess.CompletedProcess:
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(
                list(args), 128, "",
                "fatal: ambiguous argument 'main...task/t001-x': unknown revision")
        return subprocess.CompletedProcess(list(args), 0, "", "")

    def test_external_target_passes_the_gate_without_asking_git_at_all(self):
        with mock.patch.object(gitcmd, "git", self._no_such_branch):
            refused = fsm_advance._capacity_gate_refuses(
                self.conn, self.task_id, self.t, "in_dev")

        self.assertFalse(
            refused, "внешний target не имеет права попасть в fail-closed "
            "гейта ёмкости — ветка закономерно ещё не в config.ROOT")


if __name__ == "__main__":
    unittest.main()
