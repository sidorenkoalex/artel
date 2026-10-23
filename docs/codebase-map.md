---
built_at_sha: d08b9785761dd4c351d13259928e6ef71c88b736
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
- `acceptance_suite`
- `carries_random_seed`
- `clean_tree_sha`
- `collect`
- `components_full_suite`
- `drop_from_code_copy`
- `failed_entries`
- `failed_test_lines`
- `full_suite`
- `is_pytest_command`
- `is_unknown`
- `journal_suite_metrics`
- `long_lived_file_report`
- `long_lived_file_reports`
- `materialize_files`
- `materialize_from_branch`
- `observed_full_suite`
- `place_channel`
- `plank_helper_laid_out`
- `plank_in_code_copy`
- `plank_present`
- `run`
- `run_checks_local`
- `run_digest`
- `run_full_suite`
- `run_plank`
- `run_repeat`
- `run_summary_line`
- `save_failures`
- `save_suite_result`
- `saved_failures`
- `saved_suite_result`
- `short_summary_block`
- `subtest_parents`
- `subtest_unit`
- `suite_load_line`
- `suite_result_key`
- `suite_results_dir`
- `suite_tree_hash`
- `summary`
- `unknown_line`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/reporters/outcome.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/notes.py`, `orchestrator/plank_run.py`, `orchestrator/project_profile.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_summary_deselected.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_acceptance.py`, `tests/test_acceptance_collect.py`, `tests/test_acceptance_file_time.py`, `tests/test_acceptance_own_launch.py`, `tests/test_acceptance_plank_exclude_lock.py`, `tests/test_acceptance_plank_layout_refusal.py`, `tests/test_acceptance_pycache.py`, `tests/test_acceptance_seed_repeat.py`, `tests/test_acceptance_suite_profile.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_branch_freshness_gate.py`, `tests/test_component_checks.py`, `tests/test_component_report_gates.py`, `tests/test_component_report_run.py`, `tests/test_docs_dir_layout.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_full_suite_reuse.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_transitions.py`, `tests/test_model_sets.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_plank_run_edges.py`, `tests/test_project_profile.py`, `tests/test_pull.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_report_argv_rerun_ban.py`, `tests/test_suite_lock.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_task_component_places.py`, `tests/test_worktree_db_files.py`

## orchestrator/advance_gates/__init__.py

**Назначение:** Гейты переходов: проверки пункта 8 сверяют ветку с репозиторием проекта.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## orchestrator/advance_gates/_base.py

**Назначение:** Каркас гейтов `_run_gates` и общий тип исхода `GateRefusal` (SPEC R2

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/store.py`

**Импортируется:** `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/fsm_advance.py`, `tests/test_docs_dir_layout.py`

## orchestrator/advance_gates/acceptance.py

