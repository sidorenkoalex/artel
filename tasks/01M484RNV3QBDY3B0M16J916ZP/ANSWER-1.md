---
task: 01M484RNV3QBDY3B0M16J916ZP
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решение Оператора 06.10 по эскалации разработчика.

Вопрос 1 — вариант (а), но через мандат ослабления, а не через раздел SPEC «Меняемое поведение»: этот раздел засчитывается только на approve гейта SPEC (fsm._approve_spec_gate), после него не действует.

Ослабление тестов разрешено: tests/test_alerts_wave_breaker.py::CheckWaveBreakerFailureTest::test_foreign_target_is_not_counted, tests/test_runner_wave_breaker.py::WaveBreakerAlertsOpenTest::test_foreign_target_alert_is_not_returned, tests/test_catalog_wave_breaker_status.py::WaveBreakerSuffixTest::test_empty_for_foreign_target_even_if_alert_open, tests/test_split_assessment_merge_gate.py::SnapshotSplitAssessmentTest::test_external_target_skips_diff_but_still_reads_split_assessment, tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package, tests/test_step_refixation.py::OwnStepCommitRefixesWithoutIncidentTest::test_refixation_is_journaled_with_both_shas, tests/test_step_refixation.py::ForeignCommitKeepsIncidentTest::test_fixed_sha_is_not_touched, tests/test_step_refixation.py::ForeignCommitKeepsIncidentTest::test_integrity_incident_still_raised, tests/test_step_refixation.py::UnclosedRunWindowNotCountedTest::test_commit_inside_unfinished_run_still_escalates, tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py::ApproveAfterIncidentTest::test_ac9_approve_exit_from_incident, tests/test_artifact_ref_sync.py::SendAfterCommitTest::test_refusal_is_journaled_commit_kept_and_retried_on_transition, tests/test_artifact_ref_sync.py::KillDocsRefTest::test_synced_ref_kills_with_a_closing_commit_in_origin, tests/test_division_parent_cleanup.py::DivisionParentCleanupTest::test_division_keeps_the_artifact_branch_of_the_parent, tests/test_git_fixation.py::RunnerEscalationHintsIncludeShaTest::test_agent_failure_escalation_hint_includes_full_fixed_sha, tests/test_git_fixation.py::AutogateMergeGateHintIncludesShaTest::test_autogate_transition_hint_includes_full_fixed_sha

Условия мандата (обязательны, их сверит Оператор по диффу до выхода из in_dev):

1. Меняется только ожидание, названное в эскалации («было → стало»). Остальные утверждения этих 15 методов не трогать; число утверждений в каждом методе не уменьшать; методы не переименовывать и не удалять.
2. Новое ожидание — точное, той же строгости, что прежнее. Проверка «является предком» (merge-base --is-ancestor и подобные) вместо точной цепочки коммитов запрещена:
   - `KillDocsRefTest::test_synced_ref_kills_with_a_closing_commit_in_origin`: родитель коммита закрытия — коммит паспорта перехода в killed, а его единственный родитель — `head0` (точная цепочка из двух коммитов; коммит паспорта меняет только строку паспорта).
   - `DivisionParentCleanupTest::test_division_keeps_the_artifact_branch_of_the_parent`: над `head_before` ровно один новый коммит, и это коммит паспорта (его единственный родитель — `head_before`, он не трогает `tasks/<PARENT>/SPEC.md` и не несёт снапшота закрытия); ссылка не удалена. Мутация «уборка полным путём kill с публикацией снапшота закрытия» обязана ловиться и после правки.
3. У трёх тестов стоп-крана волны (alerts, runner, catalog) имена оставить, а docstring привести к новому ожиданию: «Ловит мутацию» описывает мутацию, которую тест ловит теперь (например, отбор алерта или счёт волны снова по проекту артели).
4. Изменённые методы перечислить в PLAN (раздел «Влияние на систему») по форме «метод — было → стало».

Вопрос 2 — вариант (а): `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count` красный только в окружении роли (PATH роли без /bin, строка копилки 05.10 уже заведена); на полном прогоне пульта он зелёный. Задача его не трогает.
