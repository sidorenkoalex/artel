---
built_at_sha: 78a80dd034bc47c9240351f2f43dcff8f37f5b7a
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
- `drop_from_code_copy`
- `failed_test_lines`
- `full_suite`
- `materialize_files`
- `materialize_from_branch`
- `plank_in_code_copy`
- `run`
- `run_digest`
- `run_full_suite`
- `run_plank`
- `run_summary_line`
- `summary`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/artifact_branch.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/stack.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/notes.py`, `orchestrator/plank_run.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_acceptance.py`, `tests/test_acceptance_collect.py`, `tests/test_acceptance_pycache.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_branch_freshness_gate.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_transitions.py`, `tests/test_model_sets.py`, `tests/test_plan_appendix.py`, `tests/test_plank_run_edges.py`, `tests/test_pull.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`

## orchestrator/advance_gates/__init__.py

**Назначение:** Гейты переходов `orchestrator/fsm_advance.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## orchestrator/advance_gates/_base.py

**Назначение:** Каркас гейтов `_run_gates` и общий тип исхода `GateRefusal` (SPEC R2

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/store.py`

**Импортируется:** `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/fsm_advance.py`, `tests/test_docs_dir_layout.py`

## orchestrator/advance_gates/acceptance.py

**Назначение:** `_acceptance_lock_refuses`, `_acceptance_run_refuses` (SPEC

**Публичные функции:**
- `blob_sha256`
- `long_lived_manifest`
- `long_lived_manifest_rel`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_review_long_lived_exclude.py`

## orchestrator/advance_gates/capacity.py

**Назначение:** Семейство гейта ёмкости diff снимка `_capacity_gate` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `tests/test_capacity_gate_map.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package_map.py`

## orchestrator/advance_gates/mandate.py

**Назначение:** Строка мандата Оператора: один разбор на все три места и проверка

**Публичные функции:**
- `elements`
- `in_weakening_scope`
- `refusals`

**Импортирует:** `orchestrator/gitcmd.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/answer.py`, `tests/test_answer_mandate.py`, `tests/test_canary_synthetic_answer.py`

## orchestrator/advance_gates/plan_appendix.py

**Назначение:** Гейт применимости приложений PLAN на выходе `in_dev` (SPEC

**Публичные функции:**
- `git_apply`

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_plan_appendix.py`

## orchestrator/advance_gates/review.py

**Назначение:** Семейство гейтов вокруг вердикта ревьювера — `_review_escalation_sha_gate`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm_advance.py`

## orchestrator/advance_gates/test_integrity.py

**Назначение:** Узел сравнения `tests/` ветки задачи с базой и два гейта на нём — гейт

**Публичные функции:**
- `assertion_observation`
- `findings`
- `merge_gate_escalates`
- `refusal_detail`
- `uncovered`

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/review.py`, `scripts/test_rule_stats.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_answer_mandate.py`, `tests/test_invariants.py`, `tests/test_test_integrity_gate.py`

## orchestrator/advance_gates/tests_writing.py

**Назначение:** `_tests_writing_*`, `_origin_push_gate`, `_registry_gate`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifacts.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`

## orchestrator/advance_gates/zones.py

**Назначение:** Семейство гейта зон `_zones_gate` и его прямые помощники (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/auto.py`, `orchestrator/fsm_advance.py`, `tests/test_answer_mandate.py`, `tests/test_auto_cycle.py`, `tests/test_protected_test_settings.py`, `tests/test_zones_gate.py`

## orchestrator/agent_log.py

**Назначение:** Наблюдаемость шага: файлы логов прогонов и перекачка вывода агента.

**Публичные функции:**
- `environment_fingerprint`
- `last_agent_log`
- `log_tail`
- `new_agent_log`
- `render_agent_line`
- `step_friction`
- `stream_to_log`
- `tee_lines`

**Импортирует:** `orchestrator/config.py`, `orchestrator/spend.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/auto.py`, `orchestrator/pause.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_failure_cli_isolation.py`, `tests/test_agent_log.py`, `tests/test_auto_cycle.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_kill_cleanup.py`, `tests/test_pause_now.py`, `tests/test_providers_codex.py`, `tests/test_report.py`, `tests/test_step_cost.py`

## orchestrator/alerts.py

**Назначение:** Таблица alerts: несущий носитель порогов/инцидентов/триггеров (A3,

**Публичные функции:**
- `ack`
- `auto_ack`
- `bulk_ack_selection`
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

**Импортируется:** `orchestrator/amend.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/failure_classification.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `orchestrator/pull.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_auto_cycle.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_coldstart.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`, `tests/test_prune.py`, `tests/test_runner_wave_breaker.py`, `tests/test_stall_alerts.py`, `tests/test_token_rate_divergence.py`

## orchestrator/amend.py

**Назначение:** Команда `amend-tests`: штатная правка зафиксированной планки приёмки

**Публичные функции:**
- `cmd_amend_tests`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`

## orchestrator/answer.py

**Назначение:** Команда `answer`: канал ответа Оператора на эскалацию (SPEC T075,

**Публичные функции:**
- `cmd_answer`
- `cmd_zones_extend`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_answer.py`, `tests/test_answer_mandate.py`, `tests/test_docs_ref_deleted_refusal.py`

## orchestrator/artel.py

**Назначение:** Артель, Фаза 0 — FSM-оркестратор (CLI).

**Публичные функции:**
- `main`

**Импортирует:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/docs_fetch.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/plank_run.py`, `orchestrator/pool_seal.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/venv.py`, `orchestrator/version.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`

**Импортируется:** `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_artel_bootstrap.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_canary_sets.py`, `tests/test_canary_template_flag.py`, `tests/test_detached_cycle.py`, `tests/test_doc_commit.py`, `tests/test_invariants.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_main_ci_line.py`, `tests/test_models.py`, `tests/test_new_argv_parsing.py`, `tests/test_observation_edges.py`, `tests/test_task_model_set_units.py`

## orchestrator/artifact_branch.py

**Назначение:** Ссылка документов задачи `refs/artifacts/<id>` в репозитории задачи —

**Публичные функции:**
- `append_passport_line`
- `branch_name`
- `commit_change`
- `commit_files`
- `diff_names`
- `docs_dir`
- `docs_root`
- `fetch_all_from_origin`
- `fetch_from_origin`
- `git`
- `ls_tree`
- `materialize_task_dir`
- `on_foreign_rev`
- `origin_sync_refusal`
- `push`
- `read_tree`
- `ref_head`
- `repo_for_target`
- `rev_sha`
- `send_pending`
- `show`
- `task_repo`
- `write_commit`

**Импортирует:** `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/plank_run.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_division_parent_cleanup.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_fetch_edges.py`, `tests/test_doctor.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_git_fixation.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_plan_appendix.py`, `tests/test_pull.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_timeout_checkpoint.py`, `tests/test_zones_approve.py`

## orchestrator/artifact_cleanup.py

**Назначение:** Команда `artifact-branches-cleanup [--execute]`: уборка веток

**Публичные функции:**
- `cmd_artifact_branches_cleanup`

**Импортирует:** `orchestrator/gitcmd.py`

**Импортируется:** `orchestrator/artel.py`

## orchestrator/artifact_source.py

**Назначение:** Ветка-источник `tasks/<id>/` живой задачи — общий резолвер (SPEC T094,

**Публичные функции:**
- `resolve`

**Импортирует:** `orchestrator/artifact_branch.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_long_lived.py`

## orchestrator/artifacts.py

**Назначение:** Чтение артефактов задачи: frontmatter и свежесть вердикта ревьювера.

**Публичные функции:**
- `fresh_verdict_iteration`
- `frontmatter`

**Импортирует:** `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `tests/test_review_freshness.py`, `tests/test_yaml_parsing.py`

## orchestrator/auto.py

**Назначение:** Цикл `auto`: advance до шага роли, затем — если роль ещё не закончила — run.

**Публичные функции:**
- `auto_stop`
- `auto_stop_advice`
- `cmd_auto`

**Импортирует:** `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/models.py`, `orchestrator/pause.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/advance_gates/review.py`, `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_analyst_role.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_git_fixation.py`, `tests/test_plan_appendix.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_runner_model_preflight.py`, `tests/test_stall_alerts.py`

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

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/codebase_map.py`

**Импортируется:** `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`, `tests/test_advance_refusal_history.py`, `tests/test_answer_branch_reads.py`, `tests/test_auto_cycle.py`, `tests/test_brief.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_long_lived_manifest.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_role_prompt_test_author_mission.py`

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
- `journal_warning_once`
- `recommended_budget_usd`
- `reseed_program_spend`
- `spec_budget`
- `spent_with_estimate`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/retro.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/review.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/runner.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_budget_calibration_table.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_doctor.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_program_spend_reseed.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_zone_line_parse.py`

## orchestrator/canary.py

**Назначение:** Команда `canary`: синтетический прогон конвейера, v2 (SPEC

**Публичные функции:**
- `cmd_canary`
- `merges_since_last_green_run`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `orchestrator/providers/codex.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary_drive.py`, `orchestrator/doctor/__init__.py`, `orchestrator/pin.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_canary.py`, `tests/test_canary_acceptance_reason.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_codex_clone_auth.py`, `tests/test_canary_drive.py`, `tests/test_canary_profile_safety.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_canary_template_flag.py`, `tests/test_doctor.py`, `tests/test_parent_task_division.py`

## orchestrator/canary_drive.py

**Назначение:** Вход ведения учебной задачи канарейки кодом проверяемого коммита (SPEC

**Публичные функции:**
- `build_result`
- `drive`
- `main`
- `write_result`

**Импортирует:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/providers/codex.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `tests/test_canary_drive.py`

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

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/liveness.py`, `orchestrator/merge_queue.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `orchestrator/retro.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/fsm.py`, `tests/sandbox.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer_gate.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_pin_divergence.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_tz_zones_parsing.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`, `tests/test_models_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parent_task_division.py`, `tests/test_pause_now.py`, `tests/test_plan_appendix.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_slugify.py`, `tests/test_spec_budget.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_step_cost.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_workspace.py`, `tests/test_zone_line_parse.py`

## orchestrator/checkpoint.py

**Назначение:** WIP-чекпоинты рабочего дерева задачи: таймаут шага (SPEC T041),

**Публичные функции:**
- `commit_abnormal_checkpoint`
- `commit_pause_now_checkpoint`
- `commit_pull_checkpoint`
- `commit_step_artifacts`
- `commit_success_checkpoint`
- `commit_timeout_checkpoint`
- `harvest_code_copy_docs`
- `pult_commit_failed_paths`
- `restore_out_of_bounds_deletions`
- `task_dir_zone`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/fsm.py`, `orchestrator/pause.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_artifact_materialization.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_stray_acceptance_files.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_pause_now.py`, `tests/test_plank_run_edges.py`, `tests/test_role_commit_by_pult.py`, `tests/test_step_autocommit.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/ci.py

**Назначение:** Статус CI головного коммита ветки задачи — условие merge (SPEC T017, 6).

**Публичные функции:**
- `branch_status`
- `check_finished`
- `check_run_workflow_run`
- `check_runs`
- `check_runs_page`
- `failed_check_names`
- `find_run_id`
- `first_parent_line`
- `gh`
- `head_sha`
- `main_line_status`
- `red_status_sha`
- `rerun_started`
- `run_list`
- `status_kind`
- `stuck_check_ids`
- `trigger_rerun`
- `verifying_is_red`
- `verifying_status`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `scripts/ci_push_class.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/auto.py`, `orchestrator/ci_rerun.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/pin.py`, `orchestrator/watch.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_acceptance.py`, `tests/test_auto_cycle.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_invariants.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_pin.py`, `tests/test_plan_appendix.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_verifying_ceiling.py`

## orchestrator/ci_rerun.py

**Назначение:** Команда `ci-rerun`: повтор упавшего CI ветки задачи в `verifying`

**Публичные функции:**
- `cmd_ci_rerun`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/fsm.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_stuck_check_run.py`

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

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/retro.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_artifact_ref_sync.py`, `tests/test_detached_cycle.py`, `tests/test_division_parent_cleanup.py`, `tests/test_done_branch_cleanup.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_multitarget_invariants.py`, `tests/test_retro.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_task_id_prefix_regression.py`

## orchestrator/coldstart.py

**Назначение:** Наблюдаемый мир для холодного старта пульта (SPEC T049, ADR-0005 п.5).

**Публичные функции:**
- `observed_max_task_number`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/doctor/__init__.py`, `orchestrator/store.py`, `tests/test_coldstart.py`

## orchestrator/config.py

**Назначение:** Пути и константы оркестратора — один адрес на весь пакет.

**Публичные функции:**
- `is_protected_path`

**Импортирует:** —

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/amend.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/context_package.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/parallel_limit.py`, `orchestrator/pin.py`, `orchestrator/plank_run.py`, `orchestrator/pool_seal.py`, `orchestrator/projects.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/schema.py`, `orchestrator/session.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/venv.py`, `orchestrator/version.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/ci_protected_paths.py`, `scripts/guard.py`, `scripts/test_rule_stats.py`, `tests/sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, `tests/test_acceptance.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_artel_bootstrap.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_calibration_table.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_codex_clone_auth.py`, `tests/test_canary_drive.py`, `tests/test_canary_profile_safety.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_canary_template_flag.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_catalog_fixture.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_ci_protected_paths.py`, `tests/test_ci_status.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_codebase_map.py`, `tests/test_codex_login_shell_path.py`, `tests/test_coldstart.py`, `tests/test_conftest_role_guard.py`, `tests/test_cycle_hint.py`, `tests/test_detached_cycle.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doc_commit.py`, `tests/test_doc_commit_held_base.py`, `tests/test_doc_commit_suite_gate.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_done_branch_cleanup.py`, `tests/test_draft_mr_commits.py`, `tests/test_dry_run.py`, `tests/test_failure_classification.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_fsm_retro.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_division_section.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_new_argv_parsing.py`, `tests/test_notes.py`, `tests/test_notes_apply.py`, `tests/test_notes_row_format.py`, `tests/test_observation_edges.py`, `tests/test_pair_suspension_units.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_pin_update_stale_cycles.py`, `tests/test_plan_appendix.py`, `tests/test_plank_run_edges.py`, `tests/test_program_spend_reseed.py`, `tests/test_protected_paths_gate.py`, `tests/test_protected_test_settings.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_release.py`, `tests/test_repo_context.py`, `tests/test_report.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_role_commit_by_pult.py`, `tests/test_roles_map_fixture.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_environment.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_session.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stack.py`, `tests/test_stack_codex_section.py`, `tests/test_stack_optional_tools.py`, `tests/test_stack_parity_table.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_stale_cycles_start_precision.py`, `tests/test_stall_alerts.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_store_journal.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_rule_stats.py`, `tests/test_timeout_checkpoint.py`, `tests/test_token_rate_divergence.py`, `tests/test_verifying_ceiling.py`, `tests/test_version.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/context_package.py

**Назначение:** Опись компонентов и дисциплина частей контекстных пакетов — общий слой

**Публичные функции:**
- `discipline`
- `render_component`
- `sha256_of`
- `split_into_parts`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/brief.py`, `orchestrator/review.py`, `tests/test_brief.py`, `tests/test_review_package.py`

## orchestrator/cycle_hint.py

**Назначение:** Подсказка запуска цикла `run`/`auto` (SPEC 01M3XTFJCC5TG63FHW907GQM4D).

**Публичные функции:**
- `cycle_command`
- `launch_hint`
- `launch_text`

**Импортирует:** `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci_rerun.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `tests/test_cycle_hint.py`, `tests/test_pin_update_stale_cycles.py`

## orchestrator/docs_fetch.py

**Назначение:** Команда `docs <id> [файл]` / `docs --fetch-all`: документы задачи из

**Публичные функции:**
- `cmd_docs`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/artel.py`

## orchestrator/doctor/__init__.py

**Назначение:** doctor: pre-flight, recovery-сверка, сироты, живой и офлайн-смоук CLI

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/canary.py`, `orchestrator/ci.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/doctor/artifact_branches.py`, `orchestrator/doctor/auto_ack.py`, `orchestrator/doctor/branch_freshness.py`, `orchestrator/doctor/canary_pool.py`, `orchestrator/doctor/canary_sets.py`, `orchestrator/doctor/cli.py`, `orchestrator/doctor/git_hooks.py`, `orchestrator/doctor/hung_test_watchdog.py`, `orchestrator/doctor/ignored_artifacts.py`, `orchestrator/doctor/isolation.py`, `orchestrator/doctor/lease_alerts.py`, `orchestrator/doctor/leases.py`, `orchestrator/doctor/live_smoke.py`, `orchestrator/doctor/main_ci.py`, `orchestrator/doctor/map_growth.py`, `orchestrator/doctor/misc_checks.py`, `orchestrator/doctor/model_catalog.py`, `orchestrator/doctor/model_tariffs.py`, `orchestrator/doctor/orphans.py`, `orchestrator/doctor/preflight.py`, `orchestrator/doctor/recovery.py`, `orchestrator/doctor/root_pin.py`, `orchestrator/doctor/stale_cycles.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/liveness.py`, `orchestrator/merge_lock.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/pool_seal.py`, `orchestrator/projects.py`, `orchestrator/providers/codex.py`, `orchestrator/repo_context.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`

**Импортируется:** —

## orchestrator/doctor/artifact_branches.py

**Назначение:** Пакет orchestrator/doctor -- сверка ссылок документов задач

**Публичные функции:**
- `check_artifact_ref_sync`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/auto_ack.py

**Назначение:** Пакет orchestrator/doctor -- авто-ack снятых incident-условий (tasks/T035).

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/branch_freshness.py

**Назначение:** Пакет orchestrator/doctor -- свежесть ветки активной задачи относительно main.

**Публичные функции:**
- `check_branch_freshness`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/canary_pool.py

**Назначение:** Пакет orchestrator/doctor -- изоляция пула канарейки от ролей и охват токена.

**Публичные функции:**
- `check_canary_pool_drift`
- `check_canary_trigger`
- `check_role_log_pool_leak`
- `check_token_repo_scope`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/canary_sets.py

**Назначение:** Согласованность наборов ролей канарейки (SPEC

**Публичные функции:**
- `check_canary_sets`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/cli.py

**Назначение:** Пакет orchestrator/doctor -- команда doctor: all_checks, cmd_doctor, cmd_alert_ack, cmd_alert_ack_bulk.

**Публичные функции:**
- `all_checks`
- `cmd_alert_ack`
- `cmd_alert_ack_bulk`
- `cmd_doctor`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/git_hooks.py

**Назначение:** Пакет orchestrator/doctor -- git-хуки защиты main главной копии.

**Публичные функции:**
- `check_git_hooks`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/hung_test_watchdog.py

**Назначение:** Пакет orchestrator/doctor -- сторож зависших прогонов тестов и ожидания зон.

**Публичные функции:**
- `check_hung_test_runs`
- `check_zone_waits`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/ignored_artifacts.py

**Назначение:** Пакет orchestrator/doctor -- уборка игнорируемых файлов ссылок документов задач.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/isolation.py

**Назначение:** Пакет orchestrator/doctor -- офлайн-смоук изоляции project-/user-слоя.

**Публичные функции:**
- `check_foreign_provider_secrets`
- `codex_isolation_smoke`
- `isolation_smoke`
- `provider_isolation_smokes`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/lease_alerts.py

**Назначение:** Пакет orchestrator/doctor -- разбор live-условия алертов мёртвого lease/merge_lock.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/leases.py

**Назначение:** Пакет orchestrator/doctor -- lease с мёртвым pid, мьютекс merge, рекон осиротевшего шага.

**Публичные функции:**
- `check_leases`
- `check_merge_lock`
- `check_merge_queue`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/live_smoke.py

**Назначение:** Пакет orchestrator/doctor -- живой смоук CLI.

**Публичные функции:**
- `live_smoke`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/main_ci.py

**Назначение:** Пакет orchestrator/doctor -- цвет CI main артели (SPEC

**Публичные функции:**
- `check_main_ci`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/map_growth.py

**Назначение:** Пакет orchestrator/doctor -- наблюдатель роста карты кодовой базы.

**Публичные функции:**
- `check_map_growth`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/misc_checks.py

**Назначение:** Пакет orchestrator/doctor -- разрозненные проверки: бэкап, счётчики, base-branch.

**Публичные функции:**
- `check_backup_age`
- `check_base_branch`
- `check_pending_notes`
- `check_task_counters`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/model_catalog.py

**Назначение:** Проверки каталога моделей и локального слоя (SPEC

**Публичные функции:**
- `check_models_catalog`
- `check_models_local`
- `check_role_models`
- `fix_models_local`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/model_tariffs.py

**Назначение:** Проверки действующего тарифа моделей (SPEC 01M300A14KRHCFB0DQXVCBJEKF,

**Публичные функции:**
- `check_model_tariff_freshness`
- `check_model_tariff_vs_model_change`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/orphans.py

**Назначение:** Пакет orchestrator/doctor -- сироты: каталоги без строки БД, ветки done/killed, worktree.

**Публичные функции:**
- `check_orphans`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/preflight.py

**Назначение:** Пакет orchestrator/doctor -- pre-flight проверки окружения шага.

**Публичные функции:**
- `agent_roles`
- `agent_roles_or_empty`
- `check_cli_found`
- `check_cli_version`
- `check_codex_chatgpt_auth`
- `check_codex_cli_found`
- `check_codex_cli_version`
- `check_codex_role_home`
- `check_disk_space`
- `check_git_identity`
- `check_model_provider_cli`
- `check_role_home_reference`
- `check_role_providers`
- `check_target_layout`
- `check_target_wrapper`
- `check_token`
- `cli_version`
- `codex_cli_version`
- `model_provider_mismatches`
- `preflight_checks`
- `provider_preflight_checks`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`, `tests/test_preflight_step_provider.py`

## orchestrator/doctor/recovery.py

**Назначение:** Пакет orchestrator/doctor -- recovery-сверка журнала БД со ссылками документов задач target'а.

**Публичные функции:**
- `recovery_check`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/root_pin.py

**Назначение:** Пакет orchestrator/doctor -- пин запущенной версии относительно main артели.

**Публичные функции:**
- `check_pin_unpushed`
- `check_root_pin`
- `fetch_origin_main_sha`
- `unpushed_commits`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/stale_cycles.py

**Назначение:** Пакет orchestrator/doctor -- циклы `auto`/`run` на коде старше пина.

**Публичные функции:**
- `check_stale_cycles`
- `process_start_time`
- `stale_cycle_lines`
- `stale_cycles`
- `start_interval`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/dry_run.py

**Назначение:** Команда `acceptance-dry-run`: сухой прогон приёмки — предпросмотр без

**Публичные функции:**
- `cmd_acceptance_dry_run`

**Импортирует:** `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_dry_run.py`

## orchestrator/failure_classification.py

**Назначение:** Классификация провалившейся попытки агента (SPEC T082, требования 1-2).

**Публичные функции:**
- `class_signature_text`
- `classify_attempt_failure`
- `required_cli_version`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/alerts.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_failure_classification.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_runner_model_preflight.py`

## orchestrator/fixation.py

**Назначение:** Hash-фиксация артефактов на переходах FSM (ADR-0003 п.15, п.17; tasks/T021).

**Публичные функции:**
- `approve_sha_hint`
- `check_integrity`
- `default_code_sha`
- `external_artifact_sha`
- `external_code_sha`
- `fix`
- `incident_refusal`
- `journal_drift`
- `legitimize`
- `read`
- `ref_drift`
- `refixate_after_rejected_transition`
- `stop_on_ref_drift`
- `unread_refusal`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_fsm_autogate.py`, `tests/test_git_fixation.py`, `tests/test_step_autocommit.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/fsm.py

**Назначение:** Переходы автомата: advance по артефактам, approve/reject Оператора.

**Публичные функции:**
- `cmd_advance`
- `cmd_approve`
- `cmd_reject`
- `cmd_set_models`
- `confirm_fixation`
- `guard_refuses`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/models.py`, `orchestrator/pause.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/ci_rerun.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/review.py`, `tests/sandbox.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_division_parent_cleanup.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_conflict_note.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_multitarget_invariants.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_review_freshness.py`, `tests/test_review_registry_gate.py`, `tests/test_role_commit_by_pult.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_verifying_ceiling.py`, `tests/test_zones_approve.py`

## orchestrator/fsm_advance.py

**Назначение:** Обработчики `cmd_advance` — один на состояние (SPEC T091, декомпозиция

**Публичные функции:**
- `in_dev`
- `review`
- `spec_writing`
- `tests_writing`
- `verifying`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/fsm.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_long_lived_transitions.py`, `tests/test_mutation_claim_gate.py`, `tests/test_protected_paths_gate.py`, `tests/test_test_integrity_gate.py`, `tests/test_zones_gate.py`

## orchestrator/fsm_autogate.py

**Назначение:** Автогейт acceptance по политике gates.yaml (ADR-0007, SPEC T066).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/models.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_git_fixation.py`, `tests/test_long_lived_transitions.py`

## orchestrator/fsm_merge_gate.py

**Назначение:** Тело и внешний цикл гейта `merge_gate` (SPEC T052, T053, T082, T087):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_artifact_ref_sync.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_gate_clock_isolation.py`, `tests/test_plan_appendix.py`, `tests/test_protected_paths_gate.py`, `tests/test_protected_test_settings.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_test_integrity_gate.py`

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

**Импортируется:** `orchestrator/fsm_autogate.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_fsm_autogate.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`

## orchestrator/gitcmd.py

**Назначение:** Вызовы git в корне репозитория, вопросы к ветке задачи и к произвольному

**Публичные функции:**
- `branch_exists`
- `branch_head_sha`
- `branch_merged`
- `carpentry`
- `check_ignore`
- `commit_committer_dates`
- `commit_exists`
- `commits_behind`
- `current_branch`
- `diff_base`
- `diff_base_source`
- `diff_name_status`
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
- `qualified_ref`
- `remote_branch_sha`
- `remote_ref_state`
- `show`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/doctor/__init__.py`, `orchestrator/dry_run.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/notes.py`, `orchestrator/pin.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_answer_mandate.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_catalog_new_race.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doctor.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_draft_mr_commits.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_retro.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_carpentry.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_pin.py`, `tests/test_plan_appendix.py`, `tests/test_protected_paths_gate.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_repo_context.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_test_integrity_gate.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`, `tests/test_zones_gate.py`

## orchestrator/github_adapter.py

**Назначение:** GitHub-адаптер целевого `forge: github`: Draft-MR-флоу задачи (SPEC

**Публичные функции:**
- `ensure_draft_mr`
- `ensure_head_in_origin`
- `undraft_mr`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend.py`, `tests/test_auto_cycle.py`, `tests/test_draft_mr_commits.py`, `tests/test_draft_mr_remote_base_args.py`, `tests/test_git_fixation.py`, `tests/test_github_adapter.py`, `tests/test_long_lived_transitions.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_protected_test_settings.py`

## orchestrator/idgen.py

**Назначение:** Генератор идентификатора задачи (SPEC T094, требование 2).

**Публичные функции:**
- `new_task_id`

**Импортирует:** —

**Импортируется:** `orchestrator/catalog.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_long_lived_manifest.py`

## orchestrator/keychain.py

**Назначение:** Чтение токенов из macOS keychain.

**Публичные функции:**
- `token`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`, `orchestrator/pool_seal.py`, `orchestrator/runner.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_codex_login_shell_path.py`, `tests/test_doctor_agent_roles.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`

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

**Импортируется:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `orchestrator/workspace.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_detached_cycle.py`, `tests/test_lease.py`, `tests/test_session.py`

## orchestrator/liveness.py

**Назначение:** Возраст heartbeat и адресуемость pid — общие для lease/merge_lock/doctor.

**Публичные функции:**
- `group_kill_detail`
- `terminate_process_group`

**Импортирует:** —

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_doctor.py`, `tests/test_liveness.py`, `tests/test_merge_lock.py`

## orchestrator/merge_lock.py

**Назначение:** Мьютекс merge-окна: один держатель на весь пульт (SPEC T053).

**Публичные функции:**
- `acquire`
- `release`
- `run_window`
- `touch_heartbeat`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/doctor/__init__.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/merge_queue.py`, `orchestrator/notes.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`

## orchestrator/merge_queue.py

**Назначение:** Очередь FIFO ожидания мьютекса merge-окна (SPEC

**Публичные функции:**
- `queue_wait_minutes`
- `wait_for_window`
- `wait_suffix`

**Импортирует:** `orchestrator/config.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/catalog.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_merge_queue.py`

## orchestrator/models.py

**Назначение:** Три слоя данных о моделях: каталог `models.yaml`, локальный слой

**Публичные функции:**
- `admitted_set_members`
- `autogate_refusal_blame`
- `catalog_model`
- `clean_run`
- `cmd_admit`
- `cmd_models`
- `cmd_pair_resume`
- `ensure_local_template`
- `expected_escalation_met`
- `layers_or_none`
- `live_task_set_providers`
- `load_canary_sets`
- `load_catalog`
- `load_local`
- `load_model_sets`
- `local_template_layer`
- `local_template_text`
- `members_text`
- `model_sets_path`
- `pair_admission`
- `pair_suspension_refusal`
- `record_review_verdict`
- `render_model_sets`
- `resolve_model`
- `resolve_role`
- `resolve_task_role`
- `set_admitted`
- `set_trial_reason`
- `summary_models`
- `suspend_on_autogate_refusal`
- `task_set_hint`
- `task_set_members`
- `task_set_name`
- `unclean_reason`
- `version_tuple`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/notes.py`, `orchestrator/roles.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/retro.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_agent_failure.py`, `tests/test_agent_prompt.py`, `tests/test_canary_sets.py`, `tests/test_catalog_fixture.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_canary_sets.py`, `tests/test_model_sets.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_pair_suspension_units.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_roles_map_fixture.py`, `tests/test_runner_role_model.py`, `tests/test_stack.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_task_model_set_units.py`, `tests/test_token_rate_divergence.py`, `tests/test_yaml_parsing.py`

## orchestrator/notes.py

**Назначение:** Команда `note`: строка в копилку/бэклог/очередь изолированным коммитом

**Публичные функции:**
- `cmd_doc_commit`
- `cmd_note`
- `doc_commit_content`
- `pending_notes`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/merge_lock.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor/__init__.py`, `orchestrator/models.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_doc_commit.py`, `tests/test_doc_commit_held_base.py`, `tests/test_doc_commit_suite_gate.py`, `tests/test_model_sets.py`, `tests/test_notes.py`, `tests/test_notes_apply.py`, `tests/test_notes_row_format.py`

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

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_auto_cycle.py`, `tests/test_pause.py`, `tests/test_pause_now.py`

## orchestrator/pin.py

**Назначение:** Команда `pin-update`: обновление пина запущенной версии (A7, Stage1,

**Публичные функции:**
- `cmd_pin_to`
- `cmd_pin_update`

**Импортирует:** `orchestrator/canary.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_pin.py`

## orchestrator/plank_run.py

**Назначение:** Команда `plank-run <id> [файл]`: штатный локальный прогон планки задачи в

**Публичные функции:**
- `cmd_plank_run`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`

## orchestrator/pool_seal.py

**Назначение:** Запечатанный пул шаблонов канарейки (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW).

**Публичные функции:**
- `cmd_pool_seal`
- `guids_path`
- `pool_drift_warning`
- `restore_pool_if_missing`
- `sealed_path`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/runner.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/doctor/__init__.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_canary.py`

## orchestrator/projects.py

**Назначение:** Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

**Публичные функции:**
- `cmd_target_init`
- `init_project`
- `project_dir`

**Импортирует:** `orchestrator/config.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor/__init__.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_artifact_ref_sync.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_multitarget.py`

## orchestrator/providers/__init__.py

**Назначение:** Реестр провайдеров исполнителя роли (SPEC

**Публичные функции:**
- `cli_tools`
- `default`
- `for_role`
- `get`
- `home_references`
- `name_for_role`
- `or_default`
- `role_providers`

**Импортирует:** `orchestrator/providers/base.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/roles.py`

**Импортируется:** —

## orchestrator/providers/base.py

**Назначение:** Базовый интерфейс провайдера исполнителя роли (SPEC

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** `orchestrator/providers/__init__.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`

## orchestrator/providers/claude.py

**Назначение:** Провайдер исполнителя роли `claude` (Claude Code CLI, headless).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/providers/base.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/stack.py`

**Импортируется:** `orchestrator/providers/__init__.py`, `tests/test_providers.py`

## orchestrator/providers/codex.py

**Назначение:** Провайдер исполнителя роли `codex` (OpenAI Codex CLI, `codex exec`).

**Публичные функции:**
- `codex_home_override`
- `set_codex_home_override`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/providers/base.py`, `orchestrator/runner.py`, `orchestrator/stack.py`

**Импортируется:** `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/doctor/__init__.py`, `orchestrator/providers/__init__.py`, `tests/test_canary_codex_clone_auth.py`, `tests/test_canary_drive.py`, `tests/test_canary_profile_safety.py`, `tests/test_codex_login_shell_path.py`, `tests/test_doctor_agent_roles.py`, `tests/test_providers_codex.py`, `tests/test_stack_codex_section.py`

## orchestrator/prune.py

**Назначение:** Команда `prune`: исполняет retention-политику docs/retention.md для

**Публичные функции:**
- `cmd_prune`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_prune.py`

## orchestrator/pull.py

**Назначение:** Исходы подтяжки главной ветки в ветку задачи (роадмап §3, фаза R,

**Публичные функции:**
- `evaluate`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/ci_push_class.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/fsm.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_stack_zones_pull_section.py`

## orchestrator/release.py

**Назначение:** Команда `release`: операторское снятие lease задачи (SPEC T062).

**Публичные функции:**
- `cmd_release`

**Импортирует:** `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_release.py`

## orchestrator/repo_context.py

**Назначение:** Репозиторный контекст target'а: одно место, где живёт «куда клон, какой

**Публичные функции:**
- `git`
- `path_or_none`
- `resolve`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/advance_gates/capacity.py`, `orchestrator/artifact_branch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/review.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_protected_paths_gate.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_repo_context.py`

## orchestrator/report.py

**Назначение:** Команда `report`: статический HTML-срез `state.db` + метрики гейтовой

**Публичные функции:**
- `cmd_report`
- `map_growth_calibration_median`
- `map_growth_cost_estimate`
- `map_growth_open_alerts`
- `map_size_table_rows`
- `token_rate_divergence`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/retro.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_report.py`, `tests/test_token_rate_divergence.py`

## orchestrator/retro.py

**Назначение:** Детерминированная генерация содержимого `docs/retro/<id>.md` (SPEC T043).

**Публичные функции:**
- `actor_costs`
- `build_done`
- `build_killed`
- `parse_total_cost`
- `retro_path`
- `retro_rel_path`
- `task_token_breakdown`
- `task_token_total`
- `token_breakdown_by_actor`
- `token_totals_by_actor`
- `tokens_detail_text`
- `tokens_text`
- `total_tokens_text`
- `usd_text`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/report.py`, `orchestrator/snapshot.py`, `tests/test_canary.py`, `tests/test_fsm_retro.py`, `tests/test_parent_task_division.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`

## orchestrator/retro_corpus.py

**Назначение:** Локальный кэш ретро-корпуса из локальных refs/artifacts/* (наполнить — `docs --fetch-all`)

**Публичные функции:**
- `read_cache`
- `rebuild_cache`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`, `orchestrator/yamlmini.py`

**Импортируется:** `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_retro_corpus.py`

## orchestrator/review.py

**Назначение:** Ревью-пакет: вход ревьювера собирает оркестратор, а не сам агент.

**Публичные функции:**
- `artifact_part`
- `artifact_sources_note`
- `artifact_text`
- `excluded_note`
- `git_diff_part`
- `own_commit_paths`
- `package_note`
- `previous_verdict_sha`
- `review_package`
- `snapshot_exclude`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/advance_gates/capacity.py`, `orchestrator/fsm.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_test_integrity_gate.py`

## orchestrator/role_prompt.py

**Назначение:** Миссия роли + бриф/ревью-пакет шага: сборка содержимого промпта, общего

**Публичные функции:**
- `docs_dir_note`
- `mission_brief_package`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/stack.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_docs_dir_layout.py`, `tests/test_long_lived_manifest.py`, `tests/test_role_prompt_test_author_mission.py`

## orchestrator/roles.py

**Назначение:** Карта исполнителей из roles.yaml: состав скилов роли читается кодом.

**Публичные функции:**
- `load`
- `model_tier`
- `provider`
- `skills`
- `token_slots`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/canary.py`, `orchestrator/doctor/__init__.py`, `orchestrator/models.py`, `orchestrator/providers/__init__.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_canary_sets.py`, `tests/test_codex_login_shell_path.py`, `tests/test_doctor_agent_roles.py`, `tests/test_model_sets.py`, `tests/test_models.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_roles_map_fixture.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_yaml_parsing.py`

## orchestrator/runner.py

**Назначение:** Запуск агента шага: промпт роли, окружение, попытки, исход, стоимость.

**Публичные функции:**
- `close_pump`
- `cmd_run`
- `declared_tool_path`
- `foreign_secret_env_names`
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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/models.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/roles.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/lease.py`, `orchestrator/notes.py`, `orchestrator/pause.py`, `orchestrator/pool_seal.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/review.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_codex_login_shell_path.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_environment.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/schema.py

**Назначение:** Схема БД и миграции: DDL, `migrate(conn)`, `add_column`/`table_columns`.

**Публичные функции:**
- `add_column`
- `create_schema`
- `migrate`
- `table_columns`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/store.py`, `tests/test_pair_suspension_units.py`, `tests/test_parent_task_division.py`, `tests/test_steps_task_id_index.py`

## orchestrator/session.py

**Назначение:** Идентификатор сессии оркестратора — единая функция для всех команд

**Публичные функции:**
- `resolve_session_id`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/cycle_hint.py`, `orchestrator/lease.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_detached_cycle.py`, `tests/test_observation_edges.py`, `tests/test_session.py`

## orchestrator/snapshot.py

**Назначение:** Коммит закрытия задачи (`done`/`killed`) — последний коммит RETRO в

**Публичные функции:**
- `closing_sha`
- `commit_closing`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_artifact_ref_sync.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_multitarget_invariants.py`

## orchestrator/spend.py

**Назначение:** Стоимость шага: разбор чисел, событие потока, учёт в spent_usd.

**Публичные функции:**
- `by_price_kind`
- `charge_missing_result`
- `charge_step`
- `check_rate_divergence`
- `cli_number`
- `cost_note`
- `journal_model`
- `json_number`
- `known_cost_breakdown`
- `known_cost_pairs`
- `model_tariff`
- `parse_cost_event`
- `parse_run_result`
- `partial_cost_usd`
- `partial_tokens_from_log`
- `rate_calibrated_at`
- `record_tariff`
- `role_tariff`
- `run_result_cost`
- `stream_usage_by_type`
- `tariff_cost_usd`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/doctor/__init__.py`, `orchestrator/pause.py`, `orchestrator/providers/claude.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/runner.py`, `scripts/guard.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_agent_log.py`, `tests/test_doctor.py`, `tests/test_model_tariffs.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_providers_codex.py`, `tests/test_runner_role_model.py`, `tests/test_step_cost.py`, `tests/test_task_model_set_units.py`, `tests/test_token_rate_divergence.py`

## orchestrator/stack.py

**Назначение:** Манифест объявленного стека пульта (SPEC 01M1RDCAFENSW2VVAPECHCVGMM,

**Публичные функции:**
- `check_stack`
- `demanded_optional_tools`
- `installed_cli_version`
- `model_cli_verdict`
- `model_providers`
- `pytest_python_executable`
- `python_version_string`
- `required_tools`
- `version_text`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/roles.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/doctor/__init__.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/version.py`, `scripts/guard.py`, `scripts/stack_ci.py`, `tests/sandbox.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_agent_failure.py`, `tests/test_agent_prompt.py`, `tests/test_artel_bootstrap.py`, `tests/test_git_hooks.py`, `tests/test_invariants.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_role_prompt_test_author_mission.py`, `tests/test_runner_model_preflight.py`, `tests/test_stack.py`, `tests/test_stack_ci.py`, `tests/test_stack_optional_tools.py`, `tests/test_task_model_set_units.py`

## orchestrator/store.py

**Назначение:** Состояние задач: БД, журнал шагов, смена состояния, запросы по областям.

**Публичные функции:**
- `ack_alert`
- `active_pair_suspension`
- `add_observation_tasks`
- `alerts_older_than`
- `alerts_since`
- `all_canary_runs`
- `all_leases`
- `all_steps`
- `all_tasks`
- `archive_alert`
- `canary_baseline`
- `charge`
- `charge_estimate`
- `counter_targets`
- `db`
- `delete_merge_queue_row`
- `dequeue_merge_wait`
- `disable_task_observation`
- `enable_wal`
- `enqueue_merge_wait`
- `get_alert`
- `get_task`
- `green_canary_runs`
- `insert_alert`
- `insert_canary_run`
- `insert_lease`
- `insert_pair_suspension`
- `insert_pair_verdict`
- `insert_task`
- `journal`
- `last_model_tariff`
- `last_pair_resume_mark`
- `latest_fixed_sha`
- `latest_green_canary_run`
- `lease_row`
- `matching_observation`
- `max_alert_id`
- `max_pair_verdict_id`
- `merge_lock_row`
- `merge_queue_rows`
- `next_task_number`
- `now`
- `observation`
- `observation_tasks`
- `observed_runs`
- `open_alert_exists`
- `open_alerts`
- `pair_verdicts_after`
- `peek_task_number`
- `record_fixation`
- `record_model_tariff`
- `record_observed_run`
- `refusal_history`
- `register_observation`
- `release_lease`
- `release_merge_lock`
- `remove_observation_tasks`
- `resolve_task_id`
- `resume_pair_suspension`
- `seed_task_counters`
- `session_observations`
- `set_canary_baseline`
- `set_merge_lock`
- `set_state`
- `steps_of_action`
- `stop_observation`
- `task_branch`
- `task_exists`
- `task_number`
- `task_steps`
- `task_steps_since`
- `task_target`
- `total_estimate`
- `total_spent`
- `touch_merge_queue_heartbeat`
- `touch_observation`
- `update_lease`
- `update_lease_pgid`
- `update_task`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/models.py`, `orchestrator/schema.py`, `orchestrator/session.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/alerts.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/cycle_hint.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/dry_run.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/plank_run.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/schema.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_drive.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_coldstart.py`, `tests/test_cycle_hint.py`, `tests/test_detached_cycle.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doc_commit.py`, `tests/test_doc_commit_held_base.py`, `tests/test_doc_commit_suite_gate.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_draft_mr_commits.py`, `tests/test_dry_run.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_retro.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`, `tests/test_model_sets.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_notes.py`, `tests/test_notes_apply.py`, `tests/test_observation_edges.py`, `tests/test_pair_suspension_units.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_pin_update_stale_cycles.py`, `tests/test_plan_appendix.py`, `tests/test_plank_run_edges.py`, `tests/test_program_spend_reseed.py`, `tests/test_protected_paths_gate.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_release.py`, `tests/test_report.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_review_registry_gate.py`, `tests/test_role_commit_by_pult.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stale_cycles_start_precision.py`, `tests/test_stall_alerts.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_steps_task_id_index.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_journal.py`, `tests/test_store_schema_migration_parity.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_test_integrity_gate.py`, `tests/test_timeout_checkpoint.py`, `tests/test_token_rate_divergence.py`, `tests/test_verifying_ceiling.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/targets.py

**Назначение:** Декларация целевых проектов из targets.yaml: запись target'а читается кодом.

**Публичные функции:**
- `check`
- `load`
- `target`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/projects.py`, `orchestrator/repo_context.py`, `orchestrator/retro_corpus.py`, `orchestrator/store.py`, `tests/test_github_adapter.py`, `tests/test_multitarget.py`

## orchestrator/venv.py

**Назначение:** Venv пульта: `.artel/venv`, создаётся идемпотентно средствами

**Публичные функции:**
- `cmd_venv_sync`
- `sync`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_venv.py`

## orchestrator/version.py

**Назначение:** Команда `version`: пин CLI, фактическая версия, версия схемы артефактов

**Публичные функции:**
- `cmd_version`

**Импортирует:** `orchestrator/config.py`, `orchestrator/stack.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_version.py`

## orchestrator/watch.py

**Назначение:** Команда `watch`: дозор событий журнала для сессии Оператора (SPEC

**Публичные функции:**
- `cmd_watch`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_watch.py`

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

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/artel.py`, `orchestrator/canary_drive.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/plank_run.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `tests/sandbox.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_branch_freshness_gate.py`, `tests/test_division_parent_cleanup.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_autogate.py`, `tests/test_kill_cleanup.py`, `tests/test_long_lived_transitions.py`, `tests/test_multitarget_invariants.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_role_commit_by_pult.py`, `tests/test_step_autocommit.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`

## orchestrator/yamlmini.py

**Назначение:** Подмножество YAML, которого достаточно системе: frontmatter и roles.yaml.

**Публичные функции:**
- `frontmatter`
- `mapping`
- `scalar`

**Импортирует:** —

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/review.py`, `orchestrator/amend.py`, `orchestrator/artifacts.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/gates.py`, `orchestrator/models.py`, `orchestrator/pull.py`, `orchestrator/retro_corpus.py`, `orchestrator/roles.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_canary_sets.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_model_sets.py`, `tests/test_roles_map_fixture.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_yaml_parsing.py`

## orchestrator/zone_lock.py

**Назначение:** Занятость зоны на старте кода — предусловие перед первым шагом роли

**Публичные функции:**
- `blocking_conflict`
- `claim`
- `claimed_but_not_started`
- `cmd_zone_release`
- `cmd_zone_reorder`
- `forecast_overlaps`
- `queue_order`
- `queue_position`
- `refusal`
- `release_claim`
- `task_zone_paths`
- `wait_enter_action`
- `wait_exit_action`
- `wait_minutes`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/runner.py`, `scripts/guard.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_auto_cycle.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`

## scripts/ci_protected_paths.py

**Назначение:** Сверка изменённых PR файлов со списком защищённых путей БАЗЫ сравнения —

**Публичные функции:**
- `base_protected_paths`
- `changed_files`
- `is_violation`
- `main`
- `protected_paths_from_source`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `tests/test_ci_protected_paths.py`, `tests/test_protected_test_settings.py`

## scripts/ci_push_class.py

**Назначение:** Классификатор класса пуша CI (ADR-0016) — вынесен из bash-логики job

**Публичные функции:**
- `classify`
- `is_doc_path`
- `main`

**Импортирует:** —

**Импортируется:** `orchestrator/ci.py`, `orchestrator/pull.py`, `tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py`, `tests/test_ci_push_class.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`

## scripts/codebase_map.py

**Назначение:** Codebase-map пульта: детерминированная карта модулей пакетов.

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
- `module_package_name`
- `parse_module`
- `project_for_brief`
- `render`
- `repo_root`

**Импортирует:** —

**Импортируется:** `orchestrator/brief.py`, `orchestrator/fsm_postmerge.py`, `tests/test_capacity_gate_map.py`, `tests/test_codebase_map.py`

## scripts/guard.py

**Назначение:** Guard: валидатор СТРУКТУРЫ артефактов задач (frontmatter + обязательные

**Публичные функции:**
- `acceptance_test_files`
- `acceptance_traceability_errors`
- `appendix_rename_header_error`
- `appendix_unprotected_path_error`
- `artifact_disk_read_errors_from_files`
- `changed_test_assertions`
- `check`
- `check_content`
- `ci_marker_wording_ok`
- `count_test_methods`
- `division_section_errors`
- `escalation_status_errors`
- `extraneous_task_root_files_in`
- `group_line_errors_from_files`
- `has_redness_marker`
- `id_format_patterns`
- `id_format_sample_errors`
- `indented_ac_marker_errors_from_files`
- `is_extraneous_acceptance_test_file`
- `is_extraneous_task_root_file`
- `is_long_lived_test_path`
- `long_lived_errors_from_files`
- `long_lived_path_prefix`
- `long_lived_plank_errors`
- `long_lived_sign_hits`
- `main`
- `mentioned_paths`
- `module_docstring`
- `parse_division_subsections`
- `parse_long_lived_manifest`
- `plan_appendices`
- `plank_file_group`
- `plank_has_group_lines`
- `protected_zones`
- `qualified_test_methods`
- `redness_marker_errors_from_files`
- `registry_errors`
- `registry_record_errors`
- `registry_records`
- `registry_table_rows`
- `render_long_lived_manifest`
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
- `spec_path_errors`
- `spec_unclassified_paths`
- `spec_zones_errors`
- `split_assessment_errors`
- `split_signal_names`
- `test_assertions`
- `test_functions_without_mutation_claim`
- `test_skip_markers`
- `traceability_errors_from_content`
- `unclassified_paths`
- `unclassified_paths_refusal`
- `zone_items`
- `zone_line_items`

**Импортирует:** `orchestrator/config.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/retro.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/version.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend_long_lived.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_artifact_materialization.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_guard_artifact_branch_mode.py`, `tests/test_guard_artifact_disk_read.py`, `tests/test_guard_division_section.py`, `tests/test_guard_extraneous_acceptance_files.py`, `tests/test_guard_mutation_claim.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_guard_test_ast.py`, `tests/test_guard_test_groups.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_plan_appendix.py`, `tests/test_protected_test_settings.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_review_registry_gate.py`, `tests/test_role_commit_by_pult.py`, `tests/test_test_integrity_gate.py`, `tests/test_version.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_line_parse.py`

## scripts/stack_ci.py

**Назначение:** CI-обвязка манифеста стека (01M1RDCCKBQMJ5G2K9ANJP059H, требования 1-3):

**Публичные функции:**
- `main`
- `minimum_python_version_string`

**Импортирует:** `orchestrator/stack.py`

**Импортируется:** —

## scripts/test_rule_stats.py

**Назначение:** Статистика правила «тестовый метод в tests/ меняется только с вопросом

**Публичные функции:**
- `classify`
- `groups`
- `journal`
- `main`
- `merged_tasks_touching_tests`
- `since_date`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/__init__.py

**Назначение:** нет docstring

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## tests/sandbox.py

**Назначение:** Общая тестовая песочница (SPEC T037, требование 1; SPEC T061 —

**Публичные функции:**
- `alias_docs_ref_to_branch`
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
- `make_project_repo`
- `network_guarded_real_run`
- `resilient_tmp_cleanup`
- `role_map_fixture`
- `seed_developer_brief_fixtures`
- `sync_spec_from_worktree`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/models.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, `tests/test_acceptance.py`, `tests/test_acceptance_collect.py`, `tests/test_acceptance_pycache.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_fixture.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_ci_rerun_command.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_codex_login_shell_path.py`, `tests/test_coldstart.py`, `tests/test_cycle_hint.py`, `tests/test_detached_cycle.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doc_commit.py`, `tests/test_doc_commit_held_base.py`, `tests/test_doc_commit_suite_gate.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_done_branch_cleanup.py`, `tests/test_draft_mr_commits.py`, `tests/test_dry_run.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_fsm_retro.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_schema.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_queue.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_notes.py`, `tests/test_notes_apply.py`, `tests/test_notes_row_format.py`, `tests/test_observation_edges.py`, `tests/test_pair_suspension_units.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_pin_update_stale_cycles.py`, `tests/test_plan_appendix.py`, `tests/test_program_spend_reseed.py`, `tests/test_protected_paths_gate.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_release.py`, `tests/test_repo_context.py`, `tests/test_report.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_role_commit_by_pult.py`, `tests/test_roles_map_fixture.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_sandbox.py`, `tests/test_session.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stack.py`, `tests/test_stack_optional_tools.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_stale_cycles_start_precision.py`, `tests/test_stall_alerts.py`, `tests/test_step_cost.py`, `tests/test_steps_task_id_index.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_journal.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_test_integrity_gate.py`, `tests/test_token_rate_divergence.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py

**Назначение:** Слой эфемерного клона канарейки из боевого слоя пульта, набор по

**Публичные функции:**
- `layer_text`
- `model_block`

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py

**Назначение:** Раздел `role_models:` локального слоя: модель одной роли мимо яруса —

**Публичные функции:**
- `layer_text`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py

**Назначение:** Автогейт читает обе группы файлов планки из веток задачи.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gates.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py

**Назначение:** Сводка и запись приёмки канарейки по результату процесса клона.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py

**Назначение:** Команда `models` показывает фактическую модель роли: столбец ролей по

**Публичные функции:**
- `catalog_text`
- `layer_text`
- `price_text`
- `roles_text`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py

**Назначение:** Признак шага роли и отказы команд для обоих провайдеров.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/answer.py`, `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/pool_seal.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py

**Назначение:** Main не краснеет незаметно: guard после снимка на гейте мержа, цвет CI

**Публичные функции:**
- `completed`
- `names_commit`
- `running`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py

**Назначение:** Изоляция дома Codex канарейки и сохранение дома обычной задачи.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/models.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py

**Назначение:** Публичная миграция пользовательских подключений guard-artel-bg.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py

**Назначение:** Публичный CLI наблюдения и управляемого фонового запуска.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py

**Назначение:** Подписочный профиль Codex канарейки на временном пульте.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py

**Назначение:** Коммит результата шага пультом: штатный коммит — норма, отказ git —

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py

**Назначение:** Миссии ролей не требуют от роли коммита кода; миссия developer сообщает,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`

**Импортируется:** —

## tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py

**Назначение:** Программа `scripts/test_rule_stats.py`: окно `--since`, четыре группы

**Публичные функции:**
- `group_blocks`
- `threshold_lines`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/config.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_test_rule_stats.py`

## tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py

**Назначение:** Эскалация разработчика через `PLAN.md status: escalate` пишет признак

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py

**Назначение:** Единый признак шага роли и закрытый по умолчанию отказ команд пульта.

**Публичные функции:**
- `dispatch`
- `new_seed`

**Импортирует:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/idgen.py`, `orchestrator/lease.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/pool_seal.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/store.py`, `orchestrator/venv.py`, `orchestrator/version.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py

**Назначение:** Подсказка запуска цикла называет полный порядок шагов наблюдения.

**Публичные функции:**
- `cycle_hint_module`
- `launch_hint`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py

**Назначение:** Наблюдение гейта неослабления тестов за утверждениями метода, сохранившего

**Публичные функции:**
- `ac1_sources`
- `ac2_sources`
- `delta_source`
- `identifiers`
- `seeded`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py

**Назначение:** Проверка CI, которую GitHub отдаёт «идущей» при известном исходе, и

**Публичные функции:**
- `answer`
- `check_runs_json`
- `green_check`
- `iso_ago`
- `names_age`
- `new_rng`
- `numbers_in`
- `pick_names`
- `random_sha`
- `stuck_outcome_constants`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py

**Назначение:** `pin-update` и `doctor` называют живые циклы `auto`/`run`, чей процесс

**Публичные функции:**
- `is_proc_path`
- `proc_table_hidden`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/pin.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py

**Назначение:** Удержанный `doc-commit` сверяется с базой сборки; `note --pending` и

**Публичные функции:**
- `run_command`
- `string_values`

**Импортирует:** `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py

**Назначение:** Прогоны pytest пульта отводят кеш байткода в отдельный временный каталог.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/stack.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py

**Назначение:** Обязательный артефакт шага роли: долгоживущий файл засчитывается test_author.

**Публичные функции:**
- `random_name`
- `random_task_id`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py

**Назначение:** Наборы моделей: защита `model_sets.yaml`, команда допуска пары `admit`,

**Публичные функции:**
- `model_sets_text`
- `summary`
- `verdict_of`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py

**Назначение:** Набор моделей задачи: `new --set`, модель, провайдер и стоимость шага с

**Публичные функции:**
- `model_sets_text`
- `result_event`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gates.py`, `orchestrator/models.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py

**Назначение:** Пробный период набора задачи, автоматическая приостановка пары набора,

**Публичные функции:**
- `full_suite_run`
- `model_sets_text`
- `result_event`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gates.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py

**Назначение:** Массовая форма `alert-ack --source <источник> --grep <подстрока> "<решение>" [--yes]`.

**Публичные функции:**
- `has_token`
- `new_seed`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py

**Назначение:** Черновик запроса на слияние сверяет ветку задачи с СВЕЖЕЙ удалённой базой.

**Публичные функции:**
- `git_subcommand`
- `new_seed`

**Импортирует:** `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py

**Назначение:** Отбор циклов на коде старше пина учитывает погрешность источника времени

**Публичные функции:**
- `argv_of`
- `is_lstart_call`
- `is_proc_path`
- `lstart_text`
- `proc_table_hidden`
- `sleep_until`
- `years_of`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/pin.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py

**Назначение:** Предполёт шага задачи с набором моделей: CLI и вход провайдера ШАГА

**Публичные функции:**
- `model_sets_text`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py

**Назначение:** Допуск набора сверяет роли сводки вне набора с боевыми моделями.

**Публичные функции:**
- `model_sets_text`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py

**Назначение:** Команда шага роли открывает каталог документов задачи на запись, а

**Публичные функции:**
- `add_dir_values`
- `real`

**Импортирует:** `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py

**Назначение:** Ссылка документов задачи живёт в репозитории её проекта (ADR-0021 п.3),

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/projects.py`, `orchestrator/repo_context.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py

**Назначение:** Перефиксирующие записи пульта не узаконивают сдвиг ссылки документов

**Публичные функции:**
- `incident_named`

**Импортирует:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/idgen.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_docs_ref_deleted_refusal.py`

## tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py

**Назначение:** Команда `plank-run`: штатный локальный прогон планки задачи в шаге роли.

**Публичные функции:**
- `is_pytest_call`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/role_prompt.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_plank_run_edges.py`

## tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py

**Назначение:** Шаг роли не удаляет отслеживаемые файлы вне путей, которые ей разрешено

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_plank_run_edges.py`

## tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py

**Назначение:** Артефактная ветка без особого статуса в CI: классификатор пуша не

**Публичные функции:** (нет)

**Импортирует:** `scripts/ci_push_class.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py

**Назначение:** Команда `artel.py artifact-branches-cleanup [--execute]` — уборка веток

**Публичные функции:**
- `new_seed`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py

**Назначение:** Команда `artel.py docs <id> [файл]` / `docs --fetch-all`, подсказка `show`

**Публичные функции:**
- `git_repo_of`
- `git_subcommand`
- `new_seed`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/retro_corpus.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_docs_fetch_edges.py`

## tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py

**Назначение:** `plank-run` под окружением роли проходит настоящий сторож роли `conftest.py`.

**Публичные функции:**
- `positionals`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py

**Назначение:** `amend-tests` убирает материализованный каталог задачи из рабочей копии

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/amend.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/projects.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py

**Назначение:** `python3 scripts/guard.py <путь>/SPEC.md` сверяет пути SPEC с зонами тем

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py

**Назначение:** `artel.py observe add|remove <obs>` с лишним позиционным аргументом

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py

**Назначение:** Заведение рабочего каталога роли берёт базу ветки fetch'ем, который не

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance.py

**Назначение:** Юнит-тесты orchestrator/acceptance.py::run_full_suite (ADR-0007,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance_collect.py

**Назначение:** Юнит-тесты `orchestrator/acceptance.py::collect` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance_pycache.py

**Назначение:** Юнит-тесты отведения кеша байткода прогонов pytest пульта

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance_tests_flow.py

**Назначение:** Тесты A4 — роль test_author, приёмочные тесты до кода (tasks/T023/SPEC.md).

**Публичные функции:**
- `version_stub_run`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_amend.py`, `tests/test_amend_remove.py`

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

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_agent_failure_cli_isolation.py`

## tests/test_agent_failure_cli_isolation.py

**Назначение:** Регрессия нестабильного `tests/test_agent_failure.py::CmdRunFailureTest::

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/agent_log.py`, `tests/test_agent_failure.py`

**Импортируется:** —

## tests/test_agent_log.py

**Назначение:** Тесты лога агента по ходу шага (см. tasks/T005/SPEC.md).

**Публичные функции:**
- `assistant_event`
- `tool_result_event`
- `tool_use_call`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_agent_prompt.py

**Назначение:** Тесты канала промпта роли (см. tasks/T017/SPEC.md, требование 4).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_alert_ack_bulk_parsing.py

**Назначение:** Юнит-тесты разбора и исхода массовой формы `alert-ack` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_amend_long_lived.py

**Назначение:** Юнит-тесты `amend-tests` для долгоживущих файлов задачи в `tests/`

**Публичные функции:**
- `edited_source`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/amend.py`, `orchestrator/artifact_branch.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/test_long_lived_transitions.py`

**Импортируется:** `tests/test_amend_remove.py`, `tests/test_review_long_lived_exclude.py`

## tests/test_amend_remove.py

**Назначение:** Юнит-тесты переноса удаления файла планки командой `amend-tests`

**Публичные функции:**
- `write_commit_ignoring_remove`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/amend.py`, `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend_long_lived.py`, `tests/test_long_lived_transitions.py`

**Импортируется:** —

## tests/test_analyst_role.py

**Назначение:** Тесты A5 — роль analyst: SPEC из свободного ТЗ Оператора (tasks/T025/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_answer.py

**Назначение:** Юнит-тесты `orchestrator/answer.py` (SPEC T075, SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/test_git_fixation.py`

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

## tests/test_answer_mandate.py

**Назначение:** Юнит-тесты `orchestrator/advance_gates/mandate.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/answer.py`, `orchestrator/gitcmd.py`

**Импортируется:** —

## tests/test_approve_acceptance_full_suite.py

**Назначение:** Юнит-тесты прогона полного набора tests/ на `approve` из `acceptance`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

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

## tests/test_artifact_branch_read_node.py

**Назначение:** Узел чтения документов задачи в `artifact_branch` (ADR-0021 п.3; SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_artifact_escalation_marker.py

**Назначение:** Юнит-тесты маркера эскалации по содержимому артефакта роли (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_auto_cycle.py`

**Импортируется:** —

## tests/test_artifact_materialization.py

**Назначение:** Юнит-тесты SPEC 01M1NKTF173WV5CPDZ1C3WW69K: материализация `tasks/<id>/`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_artifact_ref_sync.py

**Назначение:** Юнит-тесты ссылки документов `refs/artifacts/<id>` на настоящем git с

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_auto_cycle.py

**Назначение:** Тесты команды `auto` — цикла до ближайшего гейта (см. tasks/T014/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/zones.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_artifact_escalation_marker.py`, `tests/test_pull_conflict_marker_states.py`

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

## tests/test_budget_calibration_table.py

**Назначение:** Юнит-тесты четырёхуровневой калибровочной таблицы

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_budget_live_lease_and_escalation.py

**Назначение:** Юнит-тесты `orchestrator/budget.py`/`orchestrator/lease.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_canary.py

**Назначение:** Юнит-тесты `orchestrator/canary.py` v2 (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ;

**Публичные функции:**
- `pristine_config`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/pool_seal.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_canary_codex_clone_auth.py`

## tests/test_canary_acceptance_reason.py

**Назначение:** Границы сводки отказа автогейта приёмки канарейки.

**Публичные функции:**
- `test_refusal_survives_journal_excerpt_limit`
- `test_summary_binds_refusal_reason_to_500_characters`

**Импортирует:** `orchestrator/canary.py`

**Импортируется:** —

## tests/test_canary_budget_ceiling.py

**Назначение:** Юнит-тесты однократного подъёма потолка канареечной задачи и исхода

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_canary_codex_clone_auth.py

**Назначение:** Юнит-тесты входа Codex в эфемерном клоне канарейки (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/providers/codex.py`, `tests/test_canary.py`, `tests/test_canary_sets.py`

**Импортируется:** —

## tests/test_canary_drive.py

**Назначение:** Юнит-тесты ведения учебной задачи канарейки кодом проверяемого коммита

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/config.py`, `orchestrator/providers/codex.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_canary_profile_safety.py

**Назначение:** Границы постоянного профиля Codex канарейки.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/providers/codex.py`

**Импортируется:** —

## tests/test_canary_sets.py

**Назначение:** Юнит-тесты набора ролей канарейки (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5):

**Публичные функции:**
- `sets_block`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/roles.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_canary_codex_clone_auth.py`, `tests/test_doctor_canary_sets.py`

## tests/test_canary_synthetic_answer.py

**Назначение:** Юнит-тесты синтетического ответа канарейки на эскалацию

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_canary_template_flag.py

**Назначение:** Юнит-тесты флага выбора шаблона прогона канарейки

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_capacity_gate.py

**Назначение:** Юнит-тесты гейта ёмкости diff снимка — fail-closed на сбое git

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_capacity_gate_map.py

**Назначение:** Юнит-тесты исключения `docs/codebase-map.md` из меры гейта ёмкости

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/capacity.py`, `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/store.py`, `scripts/codebase_map.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_cas_set_state.py

**Назначение:** Юнит-тесты `orchestrator.store.set_state` (SPEC T050).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_fixture.py

**Назначение:** Каталог моделей сценария — фикстура песочницы, а не боевой

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `tests/sandbox.py`

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

**Публичные функции:**
- `tz_body`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_status_log.py

**Назначение:** Юнит-тесты `orchestrator.catalog.cmd_log`/`cmd_status` (SPEC

**Публичные функции:**
- `known_cost_detail`

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

## tests/test_catalog_zone_overlap.py

**Назначение:** Юнит-тесты предупреждения `new` о пересечении зон и пометки `status`

**Публичные функции:**
- `seed_task`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

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

## tests/test_ci_protected_paths.py

**Назначение:** Юнит-тесты `scripts/ci_protected_paths.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `scripts/ci_protected_paths.py`

**Импортируется:** —

## tests/test_ci_push_class.py

**Назначение:** Юнит-тесты scripts/ci_push_class.py (01M28NWK5X10J139Z8TD69HFAC):

**Публичные функции:** (нет)

**Импортирует:** `scripts/ci_push_class.py`

**Импортируется:** —

## tests/test_ci_rerun_command.py

**Назначение:** Юнит-тесты команды `ci-rerun` (`orchestrator/ci_rerun.py`, SPEC

**Публичные функции:**
- `red_note`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/ci.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/store.py`, `tests/test_invariants.py`

**Импортируется:** —

## tests/test_ci_stuck_check_run.py

**Назначение:** Юнит-тесты правила завершённости check-run'а и состояния «проверка

**Публичные функции:**
- `answer`
- `green`
- `iso_ago`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/config.py`, `orchestrator/store.py`

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
- `write_tree`

**Импортирует:** `orchestrator/config.py`, `scripts/codebase_map.py`

**Импортируется:** —

## tests/test_codex_login_shell_path.py

**Назначение:** Паритет PATH команд шага Codex с шагом провайдера по умолчанию (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/providers/codex.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `tests/sandbox.py`

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

## tests/test_cycle_hint.py

**Назначение:** Юнит-тесты `orchestrator/cycle_hint.py` (SPEC 01M3XTFJCC5TG63FHW907GQM4D)

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_detached_cycle.py

**Назначение:** Юнит-тесты отвязки `run`/`auto` от процесса сессии Оператора (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/session.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_kill_cleanup.py`

**Импортируется:** —

## tests/test_diff_not_collected_alerts.py

**Назначение:** Юнит-тесты новых функций tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_division_parent_cleanup.py

**Назначение:** Юнит-тесты уборки хвостов поделённого родителя на гейте SPEC

**Публичные функции:**
- `failing_branch_delete`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doc_commit.py

**Назначение:** Юнит-тесты команды `doc-commit` (`orchestrator/notes.py::cmd_doc_commit`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_doc_commit_suite_gate.py`

## tests/test_doc_commit_held_base.py

**Назначение:** Юнит-тесты базы удержанного `doc-commit` и команд `note --pending`/

**Публичные функции:**
- `run_command`

**Импортирует:** `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doc_commit_suite_gate.py

**Назначение:** Юнит-тесты гейта полного набора `tests/` перед коммитом конфигурации

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_doc_commit.py`

**Импортируется:** —

## tests/test_docs_dir_layout.py

**Назначение:** Сторожа выноса документов задачи из рабочей копии кода (ADR-0021 пп. 2,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/amend.py`, `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_docs_fetch_edges.py

**Назначение:** Углы команды `docs` (SPEC 01M41VTSE5N15P5P2WZF4GF2BQ), не покрытые

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`

**Импортируется:** —

## tests/test_docs_ref_deleted_refusal.py

**Назначение:** Записи пульта в ссылку документов при удалённой ролью ссылке и живой

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/fixation.py`, `orchestrator/store.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`

**Импортируется:** —

## tests/test_doctor.py

**Назначение:** Тесты doctor: pre-flight, recovery-сверка, сироты, alerts, смоуки

**Публичные функции:**
- `result_event`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_providers.py`

## tests/test_doctor_agent_roles.py

**Назначение:** Юнит-тесты перечня ролей предполёта `doctor` (SPEC

**Публичные функции:**
- `map_agent_roles`
- `roles_yaml`

**Импортирует:** `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/models.py`, `orchestrator/providers/codex.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_providers_codex.py`

**Импортируется:** —

## tests/test_doctor_artifact_branch_sync.py

**Назначение:** Юнит-тесты сверки ссылки документов с `origin` в `doctor` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doctor_canary_pool.py

**Назначение:** Юнит-тесты `doctor.check_role_log_pool_leak`/`check_token_repo_scope`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_doctor_canary_sets.py

**Назначение:** Юнит-тесты строки `doctor` о наборах ролей канарейки

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/models.py`, `tests/test_canary_sets.py`

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

## tests/test_draft_mr_commits.py

**Назначение:** Юнит-тесты предусловия «в кодовой ветке есть коммит» для черновика

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_draft_mr_remote_base_args.py

**Назначение:** Юнит-тест адреса базы сверки черновика запроса на слияние (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/github_adapter.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/brief.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_advance_tests_writing_dry_collect.py

**Назначение:** Юнит-тесты выхода `orchestrator/fsm_advance.py::tests_writing` — сухой

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_advance_tests_writing_test_groups.py

**Назначение:** Юнит-тесты гейта групп приёмочных тестов на выходе `tests_writing`

**Публичные функции:**
- `plank`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_autogate.py

**Назначение:** Юнит-тесты условия «а» `fsm_autogate._autogate_conditions` — чтение

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_source.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_autogate_long_lived.py

**Назначение:** Пометки и ошибки долгоживущей планки в записи приёмки.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_source.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_fsm_branch_correct_status_reads.py

**Назначение:** Юнит-тесты ветко-корректных чтений SPEC.md/REVIEW.md/QUESTIONS.md в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Назначение:** Юнит-тест закрытия на пути `done` (SPEC T094, требования 12-13,

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

**Импортируется:** `tests/test_answer.py`, `tests/test_long_lived_transitions.py`, `tests/test_step_autocommit.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`

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

**Назначение:** Юнит-тесты `guard.check_content` на черновике — наследие режима

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

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_guard_test_ast.py

**Назначение:** Юнит-тесты ast-разбора тестов в `scripts/guard.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_test_groups.py

**Назначение:** Юнит-тесты узла двух групп приёмочных тестов в `scripts/guard.py`

**Публичные функции:**
- `line_of`
- `source`

**Импортирует:** `scripts/guard.py`

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

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_ci_status_kind_gate.py`, `tests/test_review_registry_gate.py`, `tests/test_verifying_ceiling.py`

## tests/test_journal_warning_once.py

**Назначение:** Юнит-тесты `orchestrator/budget.py::journal_warning_once` и трёх его

**Публичные функции:**
- `spend_levels`

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_runner_model_preflight.py`

**Импортируется:** —

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

## tests/test_long_lived_manifest.py

**Назначение:** Юнит-тесты долгоживущих приёмочных тестов в `tests/` кодовой ветки

**Публичные функции:**
- `long_lived_source`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/test_timeout_checkpoint.py`

**Импортируется:** —

## tests/test_long_lived_step_end_to_end.py

**Назначение:** Сквозной путь «шаг test_author → чекпоинт → advance» для долгоживущего

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_timeout_checkpoint.py`

**Импортируется:** —

## tests/test_long_lived_transitions.py

**Назначение:** Юнит-тесты проводки долгоживущих файлов через переходы FSM (SPEC

**Публичные функции:**
- `capture_call`
- `long_lived_source`
- `plank_source`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/test_git_fixation.py`

**Импортируется:** `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`

## tests/test_main_ci_line.py

**Назначение:** Юнит-тесты цвета CI main по первой родительской линии и его обвязки

**Публичные функции:**
- `done`
- `sha`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_merge_gate_ci_wait.py

**Назначение:** Юнит-тесты цикла ожидания CI на гейте `merge_gate` (SPEC T087, решение

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/merge_lock.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_merge_gate_clock_isolation.py`

## tests/test_merge_gate_clock_isolation.py

**Назначение:** Регрессионный тест изоляции часов тестов гейта мержа (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fsm_merge_gate.py`, `tests/test_merge_gate_ci_wait.py`

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

## tests/test_model_sets.py

**Назначение:** Юнит-тесты наборов моделей в `orchestrator/models.py` (SPEC

**Публичные функции:**
- `canary_row`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/roles.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`

**Импортируется:** —

## tests/test_model_tariffs.py

**Назначение:** Юнит-тесты тарифа на модель, истории тарифов и проверок `doctor`

**Публичные функции:**
- `catalog_text`
- `local_text`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_models.py

**Назначение:** Юнит-тесты `orchestrator/models.py` (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/roles.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_models_doctor.py`

## tests/test_models_doctor.py

**Назначение:** Юнит-тесты проверок `doctor` по каталогу моделей и локальному слою и

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/models.py`, `tests/sandbox.py`, `tests/test_models.py`

**Импортируется:** —

## tests/test_multitarget.py

**Назначение:** Тесты мультитаргетного контура (см. tasks/T019/SPEC.md, критерии 1–8).

**Публичные функции:**
- `fake_git_config`
- `result_event`
- `silent_git`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_multitarget_invariants.py

**Назначение:** Инварианты мультитаргета — реестр docs/invariants.md (tasks/T020/SPEC.md).

**Публичные функции:**
- `fake_git_config`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_mutation_claim_gate.py

**Назначение:** Юнит-тесты гейта заявки мутации на `in_dev -> verifying` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_new_argv_parsing.py

**Назначение:** Юнит-тесты `orchestrator.artel._parse_new_args` (tasks/T102/SPEC.md):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_notes.py

**Назначение:** Юнит-тесты чистых функций `orchestrator/notes.py` (tasks/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_notes_apply.py

**Назначение:** Юнит-тесты `note --apply <файл> --message "<основание>"`

**Публичные функции:**
- `draft_with_extra_row`
- `draft_without_dropped_rows`

**Импортирует:** `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_notes_row_format.py

**Назначение:** Юнит-тесты единого формата строки бэклога (`orchestrator/notes.py`,

**Публичные функции:**
- `cells`
- `inserted_row`

**Импортирует:** `orchestrator/config.py`, `orchestrator/notes.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_observation_edges.py

**Назначение:** Дополнительные границы наблюдения и обратимой миграции.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/session.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pair_suspension_units.py

**Назначение:** Юнит-тесты пробного периода и приостановки пары набора (SPEC

**Публичные функции:**
- `columns`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/schema.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/pin.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pin_update_stale_cycles.py

**Назначение:** Юнит-тесты отбора циклов на коде старше пина

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_plan_appendix.py

**Назначение:** Юнит-тесты приложений PLAN к защищённым путям (SPEC

**Публичные функции:**
- `diff_block`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_plank_run_edges.py

**Назначение:** Углы `plank-run` и восстановления удалённых файлов, не покрытые

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`

**Импортируется:** —

## tests/test_preflight_step_provider.py

**Назначение:** Юнит-тесты предполёта шага по провайдеру шага (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/doctor/preflight.py`

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

## tests/test_protected_test_settings.py

**Назначение:** Юнит-тесты защиты настроек сбора тестов и общего помощника сверки пути

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/zones.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `scripts/ci_protected_paths.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_provider_scoped_step_env.py

**Назначение:** Сужение окружения шага по провайдеру и строка `foreign-provider-secrets`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_providers.py

**Назначение:** Юнит-тесты пакета `orchestrator/providers/` — интерфейса исполнителя

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/keychain.py`, `orchestrator/models.py`, `orchestrator/providers/claude.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_doctor.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`

**Импортируется:** —

## tests/test_providers_codex.py

**Назначение:** Юнит-тесты провайдера `codex` (SPEC 01M32NH6P053978AER66P0X4GN,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/keychain.py`, `orchestrator/models.py`, `orchestrator/providers/codex.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_doctor_agent_roles.py`

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

## tests/test_pull_additive_conflict.py

**Назначение:** Юнит-тесты аддитивного слияния конфликта подтяжки main

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/ci_push_class.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pull_conflict_marker_states.py

**Назначение:** Юнит-тесты набора состояний, эскалация которых по НЕРАЗРЕШЁННОМУ

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/auto.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_auto_cycle.py`

**Импортируется:** —

## tests/test_pull_long_lived_plank.py

**Назначение:** Юнит-тесты прогона планки после подтяжки main с долгоживущей группой

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

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

**Публичные функции:**
- `known_cost_detail`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_retro_artifact_branch_reads.py

**Назначение:** Источник байтов ретроспективы — АРТЕФАКТНАЯ ветка задачи, читаемая

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_retro_corpus.py

**Назначение:** Юнит-тесты orchestrator/retro_corpus.py: поля записи кэша ретро-корпуса

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/retro_corpus.py`

**Импортируется:** —

## tests/test_review_freshness.py

**Назначение:** Тесты свежести вердикта ревью (см. tasks/T004/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifacts.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_review_long_lived_exclude.py

**Назначение:** Юнит-тесты исключения долгоживущих файлов перечня лока из diff пакета

**Публичные функции:**
- `boundary_markers`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/test_amend_long_lived.py`

**Импортируется:** —

## tests/test_review_package.py

**Назначение:** Тесты ревью-пакета — входа ревьювера (см. tasks/T011/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_review_package_map.py

**Назначение:** Юнит-тесты исключения `docs/codebase-map.md` из diff ревью-пакета

**Публичные функции:**
- `chunk`
- `matches`

**Импортирует:** `orchestrator/advance_gates/capacity.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_review_registry_gate.py

**Назначение:** Юнит-тесты гейта «Реестр замечаний» в `orchestrator/fsm_advance.py::

**Публичные функции:**
- `row`

**Импортирует:** `orchestrator/fsm.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/test_invariants.py`

**Импортируется:** —

## tests/test_role_commit_by_pult.py

**Назначение:** Юнит-тесты сверки незакоммиченного результата шага после отказа git на

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_role_prompt_test_author_mission.py

**Назначение:** Регресс-тест пункта 5 миссии test_author (SPEC 01M29BANMM8X8JWJ5GDTJWKB0Z,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/role_prompt.py`, `orchestrator/stack.py`

**Импортируется:** —

## tests/test_roles_map_fixture.py

**Назначение:** Карта исполнителей и локальный слой моделей тестов — фикстура, а не

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/roles.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`, `tests/test_stack_optional_tools.py`

**Импортируется:** —

## tests/test_runner_model_preflight.py

**Назначение:** Юнит-тесты запуска шага роли по абсолютному пути из резолва манифеста

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_runner_role_model.py`

**Импортируется:** `tests/test_journal_warning_once.py`, `tests/test_providers.py`

## tests/test_runner_role_environment.py

**Назначение:** Граница переданного и текущего окружения признака шага роли.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/runner.py`

**Импортируется:** —

## tests/test_runner_role_model.py

**Назначение:** Юнит-тесты флага `--model` в команде шага и `model=` в журнале «agent

**Публичные функции:**
- `result_event`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_providers.py`, `tests/test_runner_model_preflight.py`, `tests/test_stack_optional_tools.py`, `tests/test_stack_roles_tier_spread.py`

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

## tests/test_snapshot_closing_outcome.py

**Назначение:** Исход в ретроспективе коммита закрытия (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/stack.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_stack_ci.py

**Назначение:** Юнит-тесты scripts/stack_ci.py (SPEC 01M1RDCCKBQMJ5G2K9ANJP059H,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/stack.py`

**Импортируется:** —

## tests/test_stack_codex_section.py

**Назначение:** Сторож раздела `docs/stack.md` о постоянном профиле Codex канарейки.

**Публичные функции:**
- `section_body`
- `stack_md_text`

**Импортирует:** `orchestrator/config.py`, `orchestrator/providers/codex.py`

**Импортируется:** —

## tests/test_stack_optional_tools.py

**Назначение:** Юнит-тесты необязательной части манифеста стека (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/stack.py`, `tests/sandbox.py`, `tests/test_runner_role_model.py`

**Импортируется:** `tests/test_roles_map_fixture.py`, `tests/test_stack_roles_tier_spread.py`

## tests/test_stack_parity_table.py

**Назначение:** Сторож таблицы паритета безопасности роли в `docs/stack.md` (SPEC

**Публичные функции:**
- `checks_named_in`
- `data_rows`
- `doctor_check_names`
- `markdown_tables`
- `missing_prohibitions`
- `parity_table`
- `row_is_open`
- `row_matches`
- `stack_md_text`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** —

## tests/test_stack_roles_tier_spread.py

**Назначение:** Регрессия 27.09: строки манифеста стека не зависят от того, на каких

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/roles.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`, `tests/test_runner_role_model.py`, `tests/test_stack_optional_tools.py`

**Импортируется:** —

## tests/test_stack_zones_pull_section.py

**Назначение:** Сторож раздела `docs/stack.md` о зонах и подтяжке main (SPEC

**Публичные функции:**
- `section_body`
- `stack_md_text`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/pull.py`, `orchestrator/zone_lock.py`

**Импортируется:** —

## tests/test_stale_cycles_start_precision.py

**Назначение:** Юнит-тесты погрешности времени старта процесса цикла в отборе циклов на

**Публичные функции:**
- `lstart_answer`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/artifact_branch.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_step_refixation.py

**Назначение:** Юнит-тесты перефиксации sha на пути отклонённого перехода FSM (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/test_git_fixation.py`

**Импортируется:** —

## tests/test_steps_task_id_index.py

**Назначение:** Юнит-тесты индекса `steps(task_id)` (SPEC 01M3GKJFN90ATK2KECNDZXPPP6,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/schema.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_store_db_connection_close.py

**Назначение:** Юнит-тесты закрытия соединений `store.db()` (tasks/T090/SPEC.md,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_store_journal.py

**Назначение:** Юнит-тесты `orchestrator.store.journal` (SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_task_model_set_units.py

**Назначение:** Юнит-тесты набора моделей задачи (SPEC 01M3YCHS4F08VTV6XX10VF92H3) —

**Публичные функции:**
- `set_task`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_test_author_long_lived_artifact.py

**Назначение:** Юнит-тесты признака «свой долгоживущий файл» обязательного артефакта

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_test_integrity_gate.py

**Назначение:** Юнит-тесты гейта неослабления тестов на `in_dev -> verifying` и на

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_test_rule_stats.py

**Назначение:** Юнит-тесты `scripts/test_rule_stats.py` (SPEC 01M3XR84299TD6V6E16D2PNXH4)

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`

**Импортируется:** —

## tests/test_timeout_checkpoint.py

**Назначение:** Юнит-тесты `checkpoint.commit_timeout_checkpoint` (tasks/T041/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/test_git_fixation.py`

**Импортируется:** `tests/test_checkpoint_zone_filter.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`

## tests/test_token_rate_divergence.py

**Назначение:** Юнит-тесты сверки тарифа токенов с фактом CLI при записи шага

**Публичные функции:**
- `cost`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/report.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

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

**Импортирует:** `orchestrator/artifacts.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/roles.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_zone_line_parse.py

**Назначение:** Юнит-тесты ОДНОГО разбора строки зон (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/catalog.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_zone_lock.py

**Назначение:** Юнит-тесты orchestrator/zone_lock.py (SPEC 01M1P9QAG65GVF69YJEV0V18D9).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_zone_lock_forecast.py

**Назначение:** Юнит-тесты прогноза очереди зон `orchestrator/zone_lock.py`

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

**Импортирует:** `orchestrator/advance_gates/zones.py`, `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —
