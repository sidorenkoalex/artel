"""Отказ заведения рабочей копии задачи внешнего проекта не теряется на
гейтах, гоняющих планку (ревью 01M42PENCS26D0656X8FR7DFA7, R1-F3; SPEC
01M42PENCS26D0656X8FR7DFA7, требование 1 — рабочая копия задачи
`worktrees/<id>/` проекта, отката нет).

`workspace.ensure` подменён отказом «клон не заведён»: прогон приёмки,
сухой сбор на выходе `tests_writing` и автогейт после ревью не запускают
планку в каталоге без кода, а называют причину `ensure` в журнале.
Песочница — `DocsDirSandbox` (настоящий git, задача в `in_dev`).
"""
from unittest import mock

from orchestrator import acceptance, fsm, fsm_advance, fsm_autogate, store, workspace
from orchestrator.advance_gates import acceptance as acceptance_gate
from tests.test_docs_dir_layout import TASK, DocsDirSandbox

EXTERNAL = "ext-proj"
REASON = "клон /нет/repo из git@example.invalid:ext.git не заведён: сбой сети"


class ExternalCodeCopyRefusalTest(DocsDirSandbox):
    def setUp(self):
        super().setUp()
        self.t = store.get_task(self.conn, TASK)
        self.branch = "refs/artifacts/" + TASK
        patcher = mock.patch.object(
            workspace, "ensure",
            lambda task_id, branch, target=None: (workspace.path(
                task_id, EXTERNAL), REASON))
        patcher.start()
        self.addCleanup(patcher.stop)

    def journal_details(self, action):
        rows = self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=?",
            (TASK, action)).fetchall()
        return [r["detail"] for r in rows]

    def test_acceptance_run_refuses_with_the_ensure_reason(self):
        """Ловит мутацию: `_acceptance_run_refuses` выбрасывает причину
        `workspace.ensure` (`run_cwd, _error = …`) — планку гоняют в
        каталоге без рабочей копии, отказа с причиной клона в журнале нет."""
        with mock.patch.object(acceptance, "run") as run:
            refused = acceptance_gate._acceptance_run_refuses(
                self.conn, TASK, self.t, self.docs, EXTERNAL, self.branch)
        self.assertTrue(refused)
        run.assert_not_called()
        details = self.journal_details("переход отклонён: приёмочные тесты")
        self.assertTrue(any(REASON in d for d in details), details)

    def test_tests_writing_refuses_before_the_dry_collect(self):
        """Ловит мутацию: выход `tests_writing` не проверяет отказ
        `workspace.ensure` (гейт `_tests_writing_code_copy_gate` снят или
        пропускает ошибку) — сухой сбор идёт в каталоге без кода."""
        with mock.patch.object(fsm, "_tests_writing_ac_state",
                               return_value=({1}, {}, [])), \
                mock.patch.object(fsm_advance, "_tests_writing_code_diff",
                                  return_value=(None, None, None)), \
                mock.patch.object(fsm_advance,
                                  "_tests_writing_stray_plank_files_gate",
                                  return_value=None), \
                mock.patch.object(fsm_advance, "_tests_writing_test_groups_gate",
                                  return_value=None), \
                mock.patch.object(fsm_advance,
                                  "_tests_writing_dry_collect_gate") as collect, \
                mock.patch.object(store, "set_state") as set_state:
            moved = fsm_advance.tests_writing(self.conn, TASK, self.t,
                                              self.docs, EXTERNAL,
                                              "tests_writing")
        self.assertFalse(moved)
        collect.assert_not_called()
        set_state.assert_not_called()
        details = self.journal_details(
            "переход отклонён: рабочая копия задачи не заведена")
        self.assertEqual(details, [REASON])

    def test_review_autogate_is_skipped_with_the_ensure_reason(self):
        """Ловит мутацию: `_review_approved` внешнего проекта выбрасывает
        причину `workspace.ensure` — автогейт приёмки гоняет планку без
        кода, записи «автогейт приёмки пропущен» с причиной клона нет."""
        with mock.patch.object(store, "set_state"), \
                mock.patch.object(fsm_autogate,
                                  "_maybe_autogate_acceptance") as autogate:
            fsm_advance._review_approved(
                self.conn, TASK, self.t, self.docs, EXTERNAL, "review",
                self.branch, "", {})
        autogate.assert_not_called()
        details = self.journal_details("автогейт приёмки пропущен")
        self.assertTrue(any(REASON in d for d in details), details)
