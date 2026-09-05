---
built_at_sha: 17bdbfcfb45c93edf7a290472888cbad93bf280c
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
- `materialize_from_branch`
- `run`
- `run_full_suite`
- `summary`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `tests/test_acceptance.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_branch_freshness_gate.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_map_conflict_autoresolve.py`

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

**Импортируется:** `orchestrator/auto.py`, `orchestrator/fsm_advance.py`, `orchestrator/pause.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_auto_cycle.py`, `tests/test_kill_cleanup.py`, `tests/test_pause_now.py`, `tests/test_report.py`, `tests/test_step_cost.py`

## orchestrator/alerts.py

**Назначение:** Таблица alerts: несущий носитель порогов/инцидентов/триггеров (A3,

**Публичные функции:**
- `ack`
- `auto_ack`
- `close_attention_alerts`
- `close_diff_not_collected_alerts`
- `open_alerts`
- `raise_alert`
- `raise_attention_alert`
- `raise_diff_not_collected_alert`
- `raise_token_rate_divergence_alert`

**Импортирует:** `orchestrator/store.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor.py`, `orchestrator/failure_classification.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/test_coldstart.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`, `tests/test_prune.py`, `tests/test_stall_alerts.py`

## orchestrator/amend.py

**Назначение:** Команда `amend-tests`: штатная правка зафиксированной планки приёмки

**Публичные функции:**
- `cmd_amend_tests`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_amend.py`

## orchestrator/answer.py

**Назначение:** Команда `answer`: канал ответа Оператора на эскалацию (SPEC T075,

**Публичные функции:**
- `cmd_answer`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_answer.py`

## orchestrator/artel.py

**Назначение:** Артель, Фаза 0 — FSM-оркестратор (CLI).

**Публичные функции:**
- `main`

**Импортирует:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/version.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`

**Импортируется:** `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_invariants.py`, `tests/test_new_argv_parsing.py`

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

**Импортирует:** `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_source.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_artifact_materialization.py`, `tests/test_catalog_new_race.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_git_fixation.py`, `tests/test_multitarget_invariants.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_zones_approve.py`

## orchestrator/artifact_source.py

**Назначение:** Ветка-источник `tasks/<id>/` живой задачи — общий резолвер (SPEC T094,

**Публичные функции:**
- `resolve`

**Импортирует:** `orchestrator/artifact_branch.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/brief.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `tests/test_fsm_autogate.py`

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

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`, `tests/test_git_fixation.py`, `tests/test_stall_alerts.py`

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

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_source.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/test_advance_refusal_history.py`, `tests/test_answer_branch_reads.py`, `tests/test_brief.py`

## orchestrator/budget.py

**Назначение:** Потолок задачи: значение из SPEC, блокировка `run`, реакция после шага.

**Публичные функции:**
- `apply_spec_budget`
- `budget_block`
- `check_program_spend`
- `cmd_budget`
- `enforce_budget`
- `reseed_program_spend`
- `spec_budget`
- `spent_with_estimate`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/retro.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/runner.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_fsm_autogate.py`, `tests/test_invariants.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_program_spend_reseed.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`

## orchestrator/canary.py

**Назначение:** Команда `canary`: синтетический прогон конвейера, v2 (SPEC

**Публичные функции:**
- `cmd_canary`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/answer.py`, `orchestrator/artifacts.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_canary.py`

## orchestrator/catalog.py

**Назначение:** Каталог задач: заведение, список, карточка задачи, журнал шагов.

**Публичные функции:**
- `cmd_init`
- `cmd_log`
- `cmd_new`
- `cmd_show`
- `cmd_status`
- `slugify`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/liveness.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer_gate.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_status_log.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parallel_limit.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_prune.py`, `tests/test_release.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_slugify.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_store_journal.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_workspace.py`, `tests/test_zone_lock.py`

## orchestrator/checkpoint.py

**Назначение:** WIP-чекпоинты рабочего дерева задачи: таймаут шага (SPEC T041),

**Публичные функции:**
- `commit_abnormal_checkpoint`
- `commit_pause_now_checkpoint`
- `commit_step_artifacts`
- `commit_timeout_checkpoint`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/pause.py`, `orchestrator/runner.py`, `tests/test_artifact_materialization.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_pause_now.py`, `tests/test_step_autocommit.py`, `tests/test_timeout_checkpoint.py`

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

**Импортируется:** `orchestrator/auto.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `tests/test_auto_cycle.py`, `tests/test_ci_status.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_invariants.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_verifying_ceiling.py`

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

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/retro.py`, `tests/test_done_branch_cleanup.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget_invariants.py`, `tests/test_retro.py`, `tests/test_task_id_prefix_regression.py`

## orchestrator/coldstart.py

**Назначение:** Наблюдаемый мир для холодного старта пульта (SPEC T049, ADR-0005 п.5).

**Публичные функции:**
- `observed_max_task_number`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/doctor.py`, `orchestrator/store.py`, `tests/test_coldstart.py`

## orchestrator/config.py

**Назначение:** Пути и константы оркестратора — один адрес на весь пакет.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/context_package.py`, `orchestrator/doctor.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/pin.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/version.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`, `tests/sandbox.py`, `tests/test_acceptance.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_canary.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_status_log.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_ci_status.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_done_branch_cleanup.py`, `tests/test_dry_run.py`, `tests/test_failure_classification.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_retro.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parallel_limit.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_program_spend_reseed.py`, `tests/test_prune.py`, `tests/test_release.py`, `tests/test_report.py`, `tests/test_retro.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stall_alerts.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_store_journal.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_verifying_ceiling.py`, `tests/test_version.py`, `tests/test_workspace.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_lock.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/context_package.py

**Назначение:** Опись компонентов и дисциплина частей контекстных пакетов — общий слой

**Публичные функции:**
- `discipline`
- `render_component`
- `sha256_of`
- `split_into_parts`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/brief.py`, `orchestrator/review.py`, `tests/test_brief.py`, `tests/test_review_package.py`

## orchestrator/doctor.py

**Назначение:** doctor: pre-flight, recovery-сверка, сироты, живой и офлайн-смоук CLI

**Публичные функции:**
- `all_checks`
- `check_backup_age`
- `check_base_branch`
- `check_branch_freshness`
- `check_cli_found`
- `check_cli_version`
- `check_disk_space`
- `check_git_identity`
- `check_hung_test_runs`
- `check_leases`
- `check_merge_lock`
- `check_orphans`
- `check_pending_snapshots`
- `check_remote_empty`
- `check_role_log_pool_leak`
- `check_root_pin`
- `check_target_layout`
- `check_target_wrapper`
- `check_task_counters`
- `check_token`
- `check_token_repo_scope`
- `check_zone_waits`
- `cli_version`
- `cmd_alert_ack`
- `cmd_doctor`
- `isolation_smoke`
- `live_smoke`
- `preflight_checks`
- `recovery_check`
- `sweep_orphan_artifact_branches`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/projects.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/runner.py`, `orchestrator/version.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_version.py`

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

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/runner.py`, `tests/test_failure_classification.py`

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

**Импортируется:** `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/test_git_fixation.py`, `tests/test_step_autocommit.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/fsm.py

**Назначение:** Переходы автомата: advance по артефактам, approve/reject Оператора.

**Публичные функции:**
- `cmd_advance`
- `cmd_approve`
- `cmd_reject`
- `confirm_fixation`
- `guard_refuses`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_git_fixation.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_registry_gate.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_verifying_ceiling.py`, `tests/test_zones_approve.py`

## orchestrator/fsm_advance.py

**Назначение:** Обработчики `cmd_advance` — один на состояние (SPEC T091, декомпозиция

**Публичные функции:**
- `in_dev`
- `review`
- `spec_writing`
- `tests_writing`
- `verifying`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_capacity_gate.py`, `tests/test_zones_gate.py`

## orchestrator/fsm_autogate.py

**Назначение:** Автогейт acceptance по политике gates.yaml (ADR-0007, SPEC T066).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_source.py`, `orchestrator/budget.py`, `orchestrator/fixation.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `tests/test_fsm_autogate.py`, `tests/test_git_fixation.py`

## orchestrator/fsm_merge_gate.py

**Назначение:** Тело и внешний цикл гейта `merge_gate` (SPEC T052, T053, T082, T087):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_merge_gate_ci_wait.py`

## orchestrator/fsm_postmerge.py

**Назначение:** Побочные эффекты merge_gate после успешного merge: карта кодовой базы

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/fsm_merge_gate.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`

## orchestrator/gates.py

**Назначение:** Политика гейтов из `gates.yaml` (ADR-0007, SPEC T066).

**Публичные функции:**
- `policy`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/fsm_autogate.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`

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
- `diff_names`
- `diff_paths`
- `git`
- `has_no_remote`
- `head_sha`
- `in_repo`
- `is_clean`
- `list_branches`
- `ls_tree_files`
- `on_foreign_branch`
- `remote_branch_sha`
- `show`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/doctor.py`, `orchestrator/dry_run.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/pin.py`, `orchestrator/projects.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_capacity_gate.py`, `tests/test_catalog_new_race.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_doctor.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_retro.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_carpentry.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`, `tests/test_zones_gate.py`

## orchestrator/github_adapter.py

**Назначение:** GitHub-адаптер целевого `forge: github`: Draft-MR-флоу задачи (SPEC

**Публичные функции:**
- `ensure_draft_mr`
- `ensure_head_in_origin`
- `undraft_mr`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_github_adapter.py`, `tests/test_merge_gate_ci_wait.py`

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

**Импортируется:** `orchestrator/runner.py`

## orchestrator/lease.py

**Назначение:** Advisory-lease задачи: замок параллельных сессий CLI (SPEC T044).

**Публичные функции:**
- `acquire`
- `foreign_live_lease`
- `release`
- `release_any`
- `run_locked`
- `warn_foreign_live`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/cleanup.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `orchestrator/workspace.py`, `tests/test_lease.py`, `tests/test_session.py`

## orchestrator/liveness.py

**Назначение:** Возраст heartbeat и адресуемость pid — общие для lease/merge_lock/doctor.

**Публичные функции:**
- `group_kill_detail`
- `terminate_process_group`

**Импортирует:** —

**Импортируется:** `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `tests/test_doctor.py`, `tests/test_liveness.py`

## orchestrator/merge_lock.py

**Назначение:** Мьютекс merge-окна: один держатель на весь пульт (SPEC T053).

**Публичные функции:**
- `acquire`
- `release`
- `run_window`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/fsm_merge_gate.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`

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
- `cmd_pin_update`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`

## orchestrator/projects.py

**Назначение:** Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

**Публичные функции:**
- `artifact_repo_has_no_remote`
- `cmd_target_init`
- `init_artifact_repo`
- `init_project`
- `project_dir`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_multitarget.py`

## orchestrator/prune.py

**Назначение:** Команда `prune`: исполняет retention-политику docs/retention.md для

**Публичные функции:**
- `cmd_prune`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_prune.py`

## orchestrator/release.py

**Назначение:** Команда `release`: операторское снятие lease задачи (SPEC T062).

**Публичные функции:**
- `cmd_release`

**Импортирует:** `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_release.py`

## orchestrator/report.py

**Назначение:** Команда `report`: статический HTML-срез `state.db` + метрики гейтовой

**Публичные функции:**
- `cmd_report`
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

**Импортируется:** `orchestrator/budget.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/snapshot.py`, `tests/test_canary.py`, `tests/test_fsm_retro.py`, `tests/test_retro.py`

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

**Импортирует:** `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`

## orchestrator/role_prompt.py

**Назначение:** Миссия роли + бриф/ревью-пакет шага: сборка содержимого промпта, общего

**Публичные функции:**
- `mission_brief_package`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/review.py`

**Импортируется:** `orchestrator/runner.py`

## orchestrator/roles.py

**Назначение:** Карта исполнителей из roles.yaml: состав скилов роли читается кодом.

**Публичные функции:**
- `load`
- `skills`
- `token_slots`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/doctor.py`, `orchestrator/runner.py`, `tests/test_yaml_parsing.py`

## orchestrator/runner.py

**Назначение:** Запуск агента шага: промпт роли, окружение, попытки, исход, стоимость.

**Публичные функции:**
- `close_pump`
- `cmd_run`
- `git_identity`
- `role_cmd`
- `role_cwd`
- `role_env`
- `role_token`
- `run_agent_once`
- `spawn_agent`
- `step_role`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/roles.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/doctor.py`, `orchestrator/lease.py`, `orchestrator/pause.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/session.py

**Назначение:** Идентификатор сессии оркестратора — единая функция для всех команд

**Публичные функции:**
- `resolve_session_id`

**Импортирует:** —

**Импортируется:** `orchestrator/lease.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/store.py`, `tests/test_session.py`

## orchestrator/snapshot.py

**Назначение:** Снапшот артефактов задачи в `refs/artifacts/<id>` ЦЕЛЕВОГО при закрытии

**Публичные функции:**
- `pending`
- `publish_and_cleanup`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/fsm_merge_gate.py`

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

**Импортируется:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/doctor.py`, `orchestrator/pause.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `tests/test_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_step_cost.py`

## orchestrator/stack.py

**Назначение:** Манифест объявленного стека пульта (SPEC 01M1RDCAFENSW2VVAPECHCVGMM,

**Публичные функции:**
- `check_stack`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor.py`, `orchestrator/version.py`, `tests/test_invariants.py`, `tests/test_stack.py`

## orchestrator/store.py

**Назначение:** Состояние задач: БД, миграции схемы, журнал шагов, смена состояния.

**Публичные функции:**
- `ack_alert`
- `add_column`
- `alerts_older_than`
- `all_leases`
- `all_tasks`
- `archive_alert`
- `canary_baseline`
- `charge`
- `charge_estimate`
- `closed_external_tasks`
- `counter_targets`
- `create_schema`
- `db`
- `enable_wal`
- `get_alert`
- `get_task`
- `insert_alert`
- `insert_canary_run`
- `insert_lease`
- `insert_task`
- `journal`
- `latest_fixed_sha`
- `lease_row`
- `merge_lock_row`
- `migrate`
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
- `table_columns`
- `task_branch`
- `task_exists`
- `task_number`
- `task_steps`
- `task_target`
- `total_estimate`
- `total_spent`
- `update_lease`
- `update_lease_pgid`
- `update_task`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/session.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/alerts.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/doctor.py`, `orchestrator/dry_run.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/prune.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_canary.py`, `tests/test_capacity_gate.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_status_log.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_coldstart.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_dry_run.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_retro.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parallel_limit.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_program_spend_reseed.py`, `tests/test_prune.py`, `tests/test_release.py`, `tests/test_report.py`, `tests/test_retro.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_review_registry_gate.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stall_alerts.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_journal.py`, `tests/test_store_schema_migration_parity.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_verifying_ceiling.py`, `tests/test_workspace.py`, `tests/test_zone_lock.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/targets.py

**Назначение:** Декларация целевых проектов из targets.yaml: запись target'а читается кодом.

**Публичные функции:**
- `check`
- `load`
- `target`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/doctor.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/projects.py`, `orchestrator/retro_corpus.py`, `orchestrator/store.py`, `tests/test_github_adapter.py`, `tests/test_multitarget.py`

## orchestrator/version.py

**Назначение:** Команда `version`: пин CLI, фактическая версия, версия схемы артефактов

**Публичные функции:**
- `cmd_version`

**Импортирует:** `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/stack.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_version.py`

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

**Импортируется:** `orchestrator/amend.py`, `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/runner.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_amend.py`, `tests/test_answer_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget_invariants.py`, `tests/test_step_autocommit.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`

## orchestrator/yamlmini.py

**Назначение:** Подмножество YAML, которого достаточно системе: frontmatter и roles.yaml.

**Публичные функции:**
- `frontmatter`
- `mapping`
- `scalar`

**Импортирует:** —

**Импортируется:** `orchestrator/artifacts.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/gates.py`, `orchestrator/retro_corpus.py`, `orchestrator/roles.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_yaml_parsing.py`

## orchestrator/zone_lock.py

**Назначение:** Занятость зоны на старте кода — предусловие перед первым шагом роли

**Публичные функции:**
- `blocking_conflict`
- `cmd_zone_release`
- `cmd_zone_reorder`
- `queue_order`
- `queue_position`
- `refusal`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/doctor.py`, `orchestrator/runner.py`, `tests/test_zone_lock.py`

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
- `module_dotted_name`
- `parse_module`
- `render`

**Импортирует:** —

**Импортируется:** `tests/test_codebase_map.py`

## scripts/guard.py

**Назначение:** Guard: валидатор СТРУКТУРЫ артефактов задач (frontmatter + обязательные

**Публичные функции:**
- `acceptance_traceability_errors`
- `basic_frontmatter_errors`
- `check`
- `check_content`
- `count_test_methods`
- `escalation_status_errors`
- `has_redness_marker`
- `id_format_patterns`
- `id_format_sample_errors`
- `is_draft_lenient`
- `main`
- `module_docstring`
- `redness_marker_errors_from_files`
- `registry_errors`
- `registry_record_errors`
- `registry_records`
- `registry_table_rows`
- `requires_ac_markup`
- `requires_registry`
- `requires_split_assessment`
- `requires_zones`
- `review_evidence_errors`
- `scan_ac_content`
- `scan_acceptance_tests`
- `scan_id_format_samples`
- `scan_redness_markers`
- `schema_errors`
- `section_body`
- `spec_ac_errors`
- `spec_zones_errors`
- `split_assessment_errors`
- `split_signal_names`
- `traceability_errors_from_content`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/canary.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/retro.py`, `orchestrator/version.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_artifact_materialization.py`, `tests/test_fsm_autogate.py`, `tests/test_guard_artifact_branch_mode.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_review_registry_gate.py`, `tests/test_version.py`, `tests/test_yaml_parsing.py`

## tests/__init__.py

**Назначение:** нет docstring

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## tests/sandbox.py

**Назначение:** Общая тестовая песочница (SPEC T037, требование 1; SPEC T061 —

**Публичные функции:**
- `capture`
- `capture_new_task_id`
- `claude_only_popen`
- `claude_only_run`
- `disk_backed_ls_tree_files`
- `disk_backed_show`
- `fake_git`
- `fake_git_for`
- `network_guarded_real_run`
- `resilient_tmp_cleanup`
- `seed_developer_brief_fixtures`
- `sync_spec_from_worktree`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_canary.py`, `tests/test_capacity_gate.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_status_log.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_coldstart.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_doctor.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_done_branch_cleanup.py`, `tests/test_dry_run.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_retro.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parallel_limit.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_program_spend_reseed.py`, `tests/test_prune.py`, `tests/test_release.py`, `tests/test_report.py`, `tests/test_retro.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_sandbox.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stall_alerts.py`, `tests/test_step_cost.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_journal.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_workspace.py`, `tests/test_zone_lock.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## tests/test_acceptance.py

**Назначение:** Юнит-тесты orchestrator/acceptance.py::run_full_suite (ADR-0007,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_acceptance_tests_flow.py

**Назначение:** Тесты A4 — роль test_author, приёмочные тесты до кода (tasks/T023/SPEC.md).

**Публичные функции:**
- `version_stub_run`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

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
- `event`
- `tool_result_event`
- `tool_use_call`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_agent_prompt.py

**Назначение:** Тесты канала промпта роли (см. tasks/T017/SPEC.md, требование 4).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_amend.py

**Назначение:** Юнит-тесты orchestrator/amend.py (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/amend.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`

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

## tests/test_artifact_materialization.py

**Назначение:** Юнит-тесты SPEC 01M1NKTF173WV5CPDZ1C3WW69K: материализация `tasks/<id>/`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_auto_cycle.py

**Назначение:** Тесты команды `auto` — цикла до ближайшего гейта (см. tasks/T014/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_canary.py

**Назначение:** Юнит-тесты `orchestrator/canary.py` v2 (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ;

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_capacity_gate.py

**Назначение:** Юнит-тесты гейта ёмкости diff снимка — fail-closed на сбое git

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_cas_set_state.py

**Назначение:** Юнит-тесты `orchestrator.store.set_state` (SPEC T050).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_new_race.py

**Назначение:** Регресс-тест на замечание major REVIEW T048 итерации 2:

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_status_log.py

**Назначение:** Юнит-тесты `orchestrator.catalog.cmd_log`/`cmd_status` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_checkpoint_external_step_artifacts.py

**Назначение:** Юнит-тесты `checkpoint._commit_external_step_artifacts` (SPEC T094,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_codebase_map.py

**Назначение:** Юнит-тесты функций scripts/codebase_map.py (tasks/T027/SPEC.md).

**Публичные функции:**
- `parse`

**Импортирует:** `scripts/codebase_map.py`

**Импортируется:** —

## tests/test_coldstart.py

**Назначение:** Юнит-тесты наблюдаемого мира холодного старта (orchestrator/coldstart.py,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/catalog.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_diff_not_collected_alerts.py

**Назначение:** Юнит-тесты новых функций tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doctor.py

**Назначение:** Тесты doctor: pre-flight, recovery-сверка, сироты, alerts, смоуки

**Публичные функции:**
- `result_event`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doctor_canary_pool.py

**Назначение:** Юнит-тесты `doctor.check_role_log_pool_leak`/`check_token_repo_scope`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_doctor_fix_ignored_artifacts.py

**Назначение:** Юнит-тесты `doctor._fix_ignored_artifact_files`/`doctor --fix` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_fsm_autogate.py

**Назначение:** Юнит-тесты условия «а» `fsm_autogate._autogate_conditions` — чтение

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_source.py`, `orchestrator/budget.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gitcmd.py`, `orchestrator/workspace.py`, `scripts/guard.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_map_regen.py

**Назначение:** Юнит-тесты регенерации/коммита карты кодовой базы на merge_gate

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_merge_gate_done_snapshot.py

**Назначение:** Юнит-тест снапшота закрытия на пути `done` (SPEC T094, требования

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_retro.py

**Назначение:** Юнит-тесты обвязки RETRO в orchestrator/fsm_postmerge.py (SPEC T043):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_gates.py

**Назначение:** Юнит-тесты orchestrator/gates.py: политика гейтов из gates.yaml

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gates.py`

**Импортируется:** —

## tests/test_git_fixation.py

**Назначение:** Git-первичка артефактов и approve-по-sha (tasks/T021/SPEC.md, критерии 1–7).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_answer.py`, `tests/test_step_autocommit.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`

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

## tests/test_guard_schema.py

**Назначение:** Тесты версии схемы артефактов (см. tasks/T017/SPEC.md, требование 3).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_split_signals.py

**Назначение:** Юнит-тесты сигналов «подозрения на большой объём» и проверки секции

**Публичные функции:**
- `spec_text`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_zones.py

**Назначение:** Юнит-тесты машиночитаемого поля `zones:` (01M1NKVPD2A79PQ6K0JVV1B2Q1,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_id_format_guard.py

**Назначение:** Юнит-тесты проверки образца формата идентификатора задачи в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `scripts/guard.py`, `tests/test_fsm_branch_correct_status_reads.py`

**Импортируется:** —

## tests/test_invariants.py

**Назначение:** Тесты системных инвариантов (см. tasks/T010/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_ci_status_kind_gate.py`, `tests/test_review_registry_gate.py`, `tests/test_verifying_ceiling.py`

## tests/test_kill_cleanup.py

**Назначение:** Тесты уборки хвостов убитой задачи (см. tasks/T008/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_merge_lock.py

**Назначение:** Юнит-тесты orchestrator/merge_lock.py (SPEC T053).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_new_argv_parsing.py

**Назначение:** Юнит-тесты `orchestrator.artel._parse_new_args` (tasks/T102/SPEC.md):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`

**Импортируется:** —

## tests/test_parallel_limit.py

**Назначение:** Юнит-тесты orchestrator/parallel_limit.py (SPEC T060).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/parallel_limit.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pause.py

**Назначение:** Юнит-тесты orchestrator/pause.py (SPEC T070).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/pause.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pause_now.py

**Назначение:** Юнит-тесты `orchestrator.pause.cmd_pause_now` (SPEC T074).

**Публичные функции:**
- `dead_pid`
- `spawn_sleep_process`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/pause.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_program_spend_reseed.py

**Назначение:** Юнит-тесты пересева программного расхода из RETRO (orchestrator/budget.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_prune.py

**Назначение:** Юнит-тесты `orchestrator/prune.py` и опорных функций `store.py`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/prune.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_release.py

**Назначение:** Юнит-тесты orchestrator/release.py (SPEC T062).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/release.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/artifacts.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_review_package.py

**Назначение:** Тесты ревью-пакета — входа ревьювера (см. tasks/T011/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_review_registry_gate.py

**Назначение:** Юнит-тесты гейта «Реестр замечаний» в `orchestrator/fsm_advance.py::

**Публичные функции:**
- `row`

**Импортирует:** `orchestrator/fsm.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/test_invariants.py`

**Импортируется:** —

## tests/test_role_bash_guard.py

**Назначение:** Сторож Bash-команд роли (`docs/reference/role-home/claude/hooks/

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## tests/test_sandbox.py

**Назначение:** Юнит-тесты перехвата сетевых git-команд `tests/sandbox.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `tests/sandbox.py`

**Импортируется:** —

## tests/test_session.py

**Назначение:** Юнит-тесты orchestrator/session.py (SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/lease.py`, `orchestrator/session.py`

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
- `event`
- `result_event`
- `timeout_then_killed_proc`
- `tool_use_event`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_step_refixation.py

**Назначение:** Юнит-тесты перефиксации sha на пути отклонённого перехода FSM (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/test_git_fixation.py`

**Импортируется:** —

## tests/test_store_db_connection_close.py

**Назначение:** Юнит-тесты закрытия соединений `store.db()` (tasks/T090/SPEC.md,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_store_journal.py

**Назначение:** Юнит-тесты `orchestrator.store.journal` (SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/version.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_workspace.py

**Назначение:** Юнит-тесты orchestrator/workspace.py: git worktree задачи в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_yaml_parsing.py

**Назначение:** Тесты разбора YAML и карты ролей (см. tasks/T017/SPEC.md, требования 1–2).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifacts.py`, `orchestrator/config.py`, `orchestrator/roles.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_zone_lock.py

**Назначение:** Юнит-тесты orchestrator/zone_lock.py (SPEC 01M1P9QAG65GVF69YJEV0V18D9).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

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