**Назначение:** `_acceptance_lock_refuses`, `_acceptance_run_refuses` (SPEC

**Публичные функции:**
- `blob_sha256`
- `branch_criterion_problems`
- `criterion_files`
- `file_records`
- `in_outcome_bounds`
- `long_lived_manifest`
- `long_lived_manifest_rel`
- `not_passed_kind`
- `outcome_kind`
- `record_criterion`
- `record_location`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/agent_log.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/amend.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_docs_dir_layout.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_guard_plank_bans.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_project_profile_gates.py`, `tests/test_refusal_classes.py`, `tests/test_review_long_lived_exclude.py`

## orchestrator/advance_gates/capacity.py

**Назначение:** Семейство гейта ёмкости diff снимка `_capacity_gate` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `tests/test_capacity_gate_map.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package_map.py`

## orchestrator/advance_gates/mandate.py

**Назначение:** Строка мандата Оператора: один разбор на все три места и проверка

**Публичные функции:**
- `approved_replacements`
- `elements`
- `id_elements`
- `in_weakening_scope`
- `line_elements`
- `matrix_refusals`
- `matrix_section`
- `refusals`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/gitcmd.py`, `orchestrator/merge_after.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/answer.py`, `orchestrator/fsm.py`, `orchestrator/merge_after.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_answer_mandate.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_mandate_file_path_token.py`, `tests/test_mandate_matrix_form.py`, `tests/test_mandate_profile_scope.py`, `tests/test_mandate_test_id.py`, `tests/test_merge_after.py`, `tests/test_task_component_places.py`

## orchestrator/advance_gates/outcome_integrity.py

**Назначение:** Гейт неослабления по исходам тестов на переходе `in_dev -> verifying` (SPEC 01M5CJVB5B5V55PQQVR2QRHWZN; ADR-0026, «Решение» п. 6).

**Публичные функции:**
- `compare`
- `covering`
- `describe`
- `fingerprint`
- `in_pass_to_pass`
- `merge_gate_escalates`
- `ordered`
- `proof_fields`
- `red_on_branch`
- `review_lines`
- `skip_growth`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/review.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5fryvp4nf81vt00fyphpwjh_outcome_action_texts.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_gate_owner_marker.py`, `tests/test_mandate_test_id.py`, `tests/test_outcome_integrity.py`, `tests/test_outcome_integrity_added_lines.py`, `tests/test_refusal_classes.py`

## orchestrator/advance_gates/plan_appendix.py

**Назначение:** Гейт применимости приложений PLAN на выходе `in_dev` (SPEC

**Публичные функции:**
- `git_apply`
- `in_base`
- `skip_in_base`

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_plan_appendix.py`, `tests/test_project_protected_paths.py`, `tests/test_refusal_classes.py`

## orchestrator/advance_gates/refusal_classes.py

**Назначение:** Классы отказов перехода из агентских состояний (SPEC

**Публичные функции:**
- `refusal_class`

**Импортирует:** —

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/fsm.py`, `orchestrator/watch.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5fryvp4nf81vt00fyphpwjh_outcome_action_texts.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_answer_in_dev_gate_journal.py`, `tests/test_network_address_gate.py`, `tests/test_refusal_classes.py`

## orchestrator/advance_gates/review.py

**Назначение:** Семейство гейтов вокруг вердикта ревьювера — `_review_escalation_sha_gate`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `tests/test_answer_in_dev_gate_journal.py`, `tests/test_task_component_places.py`

## orchestrator/advance_gates/spec_audit.py

**Назначение:** Аудит SPEC — шаг роли `spec_auditor` между сдачей SPEC и гейтом SPEC

**Публичные функции:**
- `autocommit_prefix`
- `binding_refusal`
- `blob_sha`
- `content_sha`
- `entry`
- `freshness_refusal`
- `last_verdict`
- `leave`
- `record_entry`
- `return_count`
- `signals`
- `status_suffix`
- `summary`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/role_prompt.py`, `orchestrator/rounds.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_audit_signal.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py`, `tests/test_analyst_role.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_audit_witness.py`

## orchestrator/advance_gates/test_integrity.py

**Назначение:** Гейт неослабления тестов — узел сравнения `tests/` ветки с базой: ослабление и смена ожидания, сверка с объявленным в SPEC, строгость нового ожидания, храповик (SPEC 01M3FQ2V77QNK95Z599DM124QN, 01M45FJD46BX45VHC36S4VS9QN).

**Публичные функции:**
- `declared_changes`
- `findings`
- `merge_gate_escalates`
- `ratchet_finding`
- `refusal_detail`
- `review_lines`
- `uncovered`

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/report.py`, `orchestrator/review.py`, `scripts/test_rule_stats.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_answer_mandate.py`, `tests/test_class_mandate_units.py`, `tests/test_guard_helper_scope.py`, `tests/test_guard_parametrize_variants.py`, `tests/test_invariants.py`, `tests/test_refusal_classes.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`

## orchestrator/advance_gates/tests_writing.py

**Назначение:** `_tests_writing_*`, `_origin_push_gate`, `_registry_gate`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifacts.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/reporters/outcome.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/two_sided.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/review.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_network_address_gate.py`, `tests/test_plank_helper.py`, `tests/test_project_profile_gates.py`, `tests/test_refusal_classes.py`, `tests/test_tests_writing_new_module_dir.py`

## orchestrator/advance_gates/two_sided.py

**Назначение:** Двусторонний прогон смены ожидания из раздела SPEC «Меняемое поведение» на переходе `in_dev -> verifying` (SPEC 01M45FJD46BX45VHC36S4VS9QN, требование 10).

**Публичные функции:**
- `run`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`

**Импортируется:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_gate_owner_marker.py`, `tests/test_guard_assertion_changes.py`, `tests/test_guard_parametrize_variants.py`, `tests/test_pytest_own_result_ids.py`

## orchestrator/advance_gates/zones.py

**Назначение:** Семейство гейта зон `_zones_gate` и его прямые помощники (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm_advance.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_answer_mandate.py`, `tests/test_auto_cycle.py`, `tests/test_checkpoint_zone_mandate.py`, `tests/test_protected_test_settings.py`, `tests/test_refusal_classes.py`, `tests/test_zones_gate.py`

## orchestrator/agent_log.py

**Назначение:** Наблюдаемость шага: файлы логов прогонов и перекачка вывода агента.

**Публичные функции:**
- `environment_fingerprint`
- `last_agent_log`
- `log_tail`
- `new_agent_log`
- `pytest_summaries`
- `render_agent_line`
- `step_friction`
- `stream_to_log`
- `tee_lines`
- `vitest_summaries`

**Импортирует:** `orchestrator/config.py`, `orchestrator/spend.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/auto.py`, `orchestrator/pause.py`, `orchestrator/plank_run.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/watch.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_failure_cli_isolation.py`, `tests/test_agent_log.py`, `tests/test_auto_cycle.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_kill_cleanup.py`, `tests/test_observation_acceptance_return.py`, `tests/test_pause_now.py`, `tests/test_providers_codex.py`, `tests/test_pytest_summary_pump.py`, `tests/test_report.py`, `tests/test_step_cost.py`, `tests/test_vitest_summary_pump.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/failure_classification.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `orchestrator/pull.py`, `orchestrator/reference_cache.py`, `orchestrator/report.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_auto_cycle.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_coldstart.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_fsm_map_regen.py`, `tests/test_main_copy_watch.py`, `tests/test_merge_reference_step.py`, `tests/test_prune.py`, `tests/test_reference_command.py`, `tests/test_runner_wave_breaker.py`, `tests/test_stall_alerts.py`, `tests/test_suite_duration.py`, `tests/test_token_rate_divergence.py`

## orchestrator/amend.py

**Назначение:** Команда `amend-tests`: штатная правка зафиксированной планки приёмки

**Публичные функции:**
- `cmd_amend_tests`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`

## orchestrator/answer.py

**Назначение:** Команда `answer`: канал ответа Оператора на эскалацию (SPEC T075,

**Публичные функции:**
- `cmd_answer`
- `cmd_zones_extend`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_answer.py`, `tests/test_answer_mandate.py`, `tests/test_class_mandate_units.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_lease_run_task_command.py`, `tests/test_mandate_matrix_form.py`

## orchestrator/appendix_tree.py

**Назначение:** Приложения PLAN на дереве полного прогона ветки задачи (SPEC

**Публичные функции:**
- `apply_in_order`
- `read_plan`
- `suite_tree`

**Импортирует:** `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/suite_run.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_appendix_tree.py`, `tests/test_suite_run.py`, `tests/test_task_component_places.py`

## orchestrator/artel.py

**Назначение:** Артель — FSM-оркестратор (CLI).

**Публичные функции:**
- `main`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/docs_fetch.py`, `orchestrator/dry_run.py`, `orchestrator/explore_metric.py`, `orchestrator/fsm.py`, `orchestrator/knowledge_cards.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/plank_run.py`, `orchestrator/pool_seal.py`, `orchestrator/preflight.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/pull_main.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/snapshot.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/venv.py`, `orchestrator/version.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artel_bootstrap.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_canary_detach_result.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_run_task.py`, `tests/test_canary_runs.py`, `tests/test_canary_sets.py`, `tests/test_canary_template_flag.py`, `tests/test_detached_cycle.py`, `tests/test_doc_commit.py`, `tests/test_invariants.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_launch_observation_refusals.py`, `tests/test_main_ci_line.py`, `tests/test_mandate_matrix_form.py`, `tests/test_models.py`, `tests/test_new_argv_parsing.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_edges.py`, `tests/test_observation_notification.py`, `tests/test_task_model_set_units.py`

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
- `restrict_materialized_notes`
- `rev_sha`
- `show`
- `task_repo`
- `write_commit`

**Импортирует:** `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/appendix_tree.py`, `orchestrator/artel.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_mandate.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_branch_server_retry.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_division_parent_cleanup.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_fetch_edges.py`, `tests/test_doctor.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_git_fixation.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_preflight.py`, `tests/test_pull.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace_clone_docs_refs.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/artifact_cleanup.py

**Назначение:** Команда `artifact-branches-cleanup [--execute]`: уборка веток

**Публичные функции:**
- `cmd_artifact_branches_cleanup`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`

## orchestrator/artifact_source.py

**Назначение:** Ветка-источник `tasks/<id>/` живой задачи — общий резолвер (SPEC T094,

**Публичные функции:**
- `resolve`

**Импортирует:** `orchestrator/artifact_branch.py`

**Импортируется:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/answer.py`, `orchestrator/appendix_tree.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_checkpoint_zone_mandate.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_task_component_places.py`

## orchestrator/artifacts.py

**Назначение:** Чтение артефактов задачи: frontmatter и свежесть вердикта ревьювера.

**Публичные функции:**
- `fresh_verdict_iteration`
- `frontmatter`

**Импортирует:** `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `tests/test_review_freshness.py`, `tests/test_yaml_parsing.py`

## orchestrator/auto.py

**Назначение:** Цикл `auto`: advance до шага роли, затем — если роль ещё не закончила — run.

**Публичные функции:**
- `auto_stop`
- `auto_stop_advice`
- `cmd_auto`

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/models.py`, `orchestrator/pause.py`, `orchestrator/pull.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/advance_gates/review.py`, `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/fsm_advance.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_analyst_role.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_git_fixation.py`, `tests/test_plan_appendix.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_runner_model_preflight.py`, `tests/test_spec_audit_gate.py`, `tests/test_stall_alerts.py`

## orchestrator/brief.py

**Назначение:** Бриф роли одним документом: SPEC/TZ + карта кодовой базы + конвенции

**Публичные функции:**
- `advance_refusal_history`
- `analyst_map_component`
- `component_hash`
- `developer_brief`
- `fresh_map_text`
- `is_artel_task`
- `mark_unclosed_parts`
- `new_run_id`
- `project_skills_refusal`
- `project_skills_text`
- `skills_text`
- `spec_auditor_brief`
- `step_notes_block`
- `test_author_answer_component`
- `wrap_boundary`

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `scripts/codebase_map.py`

**Импортируется:** `orchestrator/doctor/__init__.py`, `orchestrator/knowledge_cards.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_brief_map_interpreter.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_advance_refusal_history.py`, `tests/test_answer_branch_reads.py`, `tests/test_auto_cycle.py`, `tests/test_brief.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_long_lived_manifest.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_role_prompt_test_author_mission.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_step_note_contract.py`, `tests/test_step_project.py`

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

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/retro.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_budget_calibration_table.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_doctor.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_knowledge_command.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_program_spend_reseed.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_zone_line_parse.py`

## orchestrator/canary.py

**Назначение:** Команда `canary`: синтетический прогон конвейера, v2 (SPEC

**Публичные функции:**
- `cmd_canary`
- `cmd_canary_live`
- `cmd_canary_run_task`
- `cmd_canary_runs`
- `during_canary_reason_refusal`
- `escalation_roles`
- `hours_text`
- `live_marks`
- `live_run_note`
- `live_runs`
- `merges_since_last_green_run`
- `record_age`
- `refuse_main_move_during_canary`
- `registry_view`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/alerts.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `orchestrator/providers/codex.py`, `orchestrator/reference_cache.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary_drive.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/notes.py`, `orchestrator/pin.py`, `orchestrator/pool_seal.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_canary.py`, `tests/test_canary_acceptance_reason.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_codex_clone_auth.py`, `tests/test_canary_detach_result.py`, `tests/test_canary_drive.py`, `tests/test_canary_escalation_roles_storage.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_profile_safety.py`, `tests/test_canary_run_task.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_canary_template_flag.py`, `tests/test_doctor.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_parent_task_division.py`, `tests/test_pin_prune_orphan_guards.py`

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
- `new_cli_target`
- `slugify`
- `spawn_subtask`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/liveness.py`, `orchestrator/merge_after.py`, `orchestrator/merge_queue.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `orchestrator/repo_context.py`, `orchestrator/retro.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/tz_check.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/fsm.py`, `tests/sandbox.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer_gate.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_pin_divergence.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_tz_zones_parsing.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_lock_by_project.py`, `tests/test_merge_queue.py`, `tests/test_models_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parent_task_division.py`, `tests/test_pause_now.py`, `tests/test_plan_appendix.py`, `tests/test_project_protected_paths.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_slugify.py`, `tests/test_spec_budget.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_step_cost.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_workspace.py`, `tests/test_zone_line_parse.py`

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
- `main_copy_watch_start`
- `parse_step_note_saved`
- `pult_commit_failed_paths`
- `restore_out_of_bounds_deletions`
- `step_note_saved_detail`
- `task_dir_zone`
- `watch_main_copy`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/brief.py`, `orchestrator/fsm.py`, `orchestrator/pause.py`, `orchestrator/pull.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_artifact_materialization.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_stray_acceptance_files.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_checkpoint_zone_mandate.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_main_copy_watch.py`, `tests/test_pause_now.py`, `tests/test_plank_helper.py`, `tests/test_plank_run_edges.py`, `tests/test_role_commit_by_pult.py`, `tests/test_step_autocommit.py`, `tests/test_step_note_contract.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/ci.py

**Назначение:** Статус CI головного коммита ветки задачи — условие merge (SPEC T017, 6).

**Публичные функции:**
- `accepted_full_suite`
- `branch_status`
- `check_finished`
- `check_run_workflow_run`
- `check_runs`
- `check_runs_page`
- `checks_forbidden`
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
- `verifying_head_not_in_origin`
- `verifying_is_red`
- `verifying_status`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/workspace.py`, `scripts/ci_push_class.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/auto.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/pin.py`, `orchestrator/watch.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_acceptance.py`, `tests/test_auto_cycle.py`, `tests/test_ci_actions_fallback.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_project_gh_address.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_invariants.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_fetched_repo.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_pin.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_plan_appendix.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_verifying_ceiling.py`

## orchestrator/ci_rerun.py

**Назначение:** Команда `ci-rerun`: повтор упавшего CI ветки задачи в `verifying`

**Публичные функции:**
- `cmd_ci_rerun`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/fsm.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_lease_run_task_command.py`

## orchestrator/cleanup.py

**Назначение:** kill switch и уборка хвостов задачи: каталог артефактов и ветка.

**Публичные функции:**
- `artifacts_in_main`
- `artifacts_tracked_here`
- `cleanup_killed_task`
- `cleanup_merged_remote`
- `cleanup_project_remote`
- `cmd_kill`
- `drop_merged_task_branch`
- `drop_task_branch`
- `drop_task_dir`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/retro.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_artifact_ref_sync.py`, `tests/test_detached_cycle.py`, `tests/test_division_parent_cleanup.py`, `tests/test_done_branch_cleanup.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_multitarget_invariants.py`, `tests/test_retro.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_task_id_prefix_regression.py`

## orchestrator/coldstart.py

**Назначение:** Наблюдаемый мир для холодного старта пульта (SPEC T049, ADR-0005 п.5).

**Публичные функции:**
- `observed_max_task_number`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/doctor/__init__.py`, `orchestrator/store.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_coldstart.py`

## orchestrator/config.py

**Назначение:** Пути и константы оркестратора — один адрес на весь пакет.

**Публичные функции:**
- `is_protected_path`

**Импортирует:** —

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/context_package.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/doctor/observations.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/parallel_limit.py`, `orchestrator/pin.py`, `orchestrator/plank_run.py`, `orchestrator/pool_seal.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/providers/base.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/roles.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/schema.py`, `orchestrator/session.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `orchestrator/targets.py`, `orchestrator/tz_check.py`, `orchestrator/venv.py`, `orchestrator/version.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/ci_protected_paths.py`, `scripts/guard.py`, `scripts/test_rule_stats.py`, `tests/sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py`, `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_codebase_map_root.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_brief_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py`, `tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_guard.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_form.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_match.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_targets_knowledge.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cli.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_acceptance.py`, `tests/test_acceptance_seed_repeat.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artel_bootstrap.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_calibration_table.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_codex_clone_auth.py`, `tests/test_canary_doctor_owner.py`, `tests/test_canary_drive.py`, `tests/test_canary_escalation_roles_storage.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_profile_safety.py`, `tests/test_canary_run_task.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_canary_template_flag.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_catalog_fixture.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_mandate.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_project_gh_address.py`, `tests/test_ci_protected_paths.py`, `tests/test_ci_status.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_codebase_map.py`, `tests/test_codex_login_shell_path.py`, `tests/test_coldstart.py`, `tests/test_component_checks.py`, `tests/test_component_report_gates.py`, `tests/test_conftest_role_guard.py`, `tests/test_cycle_hint.py`, `tests/test_detached_cycle.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doc_commit.py`, `tests/test_doc_commit_held_base.py`, `tests/test_doc_commit_suite_gate.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_done_branch_cleanup.py`, `tests/test_draft_mr_commits.py`, `tests/test_draft_mr_remote_base_args.py`, `tests/test_dry_run.py`, `tests/test_failure_classification.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_division_section.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_knowledge_command.py`, `tests/test_launch_observation_refusals.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_template_shape.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_fetched_repo.py`, `tests/test_main_ci_line.py`, `tests/test_main_copy_watch.py`, `tests/test_merge_after.py`, `tests/test_merge_after_declared.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_lock_by_project.py`, `tests/test_merge_queue.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_network_address_gate.py`, `tests/test_new_argv_parsing.py`, `tests/test_notes.py`, `tests/test_notes_apply.py`, `tests/test_notes_row_format.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_edges.py`, `tests/test_pair_suspension_units.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_pin_update_stale_cycles.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_plank_run_edges.py`, `tests/test_preflight.py`, `tests/test_profile_layers_declared.py`, `tests/test_program_spend_reseed.py`, `tests/test_project_profile_gates.py`, `tests/test_project_protected_paths.py`, `tests/test_protected_paths_gate.py`, `tests/test_protected_test_settings.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_prune_abolished_rules.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_release.py`, `tests/test_repo_context.py`, `tests/test_report.py`, `tests/test_report_project_label.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_role_commit_by_pult.py`, `tests/test_roles_map_fixture.py`, `tests/test_rounds.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_environment.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_session.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_snapshot_history.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stack.py`, `tests/test_stack_codex_section.py`, `tests/test_stack_optional_tools.py`, `tests/test_stack_parity_table.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_stale_cycles_start_precision.py`, `tests/test_stall_alerts.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_project.py`, `tests/test_step_refixation.py`, `tests/test_store_journal.py`, `tests/test_suite_duration.py`, `tests/test_suite_lock.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_test_rule_stats.py`, `tests/test_timeout_checkpoint.py`, `tests/test_token_rate_divergence.py`, `tests/test_verifying_ceiling.py`, `tests/test_version.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_worktree_db_files.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

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

**Импортируется:** `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci_rerun.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_cycle_hint.py`, `tests/test_pin_update_stale_cycles.py`

## orchestrator/docs_fetch.py

**Назначение:** Команда `docs <id> [файл]` / `docs --fetch-all`: документы задачи из

**Публичные функции:**
- `cmd_docs`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`

## orchestrator/doctor/__init__.py

**Назначение:** doctor: pre-flight, recovery-сверка, сироты, живой и офлайн-смоук CLI

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/ci.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/doctor/artifact_branches.py`, `orchestrator/doctor/auto_ack.py`, `orchestrator/doctor/branch_freshness.py`, `orchestrator/doctor/canary_pool.py`, `orchestrator/doctor/canary_sets.py`, `orchestrator/doctor/cli.py`, `orchestrator/doctor/git_hooks.py`, `orchestrator/doctor/hung_test_watchdog.py`, `orchestrator/doctor/ignored_artifacts.py`, `orchestrator/doctor/isolation.py`, `orchestrator/doctor/lease_alerts.py`, `orchestrator/doctor/leases.py`, `orchestrator/doctor/live_smoke.py`, `orchestrator/doctor/machine_load.py`, `orchestrator/doctor/main_ci.py`, `orchestrator/doctor/map_growth.py`, `orchestrator/doctor/misc_checks.py`, `orchestrator/doctor/model_catalog.py`, `orchestrator/doctor/model_tariffs.py`, `orchestrator/doctor/observations.py`, `orchestrator/doctor/orphans.py`, `orchestrator/doctor/preflight.py`, `orchestrator/doctor/project_checks.py`, `orchestrator/doctor/recovery.py`, `orchestrator/doctor/root_pin.py`, `orchestrator/doctor/stale_cycles.py`, `orchestrator/doctor/suite_duration.py`, `orchestrator/doctor/worktree_db.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/liveness.py`, `orchestrator/merge_lock.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/pool_seal.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/providers/codex.py`, `orchestrator/repo_context.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`

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
- `check_canary_live`
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
- `full_suite_timeout_check`

**Импортирует:** `orchestrator/project_profile.py`

**Импортируется:** `orchestrator/doctor/__init__.py`, `tests/test_full_suite_profile_timeout.py`

## orchestrator/doctor/git_hooks.py

**Назначение:** Пакет orchestrator/doctor -- git-хуки защиты main главной копии.

**Публичные функции:**
- `check_clone_hooks`
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

## orchestrator/doctor/machine_load.py

**Назначение:** Machine load warning for doctor.

**Публичные функции:**
- `check_machine_load`

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
- `gh_env`

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

## orchestrator/doctor/observations.py

**Назначение:** Diagnostics for observation process ownership and obsolete Codex hooks.

**Публичные функции:**
- `check_codex_background_hooks`
- `check_observations`

**Импортирует:** `orchestrator/config.py`, `orchestrator/watch.py`

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/orphans.py

**Назначение:** Пакет orchestrator/doctor -- сироты: каталоги без строки БД, ветки done/killed, worktree.

**Публичные функции:**
- `check_orphans`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`, `tests/test_sandbox_determinism_helpers.py`

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

## orchestrator/doctor/project_checks.py

**Назначение:** Пакет orchestrator/doctor -- проверки записи внешнего проекта: клон, пуш, CI, защита ветки, токен, права токена на CI, no_paths, project_skills, компоненты.

**Публичные функции:**
- `check_artifacts_push`
- `check_base_protection`
- `check_ci_pull_request`
- `check_ci_token`
- `check_clone`
- `check_no_paths`
- `check_paths_source`
- `check_project_skills`
- `check_project_token`
- `check_tool_version`
- `check_workdir`
- `component_checks`
- `declares_pull_request`
- `find_variable`
- `project_entry_checks`
- `regex_alternatives`
- `version_matches`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`, `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py`, `tests/test_ci_actions_fallback.py`, `tests/test_component_checks.py`, `tests/test_hosting_token_units.py`

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

## orchestrator/doctor/suite_duration.py

**Назначение:** Relative full-suite duration signal, calibrated per target and worker count.

**Публичные функции:**
- `check_suite_duration`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/doctor/worktree_db.py

**Назначение:** Пакет orchestrator/doctor -- файлы БД пульта в рабочих копиях задач.

**Публичные функции:**
- `check_worktree_db_files`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

## orchestrator/dry_run.py

**Назначение:** Команда `acceptance-dry-run`: сухой прогон приёмки — предпросмотр без

**Публичные функции:**
- `cmd_acceptance_dry_run`

**Импортирует:** `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_dry_run.py`

## orchestrator/explore_metric.py

**Назначение:** Метрика разведки роли: сколько вызовов инструментов шаг тратит на чтение

**Публичные функции:**
- `cmd_explore_stats`
- `edit_kind`
- `normalize`
- `read_key`
- `render_lines`
- `search_string`
- `summarize`

**Импортирует:** `orchestrator/providers/base.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/retro.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/report.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_summarize.py`, `tests/test_explore_metric.py`

## orchestrator/failure_classification.py

**Назначение:** Классификация провалившейся попытки агента (SPEC T082, требования 1-2).

**Публичные функции:**
- `class_signature_text`
- `classify_attempt_failure`
- `required_cli_version`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/alerts.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_failure_classification.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_runner_model_preflight.py`

## orchestrator/fixation.py

**Назначение:** Hash-фиксация артефактов на переходах FSM (ADR-0003 п.15, п.17; tasks/T021).

**Публичные функции:**
- `approve_sha_hint`
- `check_integrity`
- `default_code_sha`
- `external_artifact_sha`
- `fix`
- `incident_refusal`
- `journal_drift`
- `legitimize`
- `read`
- `ref_drift`
- `refixate_after_rejected_transition`
- `stop_on_ref_drift`
- `unread_refusal`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_fsm_autogate.py`, `tests/test_git_fixation.py`, `tests/test_refusal_classes.py`, `tests/test_step_autocommit.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/fsm.py

**Назначение:** Переходы автомата: advance по артефактам, approve/reject Оператора.

**Публичные функции:**
- `cmd_advance`
- `cmd_approve`
- `cmd_reject`
- `cmd_set_models`
- `cmd_spec_audit`
- `confirm_fixation`
- `guard_refuses`
- `unanswered_role_step_escalation`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/models.py`, `orchestrator/pause.py`, `orchestrator/project_profile.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/ci_rerun.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull_main.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `tests/sandbox.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_questions_matrix.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_canary_escalation_roles_storage.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_component_report_gates.py`, `tests/test_division_parent_cleanup.py`, `tests/test_docs_dir_layout.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_conflict_note.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_multitarget_invariants.py`, `tests/test_project_protected_paths.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_main_unavailable.py`, `tests/test_review_freshness.py`, `tests/test_review_registry_gate.py`, `tests/test_role_commit_by_pult.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_suite_lock.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_verifying_ceiling.py`, `tests/test_zones_approve.py`

## orchestrator/fsm_advance.py

**Назначение:** Обработчики `cmd_advance` — один на состояние (SPEC T091, декомпозиция

**Публичные функции:**
- `in_dev`
- `review`
- `spec_audit`
- `spec_writing`
- `tests_writing`
- `verifying`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/merge_after.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/fsm.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_docs_dir_layout.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_long_lived_transitions.py`, `tests/test_mutation_claim_gate.py`, `tests/test_network_address_gate.py`, `tests/test_project_profile_gates.py`, `tests/test_protected_paths_gate.py`, `tests/test_test_integrity_gate.py`, `tests/test_zones_gate.py`

## orchestrator/fsm_autogate.py

**Назначение:** Автогейт acceptance по политике gates.yaml (ADR-0007, SPEC T066).

**Публичные функции:**
- `acceptance_checklist_measurement`
- `autogate_refusal_class`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/models.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm_advance.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py`, `tests/test_acceptance_file_time.py`, `tests/test_docs_dir_layout.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_fsm_autogate_plank_rule.py`, `tests/test_git_fixation.py`, `tests/test_long_lived_transitions.py`, `tests/test_task_component_places.py`

## orchestrator/fsm_merge_gate.py

**Назначение:** Тело и внешний цикл гейта `merge_gate` (SPEC T052, T053, T082, T087):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/alerts.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/canary.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/project_profile.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/session.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/fsm.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_artifact_ref_sync.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_component_report_gates.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_full_suite_reuse.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_gate_clock_isolation.py`, `tests/test_merge_reference_step.py`, `tests/test_plan_appendix.py`, `tests/test_protected_paths_gate.py`, `tests/test_protected_test_settings.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_task_component_places.py`, `tests/test_test_integrity_gate.py`, `tests/test_worktree_db_files.py`

## orchestrator/fsm_postmerge.py

**Назначение:** Побочные эффекты merge_gate после успешного merge: карта кодовой базы

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/codebase_map.py`

**Импортируется:** `orchestrator/fsm_merge_gate.py`, `orchestrator/snapshot.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_fsm_map_regen.py`, `tests/test_plan_appendix.py`

## orchestrator/gates.py

**Назначение:** Политика гейтов из `gates.yaml` (ADR-0007, SPEC T066).

**Публичные функции:**
- `policy`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/fsm_autogate.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`

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
- `hosting_env`
- `hosting_token`
- `in_repo`
- `is_ancestor`
- `list_branches`
- `ls_tree_files`
- `merges_between`
- `on_foreign_branch`
- `project_by_url`
- `pult_env`
- `qualified_ref`
- `remote_branch_sha`
- `remote_ref_state`
- `show`
- `url_key`

**Импортирует:** `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/runner.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/dry_run.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/notes.py`, `orchestrator/pin.py`, `orchestrator/pool_seal.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/suite_run.py`, `orchestrator/tz_check.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_answer_mandate.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_run_task.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_catalog_new_race.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doctor.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_draft_mr_commits.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_gate_owner_marker.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_carpentry.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_hosting_token_units.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_network_address_gate.py`, `tests/test_pin.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_project_profile_gates.py`, `tests/test_protected_paths_gate.py`, `tests/test_prune_abolished_rules.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_repo_context.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_project.py`, `tests/test_step_refixation.py`, `tests/test_task_component_places.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`, `tests/test_workspace_clone_docs_refs.py`, `tests/test_zones_gate.py`

## orchestrator/github_adapter.py

**Назначение:** GitHub-адаптер целевого `forge: github`: Draft-MR-флоу задачи (SPEC

**Публичные функции:**
- `ensure_draft_mr`
- `ensure_head_in_origin`
- `undraft_mr`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull_main.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_draft_mr_commits.py`, `tests/test_draft_mr_remote_base_args.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_git_fixation.py`, `tests/test_github_adapter.py`, `tests/test_long_lived_transitions.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_protected_test_settings.py`

## orchestrator/idgen.py

**Назначение:** Генератор идентификатора задачи (SPEC T094, требование 2).

**Публичные функции:**
- `is_task_id_form`
- `new_task_id`

**Импортирует:** —

**Импортируется:** `orchestrator/catalog.py`, `orchestrator/prune.py`, `scripts/guard.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`, `tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_long_lived_manifest.py`, `tests/test_merge_after.py`, `tests/test_merge_after_declared.py`

## orchestrator/keychain.py

**Назначение:** Чтение токенов из macOS keychain.

**Публичные функции:**
- `token`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`, `orchestrator/gitcmd.py`, `orchestrator/pool_seal.py`, `orchestrator/runner.py`, `tests/sandbox.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_codex_login_shell_path.py`, `tests/test_doctor_agent_roles.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`

## orchestrator/knowledge_cards.py

**Назначение:** Карточки знаний: форма, чтение по видам, сверка места, команда `knowledge`, журнал обращений, подсказка миссии.

**Публичные функции:**
- `access_tally`
- `check_text`
- `cmd_knowledge`
- `exhausted_detail`
- `hint_line`
- `is_card_file`
- `match`
- `read_cards`
- `refusal_text`
- `task_project`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/targets.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/artel.py`, `orchestrator/notes.py`, `orchestrator/role_prompt.py`, `orchestrator/suite_lock.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_form.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_match.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_knowledge_cards.py`, `tests/test_knowledge_command.py`

## orchestrator/lease.py

**Назначение:** Advisory-lease задачи: замок параллельных сессий CLI (SPEC T044).

**Публичные функции:**
- `acquire`
- `foreign_live_lease`
- `is_live`
- `release`
- `release_any`
- `run_locked`
- `run_task_command`
- `warn_foreign_live`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pause.py`, `orchestrator/pull_main.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_detached_cycle.py`, `tests/test_lease.py`, `tests/test_lease_run_task_command.py`, `tests/test_session.py`, `tests/test_zone_lock.py`

## orchestrator/liveness.py

**Назначение:** Возраст heartbeat и адресуемость pid — общие для lease/merge_lock/doctor.

**Публичные функции:**
- `group_kill_detail`
- `owner_alive`
- `owner_pid`
- `terminate_process_group`

**Импортирует:** —

**Импортируется:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/prune.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_canary_doctor_owner.py`, `tests/test_doctor.py`, `tests/test_gate_owner_marker.py`, `tests/test_lease_run_task_command.py`, `tests/test_liveness.py`, `tests/test_merge_lock.py`, `tests/test_sandbox_determinism_helpers.py`, `tests/test_zone_lock.py`

## orchestrator/merge_after.py

**Назначение:** Зависимости мержа `merge_after`: заявление при `new` строкой ТЗ «Порядок: после …» (заявленное значение — сразу в колонке `merge_after`), сверка SPEC с заявленным на гейте SPEC, добавка `status` «[мерж после: …]» до `acceptance`, проверка в каналах переписывания, отказ на гейте мержа.

**Публичные функции:**
- `apply_plan`
- `check`
- `column`
- `declared_from_tz`
- `lines_refusal`
- `mandate_value`
- `merge_gate_refuses`
- `record_added`
- `record_declared`
- `replace_divided`
- `rewrite`
- `show_line`
- `spec_gate_declared_refusal`
- `spec_gate_value`
- `status_suffix`
- `stored`
- `value_refusals`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/mandate.py`, `orchestrator/answer.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/zone_lock.py`, `tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py`, `tests/test_merge_after.py`, `tests/test_merge_after_declared.py`

## orchestrator/merge_lock.py

**Назначение:** Мьютекс merge-окна: один держатель на проект (SPEC T053; SPEC

**Публичные функции:**
- `acquire`
- `release`
- `run_window`
- `touch_heartbeat`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/doctor/__init__.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/merge_queue.py`, `orchestrator/notes.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_lock_by_project.py`, `tests/test_merge_queue.py`

## orchestrator/merge_queue.py

**Назначение:** Очередь FIFO ожидания мьютекса merge-окна (SPEC

**Публичные функции:**
- `queue_wait_minutes`
- `wait_for_window`
- `wait_suffix`

**Импортирует:** `orchestrator/config.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/catalog.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py`, `tests/test_merge_lock_by_project.py`, `tests/test_merge_queue.py`

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

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/retro.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_agent_failure.py`, `tests/test_agent_prompt.py`, `tests/test_canary_sets.py`, `tests/test_catalog_fixture.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_canary_sets.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_model_sets.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_pair_suspension_units.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_roles_map_fixture.py`, `tests/test_runner_role_model.py`, `tests/test_stack.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_suite_lock.py`, `tests/test_task_model_set_units.py`, `tests/test_token_rate_divergence.py`, `tests/test_yaml_parsing.py`

## orchestrator/notes.py

**Назначение:** Команда `note`: строка в копилку/бэклог/очередь изолированным коммитом

**Публичные функции:**
- `cmd_doc_commit`
- `cmd_note`
- `doc_commit_content`
- `pending_notes`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/knowledge_cards.py`, `orchestrator/merge_lock.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor/__init__.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_doc_commit.py`, `tests/test_doc_commit_held_base.py`, `tests/test_doc_commit_suite_gate.py`, `tests/test_knowledge_cards.py`, `tests/test_model_sets.py`, `tests/test_notes.py`, `tests/test_notes_apply.py`, `tests/test_notes_row_format.py`, `tests/test_suite_near_limit.py`

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

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_main_ci_fetched_repo.py`, `tests/test_pin.py`, `tests/test_pin_prune_orphan_guards.py`

## orchestrator/plank_helper.py

**Назначение:** Помощник планки `_pult.py`: пульт выкладывает его рядом с планкой задачи.

**Публичные функции:**
- `apply_check`
- `artifact_text`
- `branch_diff`
- `changed_paths`

**Импортирует:** —

**Импортируется:** —

## orchestrator/plank_run.py

**Назначение:** Команда `plank-run <id> [файл]`: штатный локальный прогон планки задачи в

**Публичные функции:**
- `cmd_plank_run`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`

## orchestrator/pool_seal.py

**Назначение:** Запечатанный пул шаблонов канарейки (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW).

**Публичные функции:**
- `cmd_pool_seal`
- `pool_drift_warning`
- `restore_pool_if_missing`
- `sealed_path`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/notes.py`, `orchestrator/runner.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/doctor/__init__.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_canary.py`

## orchestrator/preflight.py

**Назначение:** Команда `preflight <id>`: предпроверка выхода из `tests_writing` для роли

**Публичные функции:**
- `cmd_preflight`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_preflight.py`

## orchestrator/project_profile.py

**Назначение:** Профиль тестов проекта в проверках тестов пульта (ADR-0021 пп. 8-9;

**Публичные функции:**
- `component_limit`
- `component_profiles`
- `components`
- `decide`
- `decide_task`
- `for_row`
- `for_task`
- `for_task_target`
- `full_suite_limit`
- `is_multi`
- `journal_plank_default`
- `journal_skip`
- `layers_of`
- `long_lived_imports`
- `long_lived_rule`
- `mask_matches`
- `parse_test_id`
- `plank_rule`
- `refusal_hint`
- `report_args_of`
- `reported`
- `select_components`
- `task_components`
- `test_id`
- `unresolved_reason`
- `vitest_flags`
- `with_tools`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/brief.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/doctor/cli.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/knowledge_cards.py`, `orchestrator/notes.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/pull.py`, `orchestrator/reporters/outcome.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/suite_run.py`, `tests/sandbox.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_acceptance_plank_layout_refusal.py`, `tests/test_component_checks.py`, `tests/test_component_report_gates.py`, `tests/test_component_report_run.py`, `tests/test_fsm_autogate_plank_rule.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_gate_owner_marker.py`, `tests/test_guard_plank_bans.py`, `tests/test_mandate_file_path_token.py`, `tests/test_mandate_profile_scope.py`, `tests/test_mandate_test_id.py`, `tests/test_network_address_gate.py`, `tests/test_outcome_integrity.py`, `tests/test_outcome_integrity_added_lines.py`, `tests/test_profile_layers_declared.py`, `tests/test_project_components.py`, `tests/test_project_profile.py`, `tests/test_project_profile_gates.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_report_argv_rerun_ban.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_task_component_places.py`, `tests/test_tests_writing_new_module_dir.py`

## orchestrator/projects.py

**Назначение:** Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

**Публичные функции:**
- `cmd_reference`
- `cmd_target_init`
- `init_project`
- `project_dir`
- `reference_summary`

**Импортирует:** `orchestrator/config.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor/__init__.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_artifact_ref_sync.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_multitarget.py`, `tests/test_reference_command.py`

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

**Публичные функции:**
- `short_log_path`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/explore_metric.py`, `orchestrator/providers/__init__.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`

## orchestrator/providers/claude.py

**Назначение:** Провайдер исполнителя роли `claude` (Claude Code CLI, headless).

**Публичные функции:**
- `external_allowed_tools`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/providers/base.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/stack.py`

**Импортируется:** `orchestrator/explore_metric.py`, `orchestrator/providers/__init__.py`, `orchestrator/report.py`, `orchestrator/watch.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_summarize.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py`, `tests/test_providers.py`

## orchestrator/providers/codex.py

**Назначение:** Провайдер исполнителя роли `codex` (OpenAI Codex CLI, `codex exec`).

**Публичные функции:**
- `codex_home_override`
- `set_codex_home_override`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/providers/base.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/suite_lock.py`

**Импортируется:** `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/doctor/__init__.py`, `orchestrator/explore_metric.py`, `orchestrator/providers/__init__.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_summarize.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_canary_codex_clone_auth.py`, `tests/test_canary_drive.py`, `tests/test_canary_profile_safety.py`, `tests/test_codex_login_shell_path.py`, `tests/test_doctor_agent_roles.py`, `tests/test_providers_codex.py`, `tests/test_stack_codex_section.py`

## orchestrator/prune.py

**Назначение:** Команда `prune`: исполняет retention-политику docs/retention.md для

**Публичные функции:**
- `cmd_prune`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/liveness.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_prune.py`, `tests/test_prune_abolished_rules.py`

## orchestrator/pull.py

**Назначение:** Исходы подтяжки главной ветки в ветку задачи (роадмап §3, фаза R,

**Публичные функции:**
- `evaluate`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/ci_push_class.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/fsm.py`, `orchestrator/pull_main.py`, `orchestrator/runner.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_pull_main_unavailable.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_task_component_places.py`

## orchestrator/pull_main.py

**Назначение:** Команда `pull-main`: подтяжка main в ветку задачи на `verifying` без

**Публичные функции:**
- `cmd_pull_main`

**Импортирует:** `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/pull.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_lease_run_task_command.py`, `tests/test_pull_conflict_marker_states.py`

## orchestrator/reference_cache.py

**Назначение:** Кэш справочника ядра проекта и единый вход К-3б `get_reference`.

**Публичные функции:**
- `branch_commit`
- `get_reference`
- `get_reference_for_target`
- `min_uses`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `scripts/core_reference.py`

**Импортируется:** `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/projects.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_merge_reference_step.py`, `tests/test_reference_command.py`

## orchestrator/release.py

**Назначение:** Команда `release`: операторское снятие lease задачи (SPEC T062).

**Публичные функции:**
- `cmd_release`

**Импортирует:** `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_release.py`

## orchestrator/repo_context.py

**Назначение:** Контекст проекта: клон, база, защищённые пути проекта, признак артели.

**Публичные функции:**
- `clone_path`
- `git`
- `is_artel`
- `path_or_none`
- `profile_of`
- `projects_root`
- `protected_paths`
- `resolve`
- `unresolved_reason`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/notes.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/providers/claude.py`, `orchestrator/reference_cache.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/suite_run.py`, `orchestrator/tz_check.py`, `orchestrator/workspace.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_acceptance_suite_profile.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_project_gh_address.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_project_protected_paths.py`, `tests/test_protected_paths_gate.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_reference_command.py`, `tests/test_repo_context.py`, `tests/test_task_component_places.py`, `tests/test_worktree_db_files.py`

## orchestrator/report.py

**Назначение:** Команда `report`: статический HTML-срез `state.db` + метрики гейтовой

**Публичные функции:**
- `cmd_report`
- `map_growth_calibration_median`
- `map_growth_cost_estimate`
- `map_growth_open_alerts`
- `map_size_table_rows`
- `token_rate_divergence`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/explore_metric.py`, `orchestrator/providers/base.py`, `orchestrator/providers/claude.py`, `orchestrator/retro.py`, `orchestrator/rounds.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_report.py`, `tests/test_report_project_label.py`, `tests/test_rounds.py`, `tests/test_token_rate_divergence.py`

## orchestrator/reporters/__init__.py

**Назначение:** Отчёты прогона тестов компонента: отчётчик пульта для Vitest и разбор отчётов в итог по каждому тесту (SPEC 01M590GJAF0EDV4NBC4C99MFVH).

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## orchestrator/reporters/outcome.py

**Назначение:** Итог прогона компонента из его отчёта (SPEC 01M590GJAF0EDV4NBC4C99MFVH, требования 1, 3, 5, 6, 18).

**Публичные функции:**
- `parse_junit`
- `parse_vitest`
- `summary_block`
- `summary_line`
- `verdict`

**Импортирует:** `orchestrator/project_profile.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_component_report_gates.py`, `tests/test_component_report_run.py`, `tests/test_guard_plank_bans.py`, `tests/test_outcome_integrity.py`

## orchestrator/retro.py

**Назначение:** Детерминированная генерация содержимого RETRO задачи (SPEC T043).

**Публичные функции:**
- `actor_costs`
- `build_done`
- `build_killed`
- `parse_total_cost`
- `task_token_breakdown`
- `task_token_total`
- `token_breakdown_by_actor`
- `token_totals_by_actor`
- `tokens_detail_text`
- `tokens_text`
- `total_tokens_text`
- `usd_text`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/explore_metric.py`, `orchestrator/report.py`, `orchestrator/snapshot.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_summarize.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_canary.py`, `tests/test_parent_task_division.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`

## orchestrator/retro_corpus.py

**Назначение:** Локальный кэш ретро-корпуса из локальных refs/artifacts/* (наполнить — `docs --fetch-all`)

**Публичные функции:**
- `rebuild_cache`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/targets.py`, `orchestrator/yamlmini.py`

**Импортируется:** `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_retro_corpus.py`

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
- `review_package_measurement`
- `snapshot_exclude`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/advance_gates/capacity.py`, `orchestrator/fsm.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_acceptance_file_time.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_project_profile_gates.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_task_component_places.py`, `tests/test_test_integrity_gate.py`

## orchestrator/role_prompt.py

**Назначение:** Миссия роли + бриф/ревью-пакет шага: сборка содержимого промпта, общего

**Публичные функции:**
- `docs_dir_note`
- `knowledge_hint_note`
- `mission_brief_package`
- `step_note_note`
- `suite_run_note`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/knowledge_cards.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_docs_dir_layout.py`, `tests/test_knowledge_command.py`, `tests/test_long_lived_manifest.py`, `tests/test_role_prompt_test_author_mission.py`

## orchestrator/roles.py

**Назначение:** Карта исполнителей из roles.yaml: состав скилов роли читается кодом.

**Публичные функции:**
- `load`
- `model_tier`
- `provider`
- `skills`
- `token_slots`

**Импортирует:** `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/canary.py`, `orchestrator/doctor/__init__.py`, `orchestrator/knowledge_cards.py`, `orchestrator/models.py`, `orchestrator/providers/__init__.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_guard.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_canary_sets.py`, `tests/test_codex_login_shell_path.py`, `tests/test_doctor_agent_roles.py`, `tests/test_model_sets.py`, `tests/test_models.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_roles_map_fixture.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_yaml_parsing.py`

## orchestrator/rounds.py

**Назначение:** Метрика «круги до кода»: аудиты SPEC, возвраты и эскалации задачи по

**Публичные функции:**
- `alert_text`
- `count`
- `over_threshold`
- `raise_once`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/alerts.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/report.py`, `tests/test_rounds.py`

## orchestrator/runner.py

**Назначение:** Запуск агента шага: промпт роли, окружение, попытки, исход, стоимость.

**Публичные функции:**
- `close_pump`
- `cmd_run`
- `cmd_run_and_advance`
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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/models.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/project_profile.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/roles.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/knowledge_cards.py`, `orchestrator/lease.py`, `orchestrator/notes.py`, `orchestrator/pause.py`, `orchestrator/pool_seal.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/review.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_detach_result.py`, `tests/test_canary_run_task.py`, `tests/test_codex_login_shell_path.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pytest_summary_pump.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_runner_role_environment.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_sandbox_retry_pause.py`, `tests/test_sandbox_time_with_sleep.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_project.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/schema.py

**Назначение:** Схема БД и миграции: DDL, `migrate(conn)`, `add_column`/`table_columns`.

**Публичные функции:**
- `add_column`
- `create_schema`
- `migrate`
- `table_columns`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/store.py`, `tests/test_merge_after.py`, `tests/test_observation_migration_regression.py`, `tests/test_pair_suspension_units.py`, `tests/test_parent_task_division.py`, `tests/test_steps_task_id_index.py`

## orchestrator/session.py

**Назначение:** Идентификатор сессии оркестратора — единая функция для всех команд

**Публичные функции:**
- `resolve_session_id`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/cycle_hint.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/watch.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_detached_cycle.py`, `tests/test_launch_observation_refusals.py`, `tests/test_observation_edges.py`, `tests/test_session.py`

## orchestrator/snapshot.py

**Назначение:** Коммит закрытия задачи (`done`/`killed`) — последний коммит RETRO в

**Публичные функции:**
- `closing_sha`
- `cmd_artifact_history_snapshots`
- `commit_closing`
- `history_snapshots`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_artifact_ref_sync.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_multitarget_invariants.py`, `tests/test_snapshot_history.py`

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

**Импортируется:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/doctor/__init__.py`, `orchestrator/pause.py`, `orchestrator/providers/claude.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/watch.py`, `scripts/guard.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_agent_log.py`, `tests/test_doctor.py`, `tests/test_model_tariffs.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_providers_codex.py`, `tests/test_pytest_summary_pump.py`, `tests/test_runner_role_model.py`, `tests/test_step_cost.py`, `tests/test_task_model_set_units.py`, `tests/test_token_rate_divergence.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/doctor/__init__.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/version.py`, `scripts/guard.py`, `scripts/stack_ci.py`, `tests/sandbox.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py`, `tests/test_agent_failure.py`, `tests/test_agent_prompt.py`, `tests/test_artel_bootstrap.py`, `tests/test_git_hooks.py`, `tests/test_invariants.py`, `tests/test_project_profile.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_role_prompt_test_author_mission.py`, `tests/test_runner_model_preflight.py`, `tests/test_stack.py`, `tests/test_stack_ci.py`, `tests/test_stack_optional_tools.py`, `tests/test_suite_run.py`, `tests/test_task_model_set_units.py`

## orchestrator/store.py

**Назначение:** Состояние задач: БД, журнал шагов, смена состояния, запросы по областям.

**Публичные функции:**
- `ack_alert`
- `acknowledge_observation`
- `active_pair_suspension`
- `add_observation_tasks`
- `advance_notified`
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
- `claim_observation`
- `counter_targets`
- `db`
- `db_readonly`
- `db_tracked_count`
- `db_usable`
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
- `journal_maxima`
- `last_model_tariff`
- `last_pair_resume_mark`
- `last_task_step_of`
- `latest_fixed_sha`
- `latest_green_canary_run`
- `lease_row`
- `matching_observation`
- `max_alert_id`
- `max_pair_verdict_id`
- `merge_lock_row`
- `merge_lock_rows`
- `merge_queue_rows`
- `next_task_number`
- `now`
- `observation`
- `observation_live_steps`
- `observation_steps_since`
- `observation_tasks`
- `observed_runs`
- `open_alert_exists`
- `open_alerts`
- `pair_verdicts_after`
- `peek_task_number`
- `project_merge_lock_row`
- `project_merge_queue_rows`
- `record_fixation`
- `record_model_tariff`
- `record_observed_run`
- `refusal_history`
- `register_observation`
- `release_lease`
- `release_merge_lock`
- `release_observation`
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
- `task_id_matches`
- `task_number`
- `task_state`
- `task_steps`
- `task_steps_since`
- `task_target`
- `total_estimate`
- `total_spent`
- `touch_claimed_observation`
- `touch_merge_lock_heartbeat`
- `touch_merge_queue_heartbeat`
- `touch_observation`
- `tree_db_files`
- `update_lease`
- `update_lease_pgid`
- `update_task`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/models.py`, `orchestrator/schema.py`, `orchestrator/session.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/alerts.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/cycle_hint.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/dry_run.py`, `orchestrator/explore_metric.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/pull_main.py`, `orchestrator/reference_cache.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/schema.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/test_rule_stats.py`, `tests/sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py`, `tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_brief_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_acceptance.py`, `tests/test_acceptance_file_time.py`, `tests/test_acceptance_suite_profile.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_branch_server_retry.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_drive.py`, `tests/test_canary_escalation_roles_storage.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_run_task.py`, `tests/test_canary_runs.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_coldstart.py`, `tests/test_component_checks.py`, `tests/test_component_report_gates.py`, `tests/test_cycle_hint.py`, `tests/test_detached_cycle.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doc_commit.py`, `tests/test_doc_commit_held_base.py`, `tests/test_doc_commit_suite_gate.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_draft_mr_commits.py`, `tests/test_dry_run.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_knowledge_command.py`, `tests/test_launch_observation_refusals.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_main_copy_watch.py`, `tests/test_merge_after.py`, `tests/test_merge_after_declared.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_lock_by_project.py`, `tests/test_merge_queue.py`, `tests/test_merge_reference_step.py`, `tests/test_model_sets.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_network_address_gate.py`, `tests/test_notes.py`, `tests/test_notes_apply.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_edges.py`, `tests/test_observation_migration_regression.py`, `tests/test_observation_notification.py`, `tests/test_pair_suspension_units.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_pin_update_stale_cycles.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_plank_run_edges.py`, `tests/test_preflight.py`, `tests/test_program_spend_reseed.py`, `tests/test_project_profile_gates.py`, `tests/test_project_protected_paths.py`, `tests/test_protected_paths_gate.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_pull_main_unavailable.py`, `tests/test_reference_command.py`, `tests/test_release.py`, `tests/test_report.py`, `tests/test_report_project_label.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_review_registry_gate.py`, `tests/test_role_commit_by_pult.py`, `tests/test_rounds.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_snapshot_history.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stale_cycles_start_precision.py`, `tests/test_stall_alerts.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_project.py`, `tests/test_step_refixation.py`, `tests/test_steps_task_id_index.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_db_tracking.py`, `tests/test_store_journal.py`, `tests/test_store_schema_migration_parity.py`, `tests/test_suite_duration.py`, `tests/test_suite_lock.py`, `tests/test_suite_run.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_timeout_checkpoint.py`, `tests/test_token_rate_divergence.py`, `tests/test_verifying_ceiling.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_worktree_db_files.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/suite_lock.py

**Назначение:** Замок полных прогонов `tests/` машины: одновременно идёт не больше

**Публичные функции:**
- `acquire`
- `adopt`
- `defer_journal`
- `deferrable`
- `deliver_journal`
- `describe`
- `directory`
- `hand`
- `held_by_me`
- `holder`
- `my_task_id`
- `path`
- `release`
- `wait_acquire`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/knowledge_cards.py`, `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/knowledge_cards.py`, `orchestrator/providers/codex.py`, `orchestrator/prune.py`, `orchestrator/suite_run.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_prune_abolished_rules.py`, `tests/test_suite_lock.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run_deferred_journal.py`

## orchestrator/suite_run.py

**Назначение:** Команда `suite-run <id> [--wait <минуты> | --failed]`: полный прогон

**Публичные функции:**
- `background`
- `cmd_suite_run`
- `parse`
- `render`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/session.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_summary_deselected.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_component_report_gates.py`, `tests/test_component_report_run.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_full_suite_reuse.py`, `tests/test_suite_run.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`

## orchestrator/targets.py

**Назначение:** Декларация целевых проектов из targets.yaml: запись target'а читается кодом.

**Публичные функции:**
- `check`
- `core_reference`
- `load`
- `long_lived_pair`
- `secret_env_names`
- `target`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/brief.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/notes.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/pull.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/report.py`, `orchestrator/retro_corpus.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/workspace.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_targets_knowledge.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_min_uses_field.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5fryvp4nf81vt00fyphpwjh_rerun_ban_check.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_acceptance_plank_layout_refusal.py`, `tests/test_acceptance_suite_profile.py`, `tests/test_component_checks.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_github_adapter.py`, `tests/test_long_lived_template_shape.py`, `tests/test_multitarget.py`, `tests/test_project_components.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_reference_command.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_targets_rerun_ban_wrapper.py`, `tests/test_workspace_clone_docs_refs.py`

## orchestrator/tz_check.py

**Назначение:** Механическая проверка содержания ТЗ в `new` по дереву проекта (SPEC

**Публичные функции:**
- `check`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/catalog.py`, `tests/test_tz_check.py`

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
- `observation_age`
- `observation_link_fresh`
- `observation_process_state`
- `safe_text`

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/agent_log.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/providers/claude.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor/observations.py`, `orchestrator/knowledge_cards.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_notification.py`, `tests/test_pytest_summary_pump.py`, `tests/test_watch.py`

## orchestrator/workspace.py

**Назначение:** Рабочая поверхность задачи: область проекта (ADR-0021 п.1, этап 2; до

**Публичные функции:**
- `area_consistent`
- `cmd_workspace`
- `cmd_worktree_db_clean`
- `ensure`
- `ensure_clone`
- `hooks_path`
- `inherit_identity`
- `on_task_branch`
- `path`
- `registered_paths`
- `remove`
- `repo`
- `set_clone_hooks`
- `task_repo`
- `task_target`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/appendix_tree.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/dry_run.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/knowledge_cards.py`, `orchestrator/notes.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/suite_run.py`, `orchestrator/tz_check.py`, `orchestrator/watch.py`, `tests/sandbox.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_branch_freshness_gate.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_division_parent_cleanup.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_draft_mr_remote_base_args.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_autogate.py`, `tests/test_kill_cleanup.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_transitions.py`, `tests/test_multitarget_invariants.py`, `tests/test_network_address_gate.py`, `tests/test_plank_helper.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_reference_command.py`, `tests/test_review_package.py`, `tests/test_role_commit_by_pult.py`, `tests/test_step_autocommit.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`, `tests/test_workspace_clone_docs_refs.py`, `tests/test_worktree_db_files.py`

## orchestrator/yamlmini.py

**Назначение:** Подмножество YAML, которого достаточно системе: frontmatter и roles.yaml.

**Публичные функции:**
- `frontmatter`
- `mapping`
- `scalar`

**Импортирует:** —

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/artifacts.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/gates.py`, `orchestrator/knowledge_cards.py`, `orchestrator/models.py`, `orchestrator/preflight.py`, `orchestrator/pull.py`, `orchestrator/retro_corpus.py`, `orchestrator/roles.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_canary_sets.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_model_sets.py`, `tests/test_roles_map_fixture.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_yaml_parsing.py`

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
- `queue_wait`
- `refusal`
- `release_claim`
- `task_zone_paths`
- `wait_enter_action`
- `wait_exit_action`
- `wait_interrupted_action`
- `wait_minutes`

**Импортирует:** `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/project_profile.py`, `orchestrator/runner.py`, `scripts/guard.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_auto_cycle.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`

## scripts/ci_protected_paths.py

**Назначение:** Сверка изменённых PR файлов со списком защищённых путей БАЗЫ сравнения —

**Публичные функции:**
- `base_protected_paths`
- `changed_files`
- `is_violation`
- `main`
- `merge_first_parent`
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

**Импортируется:** `orchestrator/ci.py`, `orchestrator/pull.py`, `tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_ci_push_class.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`

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

**Импортируется:** `orchestrator/brief.py`, `orchestrator/fsm_postmerge.py`, `tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_codebase_map_root.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_capacity_gate_map.py`, `tests/test_codebase_map.py`

## scripts/core_reference.py

**Назначение:** Справочник ядра проекта: «как пользоваться» модулями коммита, разбором `ast`.

**Публичные функции:**
- `build`
- `build_report`
- `disk_sources`
- `header_fields`
- `main`
- `reference_sha`
- `setting_fields`

**Импортирует:** —

**Импортируется:** `orchestrator/reference_cache.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_generator.py`, `tests/test_core_reference.py`

## scripts/guard.py

**Назначение:** Guard: валидатор СТРУКТУРЫ артефактов задач (frontmatter + обязательные

**Публичные функции:**
- `acceptance_test_files`
- `acceptance_traceability_errors`
- `appendix_rename_header_error`
- `appendix_unprotected_path_error`
- `artifact_disk_read_errors_from_files`
- `assertion_changes`
- `behavior_change_errors`
- `behavior_change_items`
- `behavior_change_lines`
- `behavior_change_refusals`
- `changed_classes`
- `changed_test_assertions`
- `check`
- `check_content`
- `ci_marker_wording_ok`
- `count_test_methods`
- `division_section_errors`
- `escalation_status_errors`
- `extraneous_task_root_files_in`
- `first_comment`
- `group_line_errors_from_files`
- `has_redness_marker`
- `id_format_patterns`
- `id_format_sample_errors`
- `indented_ac_marker_errors_from_files`
- `is_extraneous_acceptance_test_file`
- `is_extraneous_task_root_file`
- `is_labelled_plank_test`
- `is_long_lived_test_path`
- `is_step_note`
- `is_task_passport`
- `is_test_id_form`
- `literal_pair_keys`
- `long_lived_errors_from_files`
- `long_lived_example`
- `long_lived_group_errors`
- `long_lived_path_prefix`
- `long_lived_plank_errors`
- `long_lived_sign_hits`
- `main`
- `mentioned_paths`
- `merge_after_form_errors`
- `merge_after_items`
- `method_literal_keys`
- `module_docstring`
- `network_address_errors_from_files`
- `network_address_hits`
- `network_address_host`
- `parametrize_variants`
- `parse_behavior_change_line`
- `parse_division_subsections`
- `parse_long_lived_manifest`
- `parse_replaced_test_line`
- `plan_appendices`
- `plan_appendix_errors`
- `plank_ban_errors`
- `plank_file_group`
- `plank_has_group_lines`
- `plank_test_names`
- `protected_zones`
- `qualified_test_methods`
- `questions_matrix_errors`
- `redness_marker_errors_from_files`
- `registry_errors`
- `registry_record_errors`
- `registry_records`
- `registry_table_rows`
- `render_long_lived_manifest`
- `replaced_test_items`
- `replaced_tests_errors`
- `requires_ac_markup`
- `requires_budget_field`
- `requires_registry`
- `requires_split_assessment`
- `requires_zones`
- `resolved_skip_markers`
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
- `skip_label_values`
- `spec_ac_errors`
- `spec_audit_field_errors`
- `spec_budget_field_errors`
- `spec_merge_after_errors`
- `spec_path_errors`
- `spec_unclassified_paths`
- `spec_zones_errors`
- `split_assessment_errors`
- `split_signal_names`
- `step_note_name`
- `subclass_names`
- `test_assertions`
- `test_functions_without_mutation_claim`
- `test_skip_markers`
- `traceability_errors_from_content`
- `unclassified_paths`
- `unclassified_paths_refusal`
- `value_pair_keys`
- `weakened_helpers`
- `zone_items`
- `zone_line_items`

**Импортирует:** `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/appendix_tree.py`, `orchestrator/artel.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/merge_after.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/pull.py`, `orchestrator/retro.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/tz_check.py`, `orchestrator/version.py`, `scripts/plan_appendix_ci.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_guard.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_async_test_method.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend_long_lived.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_appendix_tree.py`, `tests/test_artifact_materialization.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_plank_rule.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_guard_artifact_branch_mode.py`, `tests/test_guard_artifact_disk_read.py`, `tests/test_guard_assertion_changes.py`, `tests/test_guard_division_section.py`, `tests/test_guard_extraneous_acceptance_files.py`, `tests/test_guard_helper_scope.py`, `tests/test_guard_helper_scope_modes.py`, `tests/test_guard_mutation_claim.py`, `tests/test_guard_parametrize_variants.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_plank_bans.py`, `tests/test_guard_plank_rule_parsing.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_guard_test_ast.py`, `tests/test_guard_test_groups.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_template_shape.py`, `tests/test_network_address_gate.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_project_profile.py`, `tests/test_project_protected_paths.py`, `tests/test_protected_test_settings.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_review_registry_gate.py`, `tests/test_role_commit_by_pult.py`, `tests/test_step_note_contract.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_version.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_line_parse.py`

## scripts/plan_appendix_ci.py

**Назначение:** Приложения PLAN задачи на рабочем дереве раннера CI ветки задачи (SPEC

**Публичные функции:**
- `apply_appendix`
- `check_workflow`
- `check_workflow_on_run`
- `condition_push_only`
- `docs_ref_for_branch`
- `in_base`
- `main`
- `plan_text`
- `remote_docs_refs`
- `run`
- `task_branch`
- `tested_ref`
- `workflow_errors`

**Импортирует:** `scripts/guard.py`

**Импортируется:** `tests/test_plan_appendix_ci.py`

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

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/__init__.py

**Назначение:** нет docstring

**Публичные функции:** (нет)

**Импортирует:** `tests/direct_git.py`

**Импортируется:** —

## tests/direct_git.py

**Назначение:** Git в процессах тестов — напрямую, без системной обёртки xcrun.

**Публичные функции:**
- `prefer_direct_git`

**Импортирует:** —

**Импортируется:** `tests/__init__.py`, `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py`

## tests/fd_wait.py

**Назначение:** Ожидание готовности дескриптора на чтение без предела номера (SPEC

**Публичные функции:**
- `high_fd`
- `select_limited`
- `wait_readable`

**Импортирует:** —

**Импортируется:** `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_fd_wait.py`

## tests/mandate_matrix.py

**Назначение:** Матрица неослабления во входах тестов, подающих `answer` мандат или

**Публичные функции:**
- `matrix`
- `matrix_file`
- `with_matrix`

**Импортирует:** —

**Импортируется:** `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_answer.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_mandate_matrix_form.py`, `tests/test_mandate_profile_scope.py`, `tests/test_mandate_test_id.py`

## tests/sandbox.py

**Назначение:** Общая тестовая песочница.

**Публичные функции:**
- `alias_docs_ref_to_branch`
- `artel_target_entry`
- `assert_acceptance_run_called`
- `capture`
- `capture_new_task_id`
- `claude_only_popen`
- `claude_only_run`
- `clone_artel_from_origin`
- `declare_target`
- `declared_artel_profile`
- `declared_without_profile`
- `disk_backed_ls_tree_files`
- `disk_backed_show`
- `event`
- `fake_git`
- `fake_git_for`
- `fake_keychain_token`
- `init_bare_origin`
- `is_claude_call`
- `isolate_keychain_and_role`
- `isolate_orphan_sweep`
- `isolate_pult_db`
- `link_artel_clone_to_root`
- `make_project_repo`
- `network_guarded_real_run`
- `patch_pult_sleep`
- `patch_retry_pause`
- `patch_sleep`
- `resilient_tmp_cleanup`
- `role_map_fixture`
- `route_url_to_bare`
- `seed_artel_clone_stub`
- `seed_artel_targets`
- `seed_developer_brief_fixtures`
- `strip_dash_c`
- `sync_spec_from_worktree`
- `wait_processes_gone`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/models.py`, `orchestrator/project_profile.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`, `tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py`, `tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_codebase_map_root.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py`, `tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_brief_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_questions_matrix.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmpmz7ppcn3jwx75rtjzqn_merge_base_choice.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cli.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_acceptance.py`, `tests/test_acceptance_collect.py`, `tests/test_acceptance_pycache.py`, `tests/test_acceptance_seed_repeat.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_appendix_tree.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_branch_server_retry.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_canary_detach_result.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_run_task.py`, `tests/test_canary_runs.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_fixture.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_project_gh_address.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_codex_login_shell_path.py`, `tests/test_coldstart.py`, `tests/test_component_checks.py`, `tests/test_cycle_hint.py`, `tests/test_detached_cycle.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doc_commit.py`, `tests/test_doc_commit_held_base.py`, `tests/test_doc_commit_suite_gate.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_done_branch_cleanup.py`, `tests/test_draft_mr_commits.py`, `tests/test_dry_run.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_full_suite_reuse.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_github_adapter.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_schema.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_knowledge_command.py`, `tests/test_launch_observation_refusals.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_main_copy_watch.py`, `tests/test_merge_after.py`, `tests/test_merge_after_declared.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`, `tests/test_merge_lock_by_project.py`, `tests/test_merge_queue.py`, `tests/test_merge_reference_step.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_network_address_gate.py`, `tests/test_notes.py`, `tests/test_notes_apply.py`, `tests/test_notes_row_format.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_edges.py`, `tests/test_outcome_integrity_added_lines.py`, `tests/test_pair_suspension_units.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_pin_update_stale_cycles.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_preflight.py`, `tests/test_profile_layers_declared.py`, `tests/test_program_spend_reseed.py`, `tests/test_project_profile_gates.py`, `tests/test_protected_paths_gate.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_prune_abolished_rules.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_pytest_summary_pump.py`, `tests/test_release.py`, `tests/test_repo_context.py`, `tests/test_report.py`, `tests/test_report_project_label.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_role_commit_by_pult.py`, `tests/test_roles_map_fixture.py`, `tests/test_rounds.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_sandbox.py`, `tests/test_sandbox_determinism_helpers.py`, `tests/test_sandbox_retry_pause.py`, `tests/test_sandbox_time_with_sleep.py`, `tests/test_session.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_snapshot_history.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stack.py`, `tests/test_stack_optional_tools.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_stale_cycles_start_precision.py`, `tests/test_stall_alerts.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_steps_task_id_index.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_db_tracking.py`, `tests/test_store_journal.py`, `tests/test_suite_duration.py`, `tests/test_suite_lock.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_timeout_checkpoint.py`, `tests/test_token_rate_divergence.py`, `tests/test_vitest_summary_pump.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_workspace_clone_docs_refs.py`, `tests/test_worktree_db_files.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

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

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/idgen.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/mandate_matrix.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_docs_ref_deleted_refusal.py`

## tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py

**Назначение:** Команда `plank-run`: штатный локальный прогон планки задачи в шаге роли.

**Публичные функции:**
- `is_pytest_call`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/role_prompt.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

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

## tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py

**Назначение:** Мандат на тесты: элемент-класс покрывает находки о методах класса, и

**Публичные функции:**
- `class_source`
- `random_elements`
- `seeded`
- `vanished`
- `word`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/answer.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/mandate_matrix.py`, `tests/sandbox.py`

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

## tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py

**Назначение:** Вызов git-примитивов пульта без явного репозитория — только по перечню.

**Публичные функции:**
- `allowed`
- `calls_without_repo`
- `has_explicit_repo`
- `primitive_table`
- `violations`

**Импортирует:** —

**Импортируется:** —

## tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py

**Назначение:** Область проекта (ADR-0021, этап 2): клон проекта и рабочие копии задач

**Публичные функции:**
- `green_runs`
- `red_runs`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/keychain.py`, `orchestrator/notes.py`, `orchestrator/plank_run.py`, `orchestrator/repo_context.py`, `orchestrator/retro_corpus.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_invariants.py`

## tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py

**Назначение:** Шаг разработчика: указание Оператора в брифе (AC-6) и подтяжка `main` в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/answer.py`, `orchestrator/brief.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py

**Назначение:** Указание Оператора роли: `answer` в `in_dev`/`review` с файлом без строк

**Публичные функции:**
- `answer_rel`
- `random_whitespace`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/answer.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/projects.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/mandate_matrix.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py

**Назначение:** Сторож: тесты `tests/` не подменяют `time.sleep` на весь процесс.

**Публичные функции:**
- `global_sleep_patches`
- `scan_tests_tree`

**Импортирует:** —

**Импортируется:** `tests/test_invariants.py`

## tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py

**Назначение:** Ворота мержа и приложение PLAN, уже наложенное в подтянутом `main`.

**Публичные функции:**
- `names_appendix`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py

**Назначение:** Сценарий CI `scripts/plan_appendix_ci.py`: приложения PLAN задачи на дереве раннера.

**Публичные функции:**
- `git_subcommand`
- `names_appendix`

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py

**Назначение:** Реакция цикла `auto` на отказ предварительного `advance` — по классу отказа.

**Публичные функции:**
- `new_seed`

**Импортирует:** `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py

**Назначение:** `artel.py run <id>` после успешного шага роли один раз продвигает задачу.

**Публичные функции:**
- `plan_text`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/keychain.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py

**Назначение:** Мандат Оператора «Расширение зон разрешено: …» из ANSWER-n.md доходит до

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/zones.py`, `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/mandate_matrix.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py

**Назначение:** Клон проекта получает ссылки документов задач при заведении; сверка

**Публичные функции:**
- `docs_ref`
- `random_task_id`

**Импортирует:** `orchestrator/config.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py

**Назначение:** Итоговая строка pytest из результата инструмента шага роли — в журнал задачи.

**Публичные функции:**
- `claude_lines`
- `codex_lines`
- `framed`
- `plain_output`
- `pytest_output`
- `random_marker`
- `random_summary`
- `random_task_id`

**Импортирует:** `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py

**Назначение:** Дозор показывает ход живого шага роли: класс `pytest`, сводка, предупреждения, граница строк.

**Публичные функции:**
- `claude_call_line`
- `marker`
- `period_sec`
- `polls_in`
- `random_task_id`
- `ts_ago`
- `usage_line`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/session.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py

**Назначение:** `amend-tests` отправляет голову кодовой ветки в origin; `verifying` сам

**Публичные функции:**
- `completed`
- `fake_gh_for`

**Импортирует:** `orchestrator/amend.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/projects.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py

**Назначение:** Разбор аргументов `answer` (отказ на ключ, отсутствующий файл, лишние

**Публичные функции:**
- `bare_approve`
- `blocks`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py

**Назначение:** Мандат Оператора «Зависимости мержа: …» в ANSWER-n.md (AC-11, AC-12).

**Публичные функции:**
- `ids_of`

**Импортирует:** `orchestrator/answer.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py

**Назначение:** Проверка формы поля `merge_after` SPEC структурной проверкой guard (AC-1).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/idgen.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py

**Назначение:** Удержание `approve` на гейте мержа по зависимостям `merge_after` (AC-6..AC-8).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py

**Назначение:** Канал PLAN: смена `merge_after` на переходе `in_dev -> verifying` (AC-9, AC-10).

**Публичные функции:**
- `ids_of`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py

**Назначение:** Проверка `merge_after` по БД на `approve` гейта SPEC (AC-2..AC-5).

**Публичные функции:**
- `ids_of`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py

**Назначение:** Зависимости мержа в выводе `status` и `show` (AC-13, AC-14).

**Публичные функции:**
- `ids_of`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py

**Назначение:** Заявление зависимостей мержа строкой ТЗ «Порядок: после …» при `new --tz` (AC-1..AC-8).

**Публичные функции:**
- `ids_of`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py

**Назначение:** Сверка поля `merge_after` SPEC с заявленным Оператором на `approve` гейта SPEC (AC-9..AC-13).

**Публичные функции:**
- `ids_of`
- `no_code_tree`

**Импортирует:** `orchestrator/answer.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py

**Назначение:** Смена ожидания в существующем тесте по разделу SPEC «Меняемое поведение»:

**Публичные функции:**
- `counts_pattern`
- `fixture_counts`
- `fixture_source`
- `is_pytest_node`
- `is_worktree_add`
- `method_text`
- `pairs_text`
- `segment`
- `timeout_rule`
- `word`
- `worktree_add_path`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/artifact_source.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/projects.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m45fjd46bx45vhc36s4vs9qn_section_form.py

**Назначение:** Форма раздела SPEC «Меняемое поведение» в CLI `scripts/guard.py` (AC-1,

**Публичные функции:**
- `word`

**Импортирует:** —

**Импортируется:** —

## tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py

**Назначение:** Проверки тестов без профиля или без контекста проекта — отказ, а не

**Публичные функции:**
- `stop_at_pause`

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gates.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py

**Назначение:** Профиль тестов проекта — поле `test_profile` записи `targets.yaml`

**Публичные функции:**
- `base_entry`
- `random_profile`
- `render_entry`

**Импортирует:** `orchestrator/config.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py

**Назначение:** Подсветка защищённых путей в черновике MR задачи внешнего проекта — по

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py

**Назначение:** Гейты выхода из `in_dev` по перечню защищённых путей проекта задачи:

**Публичные функции:**
- `edit_diff`
- `new_file_diff`

**Импортирует:** `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`

## tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py

**Назначение:** Гейт мержа по перечню защищённых путей проекта задачи: защищённые пути

**Публичные функции:**
- `new_file_diff`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py

**Назначение:** Сторож зеркала: поле `no_paths` записи `artel` реального `targets.yaml`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py

**Назначение:** Защищённые зоны ТЗ (`new`) и SPEC (гейт SPEC) — по перечню защищённых

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py

**Назначение:** Команда `suite-run`: полный прогон тестов проекта задачи из шага роли.

**Публичные функции:**
- `failing`
- `gated`
- `node_id`
- `passing`
- `phrase_number`
- `pid_alive`
- `skipped`
- `standalone`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py

**Назначение:** Сценарий CI `scripts/plan_appendix_ci.py` на прогонах pull_request веток задач.

**Публичные функции:**
- `names_number`

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py

**Назначение:** Полный набор `tests/` на автогейте приёмки и на `approve` в `acceptance`

**Публичные функции:**
- `names_number`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py

**Назначение:** Команда `suite-run`: прогон ветки задачи артели на временном дереве

**Публичные функции:**
- `names_number`
- `pid_alive`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py

**Назначение:** Один полный прогон tests/ на машину; исходы полного прогона на гейте мержа.

**Публичные функции:**
- `pid_alive`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py

**Назначение:** Статус CI коммита называет событие и номер workflow-прогона у каждой

**Публичные функции:**
- `completed`
- `mentions`
- `segments`
- `stamp`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py

**Назначение:** Артель идёт по общему потоку документов и свежести, как любой проект.

**Публичные функции:**
- `docs_rel`
- `fixation_fields`
- `fixation_value`
- `run_cmd`
- `word`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/docs_fetch.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py

**Назначение:** Оставленные развилки артели узнают её одной функцией-признаком `repo_context`.

**Публичные функции:**
- `artel_also_for`
- `run_cmd`
- `subject_target`
- `word`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/docs_fetch.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/repo_context.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py

**Назначение:** Сквозной поток задачи внешнего проекта: гейты `in_dev`, подтяжка, гейт мержа.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m484rnv3qbdy3b0m16j916zp_gate_target_guard.py

**Назначение:** Сторож: в модулях проверок пункта 8 нет прямого сравнения с `config.DEFAULT_TARGET`.

**Публичные функции:**
- `default_target_comparisons`
- `guarded_files`
- `is_default_target_node`
- `module_level_insert_line`
- `report`
- `scan`

**Импортирует:** —

**Импортируется:** —

## tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py

**Назначение:** Стоп-кран волны — механика пульта: считает и блокирует задачи всех проектов.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py

**Назначение:** Замок зон действует для задачи любого проекта — внутри её проекта.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py

**Назначение:** Повторные прогоны долгоживущих файлов задачи, несущих случайное зерно, на рубеже `in_dev -> verifying` (AC-4..AC-7).

**Публичные функции:**
- `word`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/projects.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py

**Назначение:** Сторож: шаг роли в песочнице не спит настоящим `time.sleep` в паузе повтора агента.

**Публичные функции:**
- `transient_signatures`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py

**Назначение:** Действующий предел полного прогона tests/ на гейте мержа и в `suite-run`.

**Публичные функции:**
- `kill_group`
- `pid_alive`
- `standalone`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py

**Назначение:** Подполе `full_suite_timeout_sec` профиля тестов проекта и его строка в `doctor`.

**Публичные функции:**
- `popen_without_role_cli`
- `standalone`
- `with_limit`

**Импортирует:** `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py

**Назначение:** Итоги базы suite-run по содержимому дерева.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m48wt5x7zc7332drh85vy19d_excluded_reads.py

**Назначение:** Сторож чтения путей, исключённых из ключа базы.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py

**Назначение:** Тесты предела полного прогона устойчивы к наличию подполя профиля.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`

**Импортируется:** —

## tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py

**Назначение:** Повторное использование полного прогона по содержимому дерева.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py

**Назначение:** Независимость копий песочниц и ветка bare origin.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m490tdwemdq700vxtkyanf7k_passport_guard.py

**Назначение:** Паспорт задачи без frontmatter и `scripts/guard.py` — режим `--all` и

**Публичные функции:**
- `passport_text`
- `random_task_id`
- `valid_tz_text`

**Импортирует:** —

**Импортируется:** —

## tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py

**Назначение:** Полный набор CI ветки задачи — один раз на sha: пульт не засчитывает

**Публичные функции:**
- `completed`
- `stamp`
- `workflow_check_names`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/repo_context.py`

**Импортируется:** —

## tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py

**Назначение:** Замер времени долгоживущих файлов и вывод результата в двух текстах.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/fsm_autogate.py`, `orchestrator/review.py`

**Импортируется:** —

## tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py

**Назначение:** Переход с долгоживущими файлами записывает время их прогона.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`

**Импортируется:** —

## tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py

**Назначение:** Свойства полной карты, проекции и брифов после удаления секций tests/.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/store.py`, `scripts/codebase_map.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py

**Назначение:** Проверки нагрузки машины и роста времени на тест через doctor.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py

**Назначение:** Наблюдаемые записи и сообщения полного прогона.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py

**Назначение:** Публичная команда canary: отвязанный запуск, результат и справка.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py

**Назначение:** Doctor наблюдает временные каталоги канарейки и чинит только сироты.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py

**Назначение:** Уборка процессов клона и запись исхода сигнала через публичную команду канарейки.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py

**Назначение:** Канарейка пропускает полный набор только на приёмке своего клона.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gates.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py

**Назначение:** Маркер полного набора проходит только в процесс ведения канарейки.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py

**Назначение:** Гейт приёмки использует зелёный CI дерева, которое он проверяет.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gates.py`, `orchestrator/github_adapter.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py

**Назначение:** Диагностика старого фонового hook и инструкция Оператора.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4c954hbjwegd3azs7q3eha4_documentation.py

**Назначение:** Правило об общей для чатов позиции подтверждения.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py

**Назначение:** Позиции просмотра и подтверждения наблюдения через публичные команды.

**Публичные функции:**
- `watch_time_stand_in`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py

**Назначение:** Публичный дозор: уведомления, остановка, захват и отказ в песочнице.

**Публичные функции:**
- `watch_time_stand_in`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py

**Назначение:** Читатели БД пульта на непригодном и отсутствующем файле `config.DB`.

**Публичные функции:**
- `drop_db_files`
- `write_unusable`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py

**Назначение:** Файлы БД пульта в дереве полного прогона: отказ, ключ кэша, след прогона.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py

**Назначение:** Команда `worktree-db-clean` и сигнал `doctor` о файлах БД пульта в рабочей копии.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py

**Назначение:** Подсказка запуска и строка перезапуска `pin-update` — одна форма с `--observation`.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/lease.py`, `orchestrator/session.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py

**Назначение:** Отсоединённый `run`/`auto` и `observe register` без пары клиент/чат.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4g8kpp8dvnbcpgcapsvmakz_codebase_map_root.py

**Назначение:** Генератор карты кода пишет карту в дерево самого сценария, не текущего каталога.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `scripts/codebase_map.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py

**Назначение:** Сторож главной копии пульта: алерт об изменениях, появившихся за время шага роли.

**Публичные функции:**
- `claims_authorship`
- `random_task_id`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py

**Назначение:** Уборка сирот не трогает каталог origin канарейки, ещё не получивший маркер владельца.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/liveness.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py

**Назначение:** Гейт неослабления тестов видит утверждения в унаследованных помощниках и в

**Публичные функции:**
- `base_module`
- `word`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py

**Назначение:** Деление задачи на гейте SPEC переписывает `merge_after` задач, зависящих

**Публичные функции:**
- `division_spec`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py

**Назначение:** Очередь зоны решает, чей первый шаг разработчика стартует на свободной зоне.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py

**Назначение:** `amend-tests` проводит правку планки, импортирующей помощник пульта `_pult.py`.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/projects.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py

**Назначение:** `plank-run` не стирает молча незафиксированную правку планки в рабочей копии кода.

**Публичные функции:**
- `is_pytest_call`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py

**Назначение:** Рубеж `in_dev -> verifying` и приложения PLAN: прогон планки и долгоживущих файлов на дереве с приложениями, именованный отказ неприменимого, пропуск уже наложенного в базе.

**Публичные функции:**
- `names_number`
- `word`

**Импортирует:** `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/projects.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py

**Назначение:** Гейт мержа и приложение PLAN, уже наложенное в подтянутом `main`: запись журнала общей формы «приложение PLAN уже в базе».

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py

**Назначение:** Признание «приложение PLAN уже в базе» у дерева полного прогона (`appendix_tree.suite_tree`) и у CI ветки (`scripts/plan_appendix_ci.py`) и сверка их ответов.

**Публичные функции:**
- `names_number`

**Импортирует:** `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/appendix_tree.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py

**Назначение:** Сбой подсчёта членов группы не выдаётся за пустую группу.

**Публичные функции:**
- `failing_ps`
- `is_ps_command`
- `path_with_real_ps`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/liveness.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jmmh70nwjg72g422bfy1kc_bare_python3_guard.py

**Назначение:** Сторож: в коде пульта нет дочерних вызовов голого `python3`.

**Публичные функции:**
- `bare_python3_calls`
- `injected_call`
- `pult_modules`

**Импортирует:** —

**Импортируется:** —

## tests/test_01m4jmmh70nwjg72g422bfy1kc_brief_map_interpreter.py

**Назначение:** Регенерация стухшей карты кодовой базы при сборке брифа при подложном `python3` первым в PATH.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py

**Назначение:** Регенерация карты кодовой базы после мержа при подложном `python3` первым в PATH.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py

**Назначение:** Авторазрешение конфликта подтяжки по карте кодовой базы: интерпретатор регенерации и запись журнала о сбое шага.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_pull_autoresolve_step_journal.py`

## tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py

**Назначение:** Правило сетевых адресов `tests/`: проверка долгоживущих файлов и инвариант 35.

**Публичные функции:**
- `address_errors`
- `fixture_source`
- `invariant_catches`
- `random_dns_host`
- `random_tail`
- `task_id`
- `url`

**Импортирует:** `orchestrator/config.py`, `scripts/guard.py`, `tests/test_invariants.py`

**Импортируется:** —

## tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py

**Назначение:** Предел полного прогона `notes` из профиля и сигнал «длительность близка к пределу».

**Публичные функции:**
- `passed_limit`
- `probe_suite`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/appendix_tree.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py

**Назначение:** `amend-tests` применяет признак сетевых адресов к долгоживущим файлам только у артели.

**Публичные функции:**
- `long_lived_text`
- `nobody_is_artel`

**Импортирует:** `orchestrator/amend.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/projects.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py

**Назначение:** ANSWER Оператора в `in_dev` — основание шага developer, а не переход по готовым артефактам.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py

**Назначение:** Команда шага роли на Codex открывает на запись каталог `suite-run` и

**Публичные функции:**
- `add_dir_values`
- `is_within`
- `real`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/models.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py

**Назначение:** `suite-run` из процесса роли без права записи в БД пульта: итог, отчёт,

**Публичные функции:**
- `is_within`
- `passed_limit`
- `probe_suite`
- `readonly_db`
- `real`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py

**Назначение:** Мерж не кладёт в main проекта ни каталог документов задачи, ни её RETRO:

**Публичные функции:**
- `plan_text`
- `plank_text`
- `spec_text`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py

**Назначение:** Команда Оператора `artifact-history-snapshots`: исторические снимки ссылок документов для каталогов задач `origin/main` без ссылки.

**Публичные функции:**
- `ref_of`
- `task_rel`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/docs_fetch.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py

**Назначение:** Аудит SPEC — шаг роли spec_auditor между сдачей SPEC аналитиком и гейтом SPEC: вход, бриф, глубина по сигналам, выход по вердикту, свежесть и привязка вердикта, возвраты аналитику, эскалация, вердикт на гейте, флаг approve и повторный аудит.

**Публичные функции:**
- `blob_sha`
- `path_signal_categories`
- `word`

**Импортирует:** `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/keychain.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py

**Назначение:** Аудит SPEC — свойства без прогона шагов: роль состояния spec_audit, модель аудитора под набором задачи, схема артефакта SPEC-AUDIT.md в guard, белый список каталога задачи, состояние spec_audit в перечнях пульта.

**Публичные функции:**
- `audit_text`
- `random_task_id`
- `word`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/merge_after.py`, `orchestrator/models.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py

**Назначение:** Сверка раздела SPEC «Меняемое поведение» на `approve` гейта SPEC: «было»

**Публичные функции:**
- `fixture_source`
- `method`
- `word`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/projects.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4nz5kt0px0rywtstn1xefs5_questions_matrix.py

**Назначение:** Матрица последствий в QUESTIONS.md: отказ guard по форме вариантов и

**Публичные функции:**
- `cword`
- `default_line`
- `full_batch`
- `full_question`
- `label_line`
- `question_head`
- `questions_doc`
- `variant_lines`

**Импортирует:** `orchestrator/fsm.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py

**Назначение:** Матрица неослабления — обязательная форма мандата в `answer` и `zones-extend` (ADR-0022 п.4).

**Публичные функции:**
- `names`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py

**Назначение:** Раздел отчёта `report` о расходе шагов test_author за окно `OPERATOR_WINDOW_DAYS`: стоимость, токены, вызовы инструментов по видам, прогоны pytest и их время, вызовы Write, файлы и строки отдельно для `tests/` и `acceptance_tests/`, «н/д» для обрезанного пути, пропавшего файла и провайдера не Claude; ни одного вызова git (AC-12).

**Публичные функции:**
- `author_section`
- `standalone`
- `text_of`
- `tool_line`
- `word`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/config.py`, `orchestrator/report.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py

**Назначение:** Наблюдение неослабления: двусторонний прогон КАЖДОГО изменённого метода на переходе `in_dev -> verifying` — место упавшего утверждения в `Outcome`, запись «двусторонний прогон (наблюдение)», признак «в изменённых строках», неизменность вердикта гейта, флаг и предел времени, сводка наблюдения в отчёте (AC-1..AC-10, AC-13, AC-14).

**Публичные функции:**
- `config_source_constants`
- `fixture_source`
- `flag_of`
- `has_location`
- `is_pytest_node`
- `is_worktree_add`
- `leaves`
- `limit_names`
- `line_of`
- `location_found`
- `location_literals`
- `method_text`
- `nodes`
- `observation_flags`
- `outcome_extra`
- `pairs_text`
- `recording_rule`
- `report_rows`
- `row_count`
- `sandbox_disabled_names`
- `segment`
- `side_part`
- `timeout_rule`
- `word`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/artifact_source.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/projects.py`, `orchestrator/report.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py

**Назначение:** Предпроверка выхода из `tests_writing`: команда `artel.py preflight <id>`.

**Публичные функции:**
- `docstring_nodes`
- `foreign_guard_imports`
- `git_subcommand`
- `guard_bindings`
- `guard_functions`
- `headers`
- `long_lived_source`
- `module_tree`
- `plank_source`
- `preflight_guard_names`
- `referenced_guard_names`
- `refused_lines`
- `sections`
- `spec_text`
- `transition_guard_calls`
- `ulid`
- `word`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/artel.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4pmpmz7ppcn3jwx75rtjzqn_merge_base_choice.py

**Назначение:** Выбор базы сравнения джоба `protected-paths`: первый родитель

**Публичные функции:** (нет)

**Импортирует:** `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py

**Назначение:** Итог прогона pytest и провал внутри subTest — в разборах пульта.

**Публичные функции:**
- `broken_output`
- `header`
- `phrase_number`
- `plain_progress`
- `report_numbers`
- `rule`
- `summary_line`
- `xdist_progress`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py

**Назначение:** Вердикт CI на `verifying` и гейте мержа строится по проверкам прогонов

**Публичные функции:**
- `completed`
- `stamp`

**Импортирует:** `orchestrator/ci.py`

**Импортируется:** —

## tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py

**Назначение:** Команда Оператора `pull-main`: подтяжка main в ветку задачи на `verifying`.

**Публичные функции:**
- `pull_main_module`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/ci_push_class.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_pull_main_unavailable.py`

## tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py

**Назначение:** Бриф аудитора SPEC несёт решения Оператора, переданные причиной возврата с гейта SPEC.

**Публичные функции:**
- `label`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/brief.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py

**Назначение:** Отвеченный батч вопросов аналитика не эскалирует задачу повторно:

**Публичные функции:**
- `answered_actions`
- `disk_path`
- `sha256_text`

**Импортирует:** `orchestrator/artifact_source.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py

**Назначение:** Команда `answer` на гейте SPEC: приём только мандата тестов, именованные отказы, рубеж окружения роли, lease, прежний отказ прочих состояний (AC-2, AC-3, AC-4, AC-5, AC-9, AC-10).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/mandate_matrix.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py

**Назначение:** Мандат тестов, данный `answer` на гейте SPEC, — сквозь approve, reject и автокоммит аналитика до рубежей неослабления (AC-1, AC-6, AC-7).

**Публичные функции:**
- `fixture_source`
- `word`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/answer.py`, `orchestrator/artifact_source.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/mandate_matrix.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py

**Назначение:** Проект задачи: флаг `new --target`, однозначный выбор проекта и клон в `target-init`.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/projects.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py

**Назначение:** Команда `explore-stats` и блок «Разведка ролей» отчёта `report`.

**Публичные функции:**
- `explore_block_text`
- `number`
- `reads`
- `stamp`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/explore_metric.py`, `orchestrator/providers/claude.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4rzayh3swjw4wfbw4qw15fp_summarize.py

**Назначение:** Сводка метрики разведки роли — `explore_metric.summarize`.

**Публичные функции:**
- `docs_abs`
- `docs_in_wt`
- `exact_rel`
- `file_change`
- `reads`
- `stamp`
- `wt_new`
- `wt_old`

**Импортирует:** `orchestrator/explore_metric.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/retro.py`

**Импортируется:** —

## tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py

**Назначение:** Короткий путь файла в строке вызова лога шага роли (`wt:` / `docs:`): общая функция `base.short_log_path`, строки лога Claude и Codex, неизменность `ToolCall.argument` и потока событий, группы Write блока test_author отчёта.

**Публичные функции:**
- `author_section`
- `claude_line`
- `codex_event`
- `codex_line`
- `old_line`
- `serialized`
- `standalone`
- `text_of`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/config.py`, `orchestrator/providers/base.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/report.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py

**Назначение:** Бриф роли несёт шаблон своего артефакта целиком с головы `main` пульта.

**Публичные функции:**
- `blocks`
- `boundary_pattern`
- `failed_note`
- `inside_any_block`
- `label_of`
- `reassemble_parts`
- `sha256`
- `task_label`
- `template_text`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py

**Назначение:** Записка роли `NOTE-<роль>.md` в автокоммите шага и в чекпоинте старта

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py

**Назначение:** Блок записок в брифе шага: отбор не больше двух записок по таблице

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4rzbpg6exm74mtbptegw2d4_note_guard.py

**Назначение:** Записка роли `NOTE-<роль>.md` в guard: перечень ролей записки, белый

**Публичные функции:**
- `free_text`
- `non_role_note_names`
- `task_id`

**Импортирует:** `orchestrator/config.py`, `orchestrator/roles.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py

**Назначение:** Гейт мержа и записка роли: записка `NOTE-<роль>.md` первого уровня

**Публичные функции:**
- `plan_text`
- `plank_text`
- `spec_text`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py

**Назначение:** Абзац миссии о записке шага: путь записки роли в каталоге документов,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_form.py

**Назначение:** Форма файла карточек знаний: разбор, отказы формы, повторы, пределы.

**Публичные функции:**
- `card_level_cases`
- `card_texts`
- `duplicate_cases`
- `field_level_cases`
- `file_level_cases`
- `indent_cases`
- `many_cards`
- `missing_field_cases`
- `render`
- `replaced`
- `section_cases`
- `setUpModule`
- `sized_card`
- `split_total`
- `without`

**Импортирует:** `orchestrator/config.py`, `orchestrator/knowledge_cards.py`

**Импортируется:** —

## tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_match.py

**Назначение:** Сверка места карточек знаний: `orchestrator.knowledge_cards.match`.

**Публичные функции:**
- `card`
- `keys`
- `setUpModule`

**Импортирует:** `orchestrator/config.py`, `orchestrator/knowledge_cards.py`

**Импортируется:** —

## tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py

**Назначение:** Чтение карточек знаний по видам: `orchestrator.knowledge_cards.read_cards`.

**Публичные функции:**
- `setUpModule`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/knowledge_cards.py`, `orchestrator/repo_context.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py

**Назначение:** `doc-commit` файла карточек `knowledge/<имя>.yaml`: проверка формы до

**Публичные функции:**
- `run_command`
- `setUpModule`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/knowledge_cards.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s0jvb85w9ty1esgnbh97fp_importers.py

**Назначение:** Допустимые импортёры `orchestrator/knowledge_cards.py` в пакете оркестратора.

**Публичные функции:**
- `importers`
- `imports_module`

**Импортирует:** —

**Импортируется:** —

## tests/test_01m4s0jvb85w9ty1esgnbh97fp_targets_knowledge.py

**Назначение:** Поле `knowledge` записи проекта в `targets.yaml`: проверка `targets.check`.

**Публичные функции:**
- `entry`

**Импортирует:** `orchestrator/config.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py

**Назначение:** Команда `knowledge <id> <запрос>`: белый список роли, выдача карточек,

**Публичные функции:**
- `boundary_blocks`
- `card_block`
- `card_fields`
- `exit_code`
- `inside`
- `knowledge_cards_module`
- `occurrences`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/roles.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py

**Назначение:** Пометка «возможно устарела» команды `knowledge`: где сверяется символ

**Публичные функции:**
- `card_block`
- `exit_code`
- `stale_lines`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py

**Назначение:** Строка-подсказка о команде `knowledge` в миссии пяти ролей

**Публичные функции:**
- `build_missions`
- `card_block`
- `hint_lines`
- `hint_records`
- `knowledge_cards_module`
- `pult_path`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py

**Назначение:** Записи журнала команды `knowledge` среди прочих: постоянный автор и

**Публичные функции:**
- `action_names`
- `knowledge_cards_module`
- `new_seed`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/artel.py`, `orchestrator/brief.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/review.py`, `orchestrator/roles.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s24963r9h18an2xdp6r15b_cache.py

**Назначение:** Кэш справочника ядра: `orchestrator/reference_cache.get_reference` на настоящем git.

**Публичные функции:**
- `entry_yaml`
- `field`
- `has_signature`
- `numbers`
- `project_files`
- `raise_on`
- `refuse`
- `replace_fails`
- `squeeze`
- `tree_snapshot`
- `users_count`
- `wide_files`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `scripts/core_reference.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s24963r9h18an2xdp6r15b_cli.py

**Назначение:** Командная строка генератора справочника ядра и тест-сторож настройки артели.

**Публичные функции:**
- `has_signature`
- `run_cli`
- `snapshot`
- `squeeze`
- `write`

**Импортирует:** `orchestrator/config.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s24963r9h18an2xdp6r15b_generator.py

**Назначение:** Генератор справочника ядра: `scripts/core_reference.build` по набору текстов.

**Публичные функции:**
- `attr_users`
- `build`
- `generator`
- `lines_with`
- `numbers`
- `signature_lines`
- `squeeze`

**Импортирует:** `scripts/core_reference.py`

**Импортируется:** —

## tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py

**Назначение:** Поле `core_reference` записи проекта в `targets.yaml`: проверка и чтение.

**Публичные функции:**
- `as_dict`
- `entry_yaml`
- `field_yaml`

**Импортирует:** `orchestrator/config.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py

**Назначение:** Справочник ядра в брифе developer и в добавке test_author: место

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/reference_cache.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py

**Назначение:** Пересборка справочника ядра после мержа: последний шаг `approve` на

**Публичные функции:**
- `plan_text`
- `plank_text`
- `spec_text`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/reference_cache.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4tvbt9zcrqdy669qv3s95ma_min_uses_field.py

**Назначение:** Подполе `min_uses` поля `core_reference` записи `targets.yaml`: проверка записи.

**Публичные функции:**
- `entry_with`
- `new_rng`

**Импортирует:** `orchestrator/targets.py`

**Импортируется:** —

## tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py

**Назначение:** Порог справочника ядра из настройки проекта, вход без задачи и команда `reference <проект>`.

**Публичные функции:**
- `entry_yaml`
- `field`
- `has_number`
- `has_signature`
- `paths_snapshot`
- `project_files`
- `refuse`
- `replace_fails`
- `squeeze`
- `target_entries`
- `verdicts`
- `yaml_value`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/reference_cache.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py

**Назначение:** Выкладка записок проверяющим ролям через настоящий путь подготовки.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py

**Назначение:** Роли эскалаций прогона канарейки и чистота прогона по ним.

**Публичные функции:**
- `run_row`
- `seeded_rng`

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/models.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py

**Назначение:** Команда `admit`: несколько пар за один вызов, правка набора `--set` и

**Публичные функции:**
- `run_summary`
- `shows_multi_pair_set_form`
- `usage_form`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py

**Назначение:** Свежесть аудита на связке автокоммит — журнал — очередь — advance.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4x4wfb01a18x6srs0jf3g2y_delivery_preserved.py

**Назначение:** Сохранение досыла: исполнение существующих проверок без копий ожиданий.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py

**Назначение:** Раздельные исходы полного прогона и уборка его дочерней группы.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `tests/fd_wait.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py

**Назначение:** Проверка штатного kill через lease и переход FSM.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/cleanup.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py

**Назначение:** Матрица владения lease в изолированной SQLite.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py

**Назначение:** Фиксация argv, `cwd` и окружения восьми мест запуска pytest пульта для

**Публичные функции:**
- `inside`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/config.py`, `orchestrator/stack.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py

**Назначение:** Подполя `runner`, `workdir`, `env` профиля тестов проекта: проверка

**Публичные функции:**
- `entry_from_yaml`
- `env_lines`
- `registry_secrets`

**Импортирует:** `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/targets.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py

**Назначение:** Раннер `runner: pytest-own` в восьми местах запуска pytest пульта:

**Публичные функции:**
- `has_pair`
- `own_profile`
- `places_share`
- `resolves_to`
- `via_command`
- `via_new_param`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py

**Назначение:** Профиль проекта задачи у вызывающих прогон pytest: argv, `cwd` и окружение каждого места.

**Публичные функции:**
- `capture_out`
- `has_pair`
- `is_full_suite`
- `is_pytest`
- `new_file_diff`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/amend.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gates.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/plank_run.py`, `orchestrator/project_profile.py`, `orchestrator/pull_main.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py

**Назначение:** Шаг роли задачи внешнего проекта: проектные скилы в брифе, белый список

**Публичные функции:**
- `project_whitelist`
- `word`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/models.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_step_project.py`

## tests/test_01m545edths47hsb59akc1ez9c_project_token.py

**Назначение:** Токен хостинга внешнего проекта и проверки `doctor` по записи проекта.

**Публичные функции:**
- `by_name`
- `check_fake_keychain`
- `flipped`
- `git_subcommand`
- `is_gh`
- `is_git`
- `lines_with`
- `render`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/keychain.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py

**Назначение:** Чекпоинт шага test_author отбирает и коммитит долгоживущие файлы по профилю проекта задачи.

**Публичные функции:**
- `entry`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py

**Назначение:** Задание test_author и developer называет каталог и префикс долгоживущих файлов по профилю проекта задачи.

**Публичные функции:**
- `entry`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py

**Назначение:** Проверка обязательного артефакта шага test_author видит долгоживущий файл по профилю проекта задачи.

**Публичные функции:**
- `entry`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/project_profile.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py

**Назначение:** Запросы `gh` функций CI (`orchestrator/ci.py`) к репозиторию внешнего проекта.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/repo_context.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py

**Назначение:** Мандат на ослабление тестов и матрица неослабления при записи ответа —

**Публичные функции:**
- `class_source`
- `matrix`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py

**Назначение:** Гейт зон выхода из `in_dev` и собственные долгоживущие файлы задачи

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py

**Назначение:** Правило импортов долгоживущих файлов по профилю проекта — на пяти местах трёх рубежей.

**Публичные функции:**
- `long_lived_source`
- `one_off_source`
- `sections`
- `spec_text`
- `ulid`
- `word`

**Импортирует:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/preflight.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py

**Назначение:** Подполе `test_profile.long_lived_imports`: проверка записи проекта и разобранный профиль.

**Публичные функции:**
- `base_profile`
- `entry_with`
- `word`

**Импортирует:** `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py

**Назначение:** Бриф роли задачи внешнего проекта: конвенции проекта с его базовой ветки

**Публичные функции:**
- `call_text`
- `git_repo_of`
- `word`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `scripts/codebase_map.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py

**Назначение:** Окно тишины `note` открывают только задачи артели и держатель мьютекса

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py

**Назначение:** Одно наблюдение на задачи разных проектов: `observe`, `watch`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/session.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py

**Назначение:** Проект задачи в выводе `status` и на плитке HTML `report`.

**Публичные функции:**
- `tile_elements`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/report.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py

**Назначение:** `kill` задачи внешнего проекта убирает её черновой PR и ветку в `origin` проекта.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/keychain.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py

**Назначение:** Миссии ролей задачи внешнего проекта называют команды пульта `guard`, `plank-run`, `suite-run` в форме белого списка роли.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py

**Назначение:** Команда `artel.py guard <id> [<файл>]` проверяет артефакты каталога документов задачи правилом `scripts/guard.py`.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py

**Назначение:** `plank-run <id> <путь>` принимает путь долгоживущего файла своей задачи.

**Публичные функции:**
- `is_pytest`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py

**Назначение:** Ревью-пакет задачи внешнего проекта: конвенции проекта с базовой ветки

**Публичные функции:**
- `boundary_markers`
- `commit_docs`
- `word`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py

**Назначение:** Чекпоинты developer считают своими долгоживущие файлы задачи по профилю проекта.

**Публичные функции:**
- `entry`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py

**Назначение:** Нет исполняемого файла команды профиля `pytest-own`: именованный отказ

**Публичные функции:**
- `refusal`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py

**Назначение:** PATH прогона `pytest-own` в восьми местах запуска профиля: PATH

**Публичные функции:**
- `make_executable`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py

**Назначение:** Профиль артели `pult-pytest`: argv, окружение (в том числе `PATH`) и

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56kcvctw5bv9twth54tw9q9_summary_deselected.py

**Назначение:** Итоговая строка pytest с категорией `deselected`: `acceptance.run_summary_line`

**Публичные функции:**
- `pytest_output`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/suite_run.py`

**Импортируется:** —

## tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py

**Назначение:** Гейт неослабления прослеживает помощников по области ослабления проекта задачи (AC-1..AC-5).

**Публичные функции:**
- `caller_module`
- `helper_function`
- `helper_module`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56tnx1wwkv8pvq94ft4zjqb_async_test_method.py

**Назначение:** `guard.TEST_METHOD` считает `async def test_…` как одноимённый `def test_…` (AC-9).

**Публичные функции:** (нет)

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py

**Назначение:** Гейт неослабления видит пропуск через имя-метку и модульные пропуски (AC-1..AC-8).

**Публичные функции:**
- `expected_value`
- `finding_pattern`
- `function`
- `klass`
- `module`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py

**Назначение:** Гейт неослабления видит смену аргументов `parametrize` у метода с прежним именем; литерал `parametrize` не объявляется в «Меняемом поведении» (AC-4..AC-7).

**Публичные функции:**
- `klass`
- `mentions`
- `method`
- `module`
- `parametrize`
- `skip_param`
- `values_text`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/answer.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py

**Назначение:** Двусторонний прогон судит параметризованный тест по вариантам, общим обеим сторонам; исходы непараметризованного теста прежние (AC-1..AC-3).

**Публичные функции:**
- `method_text`
- `pytest_class`
- `unittest_class`

**Импортирует:** `orchestrator/advance_gates/two_sided.py`, `orchestrator/config.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py

**Назначение:** Статус CI внешнего проекта по запускам GitHub Actions, когда check-runs коммита отказаны токену проекта.

**Публичные функции:**
- `forbidden`
- `gh_request`
- `gh_why`
- `http_error`
- `ok`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py

**Назначение:** Строка doctor `project-ci-token-<проект>`: читает ли токен внешнего проекта проверки коммита (check-runs) и запуски Actions.

**Публичные функции:**
- `http_error`
- `ok`

**Импортирует:** `orchestrator/config.py`, `orchestrator/doctor/project_checks.py`, `orchestrator/keychain.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py

**Назначение:** Прогоны планки артели (`pult-pytest`, без `workdir`) дают прежние исходы и тексты.

**Публичные функции:**
- `capture_out`
- `is_pytest`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/artel.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py

**Назначение:** Планка внешнего проекта исполняется внутри `long_lived_dir`: корень, конфиг, импорты и фикстуры проекта.

**Публичные функции:**
- `capture_out`
- `files_under`
- `is_pytest`
- `under`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/artel.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py

**Назначение:** Мьютекс и очередь мержа разделены по проекту задачи: держатель и

**Публичные функции:**
- `refusal_pattern`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py

**Назначение:** Читатели мьютекса мержа вне `merge_lock` смотрят все его строки: окно

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py

**Назначение:** Проект задачи и алерта в HTML `report`; разбивка «Экономики» и доли

**Публичные функции:**
- `block_rows`
- `block_text`
- `parse`
- `ratio_text`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/report.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py

**Назначение:** Алерт уровня пульта (`target` NULL) в дозоре наблюдения и в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py

**Назначение:** Сигнал остановки в раннем окне запуска процесса ведения канарейки.

**Публичные функции:**
- `group_alive`
- `living_processes`
- `pid_alive`

**Импортирует:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m58fnwbv25ff26e7az9q9912_components.py

**Назначение:** Компоненты проекта в записи targets.yaml: схема, profile_of, выбор по путям, идентификатор теста.

**Публичные функции:**
- `base_entry`
- `component_name`
- `multi_components`
- `single_components`
- `task_conn`

**Импортирует:** `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py

**Назначение:** Строки `doctor` по компонентам проекта: версии инструментов, карта путей CI, каталоги `workdir`; `doctor` на записи с компонентами не падает.

**Публичные функции:**
- `block`
- `guarded_popen`
- `q`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py

**Назначение:** Итог тестов компонента из отчёта: `junit-xml`, отчётчик пульта `pult-vitest`, окружение и установка пультом, сторож зависших тестов; прежний разбор у артели.

**Публичные функции:**
- `block`
- `entry`
- `entry_values`
- `fld`
- `flipped`
- `junit`
- `pytest_output`
- `quoted`
- `report_arg`
- `under`
- `vitest_report`
- `vitest_test`
- `writable`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `tests/fd_wait.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_component_report_gates.py`, `tests/test_invariants.py`

## tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py

**Назначение:** Механическая проверка ТЗ в `new`: ссылки `файл:строка` и вызывающие вне зон.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m59dp2gv3san54m562cqy42r_rounds.py

**Назначение:** Метрика «круги до кода»: блок «Круги до кода» HTML `report` и оповещение

**Публичные функции:**
- `cell`
- `cell_int`
- `cell_pair`
- `cells`
- `column_map`
- `has_id`
- `known_detail`
- `new_seed`
- `numbers`
- `old_created_at`
- `report_html`
- `role_finished_since_entry`
- `rounds_block`
- `skeleton`
- `strip`
- `task_rows`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/auto.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py

**Назначение:** Правило планки компонента: допустимые файлы, метка `AC-<n>: `, пометки `//`, маркер красноты в первом комментарии, `plank_rule` проекта.

**Публичные функции:**
- `block`
- `components_entry`
- `flow`
- `profile_entry`
- `public_texts`
- `spec_text`

**Импортирует:** `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py

**Назначение:** Выкладка планки компонента по `plank_layout`, форма `plank_layout`, исключение остатка из полного набора и `plank-run` по правилу планки проекта.

**Публичные функции:**
- `arg_value`
- `block`
- `entry`
- `is_pytest`
- `junit_report`
- `listing`
- `quoted`
- `vitest_report`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/plank_run.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py

**Назначение:** Долгоживущие файлы с меткой `AC-<n>: ` на выходе из `tests_writing` и в `preflight`: трассируемость, строка группы, статика, файл не с меткой и не Python; прежние исходы у артели, `test_profile` и явной пары.

**Публичные функции:**
- `arg_value`
- `flow`
- `sections`
- `spec_text`
- `ulid`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py

**Назначение:** Подсказки о долгоживущих файлах по шаблону с `<dir>`: задание test_author и developer, отказ обязательного артефакта шага.

**Публичные функции:**
- `task_ref`
- `ulid`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py

**Назначение:** Шаблон `long_lived` компонента: форма записи, производная пара, правило имени с `<dir>`, пример пути.

**Публичные функции:**
- `entry_dict`
- `entry_yaml`
- `ulid`
- `yaml_value`

**Импортирует:** `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py

**Назначение:** Честный `FAIL_TO_PASS` на выходе из `tests_writing` у компонента с отчётом, наличие тестов критериев на ветке, запреты в тексте планки и переносы G2а/G2б-1.

**Публичные функции:**
- `arg_value`
- `flow`
- `spec_text`
- `ulid`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`

## tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py

**Назначение:** Классы новых отказов честного `FAIL_TO_PASS` и проверки ветки в перечне `REFUSAL_CLASSES` и реакция цикла `auto` на них.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py

**Назначение:** Реестр живого прогона канарейки: запись и метка рядом с ней, уборка на любом исходе, повтор run_stamp, run_stamp вызывающему и файл результата отвязанного запуска.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py

**Назначение:** Потребители реестра живого прогона канарейки: сверка живости, окно тишины note/doc-commit, мерж на merge_gate и обходы окна с --during-canary.

**Публичные функции:**
- `merge_refusal`
- `plan_text`
- `plank_text`
- `spec_text`
- `window_refusal`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py

**Назначение:** Гейт неослабления по исходам на переходе `in_dev -> verifying`: `PASS_TO_PASS`, перепрогоны, сравнение отчётов, мандат, отказы и журнал.

**Публичные функции:**
- `arg_value`
- `flow`
- `js_source`
- `py_source`
- `py_tests`
- `spec_text`
- `ulid`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`

## tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py

**Назначение:** Классы трёх действий гейта неослабления по исходам в перечне `REFUSAL_CLASSES` и реакция цикла `auto` на них.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py

**Назначение:** Мандат на ослабление теста по идентификатору при записи ответа: маркер, проверка идентификатора, путь записи и журнал, матрица неослабления, `zones-extend` (AC-1..AC-9, AC-14..AC-19).

**Публичные функции:**
- `gone_row`
- `kinds_of`
- `matrix`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_audit_signal.py

**Назначение:** Строка мандата на ослабление теста по идентификатору в ANSWER — сигнал аудита SPEC «б) мандат в ANSWER» (AC-10).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`

**Импортируется:** —

## tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py

**Назначение:** Мандат на ослабление теста по идентификатору в гейте неослабления по исходам: отбраковка автокоммита роли, точное равенство с `#n`, подсказка отказа (AC-11..AC-13).

**Публичные функции:**
- `arg_value`
- `flow`
- `js_names`
- `js_source`
- `spec_text`
- `ulid`

**Импортирует:** `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py

**Назначение:** Гейт неослабления по исходам на гейте мержа, доказательство для головы, пакет ревьювера и двусторонний прогон по имени ошибки.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`

**Импортируется:** `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`

## tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py

**Назначение:** Ошибка уровня файла в отчёте компонента, засчитывание «нового модуля» гейтом честного FAIL_TO_PASS, строка пакета ревьювера и переносы приёмок G2б-2.

**Публичные функции:**
- `parts_of`

**Импортирует:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`

**Импортируется:** —

## tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py

**Назначение:** Документы `knowledge` компонента внешнего проекта в брифе ролей и пакете

**Публичные функции:**
- `boundary_markers`
- `call_text`
- `git_repo_of`
- `word`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`

## tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py

**Назначение:** Задание test_author по правилу планки проекта: прежний текст у артели, `test_profile`, pytest-компонента и неопределённого профиля; текст Vitest-планки у компонента с меткой `AC-<n>: `.

**Публичные функции:**
- `component_entry`
- `flow`
- `ulid`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`

## tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py

**Назначение:** Итоговые строки `plank-run`: «итог vitest» у компонента `pult-vitest`, прежние «итог pytest» у артели, pytest-компонента и задачи с неопределённым профилем.

**Публичные функции:**
- `component_entry`
- `flow`
- `ulid`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/plank_run.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`

## tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py

**Назначение:** Сводка прогона Vitest в журнале шага: разбор блока, насос с `on_vitest_summary`, выбор насоса по профилю проекта задачи, прежний «прогон pytest».

**Публичные функции:**
- `component_entry`
- `flow`
- `pytest_entry`
- `tool_result_line`
- `ulid`
- `vitest_entry`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/project_profile.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`

## tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py

**Назначение:** Запись «прогон vitest» у читателей журнала: дозор относит её к классу `pytest` с общим бюджетом строк, отчёт суммирует её секунды вместе с «прогон pytest».

**Публичные функции:**
- `author_section`
- `text_of`
- `ulid`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/config.py`, `orchestrator/report.py`, `orchestrator/session.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py

**Назначение:** Проверка `doctor` `canary-live`: живые прогоны канарейки по реестру, предупреждение о зависших и мёртвых, уборка под `doctor --fix`.

**Публичные функции:**
- `hours_found`

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py

**Назначение:** Команда `canary live`: показ реестра живого прогона канарейки и снятие зависшего `--drop <run_stamp> "<основание>"`.

**Публичные функции:**
- `durations`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py

**Назначение:** Реестр живого прогона канарейки: метка `<run_stamp>.lock` без записи — живость, уборка и неприкосновенность метки рядом с живой записью.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py

**Назначение:** Метка живой канарейки без записи реестра у потребителей окна: `note`, `note --now`, `approve` на `merge_gate`; прежнее поведение без такой метки.

**Публичные функции:**
- `merge_refusal`
- `plan_text`
- `plank_text`
- `spec_text`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py

**Назначение:** Отказ `approve` на гейте SPEC о потере заявленной зависимости ведёт по исполнимому пути reject → эскалация аналитика → answer в escalated → approve (AC-8, AC-9).

**Публичные функции:**
- `meta_of`
- `spec_text`

**Импортирует:** `orchestrator/answer.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py

**Назначение:** `zone_lock.wait_minutes`: ожидание зоны закрывают запись выхода и записи цикла `auto`; снятие Оператором входом не считается (AC-4).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py

**Назначение:** Выход цикла `auto` из ожидания занятой зоны: парная запись выхода при каждом выходе, кроме освобождения; вывод, исход и журнал остановки — прежние (AC-1, AC-2, AC-3, AC-5, AC-6, AC-7).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/lease.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py

**Назначение:** Уборка ветки смерженной задачи в `origin` проекта: удаление, отказы, подсказки, сбои.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/keychain.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5fryvp4nf81vt00fyphpwjh_outcome_action_texts.py

**Назначение:** Тексты действий гейта неослабления по исходам на мерже — один источник `refusal_classes`.

**Публичные функции:**
- `source`
- `string_constants`

**Импортирует:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/refusal_classes.py`

**Импортируется:** —

## tests/test_01m5fryvp4nf81vt00fyphpwjh_rerun_ban_check.py

**Назначение:** `targets.check` отказывает компоненту с `report`, которому заданы плагины повторов pytest: аргументы, `PYTEST_ADDOPTS`, `PYTEST_PLUGINS`.

**Публичные функции:**
- `component`
- `entry`
- `forbidden_forms`

**Импортирует:** `orchestrator/targets.py`

**Импортируется:** —

## tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py

**Назначение:** Соединения `store.db()`, брошенные без `close()`, не копят дескрипторы процесса и без сборки циклов; соединение с живой внешней ссылкой остаётся рабочим.

**Публичные функции:**
- `open_fds`

**Импортирует:** `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py

**Назначение:** `amend-tests` для файлов с меткой `AC-<n>: ` при правиле планки не по умолчанию: проход годной правки, отказы трёх групп проверок до любой записи, удаление долгоживущего файла, состав файлов планки `--from-branch` (AC-16..AC-19, AC-23).

**Публичные функции:**
- `arg_value`
- `flow`
- `spec_text`
- `ulid`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`

## tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py

**Назначение:** Раздел SPEC «## Заменяемые тесты» в guard, сигнал аудита SPEC, запреты планки и трассируемость шаблонной таблицы `.each` (AC-1 — половина CLI, AC-2, AC-3, AC-10, AC-12, AC-13, AC-14).

**Публичные функции:**
- `criteria_text`
- `labelled_rule`
- `spec`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/project_profile.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py

**Назначение:** Раздел SPEC «## Заменяемые тесты» на переходе `spec_writing -> spec_gate`, утверждение на `approve` гейта SPEC, `approved_replacements` и сверка на выходе из `tests_writing` (AC-1 — половина перехода, AC-4..AC-9, AC-11, AC-20, AC-24, AC-25).

**Публичные функции:**
- `arg_value`
- `flow`
- `guard_names`
- `matrix`
- `ulid`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`

## tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py

**Назначение:** `suite-run` под маркером developer: новый полный прогон отказывает до любых записей, `--wait`/`--failed` и прочие вызывающие — прежние.

**Публичные функции:**
- `bare_full_run`
- `pytest_output`
- `readonly_db`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py

**Назначение:** `amend-tests` для файлов с меткой `AC-<n>: ` при пустом перечне долгоживущих файлов лока (оба пути), удаление долгоживущего файла с меткой с переносом имени теста в планку и отказ решения профиля записи из нескольких компонентов на `approve` гейта SPEC (AC-1..AC-5).

**Публичные функции:**
- `has_criterion`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`

**Импортируется:** —

## tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py

**Назначение:** Гейт неослабления по исходам G3б-2: прежние версии тестов на коде ветки, заменяемые тесты, строгий режим, исключения в коде, доказательство на мерже.

**Публичные функции:**
- `env_lines`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/answer.py`, `orchestrator/liveness.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`

**Импортируется:** —

## tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py

**Назначение:** Поля компонента `test_support`, `layers`, `paths` в профиле, действующие слои `layers_of` и проверка `layers` в `targets.check`.

**Публичные функции:**
- `flow`

**Импортирует:** `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py

**Назначение:** Мандаты ослабления у записи из нескольких компонентов: элемент и идентификатор годны для компонента записи в границе гейта исходов, матрица засчитывает его ссылку покрытием.

**Публичные функции:**
- `matrix`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py

**Назначение:** Гейт исходов у записи из нескольких компонентов: компоненты по диффу с потребителями, запись на компонент, граница по компоненту, строки пакета ревьювера; выход из `tests_writing` и `in_dev` задачи на один компонент; планка чужого компонента на выходе из `tests_writing` — отказ FAIL_TO_PASS в границе, прежнее поведение вне её.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`

**Импортируется:** —

## tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py

**Назначение:** Бриф, задание test_author, сводки Vitest и итог `plank-run` у задачи на компонент записи из нескольких компонентов — как у записи из одного этого компонента; при отказе `for_task` — прежний вывод.

**Публичные функции:**
- `block`
- `multi_entry`
- `new_id`
- `normalized`
- `single_entry`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/plank_run.py`, `orchestrator/project_profile.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`

**Импортируется:** —

## tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py

**Назначение:** Компонент задачи по зонам: `task_components`, `decide_task`, `for_task`, прежний отказ `decide` и зона-каталог.

**Публичные функции:**
- `flow`
- `task_conn`

**Импортирует:** `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/targets.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py

**Назначение:** Незавершённая зависимость `merge_after` с общей зоной держит старт последователя в любом состоянии.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py

**Назначение:** `kill <id> [--yes] [--reason "<текст>"]`: причина ликвидации в детали

**Публичные функции:**
- `hint_line`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/retro.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`

**Импортируется:** —

## tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py

**Назначение:** `pin-update <sha> [--wait-ci]`: ожидание CI головы main командой пульта

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/pin.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py

**Назначение:** Команда `prune`: промпты `*.prompt.txt` и каталоги `suite-run/<id>/` по

**Публичные функции:**
- `file_count`
- `suite_line`
- `tree_snapshot`
- `worktree_files`

**Импортирует:** `orchestrator/config.py`, `orchestrator/prune.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py

**Назначение:** Команда `canary runs [--since <ГГГГ-ММ-ДД> | <run_stamp>]`: история прошедших прогонов канарейки из `canary_runs`.

**Публичные функции:**
- `absent_refusal`
- `header_line`
- `incompatible_refusal`
- `money`
- `stamp_refusal`
- `task_line`
- `text`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py

**Назначение:** Git в процессах тестов — напрямую, без системной обёртки xcrun.

**Публичные функции:**
- `dev_bin`
- `direct_git_module`
- `first_index`
- `make_developer_dir`
- `run_output`

**Импортирует:** `orchestrator/runner.py`, `orchestrator/stack.py`, `tests/direct_git.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py

**Назначение:** Признаки утечки пула канарейки в логах шагов ролей:

**Публичные функции:**
- `legacy_alert_text`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/providers/claude.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py

**Назначение:** Правило о полном наборе тестов у ревьювера — одна константа `role_prompt.REVIEWER_FULL_SUITE_RULE`, в миссии ревьювера ровно один раз сразу после фразы о проверках.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py

**Назначение:** Справка пульта (докстринг `orchestrator/artel.py`) ↔ реестр команд `table`.

**Публичные функции:**
- `commands_block`
- `header`
- `mentioned_as_command`
- `registry_keys`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/pin.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py

**Назначение:** `pin-update`: после успешного сдвига пина главная копия снимает ссылки

**Публичные функции:**
- `is_remote_prune`

**Импортирует:** `orchestrator/canary.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/pin.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py

**Назначение:** Команда `prune`: вид «бесхозные каталоги .artel/worktrees» — план и

**Публичные функции:**
- `done_line`
- `failure_prefix`
- `git_repo_of`
- `is_worktree_list`
- `plan_line`
- `tree_listing`

**Импортирует:** `orchestrator/config.py`, `orchestrator/prune.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py

**Назначение:** Справочник ядра при пределе по умолчанию 16 384 байта: включение ровно

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/projects.py`, `orchestrator/reference_cache.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5mhvakhr82vzrxzr19wj677_dead_definitions.py

**Назначение:** Тринадцать определений пульта без обращений удалены и не возвращаются.

**Публичные функции:**
- `references`

**Импортирует:** —

**Импортируется:** —

## tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly.py

**Назначение:** `store.db_readonly` — одна функция открытия БД пульта только на чтение.

**Публичные функции:**
- `mode_ro_copies`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py

**Назначение:** Пять читателей БД пульта открывают её через `store.db_readonly`, а их

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/knowledge_cards.py`, `orchestrator/preflight.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py

**Назначение:** Свежесть связи наблюдения — одна функция модуля `watch` вместо трёх копий.

**Публичные функции:**
- `fromisoformat_on_last_seen`
- `frozen_datetime`
- `new_seed`
- `random_moment`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py

**Назначение:** Обвязка «префикс id задачи + блокировка задачи» команд — `lease.run_task_command`.

**Публичные функции:**
- `dotted`

**Импортирует:** `orchestrator/answer.py`, `orchestrator/ci_rerun.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/pull_main.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance.py

**Назначение:** Юнит-тесты orchestrator/acceptance.py::run_full_suite (ADR-0007,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance_collect.py

**Назначение:** Юнит-тесты `orchestrator/acceptance.py::collect` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance_file_time.py

**Назначение:** Время долгоживущих файлов из одного отчёта общего прогона pytest.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/review.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_acceptance_own_launch.py

**Назначение:** Запуск процесса места `pytest-own` (`acceptance._launch`, SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`

**Импортируется:** —

## tests/test_acceptance_plank_exclude_lock.py

**Назначение:** Дописывание шаблона выкладки в общий `info/exclude` клона — под `flock`.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`

**Импортируется:** —

## tests/test_acceptance_plank_layout_refusal.py

**Назначение:** Выкладка планки `pytest-own` без исключения из git не делается.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/project_profile.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_acceptance_pycache.py

**Назначение:** Юнит-тесты отведения кеша байткода прогонов pytest пульта

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance_seed_repeat.py

**Назначение:** Юнит-тесты повторного прогона долгоживущих файлов, несущих случайное

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_acceptance_suite_profile.py

**Назначение:** Юнит-тест `orchestrator/acceptance.py::acceptance_suite`: профиль проекта

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`

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

**Импортируется:** `tests/test_sandbox_retry_pause.py`

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

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_answer.py

**Назначение:** Юнит-тесты `orchestrator/answer.py` (SPEC T075, SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/mandate_matrix.py`, `tests/test_git_fixation.py`

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

## tests/test_answer_in_dev_gate_journal.py

**Назначение:** Юнит-тесты разбора журнала гейта неотработанного ANSWER на рубеже

**Публичные функции:**
- `answer`
- `row`

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/review.py`

**Импортируется:** —

## tests/test_answer_mandate.py

**Назначение:** Юнит-тесты `orchestrator/advance_gates/mandate.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/gitcmd.py`

**Импортируется:** —

## tests/test_appendix_tree.py

**Назначение:** Юнит-тесты `orchestrator/appendix_tree.py` (SPEC 01M46C776SZEMYPBQGPNJN1TXY)

**Публичные функции:**
- `git`

**Импортирует:** `orchestrator/appendix_tree.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_approve_acceptance_full_suite.py

**Назначение:** Юнит-тесты прогона полного набора tests/ на `approve` из `acceptance`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_suite_lock.py`

## tests/test_approve_no_answer_units.py

**Назначение:** Юнит-тесты разбора `approve --no-answer`/`answer <id> <файл>` и записи о

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_artel_bootstrap.py

**Назначение:** Юнит-тесты самовыбора интерпретатора `orchestrator/artel.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/stack.py`

**Импортируется:** —

## tests/test_artel_guard_command_forms.py

**Назначение:** Формы аргумента `<файл>` команды `artel.py guard <id> [<файл>]` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_artifact_branch_server_retry.py

**Назначение:** Юнит-тесты причины «сервер» и повтора `git push` ссылки документов

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

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

## tests/test_canary_detach_result.py

**Назначение:** Файл результата отвязанной канарейки при отказе ведения.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/runner.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_canary_doctor_owner.py

**Назначение:** Живой прогон пульта защищает временную копию базы.

**Публичные функции:**
- `test_live_origin_marker_protects_before_remote_link`
- `test_live_pult_suite_base_is_not_a_hung_canary_run`
- `test_unrelated_live_suite_run_does_not_protect_orphan_base`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`

**Импортируется:** —

## tests/test_canary_drive.py

**Назначение:** Юнит-тесты ведения учебной задачи канарейки кодом проверяемого коммита

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/config.py`, `orchestrator/providers/codex.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_canary_escalation_roles_storage.py

**Назначение:** Хранение ролей эскалаций в `canary_runs`: пустой перечень и `None` различимы.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_canary_live_registry_units.py

**Назначение:** Реестр живого прогона канарейки — свойства вне долгоживущих файлов задачи

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_canary_parallel.py

**Назначение:** Родитель параллельного прогона канарейки `canary --parallel` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_canary_parallel_protection.py

**Назначение:** Постоянная защита прогона канарейки с `--parallel` и без него (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_canary_profile_safety.py

**Назначение:** Границы постоянного профиля Codex канарейки.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/providers/codex.py`

**Импортируется:** —

## tests/test_canary_run_task.py

**Назначение:** Внутренняя подкоманда `canary run-task` (SPEC 01M5FZ9G7ME2F1T5TYEWSVNA1R,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_canary_runs.py

**Назначение:** `canary runs --since`: пустой отбор при непустой таблице (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_checkpoint_zone_mandate.py

**Назначение:** Юнит-тесты `orchestrator/checkpoint.py::_mandate_covered` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/zones.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_ci_actions_fallback.py

**Назначение:** Узлы пути Actions статуса CI внешнего проекта и строки doctor

**Публичные функции:**
- `completed`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/doctor/project_checks.py`

**Импортируется:** —

## tests/test_ci_callers_project_repo.py

**Назначение:** Вызывающие функции CI — `ci-rerun` (`orchestrator/ci_rerun.py`) и ре-ран

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_ci_project_gh_address.py

**Назначение:** Адресация `gh` функций `orchestrator/ci.py` репозиторию внешнего проекта:

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/repo_context.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/ci.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_invariants.py`

**Импортируется:** —

## tests/test_ci_stuck_check_run.py

**Назначение:** Юнит-тесты правила завершённости check-run'а и состояния «проверка

**Публичные функции:**
- `answer`
- `green`
- `iso_ago`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_ci_workflow_mergeable.py

**Назначение:** Выбор единственного полного прогона CI при открытом PR ветки задачи.

**Публичные функции:**
- `open_pr_script`

**Импортирует:** —

**Импортируется:** —

## tests/test_class_mandate_units.py

**Назначение:** Юнит-тесты покрытия находки элементом-классом и разбора мандата тестов

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/answer.py`

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

## tests/test_component_checks.py

**Назначение:** Разбор строк doctor по компонентам и суммы отслеживаемых файлов блокировки в ключе итога (SPEC 01M58PG72PG64GS790XM2EWS61).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/doctor/project_checks.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_component_report_gates.py

**Назначение:** Сторожа гейтов итога из отчёта компонента вне долгоживущего файла задачи 01M590GJAF0EDV4NBC4C99MFVH.

**Публичные функции:**
- `check`
- `profile`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`

**Импортируется:** —

## tests/test_component_report_run.py

**Назначение:** Узлы итога из отчёта компонента вне долгоживущего файла задачи 01M590GJAF0EDV4NBC4C99MFVH.

**Публичные функции:**
- `profile`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `orchestrator/suite_run.py`

**Импортируется:** —

## tests/test_conftest_role_guard.py

**Назначение:** Юнит-тесты корневого `conftest.py` (SPEC 01M2B6K3EM7F2J72RC2F520Y2K,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`

**Импортируется:** —

## tests/test_core_reference.py

**Назначение:** Генератор справочника ядра: свойства вне долгоживущих файлов задачи.

**Публичные функции:**
- `roles_row`

**Импортирует:** `scripts/core_reference.py`

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

**Импортируется:** `tests/test_external_code_copy_refusal.py`

## tests/test_docs_fetch_edges.py

**Назначение:** Углы команды `docs` (SPEC 01M41VTSE5N15P5P2WZF4GF2BQ), не покрытые

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`

**Импортируется:** —

## tests/test_docs_ref_deleted_refusal.py

**Назначение:** Записи пульта в ссылку документов при удалённой ролью ссылке и живой

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/fixation.py`, `orchestrator/store.py`, `tests/mandate_matrix.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`

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

## tests/test_doctor_closed_ref_fix.py

**Назначение:** Юнит-тесты досылки коммита закрытия `doctor --fix` из главной копии

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/workspace.py`

**Импортируется:** —

## tests/test_dry_run.py

**Назначение:** Юнит-тесты orchestrator/dry_run.py (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/dry_run.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_explore_metric.py

**Назначение:** Разбор искомой строки команды оболочки метрикой разведки

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/explore_metric.py`

**Импортируется:** —

## tests/test_external_code_copy_refusal.py

**Назначение:** Отказ заведения рабочей копии задачи внешнего проекта не теряется на

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_docs_dir_layout.py`

**Импортируется:** —

## tests/test_failure_classification.py

**Назначение:** Юнит-тесты классификатора ошибок агента (SPEC T082, требования 1-2).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/failure_classification.py`

**Импортируется:** —

## tests/test_fd_wait.py

**Назначение:** Функция ожидания `tests.fd_wait.wait_readable` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `tests/fd_wait.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_autogate.py

**Назначение:** Юнит-тесты условия «а» `fsm_autogate._autogate_conditions` — чтение

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_autogate_env_refusal.py

**Назначение:** Класс отказа автогейта «окружение» (SPEC 01M5KBGF184B07SVXMD4R1NXXC).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gates.py`, `orchestrator/models.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_autogate_long_lived.py

**Назначение:** Пометки и ошибки долгоживущей планки в записи приёмки.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_source.py`, `orchestrator/fsm_autogate.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_fsm_autogate_plank_rule.py

**Назначение:** Отказ автогейта по правилу планки `fsm_autogate._plank_rule_refusal`

**Публичные функции:**
- `profile`

**Импортирует:** `orchestrator/fsm_autogate.py`, `orchestrator/project_profile.py`, `scripts/guard.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_fsm_merge_gate_remote_branch_cleanup.py

**Назначение:** Проводка уборки ветки задачи в `origin` через тело гейта мержа (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/keychain.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_merge_gate_scratch_worktree_cleanup.py

**Назначение:** Регресс-тест R1-F1 (REVIEW.md 01M1R5B33CC7E6BZK085XV3ZCX итерация 1,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/repo_context.py`, `tests/sandbox.py`

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

## tests/test_full_suite_profile_timeout.py

**Назначение:** Предел полного прогона из test_profile: разбор, раннер и диагностика.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/doctor/cli.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_full_suite_reuse.py

**Назначение:** Границы ключа и разбора полного прогона.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/suite_run.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_gate_owner_marker.py

**Назначение:** Маркер владельца каталогов выписок гейтов исходов и двустороннего

**Публичные функции:**
- `artel_profile`
- `dead_pid`

**Импортирует:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/project_profile.py`

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

**Импортирует:** `orchestrator/github_adapter.py`, `orchestrator/targets.py`, `tests/sandbox.py`

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

## tests/test_guard_assertion_changes.py

**Назначение:** Юнит-тесты различения смены ожидания и ослабления, строгости нового

**Публичные функции:**
- `change`
- `source`

**Импортирует:** `orchestrator/advance_gates/two_sided.py`, `scripts/guard.py`

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

## tests/test_guard_helper_scope.py

**Назначение:** Юнит-тесты поиска помощников вне своего класса и своего модуля в

**Публичные функции:**
- `assertions`
- `modules`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_helper_scope_modes.py

**Назначение:** Юнит-тесты режима поиска помощников `guard.TestModules` (SPEC

**Публичные функции:**
- `found_texts`
- `in_backend_tests`

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_mutation_claim.py

**Назначение:** Юнит-тесты `scripts/guard.py::test_functions_without_mutation_claim`

**Публичные функции:** (нет)

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_parametrize_variants.py

**Назначение:** Юнит-тесты сравнения параметризации гейта неослабления (SPEC

**Публичные функции:**
- `compare`
- `source`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/two_sided.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_path_mentions.py

**Назначение:** Юнит-тесты сборщика упоминаний путей и сверки с зонами

**Публичные функции:**
- `seed`
- `spec`

**Импортирует:** `orchestrator/config.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_guard_plank_bans.py

**Назначение:** Юнит-тесты запретов в тексте файла с меткой `AC-<n>: ` в `scripts/guard.py`

**Публичные функции:**
- `bans`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_guard_plank_rule_parsing.py

**Назначение:** Юнит-тесты разбора планки по правилу компонента в `scripts/guard.py`

**Публичные функции:**
- `plank`

**Импортирует:** `scripts/guard.py`

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

## tests/test_hosting_token_units.py

**Назначение:** Мелкие свойства механизма токена хостинга (SPEC 01M545EDTHS47HSB59AKC1EZ9C),

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/doctor/project_checks.py`, `orchestrator/gitcmd.py`

**Импортируется:** —

## tests/test_id_format_guard.py

**Назначение:** Юнит-тесты проверки образца формата идентификатора задачи в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `scripts/guard.py`, `tests/sandbox.py`, `tests/test_fsm_branch_correct_status_reads.py`

**Импортируется:** —

## tests/test_invariants.py

**Назначение:** Тесты системных инвариантов (см. tasks/T010/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`

**Импортируется:** `tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_review_registry_gate.py`, `tests/test_verifying_ceiling.py`

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

**Импортируется:** `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_detached_cycle.py`, `tests/test_kill_live_cycle_refusal.py`

## tests/test_kill_live_cycle_refusal.py

**Назначение:** Юнит-тесты `cleanup._live_cycle_holder` и разбора `--yes` диспетчером

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_kill_cleanup.py`

**Импортируется:** `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`

## tests/test_knowledge_cards.py

**Назначение:** Карточки знаний: свойства сверх долгоживущих файлов задачи

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/knowledge_cards.py`, `orchestrator/notes.py`

**Импортируется:** —

## tests/test_knowledge_command.py

**Назначение:** Команда `knowledge` и подсказка миссии: свойства сверх долгоживущих

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/knowledge_cards.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_launch_observation_refusals.py

**Назначение:** Тексты отказов отвязанного `run`/`auto` из-за наблюдения (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/session.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_lease_run_task_command.py

**Назначение:** `lease.run_task_command` — одна обвязка «префикс id + блокировка задачи»

**Публичные функции:**
- `dotted`

**Импортирует:** `orchestrator/answer.py`, `orchestrator/ci_rerun.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/pull_main.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`, `tests/test_timeout_checkpoint.py`

**Импортируется:** —

## tests/test_long_lived_step_end_to_end.py

**Назначение:** Сквозной путь «шаг test_author → чекпоинт → advance» для долгоживущего

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_timeout_checkpoint.py`

**Импортируется:** —

## tests/test_long_lived_template_shape.py

**Назначение:** Форма шаблона `long_lived` и пример пути: свойства вне долгоживущих файлов задачи 01M5AA5TS90RDJ2AFXB882WTPD.

**Публичные функции:**
- `entry`
- `pytest_fields`

**Импортирует:** `orchestrator/config.py`, `orchestrator/targets.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_long_lived_transitions.py

**Назначение:** Юнит-тесты проводки долгоживущих файлов через переходы FSM (SPEC

**Публичные функции:**
- `capture_call`
- `long_lived_source`
- `plank_source`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/artifact_branch.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_git_fixation.py`

**Импортируется:** `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`

## tests/test_main_ci_fetched_repo.py

**Назначение:** Цвет CI main у `pin-update` и `doctor` читается там, куда был `fetch`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/pin.py`

**Импортируется:** —

## tests/test_main_ci_line.py

**Назначение:** Юнит-тесты цвета CI main по первой родительской линии и его обвязки

**Публичные функции:**
- `done`
- `sha`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_main_copy_watch.py

**Назначение:** Сторож главной копии пульта (SPEC 01M4G8KPP8DVNBCPGCAPSVMAKZ):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_mandate_file_path_token.py

**Назначение:** Сужение признания ячейки «Чем покрыто после» при профиле в границе гейта

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/project_profile.py`

**Импортируется:** —

## tests/test_mandate_matrix_form.py

**Назначение:** Юнит-тесты формы матрицы неослабления (`mandate.matrix_refusals`) и

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `tests/mandate_matrix.py`

**Импортируется:** —

## tests/test_mandate_profile_scope.py

**Назначение:** Юнит-тесты области мандата ослабления и ссылки матрицы по профилю

**Публичные функции:**
- `matrix`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/project_profile.py`, `tests/mandate_matrix.py`

**Импортируется:** —

## tests/test_mandate_test_id.py

**Назначение:** Юнит-тесты мандата на ослабление теста по идентификатору (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/project_profile.py`, `tests/mandate_matrix.py`

**Импортируется:** —

## tests/test_merge_after.py

**Назначение:** Юнит-тесты `orchestrator/merge_after.py` и его опор (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/merge_after.py`, `orchestrator/schema.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_merge_after_declared.py

**Назначение:** Юнит-тесты заявленных зависимостей мержа в `orchestrator/merge_after.py`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_merge_lock_by_project.py

**Назначение:** Мьютекс и очередь мержа по проекту — свойства из ответа Оператора

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_merge_queue.py

**Назначение:** Юнит-тесты orchestrator/merge_queue.py (SPEC 01M291EPQ2VFGCHZTXXC81616V).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_merge_reference_step.py

**Назначение:** Шаг пересборки справочника ядра после мержа

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/reference_cache.py`, `orchestrator/store.py`, `tests/sandbox.py`

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
- `git_config_else_real`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_mutation_claim_gate.py

**Назначение:** Юнит-тесты гейта заявки мутации на `in_dev -> verifying` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_network_address_gate.py

**Назначение:** Юнит-тесты рубежа сетевых адресов `tests/` на `in_dev -> verifying`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

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

## tests/test_observation_acceptance_return.py

**Назначение:** Возврат с приёмки задачи 01M4C954HBJWEGD3AZS7Q3EHA4: позиция дозора

**Публичные функции:**
- `test_notification_timeout_is_reported_and_not_fatal`
- `watch_time_stand_in`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_observation_edges.py

**Назначение:** Дополнительные границы наблюдения и обратимой миграции.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/session.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_observation_migration_regression.py

**Назначение:** Регрессии миграции позиций наблюдения на старых и живых БД.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/schema.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_observation_notification.py

**Назначение:** Extra safety coverage for notification arguments and terminal output.

**Публичные функции:**
- `test_notification_treats_leading_dash_and_nul_as_data`
- `test_observation_rejects_ignored_ending_flags_before_database`
- `test_seatbelt_sandbox_refuses_cycle_before_launch`
- `test_terminal_control_bytes_are_rendered_inert`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/store.py`, `orchestrator/watch.py`

**Импортируется:** —

## tests/test_outcome_integrity.py

**Назначение:** Юнит-тесты помощников гейта неослабления по исходам

**Публичные функции:**
- `junit`
- `vitest`

**Импортирует:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`

**Импортируется:** —

## tests/test_outcome_integrity_added_lines.py

**Назначение:** Разбор добавленных строк `git diff -M -U0` гейта исходов (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/project_profile.py`, `tests/sandbox.py`

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

**Назначение:** Тесты команды pin.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/pin.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pin_prune_orphan_guards.py

**Назначение:** Уточнения ANSWER-2 задачи 01M5M675F6K2TE7TTJN3AET4PP, не покрытые её

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/pin.py`, `orchestrator/prune.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_plan_appendix_ci.py

**Назначение:** Юнит-тесты `scripts/plan_appendix_ci.py` (SPEC 01M443HV9SJYVYQTHJSQ87QV68):

**Публичные функции:**
- `workflow`

**Импортирует:** `scripts/plan_appendix_ci.py`

**Импортируется:** —

## tests/test_plank_helper.py

**Назначение:** Юнит-тесты помощника планки `_pult.py` (SPEC 01M44EP4Q927DJXVX9YMMZ0B7V):

**Публичные функции:**
- `load_helper`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_plank_run_edges.py

**Назначение:** Углы `plank-run` и восстановления удалённых файлов, не покрытые

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`

**Импортируется:** —

## tests/test_preflight.py

**Назначение:** `orchestrator/preflight.py`: вырожденные входы предпроверки, которых не

**Публичные функции:**
- `run_preflight`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/preflight.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_preflight_step_provider.py

**Назначение:** Юнит-тесты предполёта шага по провайдеру шага (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/doctor/preflight.py`

**Импортируется:** —

## tests/test_profile_layers_declared.py

**Назначение:** Явное пустое `layers: []` компонента pytest — строгий режим гейта исходов (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 7).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/project_profile.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_program_spend_reseed.py

**Назначение:** Юнит-тесты пересева программного расхода из RETRO (orchestrator/budget.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_project_components.py

**Назначение:** Юнит-тесты компонентов проекта в `orchestrator/project_profile.py` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/project_profile.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_project_profile.py

**Назначение:** Юнит-тесты `orchestrator/project_profile.py` и правила имени

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_project_profile_gates.py

**Назначение:** Гейты тестов у внешнего проекта: запись о пропуске проверки без профиля

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_project_protected_paths.py

**Назначение:** Юнит-тесты перечня защищённых путей проекта в местах сверки, которые не

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `scripts/guard.py`

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

## tests/test_prune_abolished_rules.py

**Назначение:** `prune`: свойства отбора, не покрытые долгоживущим файлом задачи

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/prune.py`, `orchestrator/suite_lock.py`, `tests/sandbox.py`

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

## tests/test_pull_autoresolve_step_journal.py

**Назначение:** Отказ коммита подтяжки при авторазрешении конфликта карты пишет запись журнала до эскалации (SPEC 01M4JMMH70NWJG72G422BFY1KC, требование 2).

**Публичные функции:** (нет)

**Импортирует:** `tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py`

**Импортируется:** —

## tests/test_pull_conflict_marker_states.py

**Назначение:** Юнит-тесты набора состояний, эскалация которых по НЕРАЗРЕШЁННОМУ

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/auto.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/pull.py`, `orchestrator/pull_main.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_auto_cycle.py`

**Импортируется:** —

## tests/test_pull_long_lived_plank.py

**Назначение:** Юнит-тесты прогона планки после подтяжки main с долгоживущей группой

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pull_main_unavailable.py

**Назначение:** Команда `pull-main` при молчании git: именованный отказ, а не «main уже в ветке».

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fsm.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`

**Импортируется:** —

## tests/test_pytest_own_result_ids.py

**Назначение:** Идентификаторы в результатах мест запуска `pytest-own` — в форме от

**Публичные функции:**
- `own_profile`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_pytest_summary_pump.py

**Назначение:** Юнит-тесты распознавания итоговой строки pytest и её передачи насосом

**Публичные функции:**
- `tool_result_line`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_reference_command.py

**Назначение:** Команда `reference <проект>`, вход справочника без задачи и сводка `target-init`: края разбора.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/projects.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** —

## tests/test_refusal_classes.py

**Назначение:** Юнит-тесты единого перечня классов отказов

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/fixation.py`

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

## tests/test_report_argv_rerun_ban.py

**Назначение:** Запрет плагинов повторов в прогоне компонента по отчёту и его признак в

**Публичные функции:**
- `artel_profile`
- `component_profile`
- `digest`
- `old_data`
- `own_profile`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/project_profile.py`

**Импортируется:** —

## tests/test_report_project_label.py

**Назначение:** Метка проекта в HTML `report`: задача с `tasks.target` NULL и метка

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/report.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортируется:** `tests/test_sandbox_retry_pause.py`

## tests/test_review_long_lived_exclude.py

**Назначение:** Юнит-тесты исключения долгоживущих файлов перечня лока из diff пакета

**Публичные функции:**
- `boundary_markers`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/test_amend_long_lived.py`

**Импортируется:** —

## tests/test_review_package.py

**Назначение:** Тесты ревью-пакета — входа ревьювера (см. tasks/T011/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_review_package_map.py

**Назначение:** Юнит-тесты исключения `docs/codebase-map.md` из diff ревью-пакета

**Публичные функции:**
- `chunk`
- `matches`

**Импортирует:** `orchestrator/advance_gates/capacity.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_rounds.py

**Назначение:** `orchestrator/rounds.py` — свойства подсчёта «кругов до кода», не

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/report.py`, `orchestrator/rounds.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_runner_model_preflight.py

**Назначение:** Юнит-тесты запуска шага роли по абсолютному пути из резолва манифеста

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_runner_role_model.py`

**Импортируется:** `tests/test_journal_warning_once.py`, `tests/test_providers.py`

## tests/test_runner_pre_step_pull.py

**Назначение:** Юнит-тесты подтяжки `main` перед шагом разработчика и выбора ответов

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/fsm.py`, `orchestrator/pull.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

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

**Назначение:** Тесты перехвата git в песочнице.

**Публичные функции:** (нет)

**Импортирует:** `tests/sandbox.py`

**Импортируется:** —

## tests/test_sandbox_determinism_helpers.py

**Назначение:** Помощники песочницы детерминизма тестов (SPEC 01M4G8MNEPECNX1TCEDW4T4RPX):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/doctor/orphans.py`, `orchestrator/liveness.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_sandbox_retry_pause.py

**Назначение:** Юнит-тесты умолчания песочницы для паузы повтора агента — `TmpRootTest`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/runner.py`, `tests/sandbox.py`, `tests/test_agent_prompt.py`, `tests/test_review_freshness.py`

**Импортируется:** —

## tests/test_sandbox_time_with_sleep.py

**Назначение:** Юнит-тесты заместителя `time` песочницы — `TimeWithSleep`/`patch_sleep`/

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/runner.py`, `tests/sandbox.py`

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

## tests/test_snapshot_history.py

**Назначение:** Команда `artifact-history-snapshots` (SPEC 01M4M68557TT4KYN814H8AZ01A):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_spec_audit_gate.py

**Назначение:** Аудит SPEC (SPEC 01M4MQAGRWMWR0GFDM9086P3TD) — свойства журнала визита,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/auto.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_spec_audit_witness.py

**Назначение:** Граничные варианты свидетельства свежести, дополняющие продуктовую планку.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`

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

## tests/test_step_note_contract.py

**Назначение:** Контракт записки шага между автокоммитом и брифом (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/checkpoint.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_step_project.py

**Назначение:** Проект задачи на пути шага роли и проверка `project_skills` — свойства

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`

**Импортируется:** —

## tests/test_step_refixation.py

**Назначение:** Юнит-тесты перефиксации sha на пути отклонённого перехода FSM (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_git_fixation.py`

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

## tests/test_store_db_tracking.py

**Назначение:** Учёт соединений `store.db()`: явно закрытое соединение выходит из учёта.

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

## tests/test_suite_duration.py

**Назначение:** Unit cases for full-suite duration observations.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_suite_lock.py

**Назначение:** Юнит-тесты замка полных прогонов машины `orchestrator/suite_lock.py` и

**Публичные функции:**
- `foreign_lock`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/models.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `tests/sandbox.py`, `tests/test_approve_acceptance_full_suite.py`

**Импортируется:** —

## tests/test_suite_near_limit.py

**Назначение:** Юнит-тесты сигнала «длительность близка к пределу» (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/project_profile.py`, `orchestrator/suite_lock.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_suite_run.py

**Назначение:** Юнит-тесты `orchestrator/suite_run.py` и сохранения итогов полного набора

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_suite_run_deferred_journal.py

**Назначение:** Юнит-тесты отложенного журнала, нумерации логов и «прогон уже идёт»

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_targets_rerun_ban_wrapper.py

**Назначение:** Граница запрета повторов в `targets.check`: команда-обёртка компонента

**Публичные функции:**
- `entry`

**Импортирует:** `orchestrator/targets.py`

**Импортируется:** —

## tests/test_task_component_places.py

**Назначение:** Места задачи на записи из нескольких компонентов (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 2, таблица «Места задачи и исход при отказе `for_task`»): профиль компонента задачи и отказ вместо пропуска при отказе `for_task`.

**Публичные функции:**
- `flow`
- `matrix`
- `outcome_text`
- `patch_all`
- `yielding`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_source.py`, `orchestrator/config.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `tests/sandbox.py`

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

## tests/test_test_integrity_helper_heirs.py

**Назначение:** Наследники класса с изменённой цепочкой помощников вне диффа и сбой

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_test_rule_stats.py

**Назначение:** Юнит-тесты `scripts/test_rule_stats.py` (SPEC 01M3XR84299TD6V6E16D2PNXH4)

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`

**Импортируется:** —

## tests/test_tests_writing_new_module_dir.py

**Назначение:** Юнит-тесты засчитывания «нового модуля» гейтом честного FAIL_TO_PASS

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/project_profile.py`

**Импортируется:** —

## tests/test_timeout_checkpoint.py

**Назначение:** Юнит-тесты `checkpoint.commit_timeout_checkpoint` (tasks/T041/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_git_fixation.py`

**Импортируется:** `tests/test_checkpoint_zone_filter.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`

## tests/test_token_rate_divergence.py

**Назначение:** Юнит-тесты сверки тарифа токенов с фактом CLI при записи шага

**Публичные функции:**
- `cost`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/models.py`, `orchestrator/report.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_tz_check.py

**Назначение:** Юнит-тесты разбора `orchestrator.tz_check` (SPEC 01M598KY8V2P2GRD5Q67DRAZNA)

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/tz_check.py`

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

## tests/test_vitest_summary_pump.py

**Назначение:** Юнит-тесты передачи сводки Vitest насосом вывода шага

**Публичные функции:**
- `tool_result_line`

**Импортирует:** `orchestrator/agent_log.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_watch.py

**Назначение:** Юнит-тесты `orchestrator/watch.py` (SPEC 01M1VBEKRN0GA029J98S0K2DAQ) —

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_workspace.py

**Назначение:** Тесты рабочих копий задач.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_workspace_clone_docs_refs.py

**Назначение:** Юнит-тест края подтяжки ссылок документов при заведении клона (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_worktree_db_files.py

**Назначение:** Файлы БД пульта в дереве: граница «своя БД пульта», уборка без

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/advance_gates/zones.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —
