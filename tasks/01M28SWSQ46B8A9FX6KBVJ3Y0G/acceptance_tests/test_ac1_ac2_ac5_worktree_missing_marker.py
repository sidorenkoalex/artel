"""Приёмочные тесты AC-1/AC-2/AC-5 задачи 01M28SWSQ46B8A9FX6KBVJ3Y0G:
`_cmd_amend_tests` (worktree-путь) обязан звать `guard.
acceptance_traceability_errors(tdir)` по правленной планке ПЕРЕД
коммитом в артефактную ветку/сдвигом `tests_locked_sha`, и отказывать
именованным `sys.exit`, если правка сняла тест критерия без замены
пометкой.

Красен до реализации: `_cmd_amend_tests` (orchestrator/amend.py) сегодня
не вызывает `guard.acceptance_traceability_errors` вовсе — правка,
снимающая тест AC-1 без пометки, коммитится и сдвигает `tests_locked_sha`
как обычная валидная правка (копилка 11.09, коммит 33aeb202): все три
теста этого файла падают на отсутствии отказа/записи журнала.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (  # noqa: E402
    AC_TEST_MISSING_AC1_NO_MARKER, REFUSAL_PREFIX_RE, WorktreeGateSandbox,
    amend)
from orchestrator import gitcmd  # noqa: E402


class MissingTraceabilityWorktreeTest(WorktreeGateSandbox):

    def test_ac1_refusal_message_prefix_and_no_commit_or_lock_shift(self):
        """Правка worktree снимает единственный тест AC-1 без пометки —
        `amend-tests` отказывает `sys.exit` с текстом, начинающимся
        «[<id>] amend-tests: отказ — трассируемость AC нарушена: »,
        новый коммит на артефактную ветку не появляется, `tests_locked_
        sha` не сдвигается.

        Ловит мутацию: вызов `guard.acceptance_traceability_errors`
        отсутствует (сегодняшнее поведение) либо стоит ПОСЛЕ коммита —
        правка проходит без отказа, `tests_locked_sha` сдвигается на sha
        нового коммита с содержимым, снявшим тест AC-1.
        """
        self.edit_tests(AC_TEST_MISSING_AC1_NO_MARKER)
        old_locked = self.row()["tests_locked_sha"]
        old_branch_head = gitcmd.branch_head_sha(self.branch)

        with self.assertRaises(SystemExit) as ctx:
            amend.cmd_amend_tests(self.TASK, "правка ломает AC-1")

        message = str(ctx.exception)
        match = REFUSAL_PREFIX_RE.match(message)
        self.assertIsNotNone(
            match, f"отказ не начинается с ожидаемого префикса AC-1: {message!r}")
        self.assertEqual(match.group("task"), self.TASK)
        self.assertEqual(
            self.row()["tests_locked_sha"], old_locked,
            "tests_locked_sha не должен сдвигаться при отказе трассируемости")
        self.assertEqual(
            gitcmd.branch_head_sha(self.branch), old_branch_head,
            "отказ трассируемости не должен создавать коммит на "
            "артефактной ветке")

    def test_ac2_refusal_writes_operator_journal_entry(self):
        """Тот же отказ трассируемости пишет в журнал задачи запись
        актором `operator`, называющую отсутствующий критерий (AC-1).

        Ловит мутацию: `sys.exit` вызывается напрямую, минуя
        `store.journal` (например скопированный по образцу отказ «нет
        изменений», который журнал не пишет) — отказ трассируемости
        остаётся невидим в истории задачи, хотя SPEC явно требует записи.
        """
        self.edit_tests(AC_TEST_MISSING_AC1_NO_MARKER)
        before = len(self.journal_rows())

        with self.assertRaises(SystemExit):
            amend.cmd_amend_tests(self.TASK, "правка ломает AC-1")

        after = self.journal_rows()
        new_rows = after[before:]
        self.assertTrue(
            new_rows,
            f"отказ трассируемости не добавил записи в журнал: {after!r}")
        matched = [r for r in new_rows
                  if r["actor"] == "operator" and "AC-1" in (r["detail"] or "")]
        self.assertTrue(
            matched,
            f"нет новой записи actor=operator, называющей AC-1: {new_rows!r}")

    def test_ac5_refusal_names_the_missing_criterion_and_leaves_lock_unmoved(self):
        """Сценарий требования 4(а): правка worktree сняла ЕДИНСТВЕННЫЙ
        тест критерия (AC-1) без пометки — отказ называет именно этот
        критерий, `tests_locked_sha` остаётся прежним.

        Ловит мутацию: проверка ссылается на неверный номер критерия
        (например всегда называет AC-2 вместо реально сломанного AC-1)
        либо срабатывает только для критериев БЕЗ какой-либо пометки на
        файл целиком, а не для «единственный тест критерия снят».
        """
        self.edit_tests(AC_TEST_MISSING_AC1_NO_MARKER)
        old_locked = self.row()["tests_locked_sha"]

        with self.assertRaises(SystemExit) as ctx:
            amend.cmd_amend_tests(self.TASK, "снят тест AC-1 без пометки")

        self.assertIn("AC-1", str(ctx.exception),
                      "отказ обязан называть критерий AC-1 — тот, чей тест снят")
        self.assertEqual(
            self.row()["tests_locked_sha"], old_locked,
            "tests_locked_sha не должен сдвигаться при отказе трассируемости")


if __name__ == "__main__":
    unittest.main()
