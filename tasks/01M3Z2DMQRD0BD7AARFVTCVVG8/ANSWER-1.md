---
task: 01M3Z2DMQRD0BD7AARFVTCVVG8
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответ Оператора на эскалацию 02.10.2026.

1. Мандат на удаление тестов снятой механики выдаётся (вариант а): проверка CI ветки artifact/<id>, уборка сирот artifact/*, коммиты репозитория фиксации и «грязная копия» документов сняты требованиями SPEC; покрытие названо в таблице «Удалены» PLAN.

Ослабление тестов разрешено: tests/test_doctor_artifact_branch_ci.py, tests/test_doctor.py::OrphanArtifactBranchSweepTest::test_sweep_deletes_only_branches_without_a_db_row, tests/test_doctor.py::OrphanArtifactBranchSweepTest::test_failed_deletion_is_not_reported_as_deleted, tests/test_doctor.py::OrphanArtifactBranchSweepTest::test_cmd_doctor_fix_reports_found_but_not_removed_honestly, tests/test_doctor.py::OrphanArtifactBranchSweepTest::test_no_orphans_raises_no_alert, tests/test_doctor.py::OrphanArtifactBranchSweepTest::test_cmd_doctor_default_does_not_sweep, tests/test_doctor.py::OrphanArtifactBranchSweepTest::test_cmd_doctor_fix_sweeps_once_and_lists_output, tests/test_doctor.py::RemoteArtifactBranchNamesTest::test_parses_branch_names_from_ls_remote_output, tests/test_doctor.py::RemoteArtifactBranchNamesTest::test_empty_response_is_an_empty_set_not_none, tests/test_doctor.py::RemoteArtifactBranchNamesTest::test_nonzero_return_code_is_none, tests/test_doctor.py::RemoteArtifactBranchNamesTest::test_git_not_answering_at_all_is_none, tests/test_doctor.py::OrphanArtifactBranchOriginFilterTest::test_present_on_origin_is_not_an_orphan_even_without_a_db_row, tests/test_doctor.py::OrphanArtifactBranchOriginFilterTest::test_absent_from_both_is_an_orphan, tests/test_doctor.py::OrphanArtifactBranchOriginFilterTest::test_known_to_db_but_absent_from_origin_is_not_an_orphan, tests/test_doctor.py::OrphanArtifactBranchOriginFilterTest::test_remote_none_makes_the_whole_result_none, tests/test_doctor.py::OrphanArtifactBranchOriginFilterTest::test_default_argument_computes_remote_itself, tests/test_doctor.py::SweepOrphanArtifactBranchesOriginGateTest::test_orphans_none_deletes_nothing_and_raises_no_incident, tests/test_doctor.py::SweepOrphanArtifactBranchesOriginGateTest::test_default_argument_computes_orphans_itself, tests/test_doctor.py::PrintOrphanBranchCandidatesTest::test_truncates_names_to_the_configured_limit, tests/test_doctor.py::PrintOrphanBranchCandidatesTest::test_empty_list_does_not_crash, tests/test_doctor.py::CmdDoctorOriginUnavailableTest::test_fix_mode_fails_named_and_does_not_call_sweep, tests/test_doctor.py::CmdDoctorOriginUnavailableTest::test_preview_mode_reports_uncomputable_and_does_not_exit, tests/test_git_fixation.py::ExternalTransitionCommitsTest::test_transition_commits_the_artifact_repo, tests/test_git_fixation.py::ExternalTransitionCommitsTest::test_sha_lands_in_the_journal, tests/test_git_fixation.py::ExternalIntegrityIncidentBlocksRunTest::test_tampering_after_fixation_blocks_the_run, tests/test_git_fixation.py::ExternalIntegrityIncidentBlocksRunTest::test_check_integrity_does_not_commit_when_tampered, tests/test_git_fixation.py::ExternalIntegrityIncidentBlocksRunTest::test_check_integrity_does_not_commit_another_tasks_work_in_progress, tests/test_git_fixation.py::ExternalApproveDoesNotCommitOthersWorkInProgressTest::test_approve_without_sha_does_not_commit_another_tasks_wip, tests/test_git_fixation.py::ExternalApproveDoesNotCommitOthersWorkInProgressTest::test_rejected_approve_does_not_commit_another_tasks_wip, tests/test_git_fixation.py::DogfoodTransitionJournalsShaTest::test_uncommitted_artifact_is_journaled_as_dirty, tests/test_git_fixation.py::ApproveByShaTest::test_approve_without_sha_on_dirty_copy_is_refused_and_state_unchanged, tests/test_git_fixation.py::IntegrityIncidentBlocksRunTest::test_uncommitted_change_after_approve_blocks_the_run

2. Изменённые утверждения 14 методов приняты (вариант а). Оговорка: ссылка документов внешнего target теперь отправляется в origin пульта, а не в origin target (test_done_transition_publishes_a_snapshot_like_killed_does, test_excludes_done_and_external_target) — это расходится с ADR-0021 п.3 (документы в репозитории самого проекта). Внешних задач в базе нет; в этой части не исправлять — исправление переносится в часть (б), Оператор записывает его в бэклог.

3. Инвариант 25: «(или грязная копия)» оставить до части (б) (вариант а).

Больше ничего не менять: сдай PLAN status: ready, как написано в эскалации.
