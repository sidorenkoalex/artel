---
built_at_sha: 958a52c7f8fd1709ffe1226058eb266c4f378d92
---

# Codebase-map пульта

Автосгенерировано `scripts/codebase_map.py` — правки руками теряются при следующем запуске.

## orchestrator/__init__.py

**Назначение:** Пакет оркестратора Артели. Точка входа — `orchestrator/artel.py`.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## orchestrator/acceptance.py

**Назначение:** Прогон и сводка приёмочных тестов задачи: tasks/<id>/acceptance_tests/

**Публичные функции:**
- `collect`
- `materialize_from_branch`
- `run`
- `run_full_suite`
- `summary`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/stack.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `tests/test_acceptance.py`, `tests/test_acceptance_collect.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_branch_freshness_gate.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_plan_appendix.py`, `tests/test_pull.py`

## orchestrator/agent_log.py

**Назначение:** Наблюдаемость шага: файлы логов прогонов и перекачка вывода агента.

**Публичные функции:**
- `environment_fingerprint`
- `last_agent_log`
- `log_tail`
- `new_agent_log`
- `render_agent_line`
- `render_block`
- `step_friction`
- `stream_to_log`
- `tee_lines`

**Импортирует:** `orchestrator/config.py`, `orchestrator/spend.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/pause.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_auto_cycle.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_kill_cleanup.py`, `tests/test_pause_now.py`, `tests/test_report.py`, `tests/test_step_cost.py`

## orchestrator/alerts.py

