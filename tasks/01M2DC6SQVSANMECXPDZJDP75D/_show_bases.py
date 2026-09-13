import ast
from pathlib import Path

TESTS = Path("tests")

TARGET_CLASSES = {
    "tests/test_detached_cycle.py": ["LaunchDetachedTest", "CmdStopTest", "LeaseForceTest", "WaitZoneFlagHotfix22Test"],
    "tests/test_doctor.py": ["LeaseFailDetailAndReconciliationTest", "BranchFreshnessCheckTest", "TaskCounterCheckTest",
                              "CanaryTriggerCheckTest", "LeasesCheckTest", "MergeLockCheckTest"],
    "tests/test_lease.py": ["AcquireReleaseTest", "OwnSessionLiveOtherPidTest", "AcquireJournalCauseTest",
                             "ReleaseAnyTest", "RunLockedTest", "ForeignLiveLeaseTest"],
    "tests/test_parallel_limit.py": ["ParallelLimitTest"],
    "tests/test_zone_lock.py": ["ZoneLockTest"],
    "tests/test_alerts_wave_breaker.py": ["WaveBreakerTestBase"],
    "tests/test_diff_not_collected_alerts.py": ["RaiseDiffNotCollectedAlertTest", "CloseDiffNotCollectedAlertsTest"],
    "tests/test_doctor_wave_breaker.py": ["DoctorWaveBreakerFirstLineTest"],
    "tests/test_notes.py": ["CmdNoteArgumentValidationTest"],
    "tests/test_runner_wave_breaker.py": ["WaveBreakerAlertsOpenTest"],
    "tests/test_stall_alerts.py": ["RaiseAttentionAlertTest", "CloseAttentionAlertsTest", "SetStateClosesAttentionAlertTest"],
    "tests/test_auto_escalated_return_rework_gate.py": ["RoleStepSinceStateEntryTest"],
    "tests/test_fsm_review_rework_gate.py": ["ReviewerVerdictBaselineTest"],
    "tests/test_fsm_review_rework_sha_gate.py": ["CodeShaAtReviewEscalationTest"],
    "tests/test_program_spend_reseed.py": ["ProgramSpendReseedTest"],
    "tests/test_spent_estimate_store.py": ["TotalEstimateTest"],
    "tests/test_prune.py": ["PruneCanaryDiagCandidatesTest", "PruneAlertArchiveStoreTest", "PruneReportEmptyStateTest"],
    "tests/test_acceptance_collect.py": ["CollectTest"],
    "tests/test_acceptance_tests_flow.py": ["ScanAcceptanceTestsTest", "ScanRednessMarkersTest",
                                             "AcceptanceTraceabilityFunctionTest", "IndentedAcMarkerTest"],
    "tests/test_id_format_guard.py": ["ScanIdFormatSamplesTest"],
    "tests/test_canary.py": ["MergesSinceLastGreenRunTest", "CanaryBaselineStoreRoundtripTest", "GreenCanaryRunsTest"],
    "tests/test_dry_run.py": ["DryRunSandboxTest"],
    "tests/test_pin.py": ["PinUpdateGateOrderTest", "PinToResetFailureTest", "PinUpdateRefusalMessageTest"],
    "tests/test_agent_failure.py": ["_AgentFailureTmpRootTest"],
    "tests/test_agent_log.py": ["_AgentLogTmpRootTest"],
    "tests/test_step_cost.py": ["_StepCostTmpRootTest"],
    "tests/test_catalog_status_log.py": ["CmdLogSessionIdTest", "CmdStatusLeaseHolderTest"],
    "tests/test_store_journal.py": ["JournalSessionIdTest"],
    "tests/test_catalog_wave_breaker_status.py": ["CmdStatusWaveBreakerMarkTest"],
    "tests/test_pause.py": ["PauseTest"],
    "tests/test_release.py": ["ReleaseTest"],
    "tests/test_ci_status.py": ["BranchStatusTest", "VerifyingStatusTest", "VerifyingStatus422Test"],
    "tests/test_answer_branch_reads.py": ["AnswerFileCountOnForeignBranchTest", "BriefAnswerComponentsOnForeignBranchTest"],
    "tests/test_artifact_branch_push.py": ["PushSuccessTest"],
    "tests/test_doctor_artifact_branch_sync.py": ["ArtifactBranchSyncSandbox"],
    "tests/test_budget_live_lease_and_escalation.py": ["AcquireSameHostOkTest", "IsLiveTest"],
    "tests/test_cas_set_state.py": ["SetStateCasTest"],
    "tests/test_doctor_fix_ignored_artifacts.py": ["FixIgnoredArtifactFilesTest"],
    "tests/test_gitcmd_check_ignore.py": ["CheckIgnoreTest"],
    "tests/test_guard_schema.py": ["SchemaVersionTest"],
    "tests/test_yaml_parsing.py": ["ArtifactsReadTest"],
    "tests/test_mutation_claim_gate.py": ["MutationClaimGateGitFailureTest", "MutationClaimGateFileSelectionTest", "MutationClaimGateRefusalContentTest"],
    "tests/test_protected_paths_gate.py": ["ZonesGateProtectedPathPriorityTest"],
}

for relpath, names in TARGET_CLASSES.items():
    path = Path(relpath)
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in names:
            bases = [ast.unparse(b) for b in node.bases]
            print(f"{relpath}:{node.lineno} class {node.name}({', '.join(bases)})")