**Назначение:** Таблица alerts: несущий носитель порогов/инцидентов/триггеров (A3,

**Публичные функции:**
- `ack`
- `auto_ack`
- `check_wave_breaker_failure`
- `check_wave_breaker_timeout`
- `close_attention_alerts`
- `close_diff_not_collected_alerts`
- `open_alerts`
- `raise_alert`
- `raise_attention_alert`
- `raise_diff_not_collected_alert`
- `raise_token_rate_divergence_alert`

**Импортирует:** `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/failure_classification.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/pool_seal.py`, `orchestrator/pull.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_auto_cycle.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_coldstart.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`, `tests/test_prune.py`, `tests/test_runner_wave_breaker.py`, `tests/test_stall_alerts.py`

## orchestrator/amend.py

**Назначение:** Команда `amend-tests`: штатная правка зафиксированной планки приёмки

**Публичные функции:**
- `cmd_amend_tests`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_amend.py`

## orchestrator/answer.py

**Назначение:** Команда `answer`: канал ответа Оператора на эскалацию (SPEC T075,

**Публичные функции:**
- `cmd_answer`
- `cmd_zones_extend`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_answer.py`

## orchestrator/artel.py

**Назначение:** Артель, Фаза 0 — FSM-оркестратор (CLI).

**Публичные функции:**
- `main`

**Импортирует:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/notes.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/pool_seal.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/venv.py`, `orchestrator/version.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`

**Импортируется:** `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_artel_bootstrap.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_detached_cycle.py`, `tests/test_doc_commit.py`, `tests/test_invariants.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_new_argv_parsing.py`

## orchestrator/artifact_branch.py

**Назначение:** Артефактная ветка пульта: `tasks/<id>/` target'а при жизни задачи

**Публичные функции:**
- `append_passport_line`
- `branch_name`
- `commit_files`
- `drop`
- `materialize_task_dir`
- `push`
- `read_tree`
- `snapshot_pending`
- `write_commit`

**Импортирует:** `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_source.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/fixation.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_materialization.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_doctor_artifact_branch_ci.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_git_fixation.py`, `tests/test_multitarget_invariants.py`, `tests/test_plan_appendix.py`, `tests/test_pull.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_zones_approve.py`

## orchestrator/artifact_source.py

**Назначение:** Ветка-источник `tasks/<id>/` живой задачи — общий резолвер (SPEC T094,

**Публичные функции:**
- `resolve`

**Импортирует:** `orchestrator/artifact_branch.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `tests/test_fsm_autogate.py`

## orchestrator/artifacts.py

**Назначение:** Чтение артефактов задачи: frontmatter и свежесть вердикта ревьювера.

**Публичные функции:**
- `fresh_verdict_iteration`
- `frontmatter`

**Импортирует:** `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `tests/test_review_freshness.py`, `tests/test_yaml_parsing.py`

## orchestrator/auto.py

**Назначение:** Цикл `auto`: advance до шага роли, затем — если роль ещё не закончила — run.

**Публичные функции:**
- `auto_stop`
- `auto_stop_advice`
- `cmd_auto`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/pause.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_analyst_role.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_git_fixation.py`, `tests/test_plan_appendix.py`, `tests/test_runner_model_preflight.py`, `tests/test_stall_alerts.py`

## orchestrator/brief.py

**Назначение:** Бриф роли одним документом: SPEC/TZ + карта кодовой базы + конвенции

**Публичные функции:**
- `advance_refusal_history`
- `analyst_map_component`
- `component_hash`
- `developer_brief`
- `fresh_map_text`
- `mark_unclosed_parts`
- `new_run_id`
- `skills_text`
- `test_author_answer_component`
- `wrap_boundary`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_source.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/codebase_map.py`

**Импортируется:** `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/test_advance_refusal_history.py`, `tests/test_answer_branch_reads.py`, `tests/test_auto_cycle.py`, `tests/test_brief.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_role_prompt_test_author_mission.py`

## orchestrator/budget.py

**Назначение:** Потолок задачи: значение из SPEC, блокировка `run`, реакция после шага.

**Публичные функции:**
- `apply_spec_budget`
- `budget_block`
- `calibration_warning`
- `check_program_spend`
- `cmd_budget`
- `count_zone_paths`
- `enforce_budget`
- `recommended_budget_usd`
- `reseed_program_spend`
- `spec_budget`
- `spent_with_estimate`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/retro.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/runner.py`, `tests/test_auto_cycle.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_doctor.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_invariants.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_program_spend_reseed.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`

## orchestrator/canary.py

**Назначение:** Команда `canary`: синтетический прогон конвейера, v2 (SPEC

**Публичные функции:**
- `cmd_canary`
- `merges_since_last_green_run`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/pool_seal.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/pin.py`, `tests/test_canary.py`, `tests/test_doctor.py`, `tests/test_parent_task_division.py`

## orchestrator/catalog.py

**Назначение:** Каталог задач: заведение, список, карточка задачи, журнал шагов.

**Публичные функции:**
- `cmd_init`
- `cmd_log`
- `cmd_new`
- `cmd_show`
- `cmd_status`
- `slugify`
- `spawn_subtask`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/liveness.py`, `orchestrator/merge_queue.py`, `orchestrator/pool_seal.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer_gate.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_pin_divergence.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_tz_zones_parsing.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parent_task_division.py`, `tests/test_pause_now.py`, `tests/test_plan_appendix.py`, `tests/test_prune.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_slugify.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_workspace.py`

## orchestrator/checkpoint.py

**Назначение:** WIP-чекпоинты рабочего дерева задачи: таймаут шага (SPEC T041),

**Публичные функции:**
- `commit_abnormal_checkpoint`
- `commit_pause_now_checkpoint`
- `commit_pull_checkpoint`
- `commit_step_artifacts`
- `commit_success_checkpoint`
- `commit_timeout_checkpoint`
- `task_dir_zone`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/pause.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `tests/test_artifact_materialization.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_stray_acceptance_files.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_pause_now.py`, `tests/test_step_autocommit.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/ci.py

**Назначение:** Статус CI головного коммита ветки задачи — условие merge (SPEC T017, 6).

**Публичные функции:**
- `branch_status`
- `check_runs`
- `check_runs_page`
- `find_run_id`
- `gh`
- `head_sha`
- `run_list`
- `status_kind`
- `trigger_rerun`
- `verifying_is_red`
- `verifying_status`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/auto.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/watch.py`, `tests/test_acceptance.py`, `tests/test_auto_cycle.py`, `tests/test_ci_status.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_doctor_artifact_branch_ci.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_invariants.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_plan_appendix.py`, `tests/test_verifying_ceiling.py`

## orchestrator/cleanup.py

**Назначение:** kill switch и уборка хвостов задачи: каталог артефактов и ветка.

**Публичные функции:**
- `artifacts_in_main`
- `artifacts_tracked_here`
- `cleanup_killed_task`
- `cmd_kill`
- `drop_merged_task_branch`
- `drop_task_branch`
- `drop_task_dir`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/retro.py`, `tests/test_detached_cycle.py`, `tests/test_done_branch_cleanup.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_multitarget_invariants.py`, `tests/test_retro.py`, `tests/test_task_id_prefix_regression.py`

## orchestrator/coldstart.py

**Назначение:** Наблюдаемый мир для холодного старта пульта (SPEC T049, ADR-0005 п.5).

**Публичные функции:**
- `observed_max_task_number`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/store.py`, `tests/test_coldstart.py`

## orchestrator/config.py

**Назначение:** Пути и константы оркестратора — один адрес на весь пакет.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/context_package.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/notes.py`, `orchestrator/parallel_limit.py`, `orchestrator/pin.py`, `orchestrator/pool_seal.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/schema.py`, `orchestrator/session.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/venv.py`, `orchestrator/version.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`, `tests/sandbox.py`, `tests/test_acceptance.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_artel_bootstrap.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_capacity_gate.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_ci_status.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_coldstart.py`, `tests/test_conftest_role_guard.py`, `tests/test_detached_cycle.py`, `tests/test_doc_commit.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_done_branch_cleanup.py`, `tests/test_dry_run.py`, `tests/test_failure_classification.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_fsm_retro.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_division_section.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_notes.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_plan_appendix.py`, `tests/test_program_spend_reseed.py`, `tests/test_protected_paths_gate.py`, `tests/test_prune.py`, `tests/test_pull.py`, `tests/test_release.py`, `tests/test_repo_context.py`, `tests/test_report.py`, `tests/test_retro.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_session.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stack.py`, `tests/test_stall_alerts.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_verifying_ceiling.py`, `tests/test_version.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_lock.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/context_package.py

**Назначение:** Опись компонентов и дисциплина частей контекстных пакетов — общий слой

**Публичные функции:**
- `discipline`
- `render_component`
- `sha256_of`
- `split_into_parts`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/brief.py`, `orchestrator/review.py`, `tests/test_brief.py`, `tests/test_review_package.py`

## orchestrator/dry_run.py

**Назначение:** Команда `acceptance-dry-run`: сухой прогон приёмки — предпросмотр без

**Публичные функции:**
- `cmd_acceptance_dry_run`

**Импортирует:** `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_dry_run.py`

## orchestrator/failure_classification.py

**Назначение:** Классификация провалившейся попытки агента (SPEC T082, требования 1-2).

**Публичные функции:**
- `classify_attempt_failure`
- `required_cli_version`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/alerts.py`, `orchestrator/runner.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_failure_classification.py`, `tests/test_runner_model_preflight.py`

## orchestrator/fixation.py

**Назначение:** Hash-фиксация артефактов на переходах FSM (ADR-0003 п.15, п.17; tasks/T021).

**Публичные функции:**
- `approve_sha_hint`
- `check_integrity`
- `default_code_sha`
- `external_artifact_sha`
- `external_code_sha`
- `fix`
- `read`
- `refixate_after_rejected_transition`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/test_fsm_autogate.py`, `tests/test_git_fixation.py`, `tests/test_step_autocommit.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/fsm.py

**Назначение:** Переходы автомата: advance по артефактам, approve/reject Оператора.

**Публичные функции:**
- `cmd_advance`
- `cmd_approve`
- `cmd_reject`
- `confirm_fixation`
- `guard_refuses`

**Импортирует:** `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/review.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_conflict_note.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_registry_gate.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_verifying_ceiling.py`, `tests/test_zones_approve.py`

## orchestrator/fsm_advance.py

**Назначение:** Обработчики `cmd_advance` — один на состояние (SPEC T091, декомпозиция

**Публичные функции:**
- `in_dev`
- `review`
- `spec_writing`
- `tests_writing`
- `verifying`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/fsm.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_capacity_gate.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_protected_paths_gate.py`, `tests/test_zones_gate.py`

## orchestrator/fsm_autogate.py

**Назначение:** Автогейт acceptance по политике gates.yaml (ADR-0007, SPEC T066).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_source.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `tests/test_fsm_autogate.py`, `tests/test_git_fixation.py`

## orchestrator/fsm_merge_gate.py

**Назначение:** Тело и внешний цикл гейта `merge_gate` (SPEC T052, T053, T082, T087):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/repo_context.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_plan_appendix.py`, `tests/test_protected_paths_gate.py`

## orchestrator/fsm_postmerge.py

**Назначение:** Побочные эффекты merge_gate после успешного merge: карта кодовой базы

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `scripts/codebase_map.py`

**Импортируется:** `orchestrator/fsm_merge_gate.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`, `tests/test_plan_appendix.py`

## orchestrator/gates.py

**Назначение:** Политика гейтов из `gates.yaml` (ADR-0007, SPEC T066).

**Публичные функции:**
- `policy`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/fsm_autogate.py`, `tests/test_fsm_autogate.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`

## orchestrator/gitcmd.py

**Назначение:** Вызовы git в корне репозитория, вопросы к ветке задачи и к произвольному

**Публичные функции:**
- `branch_exists`
- `branch_head_sha`
- `branch_merged`
- `carpentry`
- `check_ignore`
- `commit_committer_dates`
- `commits_behind`
- `current_branch`
- `diff_base`
- `diff_base_source`
- `diff_names`
- `diff_paths`
- `fetch_head_sha`
- `fetch_ref_sha`
- `git`
- `has_no_remote`
- `head_sha`
- `in_repo`
- `is_ancestor`
- `is_clean`
- `list_branches`
- `ls_tree_files`
- `merges_between`
- `on_foreign_branch`
- `pult_env`
- `remote_branch_sha`
- `show`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/dry_run.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/notes.py`, `orchestrator/pin.py`, `orchestrator/projects.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_capacity_gate.py`, `tests/test_catalog_new_race.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_doctor.py`, `tests/test_doctor_artifact_branch_ci.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_retro.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_carpentry.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_pin.py`, `tests/test_plan_appendix.py`, `tests/test_protected_paths_gate.py`, `tests/test_pull.py`, `tests/test_repo_context.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`, `tests/test_zones_gate.py`

## orchestrator/github_adapter.py

**Назначение:** GitHub-адаптер целевого `forge: github`: Draft-MR-флоу задачи (SPEC

**Публичные функции:**
- `ensure_draft_mr`
- `ensure_head_in_origin`
- `undraft_mr`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend.py`, `tests/test_auto_cycle.py`, `tests/test_git_fixation.py`, `tests/test_github_adapter.py`, `tests/test_merge_gate_ci_wait.py`

## orchestrator/idgen.py

**Назначение:** Генератор идентификатора задачи (SPEC T094, требование 2).

**Публичные функции:**
- `new_task_id`

**Импортирует:** —

**Импортируется:** `orchestrator/catalog.py`

## orchestrator/keychain.py

**Назначение:** Чтение токенов из macOS keychain.

**Публичные функции:**
- `token`

**Импортирует:** —

**Импортируется:** `orchestrator/pool_seal.py`, `orchestrator/runner.py`

## orchestrator/lease.py

**Назначение:** Advisory-lease задачи: замок параллельных сессий CLI (SPEC T044).

**Публичные функции:**
- `acquire`
- `foreign_live_lease`
- `is_live`
- `release`
- `release_any`
- `run_locked`
- `warn_foreign_live`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/cleanup.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `orchestrator/workspace.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_detached_cycle.py`, `tests/test_lease.py`, `tests/test_session.py`

## orchestrator/liveness.py

**Назначение:** Возраст heartbeat и адресуемость pid — общие для lease/merge_lock/doctor.

**Публичные функции:**
- `group_kill_detail`
- `terminate_process_group`

**Импортирует:** —

**Импортируется:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `tests/test_doctor.py`, `tests/test_liveness.py`, `tests/test_merge_lock.py`

## orchestrator/merge_lock.py

**Назначение:** Мьютекс merge-окна: один держатель на весь пульт (SPEC T053).

**Публичные функции:**
- `acquire`
- `release`
- `run_window`
- `touch_heartbeat`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/fsm_merge_gate.py`, `orchestrator/merge_queue.py`, `orchestrator/notes.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`

## orchestrator/merge_queue.py

**Назначение:** Очередь FIFO ожидания мьютекса merge-окна (SPEC

**Публичные функции:**
- `queue_wait_minutes`
- `wait_for_window`
- `wait_suffix`

**Импортирует:** `orchestrator/config.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/catalog.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_merge_queue.py`

## orchestrator/notes.py

**Назначение:** Команда `note`: строка в копилку/бэклог/очередь изолированным коммитом

**Публичные функции:**
- `cmd_doc_commit`
- `cmd_note`
- `pending_notes`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/merge_lock.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_doc_commit.py`, `tests/test_notes.py`

## orchestrator/parallel_limit.py

**Назначение:** Лимитер параллельных задач: MAX_PARALLEL_TASKS (SPEC T060).

**Публичные функции:**
- `busy_other_tasks`
- `refusal`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/runner.py`, `tests/test_parallel_limit.py`

## orchestrator/pause.py

**Назначение:** Команда `pause`/`resume`: штатная приостановка задачи (SPEC T070).

**Публичные функции:**
- `cmd_pause`
- `cmd_pause_now`
- `cmd_resume`
- `is_paused`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/checkpoint.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/runner.py`, `tests/test_auto_cycle.py`, `tests/test_pause.py`, `tests/test_pause_now.py`

## orchestrator/pin.py

**Назначение:** Команда `pin-update`: обновление пина запущенной версии (A7, Stage1,

**Публичные функции:**
- `cmd_pin_to`
- `cmd_pin_update`

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_pin.py`

## orchestrator/pool_seal.py

**Назначение:** Запечатанный пул шаблонов канарейки (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW).

**Публичные функции:**
- `cmd_pool_seal`
- `guids_path`
- `pool_drift_warning`
- `restore_pool_if_missing`
- `sealed_path`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/runner.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_canary.py`

## orchestrator/projects.py

**Назначение:** Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

**Публичные функции:**
- `artifact_repo_has_no_remote`
- `cmd_target_init`
- `init_artifact_repo`
- `init_project`
- `project_dir`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/fixation.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_multitarget.py`

## orchestrator/prune.py

**Назначение:** Команда `prune`: исполняет retention-политику docs/retention.md для

**Публичные функции:**
- `cmd_prune`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_prune.py`

## orchestrator/pull.py

**Назначение:** Исходы подтяжки главной ветки в ветку задачи (роадмап §3, фаза R,

**Публичные функции:**
- `evaluate`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/ci_push_class.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/fsm.py`, `tests/test_pull.py`

## orchestrator/release.py

**Назначение:** Команда `release`: операторское снятие lease задачи (SPEC T062).

**Публичные функции:**
- `cmd_release`

**Импортирует:** `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_release.py`

## orchestrator/repo_context.py

**Назначение:** Репозиторный контекст target'а: одно место, где живёт «куда клон, какой

**Публичные функции:**
- `git`
- `path_or_none`
- `resolve`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/review.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_protected_paths_gate.py`, `tests/test_repo_context.py`

## orchestrator/report.py

**Назначение:** Команда `report`: статический HTML-срез `state.db` + метрики гейтовой

**Публичные функции:**
- `cmd_report`
- `map_growth_calibration_median`
- `map_growth_cost_estimate`
- `map_growth_open_alerts`
- `map_size_table_rows`
- `token_rate_divergence`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_report.py`

## orchestrator/retro.py

**Назначение:** Детерминированная генерация содержимого `docs/retro/<id>.md` (SPEC T043).

**Публичные функции:**
- `build_done`
- `build_killed`
- `parse_total_cost`
- `retro_path`
- `retro_rel_path`

**Импортирует:** `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/budget.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/snapshot.py`, `tests/test_canary.py`, `tests/test_fsm_retro.py`, `tests/test_parent_task_division.py`, `tests/test_retro.py`

## orchestrator/retro_corpus.py

**Назначение:** Локальный кэш ретро-корпуса — расходный, пересобирается ЛОКАЛЬНО

**Публичные функции:**
- `read_cache`
- `rebuild_cache`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`, `orchestrator/yamlmini.py`

**Импортируется:** —

## orchestrator/review.py

**Назначение:** Ревью-пакет: вход ревьювера собирает оркестратор, а не сам агент.

**Публичные функции:**
- `artifact_part`
- `artifact_text`
- `git_diff_part`
- `package_note`
- `previous_verdict_sha`
- `review_package`

**Импортирует:** `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/fsm.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/test_capacity_gate.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`

## orchestrator/role_prompt.py

**Назначение:** Миссия роли + бриф/ревью-пакет шага: сборка содержимого промпта, общего

**Публичные функции:**
- `mission_brief_package`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/review.py`, `orchestrator/stack.py`

**Импортируется:** `orchestrator/runner.py`, `tests/test_role_prompt_test_author_mission.py`

## orchestrator/roles.py

**Назначение:** Карта исполнителей из roles.yaml: состав скилов роли читается кодом.

**Публичные функции:**
- `load`
- `model`
- `skills`
- `token_slots`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/runner.py`, `orchestrator/stack.py`, `tests/test_yaml_parsing.py`

## orchestrator/runner.py

**Назначение:** Запуск агента шага: промпт роли, окружение, попытки, исход, стоимость.

**Публичные функции:**
- `close_pump`
- `cmd_run`
- `git_identity`
- `in_role_environment`
- `role_cmd`
- `role_cwd`
- `role_cwd_path`
- `role_env`
- `role_token`
- `run_agent_once`
- `spawn_agent`
- `step_role`
- `wave_breaker_alerts_open`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/roles.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/lease.py`, `orchestrator/notes.py`, `orchestrator/pause.py`, `orchestrator/pool_seal.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_invariants.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/schema.py

**Назначение:** Схема БД и миграции: DDL, `migrate(conn)`, `add_column`/`table_columns`.

**Публичные функции:**
- `add_column`
- `create_schema`
- `migrate`
- `table_columns`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/store.py`, `tests/test_parent_task_division.py`

## orchestrator/session.py

**Назначение:** Идентификатор сессии оркестратора — единая функция для всех команд

**Публичные функции:**
- `resolve_session_id`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/lease.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/test_session.py`

## orchestrator/snapshot.py

**Назначение:** Снапшот артефактов задачи в `refs/artifacts/<id>` ЦЕЛЕВОГО при закрытии

**Публичные функции:**
- `pending`
- `publish_and_cleanup`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/cleanup.py`, `orchestrator/fsm_merge_gate.py`

## orchestrator/spend.py

**Назначение:** Стоимость шага: разбор чисел, событие потока, учёт в spent_usd.

**Публичные функции:**
- `charge_missing_result`
- `charge_step`
- `cli_number`
- `cost_note`
- `json_number`
- `parse_cost_event`
- `partial_cost_usd`
- `partial_tokens_from_log`
- `step_tokens`
- `stream_usage_by_type`
- `usage_tokens_by_type`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/pause.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `scripts/guard.py`, `tests/test_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_step_cost.py`

## orchestrator/stack.py

**Назначение:** Манифест объявленного стека пульта (SPEC 01M1RDCAFENSW2VVAPECHCVGMM,

**Публичные функции:**
- `check_stack`
- `installed_cli_version`
- `model_cli_verdict`
- `pytest_python_executable`
- `python_version_string`
- `version_text`

**Импортирует:** `orchestrator/config.py`, `orchestrator/roles.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/version.py`, `scripts/stack_ci.py`, `tests/sandbox.py`, `tests/test_agent_prompt.py`, `tests/test_artel_bootstrap.py`, `tests/test_git_hooks.py`, `tests/test_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_role_prompt_test_author_mission.py`, `tests/test_runner_model_preflight.py`, `tests/test_stack.py`, `tests/test_stack_ci.py`

## orchestrator/store.py

**Назначение:** Состояние задач: БД, журнал шагов, смена состояния, запросы по областям.

**Публичные функции:**
- `ack_alert`
- `alerts_older_than`
- `alerts_since`
- `all_leases`
- `all_tasks`
- `archive_alert`
- `canary_baseline`
- `charge`
- `charge_estimate`
- `closed_external_tasks`
- `counter_targets`
- `db`
- `delete_merge_queue_row`
- `dequeue_merge_wait`
- `enable_wal`
- `enqueue_merge_wait`
- `get_alert`
- `get_task`
- `green_canary_runs`
- `insert_alert`
- `insert_canary_run`
- `insert_lease`
- `insert_task`
- `journal`
- `latest_fixed_sha`
- `latest_green_canary_run`
- `lease_row`
- `max_alert_id`
- `merge_lock_row`
- `merge_queue_rows`
- `next_task_number`
- `now`
- `open_alert_exists`
- `open_alerts`
- `peek_task_number`
- `record_fixation`
- `refusal_history`
- `release_lease`
- `release_merge_lock`
- `resolve_task_id`
- `seed_task_counters`
- `set_canary_baseline`
- `set_merge_lock`
- `set_state`
- `task_branch`
- `task_exists`
- `task_number`
- `task_steps`
- `task_target`
- `total_estimate`
- `total_spent`
- `touch_merge_queue_heartbeat`
- `update_lease`
- `update_lease_pgid`
- `update_task`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/schema.py`, `orchestrator/session.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/alerts.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/dry_run.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/notes.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/schema.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_capacity_gate.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_coldstart.py`, `tests/test_detached_cycle.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_doc_commit.py`, `tests/test_doctor.py`, `tests/test_doctor_artifact_branch_ci.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_dry_run.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_retro.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_notes.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_plan_appendix.py`, `tests/test_program_spend_reseed.py`, `tests/test_protected_paths_gate.py`, `tests/test_prune.py`, `tests/test_pull.py`, `tests/test_release.py`, `tests/test_report.py`, `tests/test_retro.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_review_registry_gate.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stall_alerts.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_journal.py`, `tests/test_store_schema_migration_parity.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_verifying_ceiling.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_zone_lock.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/targets.py

**Назначение:** Декларация целевых проектов из targets.yaml: запись target'а читается кодом.

**Публичные функции:**
- `check`
- `load`
- `target`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/projects.py`, `orchestrator/repo_context.py`, `orchestrator/retro_corpus.py`, `orchestrator/store.py`, `tests/test_github_adapter.py`, `tests/test_multitarget.py`

## orchestrator/venv.py

**Назначение:** Venv пульта: `.artel/venv`, создаётся идемпотентно средствами

**Публичные функции:**
- `cmd_venv_sync`
- `sync`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_venv.py`

## orchestrator/version.py

**Назначение:** Команда `version`: пин CLI, фактическая версия, версия схемы артефактов

**Публичные функции:**
- `cmd_version`

**Импортирует:** `orchestrator/config.py`, `orchestrator/stack.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_version.py`

## orchestrator/watch.py

**Назначение:** Команда `watch`: дозор событий журнала для сессии Оператора (SPEC

**Публичные функции:**
- `cmd_watch`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_watch.py`

## orchestrator/workspace.py

**Назначение:** Рабочая поверхность задачи: git worktree в стандартном месте (SPEC T045).

**Публичные функции:**
- `cmd_workspace`
- `ensure`
- `on_task_branch`
- `path`
- `registered_paths`
- `remove`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_amend.py`, `tests/test_answer_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_fsm_autogate.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget_invariants.py`, `tests/test_pull.py`, `tests/test_step_autocommit.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`

## orchestrator/yamlmini.py

**Назначение:** Подмножество YAML, которого достаточно системе: frontmatter и roles.yaml.

**Публичные функции:**
- `frontmatter`
- `mapping`
- `scalar`

**Импортирует:** —

**Импортируется:** `orchestrator/amend.py`, `orchestrator/artifacts.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/gates.py`, `orchestrator/pull.py`, `orchestrator/retro_corpus.py`, `orchestrator/roles.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_yaml_parsing.py`

## orchestrator/zone_lock.py

**Назначение:** Занятость зоны на старте кода — предусловие перед первым шагом роли

**Публичные функции:**
- `blocking_conflict`
- `claim`
- `claimed_but_not_started`
- `cmd_zone_release`
- `cmd_zone_reorder`
- `queue_order`
- `queue_position`
- `refusal`
- `release_claim`
- `wait_enter_action`
- `wait_exit_action`
- `wait_minutes`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/runner.py`, `scripts/guard.py`, `tests/test_catalog_status_log.py`, `tests/test_zone_lock.py`

## scripts/ci_push_class.py

**Назначение:** Классификатор класса пуша CI (ADR-0016) — вынесен из bash-логики job

**Публичные функции:**
- `classify`
- `is_doc_path`
- `main`

**Импортирует:** —

**Импортируется:** `orchestrator/pull.py`, `tests/test_ci_push_class.py`, `tests/test_pull.py`

## scripts/codebase_map.py

**Назначение:** Codebase-map пульта: детерминированная карта модулей верхнего уровня.

**Публичные функции:**
- `build_modules`
- `discover_module_paths`
- `extract_imported_dotted_names`
- `extract_public_functions`
- `extract_purpose`
- `git_head_sha`
- `main`
- `map_stats`
- `module_dotted_name`
- `parse_module`
- `project_for_brief`
- `render`
- `repo_root`

**Импортирует:** —

**Импортируется:** `orchestrator/brief.py`, `orchestrator/fsm_postmerge.py`, `tests/test_codebase_map.py`

## scripts/guard.py

**Назначение:** Guard: валидатор СТРУКТУРЫ артефактов задач (frontmatter + обязательные

**Публичные функции:**
- `acceptance_traceability_errors`
- `appendix_rename_header_error`
- `appendix_unprotected_path_error`
- `artifact_disk_read_errors_from_files`
- `basic_frontmatter_errors`
- `check`
- `check_content`
- `ci_marker_wording_ok`
- `count_test_methods`
- `division_section_errors`
- `escalation_status_errors`
- `extraneous_task_root_files_in`
- `has_redness_marker`
- `id_format_patterns`
- `id_format_sample_errors`
- `indented_ac_marker_errors_from_files`
- `is_draft_lenient`
- `is_extraneous_acceptance_test_file`
- `is_extraneous_task_root_file`
- `main`
- `mentioned_paths`
- `module_docstring`
- `parse_division_subsections`
- `plan_appendices`
- `protected_zones`
- `redness_marker_errors_from_files`
- `registry_errors`
- `registry_record_errors`
- `registry_records`
- `registry_table_rows`
- `requires_ac_markup`
- `requires_budget_field`
- `requires_registry`
- `requires_split_assessment`
- `requires_zones`
- `review_evidence_errors`
- `role_budget_cap_errors`
- `sandbox_reuse_check`
- `scan_ac_content`
- `scan_acceptance_tests`
- `scan_artifact_disk_reads`
- `scan_extraneous_acceptance_files`
- `scan_extraneous_task_root_files`
- `scan_id_format_samples`
- `scan_indented_ac_markers`
- `scan_redness_markers`
- `schema_errors`
- `section_body`
- `spec_ac_errors`
- `spec_budget_field_errors`
- `spec_unclassified_paths`
- `spec_zones_errors`
- `split_assessment_errors`
- `split_signal_names`
- `test_functions_without_mutation_claim`
- `traceability_errors_from_content`
- `unclassified_paths`
- `unclassified_paths_refusal`
- `zone_items`

**Импортирует:** `orchestrator/config.py`, `orchestrator/spend.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/retro.py`, `orchestrator/version.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_artifact_materialization.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_guard_artifact_branch_mode.py`, `tests/test_guard_artifact_disk_read.py`, `tests/test_guard_division_section.py`, `tests/test_guard_extraneous_acceptance_files.py`, `tests/test_guard_mutation_claim.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_plan_appendix.py`, `tests/test_review_registry_gate.py`, `tests/test_version.py`, `tests/test_yaml_parsing.py`

## scripts/stack_ci.py

**Назначение:** CI-обвязка манифеста стека (01M1RDCCKBQMJ5G2K9ANJP059H, требования 1-3):

**Публичные функции:**
- `main`
- `minimum_python_version_string`

**Импортирует:** `orchestrator/stack.py`

**Импортируется:** —

## tests/__init__.py

**Назначение:** нет docstring

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## tests/sandbox.py

**Назначение:** Общая тестовая песочница (SPEC T037, требование 1; SPEC T061 —

**Публичные функции:**
- `assert_acceptance_run_called`
- `capture`
- `capture_new_task_id`
- `claude_only_popen`
- `claude_only_run`
- `disk_backed_ls_tree_files`
- `disk_backed_show`
- `event`
- `fake_git`
- `fake_git_for`
- `is_claude_call`
- `network_guarded_real_run`
- `resilient_tmp_cleanup`
- `seed_developer_brief_fixtures`
- `sync_spec_from_worktree`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `tests/test_acceptance_collect.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_capacity_gate.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_coldstart.py`, `tests/test_detached_cycle.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_doc_commit.py`, `tests/test_doctor.py`, `tests/test_doctor_artifact_branch_ci.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_done_branch_cleanup.py`, `tests/test_dry_run.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_fsm_retro.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_schema.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_notes.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_plan_appendix.py`, `tests/test_program_spend_reseed.py`, `tests/test_protected_paths_gate.py`, `tests/test_prune.py`, `tests/test_pull.py`, `tests/test_release.py`, `tests/test_repo_context.py`, `tests/test_report.py`, `tests/test_retro.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_sandbox.py`, `tests/test_session.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stack.py`, `tests/test_stall_alerts.py`, `tests/test_step_cost.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_journal.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_lock.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## tests/test_acceptance.py

**Назначение:** Юнит-тесты orchestrator/acceptance.py::run_full_suite (ADR-0007,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/ci.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_acceptance_collect.py

**Назначение:** Юнит-тесты `orchestrator/acceptance.py::collect` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance_tests_flow.py

**Назначение:** Тесты A4 — роль test_author, приёмочные тесты до кода (tasks/T023/SPEC.md).

**Публичные функции:**
- `version_stub_run`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_amend.py`

## tests/test_advance_guard.py

**Назначение:** Тесты guard на переходах FSM (см. tasks/T017/SPEC.md, требование 5).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_advance_refusal_history.py

**Назначение:** Юнит-тесты `store.refusal_history` / `brief.advance_refusal_history`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_agent_failure.py

**Назначение:** Тесты провала шага по коду возврата агента (см. tasks/T006/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_agent_log.py

**Назначение:** Тесты лога агента по ходу шага (см. tasks/T005/SPEC.md).

**Публичные функции:**
- `assistant_event`
- `tool_result_event`
- `tool_use_call`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_agent_prompt.py

**Назначение:** Тесты канала промпта роли (см. tasks/T017/SPEC.md, требование 4).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_alerts_wave_breaker.py

**Назначение:** Юнит-тесты стоп-крана волны, часть 1 (tasks/01M1THKPNZ11DBZAQDMJ33EMJR/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_amend.py

**Назначение:** Юнит-тесты orchestrator/amend.py (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/amend.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`

**Импортируется:** —

## tests/test_analyst_role.py

**Назначение:** Тесты A5 — роль analyst: SPEC из свободного ТЗ Оператора (tasks/T025/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_answer.py

**Назначение:** Юнит-тесты `orchestrator/answer.py` (SPEC T075, SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/test_git_fixation.py`

**Импортируется:** —

## tests/test_answer_branch_reads.py

**Назначение:** Юнит-тесты ветко-корректного чтения ANSWER/QUESTIONS (SPEC T075):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_answer_gate.py

**Назначение:** Юнит-тест гейта возврата из эскалации (SPEC T075, AC-3/AC-4): второй

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_artel_bootstrap.py

**Назначение:** Юнит-тесты самовыбора интерпретатора `orchestrator/artel.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/stack.py`

**Импортируется:** —

## tests/test_artel_role_restricted_commands.py

**Назначение:** Юнит-тесты гейта диспетчера `orchestrator/artel.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/pool_seal.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_artifact_branch_new_parent.py

**Назначение:** Юнит-тест R2-F3 REVIEW.md 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH итерации 2:

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_artifact_branch_push.py

**Назначение:** Юнит-тесты классификации/журналирования push артефактной ветки

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_artifact_escalation_marker.py

**Назначение:** Юнит-тесты маркера эскалации по содержимому артефакта роли (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/auto.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_auto_cycle.py`

**Импортируется:** —

## tests/test_artifact_materialization.py

**Назначение:** Юнит-тесты SPEC 01M1NKTF173WV5CPDZ1C3WW69K: материализация `tasks/<id>/`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_auto_cycle.py

**Назначение:** Тесты команды `auto` — цикла до ближайшего гейта (см. tasks/T014/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_artifact_escalation_marker.py`

## tests/test_auto_escalated_return_rework_gate.py

**Назначение:** Юнит-тесты `orchestrator.auto._role_step_since_state_entry` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/auto.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_branch_freshness_gate.py

**Назначение:** Юнит-тесты сверки свежести ветки на входе в гейт (SPEC T051, требования

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_brief.py

**Назначение:** Юнит-тесты `orchestrator/brief.py` (T028): хэш компонента, сверка

**Публичные функции:**
- `fake_git_checkout_fails`
- `fake_git_stale`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_budget_live_lease_and_escalation.py

**Назначение:** Юнит-тесты `orchestrator/budget.py`/`orchestrator/lease.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_canary.py

**Назначение:** Юнит-тесты `orchestrator/canary.py` v2 (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ;

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/pool_seal.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_capacity_gate.py

**Назначение:** Юнит-тесты гейта ёмкости diff снимка — fail-closed на сбое git

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_cas_set_state.py

**Назначение:** Юнит-тесты `orchestrator.store.set_state` (SPEC T050).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_new_race.py

**Назначение:** Регресс-тест на замечание major REVIEW T048 итерации 2:

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_pin_divergence.py

**Назначение:** Юнит-тесты `orchestrator.catalog._pin_divergence_warning_text`/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`

**Импортируется:** —

## tests/test_catalog_spawn_subtask.py

**Назначение:** Юнит-тесты `orchestrator.catalog.spawn_subtask`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_status_log.py

**Назначение:** Юнит-тесты `orchestrator.catalog.cmd_log`/`cmd_status` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_tz_path_check.py

**Назначение:** Юнит-тесты сверки путей ТЗ с зонами в `orchestrator/catalog.py`

**Публичные функции:**
- `seed`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_tz_zones_parsing.py

**Назначение:** Юнит-тесты `orchestrator.catalog._tz_calibration_inputs`/`_TZ_ZONES_RE`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`

**Импортируется:** —

## tests/test_catalog_wave_breaker_status.py

**Назначение:** Юнит-тесты `orchestrator.catalog._wave_breaker_suffix`/`cmd_status` —

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_checkpoint_external_step_artifacts.py

**Назначение:** Юнит-тесты `checkpoint._commit_external_step_artifacts` (SPEC T094,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_checkpoint_stray_acceptance_files.py

**Назначение:** Юнит-тесты `checkpoint._is_stray_acceptance_test_file` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`

**Импортируется:** —

## tests/test_checkpoint_zone_filter.py

**Назначение:** Юнит-тесты вспомогательных функций фильтра по зонам WIP-чекпоинтов

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/test_timeout_checkpoint.py`

**Импортируется:** —

## tests/test_ci_push_class.py

**Назначение:** Юнит-тесты scripts/ci_push_class.py (01M28NWK5X10J139Z8TD69HFAC):

**Публичные функции:** (нет)

**Импортирует:** `scripts/ci_push_class.py`

**Импортируется:** —

## tests/test_ci_status.py

**Назначение:** Тесты статуса CI ветки задачи (см. tasks/T017/SPEC.md, требование 6).

**Публичные функции:**
- `run`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_ci_status_kind_gate.py

**Назначение:** Юнит-тесты подтипа не-зелёного статуса CI на гейте `merge_gate`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/ci.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/test_invariants.py`

**Импортируется:** —

## tests/test_cmd_approve_dispatch.py

**Назначение:** Юнит-тесты таблицы «состояние -> обработчик» `orchestrator.fsm._cmd_

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_codebase_map.py

**Назначение:** Юнит-тесты функций scripts/codebase_map.py (tasks/T027/SPEC.md).

**Публичные функции:**
- `parse`

**Импортирует:** `scripts/codebase_map.py`

**Импортируется:** —

## tests/test_coldstart.py

**Назначение:** Юнит-тесты наблюдаемого мира холодного старта (orchestrator/coldstart.py,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/catalog.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_conftest_role_guard.py

**Назначение:** Юнит-тесты корневого `conftest.py` (SPEC 01M2B6K3EM7F2J72RC2F520Y2K,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`

**Импортируется:** —

## tests/test_detached_cycle.py

**Назначение:** Юнит-тесты отвязки `run`/`auto` от процесса сессии Оператора (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_kill_cleanup.py`

**Импортируется:** —

## tests/test_diff_not_collected_alerts.py

**Назначение:** Юнит-тесты новых функций tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doc_commit.py

**Назначение:** Юнит-тесты команды `doc-commit` (`orchestrator/notes.py::cmd_doc_commit`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doctor.py

**Назначение:** Тесты doctor: pre-flight, recovery-сверка, сироты, alerts, смоуки

**Публичные функции:**
- `result_event`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doctor_artifact_branch_ci.py

**Назначение:** Юнит-тесты `doctor.check_artifact_branch_ci` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/ci.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doctor_artifact_branch_sync.py

**Назначение:** Юнит-тесты `doctor.check_artifact_branch_sync` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doctor_canary_pool.py

**Назначение:** Юнит-тесты `doctor.check_role_log_pool_leak`/`check_token_repo_scope`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_doctor_fix_ignored_artifacts.py

**Назначение:** Юнит-тесты `doctor._fix_ignored_artifact_files`/`doctor --fix` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doctor_wave_breaker.py

**Назначение:** Юнит-тесты первой строки `doctor.cmd_doctor` — стоп-кран волны, часть 2

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_done_branch_cleanup.py

**Назначение:** Юнит-тесты `cleanup.drop_merged_task_branch` (tasks/T073/SPEC.md,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/cleanup.py`, `orchestrator/config.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_dry_run.py

**Назначение:** Юнит-тесты orchestrator/dry_run.py (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/dry_run.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_failure_classification.py

**Назначение:** Юнит-тесты классификатора ошибок агента (SPEC T082, требования 1-2).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/failure_classification.py`

**Импортируется:** —

## tests/test_fsm_advance_gate_framework.py

**Назначение:** Юнит-тесты каркаса гейтов `orchestrator.fsm_advance._run_gates`/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fsm_advance.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_advance_gate_smoke.py

**Назначение:** Смоук трёх сценариев рефакторинга R2 (SPEC 01M1TKNXX5YN5KT4WHG4T44JWV,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_advance_tests_writing_artifact_source.py

**Назначение:** Юнит-тесты гейта источника артефактов на выходе `tests_writing`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/brief.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_advance_tests_writing_dry_collect.py

**Назначение:** Юнит-тесты выхода `orchestrator/fsm_advance.py::tests_writing` — сухой

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_autogate.py

**Назначение:** Юнит-тесты условия «а» `fsm_autogate._autogate_conditions` — чтение

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_source.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/fixation.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_fsm_branch_correct_status_reads.py

**Назначение:** Юнит-тесты ветко-корректных чтений SPEC.md/REVIEW.md/QUESTIONS.md в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_id_format_guard.py`

## tests/test_fsm_draft_mr_reentry.py

**Назначение:** Регресс-тесты REVIEW.md T079 итерации 1, замечание 1 (major):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_map_conflict_autoresolve.py

**Назначение:** Юнит-тесты авторазрешения конфликта подтяжки, где единственный

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_map_regen.py

**Назначение:** Юнит-тесты регенерации/коммита карты кодовой базы на merge_gate

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_merge_conflict_note.py

**Назначение:** Юнит-тесты `orchestrator.fsm._merge_conflict_note` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fsm.py`

**Импортируется:** —

## tests/test_fsm_merge_gate_done_snapshot.py

**Назначение:** Юнит-тест снапшота закрытия на пути `done` (SPEC T094, требования

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_merge_gate_scratch_worktree_cleanup.py

**Назначение:** Регресс-тест R1-F1 (REVIEW.md 01M1R5B33CC7E6BZK085XV3ZCX итерация 1,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/repo_context.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_retro.py

**Назначение:** Юнит-тесты обвязки RETRO в orchestrator/fsm_postmerge.py (SPEC T043):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_review_rework_gate.py

**Назначение:** Юнит-тесты `orchestrator.fsm_advance._reviewer_verdict_baseline` (регрессия

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_review_rework_sha_gate.py

**Назначение:** Юнит-тесты `orchestrator.fsm_advance._code_sha_at_review_escalation`/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_spec_gate_path_check.py

**Назначение:** Юнит-тесты сверки путей SPEC на гейте `spec_gate`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fsm.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_spec_gate_reject.py

**Назначение:** Юнит-тесты ветки `spec_gate` команды `orchestrator/fsm.py::_cmd_reject`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_gates.py

**Назначение:** Юнит-тесты orchestrator/gates.py: политика гейтов из gates.yaml

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gates.py`

**Импортируется:** —

## tests/test_git_fixation.py

**Назначение:** Git-первичка артефактов и approve-по-sha (tasks/T021/SPEC.md, критерии 1–7).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_answer.py`, `tests/test_step_autocommit.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`

## tests/test_git_hooks.py

**Назначение:** Юнит-тесты защиты main главной копии (SPEC 01M2XMCC837R5CX9M58VARK85G):

**Публичные функции:**
- `env_without_marker`
- `squeeze`

**Импортирует:** `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_gitcmd_branch_reads.py

**Назначение:** Юнит-тесты ветко-корректных примитивов `orchestrator/gitcmd.py`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_gitcmd_carpentry.py

**Назначение:** Юнит-тесты `gitcmd.carpentry` (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требования

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/gitcmd.py`

**Импортируется:** —

## tests/test_gitcmd_check_ignore.py

**Назначение:** Юнит-тесты `gitcmd.check_ignore`/`gitcmd.diff_names` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_gitcmd_fetch_ref_sha.py

**Назначение:** Юнит-тесты `gitcmd.fetch_ref_sha` (SPEC 01M2ARQGY51B99YNP9PY806AN1) —

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_github_adapter.py

**Назначение:** Юнит-тесты orchestrator/github_adapter.py (SPEC T079, требования 1-3).

**Публичные функции:**
- `task_row`

**Импортирует:** `orchestrator/github_adapter.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_guard_artifact_branch_mode.py

**Назначение:** Юнит-тесты режима артефактной ветки guard (01M1R66X5SMD3ZEDCVAJ0DR7K2,

**Публичные функции:** (нет)

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_artifact_disk_read.py

**Назначение:** Юнит-тесты `scripts/guard.py::artifact_disk_read_errors_from_files`/

**Публичные функции:**
- `errors_for`
- `source_with`

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_division_section.py

**Назначение:** Юнит-тесты формата секции «## Деление» SPEC

**Публичные функции:**
- `spec_text`
- `subsection`

**Импортирует:** `orchestrator/config.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_extraneous_acceptance_files.py

**Назначение:** Юнит-тесты `guard.is_extraneous_acceptance_test_file`/`guard.

**Публичные функции:** (нет)

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_mutation_claim.py

**Назначение:** Юнит-тесты `scripts/guard.py::test_functions_without_mutation_claim`

**Публичные функции:** (нет)

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_path_mentions.py

**Назначение:** Юнит-тесты сборщика упоминаний путей и сверки с зонами

**Публичные функции:**
- `seed`
- `spec`

**Импортирует:** `orchestrator/config.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_guard_schema.py

**Назначение:** Тесты версии схемы артефактов (см. tasks/T017/SPEC.md, требование 3).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/yamlmini.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_guard_split_signals.py

**Назначение:** Юнит-тесты сигналов «подозрения на большой объём» и проверки секции

**Публичные функции:**
- `spec_text`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_task_root_subdirectory.py

**Назначение:** Юнит-тесты R1-F1 (REVIEW.md 01M1TNN4TMWAQSQ9Y1PW37J5H0 итерация 1,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_guard_zones.py

**Назначение:** Юнит-тесты машиночитаемого поля `zones:` (01M1NKVPD2A79PQ6K0JVV1B2Q1,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_id_format_guard.py

**Назначение:** Юнит-тесты проверки образца формата идентификатора задачи в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `scripts/guard.py`, `tests/sandbox.py`, `tests/test_fsm_branch_correct_status_reads.py`

**Импортируется:** —

## tests/test_invariants.py

**Назначение:** Тесты системных инвариантов (см. tasks/T010/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_ci_status_kind_gate.py`, `tests/test_review_registry_gate.py`, `tests/test_verifying_ceiling.py`

## tests/test_kill_cleanup.py

**Назначение:** Тесты уборки хвостов убитой задачи (см. tasks/T008/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_detached_cycle.py`, `tests/test_kill_live_cycle_refusal.py`

## tests/test_kill_live_cycle_refusal.py

**Назначение:** Юнит-тесты `cleanup._live_cycle_holder` и разбора `--yes` диспетчером

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_kill_cleanup.py`

**Импортируется:** —

## tests/test_lease.py

**Назначение:** Юнит-тесты orchestrator/lease.py (SPEC T044).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_lease_pgid_store.py

**Назначение:** Юнит-тесты `orchestrator.store.update_lease_pgid` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_liveness.py

**Назначение:** Юнит-тесты `orchestrator.liveness.terminate_process_group`/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/liveness.py`

**Импортируется:** —

## tests/test_merge_gate_ci_wait.py

**Назначение:** Юнит-тесты цикла ожидания CI на гейте `merge_gate` (SPEC T087, решение

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/merge_lock.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_merge_lock.py

**Назначение:** Юнит-тесты orchestrator/merge_lock.py (SPEC T053).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_merge_queue.py

**Назначение:** Юнит-тесты orchestrator/merge_queue.py (SPEC 01M291EPQ2VFGCHZTXXC81616V).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_multitarget.py

**Назначение:** Тесты мультитаргетного контура (см. tasks/T019/SPEC.md, критерии 1–8).

**Публичные функции:**
- `fake_git_config`
- `result_event`
- `silent_git`

**Импортирует:** `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_multitarget_invariants.py

**Назначение:** Инварианты мультитаргета — реестр docs/invariants.md (tasks/T020/SPEC.md).

**Публичные функции:**
- `fake_git_config`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_mutation_claim_gate.py

**Назначение:** Юнит-тесты гейта заявки мутации на `in_dev -> verifying` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_new_argv_parsing.py

**Назначение:** Юнит-тесты `orchestrator.artel._parse_new_args` (tasks/T102/SPEC.md):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`

**Импортируется:** —

## tests/test_notes.py

**Назначение:** Юнит-тесты чистых функций `orchestrator/notes.py` (tasks/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_parallel_limit.py

**Назначение:** Юнит-тесты orchestrator/parallel_limit.py (SPEC T060).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/parallel_limit.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_parent_task_division.py

**Назначение:** Юнит-тесты 01M29284PTCJXGERV5262E9XMM — углы, не закрытые приёмочными

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/retro.py`, `orchestrator/schema.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pause.py

**Назначение:** Юнит-тесты orchestrator/pause.py (SPEC T070).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/pause.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pause_now.py

**Назначение:** Юнит-тесты `orchestrator.pause.cmd_pause_now` (SPEC T074).

**Публичные функции:**
- `dead_pid`
- `spawn_sleep_process`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/pause.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pin.py

**Назначение:** Юнит-тесты `orchestrator/pin.py` (tasks/01M1NGFK3N6MRMYGCC09H975V3/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/pin.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_plan_appendix.py

**Назначение:** Юнит-тесты приложений PLAN к защищённым путям (SPEC

**Публичные функции:**
- `diff_block`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_program_spend_reseed.py

**Назначение:** Юнит-тесты пересева программного расхода из RETRO (orchestrator/budget.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_protected_paths_gate.py

**Назначение:** Юнит-тесты защищённых путей — единый список, гейт зон и гейт мержа

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_prune.py

**Назначение:** Юнит-тесты `orchestrator/prune.py` и опорных функций `store.py`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/prune.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pull.py

**Назначение:** Юнит-тесты `orchestrator/pull.py::evaluate` (роадмап §3, фаза R, R3):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/ci_push_class.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_release.py

**Назначение:** Юнит-тесты orchestrator/release.py (SPEC T062).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/release.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_repo_context.py

**Назначение:** Юнит-тесты orchestrator/repo_context.py (SPEC 01M1R5B33CC7E6BZK085XV3ZCX,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_report.py

**Назначение:** Юнит-тесты чистых функций `orchestrator/report.py` (tasks/T092/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/config.py`, `orchestrator/report.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_retro.py

**Назначение:** Юнит-тесты генерации содержимого RETRO (orchestrator/retro.py, SPEC T043).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_review_freshness.py

**Назначение:** Тесты свежести вердикта ревью (см. tasks/T004/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifacts.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_review_package.py

**Назначение:** Тесты ревью-пакета — входа ревьювера (см. tasks/T011/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_review_registry_gate.py

**Назначение:** Юнит-тесты гейта «Реестр замечаний» в `orchestrator/fsm_advance.py::

**Публичные функции:**
- `row`

**Импортирует:** `orchestrator/fsm.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/test_invariants.py`

**Импортируется:** —

## tests/test_role_prompt_test_author_mission.py

**Назначение:** Регресс-тест пункта 5 миссии test_author (SPEC 01M29BANMM8X8JWJ5GDTJWKB0Z,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/role_prompt.py`, `orchestrator/stack.py`

**Импортируется:** —

## tests/test_runner_model_preflight.py

**Назначение:** Юнит-тесты запуска шага роли по абсолютному пути из резолва манифеста

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_runner_role_model.py`

**Импортируется:** —

## tests/test_runner_role_model.py

**Назначение:** Юнит-тесты флага `--model` в команде шага и `model=` в журнале «agent

**Публичные функции:**
- `result_event`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_runner_model_preflight.py`

## tests/test_runner_wave_breaker.py

**Назначение:** Юнит-тесты `orchestrator.runner.wave_breaker_alerts_open` — стоп-кран

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_sandbox.py

**Назначение:** Юнит-тесты перехвата сетевых git-команд `tests/sandbox.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `tests/sandbox.py`

**Импортируется:** —

## tests/test_session.py

**Назначение:** Юнит-тесты orchestrator/session.py (SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/session.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_slugify.py

**Назначение:** Тесты для orchestrator.catalog.slugify (см. tasks/T003/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`

**Импортируется:** —

## tests/test_spec_budget.py

**Назначение:** Тесты бюджета задачи из frontmatter SPEC (см. tasks/T012/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_spent_estimate_store.py

**Назначение:** Юнит-тесты `orchestrator.store.charge_estimate`/`total_estimate` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_split_assessment_merge_gate.py

**Назначение:** Юнит-тесты `orchestrator.fsm._snapshot_split_assessment`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_stack.py

**Назначение:** Юнит-тесты orchestrator/stack.py (SPEC 01M1RDCAFENSW2VVAPECHCVGMM,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/stack.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_stack_ci.py

**Назначение:** Юнит-тесты scripts/stack_ci.py (SPEC 01M1RDCCKBQMJ5G2K9ANJP059H,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/stack.py`

**Импортируется:** —

## tests/test_stall_alerts.py

**Назначение:** Юнит-тесты новых функций tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/SPEC.md

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/auto.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_step_autocommit.py

**Назначение:** Юнит-тесты `checkpoint.commit_step_artifacts` (tasks/T059/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/test_git_fixation.py`

**Импортируется:** —

## tests/test_step_cost.py

**Назначение:** Тесты учёта стоимости шага и потолка бюджета (см. tasks/T007/SPEC.md).

**Публичные функции:**
- `assistant_event`
- `result_event`
- `timeout_then_killed_proc`
- `tool_use_event`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_step_refixation.py

**Назначение:** Юнит-тесты перефиксации sha на пути отклонённого перехода FSM (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/test_git_fixation.py`

**Импортируется:** —

## tests/test_store_db_connection_close.py

**Назначение:** Юнит-тесты закрытия соединений `store.db()` (tasks/T090/SPEC.md,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_store_journal.py

**Назначение:** Юнит-тесты `orchestrator.store.journal` (SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_store_schema_migration_parity.py

**Назначение:** Юнит-тест регресса R1-F2 (REVIEW.md 01M1NKTF173WV5CPDZ1C3WW69K итерации 1,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/store.py`

**Импортируется:** —

## tests/test_task_id_prefix_regression.py

**Назначение:** Регресс-тесты систематического бага разрешения префикса id (REVIEW.md

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_timeout_checkpoint.py

**Назначение:** Юнит-тесты `checkpoint.commit_timeout_checkpoint` (tasks/T041/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/test_git_fixation.py`

**Импортируется:** `tests/test_checkpoint_zone_filter.py`

## tests/test_venv.py

**Назначение:** Юнит-тесты orchestrator/venv.py (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/venv.py`

**Импортируется:** —

## tests/test_verifying_ceiling.py

**Назначение:** Юнит-тесты потолка ожидания CI в `verifying` по времени, не по числу

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/test_invariants.py`

**Импортируется:** —

## tests/test_version.py

**Назначение:** Юнит-тесты orchestrator.version (см. tasks/T030/SPEC.md).

**Публичные функции:**
- `claude_version_missing`
- `claude_version_run`

**Импортирует:** `orchestrator/config.py`, `orchestrator/version.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_watch.py

**Назначение:** Юнит-тесты `orchestrator/watch.py` (SPEC 01M1VBEKRN0GA029J98S0K2DAQ) —

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_workspace.py

**Назначение:** Юнит-тесты orchestrator/workspace.py: git worktree задачи в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_yaml_parsing.py

**Назначение:** Тесты разбора YAML и карты ролей (см. tasks/T017/SPEC.md, требования 1–2).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifacts.py`, `orchestrator/config.py`, `orchestrator/roles.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_zone_lock.py

**Назначение:** Юнит-тесты orchestrator/zone_lock.py (SPEC 01M1P9QAG65GVF69YJEV0V18D9).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_zones_approve.py

**Назначение:** Юнит-тесты сохранения `zones` при `approve` на `spec_gate`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_zones_gate.py

**Назначение:** Юнит-тесты гейта зон на `in_dev -> review` (tasks/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —
