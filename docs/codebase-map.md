---
built_at_sha: c30e098d0ed2383fde45199defabbaa1a4e18cf7
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

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/plank_layout.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/reporters/outcome.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_durations.py`, `orchestrator/suite_lock.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/mutation_run.py`, `orchestrator/notes.py`, `orchestrator/plank_run.py`, `orchestrator/project_profile.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/report_outcome_sandbox.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_summary_deselected.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py`, `tests/test_01m5n8asj63zkf3m9etc7a3p5v_durations_reader_failure.py`, `tests/test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py`, `tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py`, `tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py`, `tests/test_acceptance.py`, `tests/test_acceptance_collect.py`, `tests/test_acceptance_file_time.py`, `tests/test_acceptance_own_launch.py`, `tests/test_acceptance_plank_exclude_lock.py`, `tests/test_acceptance_plank_layout_refusal.py`, `tests/test_acceptance_pycache.py`, `tests/test_acceptance_seed_repeat.py`, `tests/test_acceptance_suite_profile.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_branch_freshness_gate.py`, `tests/test_component_checks.py`, `tests/test_component_report_run.py`, `tests/test_doc_commit_module.py`, `tests/test_docs_dir_layout.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_full_suite_reuse.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_transitions.py`, `tests/test_merge_outcome_module.py`, `tests/test_model_sets.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_plank_run_edges.py`, `tests/test_project_profile.py`, `tests/test_pull.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_report_argv_rerun_ban.py`, `tests/test_report_outcome_module.py`, `tests/test_suite_lock.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_task_component_places.py`, `tests/test_worktree_db_files.py`

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
- `is_repeat`
- `long_lived_manifest`
- `long_lived_manifest_rel`
- `not_passed_kind`
- `outcome_kind`
- `record_criterion`
- `record_location`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/agent_log.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/amend.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_docs_dir_layout.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_guard_plank_bans.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_project_profile_gates.py`, `tests/test_refusal_classes.py`, `tests/test_review_long_lived_exclude.py`

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

**Импортируется:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/answer.py`, `orchestrator/fsm.py`, `orchestrator/merge_after.py`, `tests/components_outcome_sandbox.py`, `tests/prior_outcome_sandbox.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_start_after_write.py`, `tests/test_answer_mandate.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_mandate_file_path_token.py`, `tests/test_mandate_matrix_form.py`, `tests/test_mandate_profile_scope.py`, `tests/test_mandate_test_id.py`, `tests/test_merge_after_module.py`, `tests/test_outcome_components_module.py`, `tests/test_task_component_places.py`

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

**Импортируется:** `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/review.py`, `tests/components_outcome_sandbox.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5fryvp4nf81vt00fyphpwjh_outcome_action_texts.py`, `tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py`, `tests/test_gate_owner_marker.py`, `tests/test_mandate_test_id.py`, `tests/test_outcome_components_module.py`, `tests/test_outcome_gate_module.py`, `tests/test_refusal_classes.py`

## orchestrator/advance_gates/plan_appendix.py

**Назначение:** Гейт применимости приложений PLAN на выходе `in_dev` (SPEC

**Публичные функции:**
- `git_apply`
- `in_base`
- `skip_in_base`

**Импортирует:** `orchestrator/advance_gates/_base.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_plan_appendix.py`, `tests/test_project_protected_paths.py`, `tests/test_refusal_classes.py`

## orchestrator/advance_gates/refusal_classes.py

**Назначение:** Классы отказов перехода из агентских состояний (SPEC

**Публичные функции:**
- `refusal_class`

**Импортирует:** —

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/fsm.py`, `orchestrator/watch.py`, `tests/merge_outcome_sandbox.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5fryvp4nf81vt00fyphpwjh_outcome_action_texts.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_answer_in_dev_gate_journal.py`, `tests/test_merge_outcome_module.py`, `tests/test_network_address_gate.py`, `tests/test_refusal_classes.py`

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

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/role_prompt.py`, `orchestrator/rounds.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_audit_signal.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_division_epic.py`, `tests/test_analyst_role.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_audit_witness.py`

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

**Импортируется:** `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/report.py`, `orchestrator/review.py`, `scripts/test_rule_stats.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m5n9wk9sgb7kdyjp736dp6cv_fixture_gate.py`, `tests/test_01m5n9wk9sgb7kdyjp736dp6cv_fixture_records.py`, `tests/test_answer_mandate.py`, `tests/test_class_mandate_units.py`, `tests/test_guard_helper_scope.py`, `tests/test_guard_parametrize_variants.py`, `tests/test_invariants.py`, `tests/test_refusal_classes.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`

## orchestrator/advance_gates/tests_writing.py

**Назначение:** `_tests_writing_*`, `_origin_push_gate`, `_registry_gate`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifacts.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/reporters/outcome.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/two_sided.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/review.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_network_address_gate.py`, `tests/test_plank_helper.py`, `tests/test_project_profile_gates.py`, `tests/test_refusal_classes.py`, `tests/test_tests_writing_new_module_dir.py`

## orchestrator/advance_gates/two_sided.py

**Назначение:** Двусторонний прогон смены ожидания из раздела SPEC «Меняемое поведение» на переходе `in_dev -> verifying` (SPEC 01M45FJD46BX45VHC36S4VS9QN, требование 10).

**Публичные функции:**
- `run`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`

**Импортируется:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/report.py`, `tests/merge_outcome_sandbox.py`, `tests/report_outcome_sandbox.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py`, `tests/test_gate_owner_marker.py`, `tests/test_guard_assertion_changes.py`, `tests/test_guard_parametrize_variants.py`, `tests/test_merge_outcome_module.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_report_outcome_module.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/auto.py`, `orchestrator/pause.py`, `orchestrator/plank_run.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/watch.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_alert.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_failure_cli_isolation.py`, `tests/test_agent_log.py`, `tests/test_auto_cycle.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_kill_cleanup.py`, `tests/test_observation_acceptance_return.py`, `tests/test_pause_now.py`, `tests/test_providers_codex.py`, `tests/test_pytest_summary_pump.py`, `tests/test_report.py`, `tests/test_step_cost.py`, `tests/test_vitest_summary_pump.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/amend.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/failure_classification.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `orchestrator/pull.py`, `orchestrator/reference_cache.py`, `orchestrator/report.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_watch_layer.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_auto_stop.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_auto_cycle.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_coldstart.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_fsm_map_regen.py`, `tests/test_gitcmd_push_point.py`, `tests/test_main_copy_watch.py`, `tests/test_merge_reference_step.py`, `tests/test_prune.py`, `tests/test_reference_command.py`, `tests/test_runner_wave_breaker.py`, `tests/test_stall_alerts.py`, `tests/test_suite_duration.py`, `tests/test_token_rate_divergence.py`

## orchestrator/amend.py

**Назначение:** Команда `amend-tests`: штатная правка зафиксированной планки приёмки

**Публичные функции:**
- `cmd_amend_tests`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`

## orchestrator/answer.py

**Назначение:** Команда `answer`: канал ответа Оператора на эскалацию (SPEC T075,

**Публичные функции:**
- `cmd_answer`
- `cmd_zones_extend`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/components_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/prior_outcome_sandbox.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_answer.py`, `tests/test_answer_mandate.py`, `tests/test_class_mandate_units.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_lease_run_task_command.py`, `tests/test_mandate_matrix_form.py`, `tests/test_merge_after_module.py`, `tests/test_outcome_components_module.py`, `tests/test_outcome_gate_module.py`

## orchestrator/appendix_tree.py

**Назначение:** Приложения PLAN на дереве полного прогона ветки задачи (SPEC

**Публичные функции:**
- `apply_in_order`
- `read_plan`
- `suite_tree`

**Импортирует:** `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/mutation_run.py`, `orchestrator/pull.py`, `orchestrator/suite_run.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_appendix_tree.py`, `tests/test_suite_run.py`, `tests/test_task_component_places.py`

## orchestrator/artel.py

**Назначение:** Артель — FSM-оркестратор (CLI).

**Публичные функции:**
- `main`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/auto.py`, `orchestrator/board.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/conventions.py`, `orchestrator/docs_fetch.py`, `orchestrator/dry_run.py`, `orchestrator/epics.py`, `orchestrator/explore_metric.py`, `orchestrator/fsm.py`, `orchestrator/knowledge_cards.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/models.py`, `orchestrator/mutation_run.py`, `orchestrator/notes.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/plank_run.py`, `orchestrator/pool_seal.py`, `orchestrator/preflight.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/pull_main.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/snapshot.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/venv.py`, `orchestrator/version.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py`, `tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_texts.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_targets_migrate.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_stamp.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_entry.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_division_epic.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_epic_commands.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_auto_stop.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_envelope_run.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_alert.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_view.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_watch.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_start_after_write.py`, `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_drafts.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_epic_ref.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_migration.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_board_command.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_external_refs.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_report_model.py`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_amend.py`, `tests/test_analyst_role.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artel_bootstrap.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_canary_detach_result.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_run_task.py`, `tests/test_canary_runs.py`, `tests/test_canary_sets.py`, `tests/test_canary_template_flag.py`, `tests/test_detached_cycle.py`, `tests/test_doc_commit_module.py`, `tests/test_epic_draft_promote_unsupported_project.py`, `tests/test_epic_drafts_units.py`, `tests/test_epic_supervisor_units.py`, `tests/test_invariants.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_launch_observation_refusals.py`, `tests/test_main_ci_line.py`, `tests/test_mandate_matrix_form.py`, `tests/test_models.py`, `tests/test_new_argv_parsing.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_edges.py`, `tests/test_observation_notification.py`, `tests/test_start_after_units.py`, `tests/test_task_model_set_units.py`

## orchestrator/artifact_branch.py

**Назначение:** Ссылка документов задачи `refs/artifacts/<id>` в репозитории задачи —

**Публичные функции:**
- `append_passport_line`
- `branch_name`
- `commit_change`
- `commit_files`
- `deferred_sends`
- `diff_names`
- `docs_dir`
- `docs_root`
- `epic_ref_key`
- `fetch_all_from_origin`
- `fetch_from_origin`
- `git`
- `is_epic_ref_key`
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
- `send_pending`
- `show`
- `task_repo`
- `write_commit`

**Импортирует:** `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/appendix_tree.py`, `orchestrator/artel.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/epics.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/mutation_run.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_mandate.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_branch_server_retry.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_division_parent_cleanup.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_fetch_edges.py`, `tests/test_doctor.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_git_fixation.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_preflight.py`, `tests/test_pull.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace_clone_docs_refs.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

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
- `cmd_auto_epic`
- `drop_dead_supervisor_lock`
- `live_epic_children`
- `live_supervisor_lock`

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/amend.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/models.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/pull.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/advance_gates/review.py`, `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/epics.py`, `orchestrator/fsm_advance.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_auto_stop.py`, `tests/test_analyst_role.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_epic_supervisor_units.py`, `tests/test_git_fixation.py`, `tests/test_plan_appendix.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_runner_model_preflight.py`, `tests/test_spec_audit_gate.py`, `tests/test_stall_alerts.py`

## orchestrator/board.py

**Назначение:** Модель доски: одна проекция БД и журнала проекта, из которой строятся

**Публичные функции:**
- `build_model`
- `cmd_board`
- `render_html`
- `render_json`
- `render_md`
- `waiting_on`

**Импортирует:** `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/watch.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/epics.py`, `orchestrator/report.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_view.py`, `tests/test_board_refs_units.py`, `tests/test_epics_board_units.py`, `tests/test_invariants.py`

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

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/conventions.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `scripts/codebase_map.py`

**Импортируется:** `orchestrator/doctor/__init__.py`, `orchestrator/knowledge_cards.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_brief_map_interpreter.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_answer_branch_reads.py`, `tests/test_auto_cycle.py`, `tests/test_brief.py`, `tests/test_conventions.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_long_lived_manifest.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_role_prompt_test_author_mission.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_step_note_contract.py`, `tests/test_step_project.py`

## orchestrator/budget.py

**Назначение:** Потолок задачи: значение из SPEC, блокировка `run`, реакция после шага.

**Публичные функции:**
- `apply_division_frame`
- `apply_operator_frame`
- `apply_spec_budget`
- `budget_block`
- `calibration_warning`
- `check_epic_alert`
- `check_program_spend`
- `cmd_budget`
- `count_zone_paths`
- `enforce_budget`
- `epic_envelope_warning`
- `epic_spent`
- `epic_warning_text`
- `journal_warning_once`
- `recommended_budget_usd`
- `reseed_program_spend`
- `spec_budget`
- `spent_with_estimate`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/retro.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/board.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/epics.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/pause.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/watch.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_envelope_run.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_drafts.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_budget_calibration_table.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_doctor.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_knowledge_command.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_program_spend_reseed.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_zone_line_parse.py`

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

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary_drive.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/notes.py`, `orchestrator/pin.py`, `orchestrator/pool_seal.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_01m5mvg2b1ygvptzwkb18evghz_row_write_deadline.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py`, `tests/test_canary.py`, `tests/test_canary_acceptance_reason.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_child_row_write.py`, `tests/test_canary_codex_clone_auth.py`, `tests/test_canary_detach_result.py`, `tests/test_canary_drive.py`, `tests/test_canary_escalation_roles_storage.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_profile_safety.py`, `tests/test_canary_run_task.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_canary_template_flag.py`, `tests/test_doctor.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_parent_task_division.py`, `tests/test_pin_prune_orphan_guards.py`

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
- `branch_name`
- `branch_refusal`
- `branch_template`
- `cmd_init`
- `cmd_link`
- `cmd_log`
- `cmd_new`
- `cmd_show`
- `cmd_status`
- `division_branches`
- `new_cli_target`
- `slugify`
- `spawn_subtask`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/board.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/epics.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/liveness.py`, `orchestrator/merge_after.py`, `orchestrator/merge_queue.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `orchestrator/repo_context.py`, `orchestrator/retro.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/tz_check.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/epics.py`, `orchestrator/fsm.py`, `tests/sandbox.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_worktree.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_closed_as.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_division_epic.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_envelope_run.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_external_refs.py`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer_gate.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_pin_divergence.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_tz_zones_parsing.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_coldstart.py`, `tests/test_division_order_units.py`, `tests/test_doctor.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_merge_after_module.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock_module.py`, `tests/test_merge_queue.py`, `tests/test_models_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parent_task_division.py`, `tests/test_pause_now.py`, `tests/test_plan_appendix.py`, `tests/test_project_protected_paths.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_slugify.py`, `tests/test_spec_budget.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_step_cost.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_workspace.py`, `tests/test_zone_line_parse.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/brief.py`, `orchestrator/fsm.py`, `orchestrator/pause.py`, `orchestrator/pull.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/components_outcome_sandbox.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_watch_layer.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_worktree.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_alert.py`, `tests/test_artifact_materialization.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_stray_acceptance_files.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_checkpoint_zone_mandate.py`, `tests/test_docs_dir_layout.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_main_copy_watch.py`, `tests/test_merge_outcome_module.py`, `tests/test_outcome_gate_module.py`, `tests/test_pause_now.py`, `tests/test_plank_helper.py`, `tests/test_plank_run_edges.py`, `tests/test_role_commit_by_pult.py`, `tests/test_step_autocommit.py`, `tests/test_step_note_contract.py`, `tests/test_timeout_checkpoint.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/auto.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/pin.py`, `orchestrator/watch.py`, `tests/merge_outcome_sandbox.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_acceptance.py`, `tests/test_auto_cycle.py`, `tests/test_ci_actions_fallback.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_project_gh_address.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_invariants.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_fetched_repo.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_pin.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_plan_appendix.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_verifying_ceiling.py`

## orchestrator/ci_rerun.py

**Назначение:** Команда `ci-rerun`: повтор упавшего CI ветки задачи в `verifying`

**Публичные функции:**
- `cmd_ci_rerun`

**Импортирует:** `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/fsm.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_lease_run_task_command.py`

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

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/retro.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_artifact_ref_sync.py`, `tests/test_detached_cycle.py`, `tests/test_division_parent_cleanup.py`, `tests/test_done_branch_cleanup.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_multitarget_invariants.py`, `tests/test_retro.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_task_id_prefix_regression.py`

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
- `is_protected_zone`

**Импортирует:** —

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/auto.py`, `orchestrator/board.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/context_package.py`, `orchestrator/conventions.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/doctor/observations.py`, `orchestrator/epics.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/models.py`, `orchestrator/mutation_run.py`, `orchestrator/notes.py`, `orchestrator/parallel_limit.py`, `orchestrator/pin.py`, `orchestrator/plank_run.py`, `orchestrator/pool_seal.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/providers/base.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/roles.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/schema.py`, `orchestrator/session.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `orchestrator/targets.py`, `orchestrator/tz_check.py`, `orchestrator/venv.py`, `orchestrator/version.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/ci_protected_paths.py`, `scripts/guard.py`, `scripts/test_rule_stats.py`, `tests/components_outcome_sandbox.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/report_outcome_sandbox.py`, `tests/sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py`, `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_codebase_map_root.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_brief_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py`, `tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_guard.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_form.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_match.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_targets_knowledge.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cli.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py`, `tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py`, `tests/test_01m5n8asj63zkf3m9etc7a3p5v_durations_reader_failure.py`, `tests/test_01m5n9v4s984grrxsmbk5jx7v1_fixtures.py`, `tests/test_01m5n9wk9sgb7kdyjp736dp6cv_fixture_gate.py`, `tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py`, `tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py`, `tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py`, `tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_doctor_layer.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_targets_migrate.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_watch_layer.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_stamp.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_doctor.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_entry.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_worktree.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_closed_as.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_guard_frame.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_division_epic.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_epic_commands.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_migration.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_auto_stop.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_envelope_run.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_alert.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_view.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_watch.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_start_after_write.py`, `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_drafts.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_epic_ref.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_migration.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_board_command.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_external_refs.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_report_model.py`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py`, `tests/test_acceptance.py`, `tests/test_acceptance_seed_repeat.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artel_bootstrap.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_calibration_table.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_codex_clone_auth.py`, `tests/test_canary_doctor_owner.py`, `tests/test_canary_drive.py`, `tests/test_canary_escalation_roles_storage.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_profile_safety.py`, `tests/test_canary_run_task.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_canary_template_flag.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_catalog_fixture.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_mandate.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_project_gh_address.py`, `tests/test_ci_protected_paths.py`, `tests/test_ci_status.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_codebase_map.py`, `tests/test_codex_login_shell_path.py`, `tests/test_coldstart.py`, `tests/test_component_checks.py`, `tests/test_conftest_role_guard.py`, `tests/test_conventions.py`, `tests/test_cycle_hint.py`, `tests/test_detached_cycle.py`, `tests/test_division_order_units.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doc_commit_module.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_done_branch_cleanup.py`, `tests/test_draft_mr_commits.py`, `tests/test_draft_mr_remote_base_args.py`, `tests/test_dry_run.py`, `tests/test_epic_draft_promote_unsupported_project.py`, `tests/test_epic_drafts_units.py`, `tests/test_epic_ref_scan_filters.py`, `tests/test_epic_supervisor_units.py`, `tests/test_epics_board_units.py`, `tests/test_failure_classification.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_gitcmd_push_point.py`, `tests/test_guard_division_section.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_knowledge_command.py`, `tests/test_launch_observation_refusals.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_template_shape.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_fetched_repo.py`, `tests/test_main_ci_line.py`, `tests/test_main_copy_watch.py`, `tests/test_merge_after_module.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock_module.py`, `tests/test_merge_outcome_module.py`, `tests/test_merge_queue.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_network_address_gate.py`, `tests/test_new_argv_parsing.py`, `tests/test_notes_module.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_edges.py`, `tests/test_outcome_gate_module.py`, `tests/test_pair_suspension_units.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_pin_update_stale_cycles.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_plank_run_edges.py`, `tests/test_preflight.py`, `tests/test_profile_layers_declared.py`, `tests/test_program_spend_reseed.py`, `tests/test_project_profile_gates.py`, `tests/test_project_protected_paths.py`, `tests/test_protected_paths_gate.py`, `tests/test_protected_test_settings.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_prune_abolished_rules.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_release.py`, `tests/test_repo_context.py`, `tests/test_report.py`, `tests/test_report_outcome_module.py`, `tests/test_report_project_label.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_role_commit_by_pult.py`, `tests/test_roles_map_fixture.py`, `tests/test_rounds.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_environment.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_session.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_snapshot_history.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stack.py`, `tests/test_stack_codex_section.py`, `tests/test_stack_optional_tools.py`, `tests/test_stack_parity_table.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_stale_cycles_start_precision.py`, `tests/test_stall_alerts.py`, `tests/test_start_after_units.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_project.py`, `tests/test_step_refixation.py`, `tests/test_store_journal.py`, `tests/test_suite_duration.py`, `tests/test_suite_lock.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_test_rule_stats.py`, `tests/test_timeout_checkpoint.py`, `tests/test_token_rate_divergence.py`, `tests/test_verifying_ceiling.py`, `tests/test_version.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_workspace_wrapper_excludes.py`, `tests/test_worktree_db_files.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/context_package.py

**Назначение:** Опись компонентов и дисциплина частей контекстных пакетов — общий слой

**Публичные функции:**
- `discipline`
- `render_component`
- `sha256_of`
- `split_into_parts`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/brief.py`, `orchestrator/review.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py`, `tests/test_brief.py`, `tests/test_review_package.py`

## orchestrator/conventions.py

**Назначение:** Конвенции внешнего проекта из файла пульта: чтение, заголовок отметки

**Публичные функции:**
- `base_commit`
- `brief_text`
- `clone_refusal`
- `cmd_conventions_stamp`
- `drift`
- `parse`
- `path`
- `read_file`
- `rel`
- `render_header`
- `stamp_refusal`
- `tree_objects`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/brief.py`, `orchestrator/doctor/__init__.py`, `tests/test_conventions.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/ci.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/conventions.py`, `orchestrator/cycle_hint.py`, `orchestrator/doctor/artifact_branches.py`, `orchestrator/doctor/auto_ack.py`, `orchestrator/doctor/branch_freshness.py`, `orchestrator/doctor/canary_pool.py`, `orchestrator/doctor/canary_sets.py`, `orchestrator/doctor/cli.py`, `orchestrator/doctor/git_hooks.py`, `orchestrator/doctor/hung_test_watchdog.py`, `orchestrator/doctor/ignored_artifacts.py`, `orchestrator/doctor/isolation.py`, `orchestrator/doctor/lease_alerts.py`, `orchestrator/doctor/leases.py`, `orchestrator/doctor/live_smoke.py`, `orchestrator/doctor/machine_load.py`, `orchestrator/doctor/main_ci.py`, `orchestrator/doctor/map_growth.py`, `orchestrator/doctor/misc_checks.py`, `orchestrator/doctor/model_catalog.py`, `orchestrator/doctor/model_tariffs.py`, `orchestrator/doctor/observations.py`, `orchestrator/doctor/orphans.py`, `orchestrator/doctor/preflight.py`, `orchestrator/doctor/project_checks.py`, `orchestrator/doctor/project_conventions.py`, `orchestrator/doctor/recovery.py`, `orchestrator/doctor/root_pin.py`, `orchestrator/doctor/stale_cycles.py`, `orchestrator/doctor/suite_duration.py`, `orchestrator/doctor/worktree_db.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/liveness.py`, `orchestrator/merge_lock.py`, `orchestrator/models.py`, `orchestrator/notes.py`, `orchestrator/pool_seal.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/providers/codex.py`, `orchestrator/repo_context.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`

**Импортируется:** —

## orchestrator/doctor/artifact_branches.py

**Назначение:** Пакет orchestrator/doctor -- сверка ссылок документов задач

**Публичные функции:**
- `check_artifact_ref_sync`

**Импортирует:** `orchestrator/fsm.py`

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

**Импортирует:** `orchestrator/fsm.py`

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
- `project_support_check`
- `targets_local_layer_check`

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

**Импортирует:** `orchestrator/fsm.py`

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

**Импортирует:** `orchestrator/fsm.py`

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
- `check_target_wrapper_worktrees`
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

## orchestrator/doctor/project_conventions.py

**Назначение:** Пакет orchestrator/doctor -- дрейф конвенций внешнего проекта: файл пульта

**Публичные функции:**
- `check_project_conventions`

**Импортирует:** —

**Импортируется:** `orchestrator/doctor/__init__.py`

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

## orchestrator/epics.py

**Назначение:** Эпик — сущность пульта: задачи одного проекта под общей целью (SPEC

**Публичные функции:**
- `binding_refusal`
- `cmd_add`
- `cmd_close`
- `cmd_decision`
- `cmd_draft`
- `cmd_draft_add`
- `cmd_draft_drop`
- `cmd_draft_edit`
- `cmd_draft_promote`
- `cmd_edit`
- `cmd_envelope`
- `cmd_epic`
- `cmd_export`
- `cmd_new`
- `cmd_parallel`
- `cmd_remove`
- `cmd_restore`
- `cmd_retry`
- `cmd_show`
- `cmd_start_after`
- `cmd_stop`
- `counts_text`
- `create_from_division`
- `draft_address`
- `envelope_warning_text`
- `new_epic_id`
- `not_found`
- `parse_address`
- `ref_files`
- `show_lines`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/board.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `tests/test_epic_draft_promote_unsupported_project.py`, `tests/test_epic_drafts_units.py`, `tests/test_invariants.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/cycle_hint.py`, `orchestrator/epics.py`, `orchestrator/fixation.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/models.py`, `orchestrator/pause.py`, `orchestrator/project_profile.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/board.py`, `orchestrator/canary.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/artifact_branches.py`, `orchestrator/doctor/branch_freshness.py`, `orchestrator/doctor/ignored_artifacts.py`, `orchestrator/doctor/orphans.py`, `orchestrator/epics.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/models.py`, `orchestrator/prune.py`, `orchestrator/pull_main.py`, `orchestrator/report.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/watch.py`, `orchestrator/zone_lock.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/sandbox.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_questions_matrix.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_division_epic.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_epic_commands.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py`, `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_canary_escalation_roles_storage.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_division_parent_cleanup.py`, `tests/test_docs_dir_layout.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_merge_conflict_note.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_merge_after_module.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_multitarget_invariants.py`, `tests/test_outcome_gate_module.py`, `tests/test_project_protected_paths.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_main_unavailable.py`, `tests/test_report_outcome_module.py`, `tests/test_review_freshness.py`, `tests/test_review_registry_gate.py`, `tests/test_role_commit_by_pult.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_suite_lock.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_verifying_ceiling.py`, `tests/test_zones_approve.py`

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

**Импортируется:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/fsm.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_artifact_ref_sync.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_full_suite_reuse.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_gate_clock_isolation.py`, `tests/test_merge_reference_step.py`, `tests/test_plan_appendix.py`, `tests/test_protected_paths_gate.py`, `tests/test_protected_test_settings.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_report_outcome_module.py`, `tests/test_task_component_places.py`, `tests/test_test_integrity_gate.py`, `tests/test_worktree_db_files.py`

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
- `read`
- `read_env`
- `read_stream`
- `remote_branch_sha`
- `remote_ref_state`
- `show`
- `url_key`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/keychain.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/conventions.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/dry_run.py`, `orchestrator/epics.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/mutation_run.py`, `orchestrator/notes.py`, `orchestrator/pin.py`, `orchestrator/plank_layout.py`, `orchestrator/pool_seal.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/suite_run.py`, `orchestrator/tz_check.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_answer_mandate.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_run_task.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_catalog_new_race.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doctor.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_draft_mr_commits.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_gate_owner_marker.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_carpentry.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_gitcmd_push_point.py`, `tests/test_gitcmd_reads.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_hosting_token_units.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_network_address_gate.py`, `tests/test_pin.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_project_profile_gates.py`, `tests/test_protected_paths_gate.py`, `tests/test_prune_abolished_rules.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_repo_context.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_role_model.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_spec_budget.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_project.py`, `tests/test_step_refixation.py`, `tests/test_task_component_places.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`, `tests/test_workspace_clone_docs_refs.py`, `tests/test_zones_gate.py`

## orchestrator/github_adapter.py

**Назначение:** GitHub-адаптер целевого `forge: github`: Draft-MR-флоу задачи (SPEC

**Публичные функции:**
- `ensure_draft_mr`
- `ensure_head_in_origin`
- `undraft_mr`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull_main.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_draft_mr_commits.py`, `tests/test_draft_mr_remote_base_args.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_git_fixation.py`, `tests/test_github_adapter.py`, `tests/test_long_lived_transitions.py`, `tests/test_merge_after_module.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_outcome_gate_module.py`, `tests/test_protected_test_settings.py`

## orchestrator/idgen.py

**Назначение:** Генератор идентификатора задачи (SPEC T094, требование 2).

**Публичные функции:**
- `is_task_id_form`
- `new_task_id`

**Импортирует:** —

**Импортируется:** `orchestrator/catalog.py`, `orchestrator/epics.py`, `orchestrator/merge_after.py`, `orchestrator/prune.py`, `scripts/guard.py`, `tests/report_outcome_sandbox.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_doctor.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_worktree.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_closed_as.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_epic_commands.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_migration.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_drafts.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_epic_ref.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_migration.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_board_command.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_external_refs.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_report_model.py`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_gitcmd_push_point.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_merge_after_module.py`, `tests/test_workspace_wrapper_excludes.py`

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

**Импортируется:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/artel.py`, `orchestrator/notes.py`, `orchestrator/role_prompt.py`, `orchestrator/suite_lock.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_form.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_match.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_doc_commit_module.py`, `tests/test_knowledge_cards.py`, `tests/test_knowledge_command.py`

## orchestrator/lease.py

**Назначение:** Advisory-lease задачи: замок параллельных сессий CLI (SPEC T044).

**Публичные функции:**
- `acquire`
- `foreign_live_lease`
- `is_live`
- `process_alive`
- `release`
- `release_any`
- `run_locked`
- `run_task_command`
- `warn_foreign_live`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/epics.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pause.py`, `orchestrator/pull_main.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_division_epic.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_epic_commands.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_detached_cycle.py`, `tests/test_epic_supervisor_units.py`, `tests/test_lease.py`, `tests/test_lease_run_task_command.py`, `tests/test_session.py`, `tests/test_zone_lock.py`

## orchestrator/liveness.py

**Назначение:** Возраст heartbeat и адресуемость pid — общие для lease/merge_lock/doctor.

**Публичные функции:**
- `group_kill_detail`
- `owner_alive`
- `owner_pid`
- `terminate_process_group`

**Импортирует:** —

**Импортируется:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/prune.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `tests/prior_outcome_sandbox.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_01m5mvg2b1ygvptzwkb18evghz_row_write_deadline.py`, `tests/test_canary_doctor_owner.py`, `tests/test_doctor.py`, `tests/test_gate_owner_marker.py`, `tests/test_lease_run_task_command.py`, `tests/test_liveness.py`, `tests/test_merge_lock_module.py`, `tests/test_sandbox_determinism_helpers.py`, `tests/test_zone_lock.py`

## orchestrator/merge_after.py

**Назначение:** Зависимости мержа `merge_after`: заявление при `new` строкой ТЗ «Порядок: после …» (заявленное значение — сразу в колонке `merge_after`), сверка SPEC с заявленным на гейте SPEC, добавка `status` «[мерж после: …]» до `acceptance`, проверка в каналах переписывания, отказ на гейте мержа.

**Публичные функции:**
- `apply_plan`
- `check`
- `column`
- `declared_for_new`
- `declared_from_tz`
- `division_order`
- `division_order_items`
- `last_division_part`
- `lines_refusal`
- `mandate_value`
- `merge_gate_refuses`
- `record_added`
- `record_declared`
- `replace_divided`
- `rewrite`
- `rewrite_start_after`
- `role_step_started`
- `show_line`
- `spec_gate_declared_refusal`
- `spec_gate_value`
- `start_after_blocks`
- `start_after_pending`
- `start_after_value`
- `status_suffix`
- `stored`
- `value_refusals`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/advance_gates/mandate.py`, `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/board.py`, `orchestrator/catalog.py`, `orchestrator/epics.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/runner.py`, `orchestrator/zone_lock.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_start_after_write.py`, `tests/test_division_order_units.py`, `tests/test_invariants.py`, `tests/test_merge_after_module.py`, `tests/test_start_after_units.py`

## orchestrator/merge_lock.py

**Назначение:** Мьютекс merge-окна: один держатель на проект (SPEC T053; SPEC

**Публичные функции:**
- `acquire`
- `release`
- `run_window`
- `touch_heartbeat`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/session.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/doctor/__init__.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/merge_queue.py`, `orchestrator/notes.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock_module.py`, `tests/test_merge_queue.py`

## orchestrator/merge_queue.py

**Назначение:** Очередь FIFO ожидания мьютекса merge-окна (SPEC

**Публичные функции:**
- `queue_wait_minutes`
- `wait_for_window`
- `wait_suffix`

**Импортирует:** `orchestrator/config.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/catalog.py`, `orchestrator/fsm_merge_gate.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_merge_queue.py`

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

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/fsm.py`, `orchestrator/notes.py`, `orchestrator/roles.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/retro.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_agent_failure.py`, `tests/test_agent_prompt.py`, `tests/test_canary_sets.py`, `tests/test_catalog_fixture.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_canary_sets.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_model_sets.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_pair_suspension_units.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_roles_map_fixture.py`, `tests/test_runner_role_model.py`, `tests/test_stack.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_suite_lock.py`, `tests/test_task_model_set_units.py`, `tests/test_token_rate_divergence.py`, `tests/test_yaml_parsing.py`

## orchestrator/mutation_run.py

**Назначение:** Команда `mutation-run <id> --ref <base|head|worktree> --tests <путь>[,…]

**Публичные функции:**
- `background`
- `classify`
- `cmd_mutation_run`
- `patch_paths`
- `touches_tests`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/reporters/outcome.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_texts.py`

## orchestrator/notes.py

**Назначение:** Команда `note`: строка в копилку/бэклог/очередь изолированным коммитом

**Публичные функции:**
- `cmd_doc_commit`
- `cmd_note`
- `doc_commit_content`
- `pending_notes`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/knowledge_cards.py`, `orchestrator/merge_lock.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor/__init__.py`, `orchestrator/models.py`, `orchestrator/pool_seal.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py`, `tests/test_doc_commit_module.py`, `tests/test_knowledge_cards.py`, `tests/test_model_sets.py`, `tests/test_notes_module.py`, `tests/test_suite_near_limit.py`

## orchestrator/parallel_limit.py

**Назначение:** Лимитер параллельных задач: MAX_PARALLEL_TASKS (SPEC T060).

**Публичные функции:**
- `busy_other_tasks`
- `refusal`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/runner.py`, `tests/test_parallel_limit.py`

## orchestrator/pause.py

**Назначение:** Команда `pause`/`resume`: штатная приостановка задачи (SPEC T070).

**Публичные функции:**
- `cmd_pause`
- `cmd_pause_now`
- `cmd_resume`
- `is_paused`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/checkpoint.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_alert.py`, `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`, `tests/test_auto_cycle.py`, `tests/test_pause.py`, `tests/test_pause_now.py`

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

## orchestrator/plank_layout.py

**Назначение:** Выкладка планки в рабочую копию: самодостаточная часть (SPEC

**Публичные функции:**
- `drop_component_layout`
- `drop_layout`
- `exclude_layout`
- `exclude_pattern`
- `layout_mode`
- `layout_root`
- `plank_layout`
- `uses_plank_layout`

**Импортирует:** `orchestrator/gitcmd.py`

**Импортируется:** `orchestrator/acceptance.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/brief.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/doctor/cli.py`, `orchestrator/dry_run.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/knowledge_cards.py`, `orchestrator/mutation_run.py`, `orchestrator/notes.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/pull.py`, `orchestrator/reporters/outcome.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/suite_run.py`, `tests/components_outcome_sandbox.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/prior_outcome_sandbox.py`, `tests/report_outcome_sandbox.py`, `tests/sandbox.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py`, `tests/test_acceptance_plank_layout_refusal.py`, `tests/test_component_checks.py`, `tests/test_component_report_run.py`, `tests/test_fsm_autogate_plank_rule.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_gate_owner_marker.py`, `tests/test_guard_plank_bans.py`, `tests/test_mandate_file_path_token.py`, `tests/test_mandate_profile_scope.py`, `tests/test_mandate_test_id.py`, `tests/test_network_address_gate.py`, `tests/test_outcome_components_module.py`, `tests/test_outcome_gate_module.py`, `tests/test_profile_layers_declared.py`, `tests/test_project_components.py`, `tests/test_project_profile.py`, `tests/test_project_profile_gates.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_report_argv_rerun_ban.py`, `tests/test_report_outcome_module.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_task_component_places.py`, `tests/test_tests_writing_new_module_dir.py`

## orchestrator/projects.py

**Назначение:** Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

**Публичные функции:**
- `cmd_reference`
- `cmd_target_init`
- `cmd_targets_migrate`
- `init_project`
- `project_dir`
- `reference_summary`

**Импортирует:** `orchestrator/config.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor/__init__.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_artifact_ref_sync.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_multitarget.py`, `tests/test_reference_command.py`

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

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/liveness.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_prune.py`, `tests/test_prune_abolished_rules.py`

## orchestrator/pull.py

**Назначение:** Исходы подтяжки главной ветки в ветку задачи (роадмап §3, фаза R,

**Публичные функции:**
- `evaluate`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/alerts.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_source.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/ci_push_class.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/fsm.py`, `orchestrator/pull_main.py`, `orchestrator/runner.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_pull_main_unavailable.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_task_component_places.py`

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

**Импортируется:** `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/conventions.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/projects.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py`, `tests/test_merge_reference_step.py`, `tests/test_reference_command.py`

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
- `wrapper_paths`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/appendix_tree.py`, `orchestrator/artifact_branch.py`, `orchestrator/brief.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/conventions.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/mutation_run.py`, `orchestrator/notes.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/providers/claude.py`, `orchestrator/reference_cache.py`, `orchestrator/retro_corpus.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/suite_run.py`, `orchestrator/tz_check.py`, `orchestrator/workspace.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_stamp.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_entry.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`, `tests/test_acceptance_suite_profile.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_project_gh_address.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_epic_draft_promote_unsupported_project.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_gitcmd_push_point.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_project_protected_paths.py`, `tests/test_protected_paths_gate.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_reference_command.py`, `tests/test_repo_context.py`, `tests/test_task_component_places.py`, `tests/test_worktree_db_files.py`

## orchestrator/report.py

**Назначение:** Команда `report`: статический HTML-срез `state.db` + метрики гейтовой

**Публичные функции:**
- `cmd_report`
- `map_growth_calibration_median`
- `map_growth_cost_estimate`
- `map_growth_open_alerts`
- `map_size_table_rows`
- `token_rate_divergence`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/board.py`, `orchestrator/config.py`, `orchestrator/explore_metric.py`, `orchestrator/fsm.py`, `orchestrator/providers/base.py`, `orchestrator/providers/claude.py`, `orchestrator/retro.py`, `orchestrator/rounds.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_report_model.py`, `tests/test_report.py`, `tests/test_report_project_label.py`, `tests/test_rounds.py`, `tests/test_token_rate_divergence.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/mutation_run.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py`, `tests/test_component_report_run.py`, `tests/test_guard_plank_bans.py`, `tests/test_outcome_gate_module.py`, `tests/test_report_outcome_module.py`

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

**Импортируется:** `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/explore_metric.py`, `orchestrator/report.py`, `orchestrator/snapshot.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_summarize.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py`, `tests/test_canary.py`, `tests/test_parent_task_division.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`

## orchestrator/retro_corpus.py

**Назначение:** Локальный кэш ретро-корпуса из локальных refs/artifacts/* (наполнить — `docs --fetch-all`)

**Публичные функции:**
- `rebuild_cache`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/targets.py`, `orchestrator/yamlmini.py`

**Импортируется:** `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`, `tests/test_retro_corpus.py`

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

**Импортируется:** `orchestrator/advance_gates/capacity.py`, `orchestrator/fsm.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `tests/merge_outcome_sandbox.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_acceptance_file_time.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_outcome_components_module.py`, `tests/test_project_profile_gates.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_task_component_places.py`, `tests/test_test_integrity_gate.py`

## orchestrator/role_prompt.py

**Назначение:** Миссия роли + бриф/ревью-пакет шага: сборка содержимого промпта, общего

**Публичные функции:**
- `docs_dir_note`
- `knowledge_hint_note`
- `mission_brief_package`
- `step_note_note`
- `suite_run_note`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/knowledge_cards.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/runner.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py`, `tests/test_docs_dir_layout.py`, `tests/test_knowledge_command.py`, `tests/test_long_lived_manifest.py`, `tests/test_role_prompt_test_author_mission.py`

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
- `refuse_unsupported_project`
- `role_cmd`
- `role_cwd`
- `role_cwd_path`
- `role_env`
- `role_token`
- `run_agent_once`
- `spawn_agent`
- `step_role`
- `wave_breaker_alerts_open`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_source.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/lease.py`, `orchestrator/liveness.py`, `orchestrator/merge_after.py`, `orchestrator/models.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/project_profile.py`, `orchestrator/pull.py`, `orchestrator/repo_context.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/roles.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/gitcmd.py`, `orchestrator/knowledge_cards.py`, `orchestrator/lease.py`, `orchestrator/notes.py`, `orchestrator/pause.py`, `orchestrator/pool_seal.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/review.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_worktree.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_auto_stop.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_envelope_run.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_alert.py`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_artifact_materialization.py`, `tests/test_auto_cycle.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_detach_result.py`, `tests/test_canary_run_task.py`, `tests/test_codex_login_shell_path.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pytest_summary_pump.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_runner_role_environment.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_sandbox_retry_pause.py`, `tests/test_sandbox_time_with_sleep.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_project.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/schema.py

**Назначение:** Схема БД и миграции: DDL, `migrate(conn)`, `add_column`/`table_columns`.

**Публичные функции:**
- `add_column`
- `create_schema`
- `migrate`
- `table_columns`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/store.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_closed_as.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_migration.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_migration.py`, `tests/test_epics_board_units.py`, `tests/test_merge_after_module.py`, `tests/test_observation_migration_regression.py`, `tests/test_pair_suspension_units.py`, `tests/test_parent_task_division.py`, `tests/test_steps_task_id_index.py`

## orchestrator/session.py

**Назначение:** Идентификатор сессии оркестратора — единая функция для всех команд

**Публичные функции:**
- `resolve_session_id`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/cycle_hint.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/watch.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_detached_cycle.py`, `tests/test_launch_observation_refusals.py`, `tests/test_observation_edges.py`, `tests/test_session.py`

## orchestrator/snapshot.py

**Назначение:** Коммит закрытия задачи (`done`/`killed`) — последний коммит RETRO в

**Публичные функции:**
- `closing_sha`
- `cmd_artifact_history_snapshots`
- `commit_closing`
- `history_snapshots`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/cleanup.py`, `orchestrator/doctor/__init__.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_artifact_ref_sync.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_multitarget_invariants.py`, `tests/test_snapshot_history.py`

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

**Импортируется:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/doctor/__init__.py`, `orchestrator/epics.py`, `orchestrator/pause.py`, `orchestrator/providers/claude.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/watch.py`, `scripts/guard.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_agent_log.py`, `tests/test_doctor.py`, `tests/test_model_tariffs.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_providers_codex.py`, `tests/test_pytest_summary_pump.py`, `tests/test_runner_role_model.py`, `tests/test_step_cost.py`, `tests/test_task_model_set_units.py`, `tests/test_token_rate_divergence.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/doctor/__init__.py`, `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/version.py`, `scripts/guard.py`, `scripts/stack_ci.py`, `tests/report_outcome_sandbox.py`, `tests/sandbox.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_agent_failure.py`, `tests/test_agent_prompt.py`, `tests/test_artel_bootstrap.py`, `tests/test_git_hooks.py`, `tests/test_invariants.py`, `tests/test_project_profile.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_report_outcome_module.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_role_prompt_test_author_mission.py`, `tests/test_runner_model_preflight.py`, `tests/test_stack.py`, `tests/test_stack_ci.py`, `tests/test_stack_optional_tools.py`, `tests/test_suite_run.py`, `tests/test_task_model_set_units.py`

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
- `any_task_in_epic`
- `archive_alert`
- `begin_immediate`
- `canary_baseline`
- `charge`
- `charge_estimate`
- `claim_observation`
- `copy_external_refs`
- `counter_targets`
- `db`
- `db_readonly`
- `db_tracked_count`
- `db_usable`
- `delete_epic_supervisor`
- `delete_external_ref`
- `delete_merge_queue_row`
- `dequeue_merge_wait`
- `disable_task_observation`
- `enable_wal`
- `enqueue_merge_wait`
- `epic_decisions`
- `epic_drafts`
- `epic_supervisor_row`
- `epic_supervisor_steps_since`
- `epic_tasks`
- `external_refs`
- `get_alert`
- `get_draft`
- `get_epic`
- `get_task`
- `green_canary_runs`
- `insert_alert`
- `insert_canary_run`
- `insert_decision`
- `insert_draft`
- `insert_epic`
- `insert_epic_child`
- `insert_epic_row`
- `insert_epic_supervisor`
- `insert_external_ref`
- `insert_lease`
- `insert_pair_suspension`
- `insert_pair_verdict`
- `insert_task`
- `journal`
- `journal_action_exists`
- `journal_maxima`
- `last_epic_children`
- `last_model_tariff`
- `last_pair_resume_mark`
- `last_step_times`
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
- `project_branch_tasks`
- `project_epics`
- `project_external_refs`
- `project_merge_lock_row`
- `project_merge_queue_rows`
- `project_tasks`
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
- `session_active_observations`
- `session_observations`
- `set_canary_baseline`
- `set_merge_lock`
- `set_state`
- `set_task_epic`
- `steps_of_action`
- `stop_observation`
- `task_branch`
- `task_epic_id`
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
- `update_draft`
- `update_epic`
- `update_lease`
- `update_lease_pgid`
- `update_task`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifact_branch.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/models.py`, `orchestrator/schema.py`, `orchestrator/session.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/_base.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/alerts.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/auto.py`, `orchestrator/board.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/cycle_hint.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/dry_run.py`, `orchestrator/epics.py`, `orchestrator/explore_metric.py`, `orchestrator/failure_classification.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/models.py`, `orchestrator/mutation_run.py`, `orchestrator/notes.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/pin.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/pull_main.py`, `orchestrator/reference_cache.py`, `orchestrator/release.py`, `orchestrator/report.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/rounds.py`, `orchestrator/runner.py`, `orchestrator/schema.py`, `orchestrator/snapshot.py`, `orchestrator/spend.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `orchestrator/watch.py`, `orchestrator/workspace.py`, `orchestrator/zone_lock.py`, `scripts/test_rule_stats.py`, `tests/components_outcome_sandbox.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/prior_outcome_sandbox.py`, `tests/report_outcome_sandbox.py`, `tests/sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_brief_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py`, `tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py`, `tests/test_01m5n9wk9sgb7kdyjp736dp6cv_fixture_gate.py`, `tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py`, `tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py`, `tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_doctor_layer.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_watch_layer.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_stamp.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_doctor.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_worktree.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_closed_as.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_division_epic.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_epic_commands.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_migration.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_auto_stop.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_envelope_run.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_alert.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_view.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_watch.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_start_after_write.py`, `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_drafts.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_epic_ref.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_migration.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_board_command.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_external_refs.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_report_model.py`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py`, `tests/test_acceptance.py`, `tests/test_acceptance_file_time.py`, `tests/test_acceptance_suite_profile.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_amend_long_lived.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_branch_server_retry.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_canary_budget_ceiling.py`, `tests/test_canary_child_row_write.py`, `tests/test_canary_drive.py`, `tests/test_canary_escalation_roles_storage.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_run_task.py`, `tests/test_canary_runs.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_ci_stuck_check_run.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_coldstart.py`, `tests/test_component_checks.py`, `tests/test_conventions.py`, `tests/test_cycle_hint.py`, `tests/test_detached_cycle.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_division_order_units.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doc_commit_module.py`, `tests/test_docs_dir_layout.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_canary_pool.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_draft_mr_commits.py`, `tests/test_dry_run.py`, `tests/test_epic_draft_promote_unsupported_project.py`, `tests/test_epic_drafts_units.py`, `tests/test_epic_supervisor_units.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_fsm_autogate_long_lived.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_push_point.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_knowledge_command.py`, `tests/test_launch_observation_refusals.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_main_copy_watch.py`, `tests/test_merge_after_module.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock_module.py`, `tests/test_merge_outcome_module.py`, `tests/test_merge_queue.py`, `tests/test_merge_reference_step.py`, `tests/test_model_sets.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_network_address_gate.py`, `tests/test_notes_module.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_edges.py`, `tests/test_observation_migration_regression.py`, `tests/test_observation_notification.py`, `tests/test_outcome_gate_module.py`, `tests/test_pair_suspension_units.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_pin_update_stale_cycles.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_plank_run_edges.py`, `tests/test_preflight.py`, `tests/test_program_spend_reseed.py`, `tests/test_project_profile_gates.py`, `tests/test_project_protected_paths.py`, `tests/test_protected_paths_gate.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_pull_main_unavailable.py`, `tests/test_reference_command.py`, `tests/test_release.py`, `tests/test_report.py`, `tests/test_report_outcome_module.py`, `tests/test_report_project_label.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_freshness.py`, `tests/test_review_long_lived_exclude.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_review_registry_gate.py`, `tests/test_role_commit_by_pult.py`, `tests/test_rounds.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_snapshot_history.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stale_cycles_start_precision.py`, `tests/test_stall_alerts.py`, `tests/test_start_after_units.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_project.py`, `tests/test_step_refixation.py`, `tests/test_steps_task_id_index.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_db_tracking.py`, `tests/test_store_journal.py`, `tests/test_store_schema_migration_parity.py`, `tests/test_suite_duration.py`, `tests/test_suite_lock.py`, `tests/test_suite_run.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_timeout_checkpoint.py`, `tests/test_token_rate_divergence.py`, `tests/test_verifying_ceiling.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_workspace_wrapper_excludes.py`, `tests/test_worktree_db_files.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

## orchestrator/suite_durations.py

**Назначение:** Время каждого теста полного прогона по отметкам времени строк хода (SPEC

**Публичные функции:**
- `durations`
- `path_for`
- `slowest_block`
- `slowest_path`
- `write_slowest`

**Импортирует:** `orchestrator/suite_run.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/suite_run.py`, `tests/test_01m5n8asj63zkf3m9etc7a3p5v_durations_reader_failure.py`, `tests/test_suite_durations.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/knowledge_cards.py`, `orchestrator/mutation_run.py`, `orchestrator/providers/codex.py`, `orchestrator/prune.py`, `orchestrator/suite_run.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py`, `tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_prune_abolished_rules.py`, `tests/test_suite_lock.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run_deferred_journal.py`

## orchestrator/suite_run.py

**Назначение:** Команда `suite-run <id> [--wait <минуты> | --failed]`: полный прогон

**Публичные функции:**
- `background`
- `cmd_suite_run`
- `parse`
- `render`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/appendix_tree.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/session.py`, `orchestrator/store.py`, `orchestrator/suite_durations.py`, `orchestrator/suite_lock.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/mutation_run.py`, `orchestrator/suite_durations.py`, `tests/report_outcome_sandbox.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_summary_deselected.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_component_report_run.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_full_suite_reuse.py`, `tests/test_report_outcome_module.py`, `tests/test_suite_run.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`

## orchestrator/targets.py

**Назначение:** Декларация целевых проектов из targets.yaml: запись target'а читается кодом.

**Публичные функции:**
- `cache_dir`
- `check`
- `core_reference`
- `layers`
- `load`
- `local_path`
- `long_lived_pair`
- `merge_local`
- `push_option_error`
- `push_whitelisted`
- `secret_env_names`
- `target`
- `unsupported_reason`
- `wrapper_paths`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/board.py`, `orchestrator/brief.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/cleanup.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/epics.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/knowledge_cards.py`, `orchestrator/mutation_run.py`, `orchestrator/notes.py`, `orchestrator/project_profile.py`, `orchestrator/projects.py`, `orchestrator/pull.py`, `orchestrator/reference_cache.py`, `orchestrator/repo_context.py`, `orchestrator/report.py`, `orchestrator/retro_corpus.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/workspace.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_targets_knowledge.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_min_uses_field.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5fryvp4nf81vt00fyphpwjh_rerun_ban_check.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_targets_migrate.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_entry.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_external_refs.py`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py`, `tests/test_acceptance_plank_layout_refusal.py`, `tests/test_acceptance_suite_profile.py`, `tests/test_board_refs_units.py`, `tests/test_component_checks.py`, `tests/test_epic_draft_promote_unsupported_project.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_gitcmd_push_point.py`, `tests/test_github_adapter.py`, `tests/test_long_lived_template_shape.py`, `tests/test_multitarget.py`, `tests/test_project_components.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_reference_command.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_targets_rerun_ban_wrapper.py`, `tests/test_workspace_clone_docs_refs.py`

## orchestrator/test_lint.py

**Назначение:** Линт детерминизма тестов: ожидание по часам и чтение живых файлов репозитория.

**Публичные функции:**
- `findings`
- `top_level_functions`

**Импортирует:** —

**Импортируется:** `scripts/guard.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_targets_migrate.py`, `tests/test_invariants.py`

## orchestrator/tz_check.py

**Назначение:** Механическая проверка содержания ТЗ в `new` по дереву проекта (SPEC

**Публичные функции:**
- `check`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/workspace.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/catalog.py`, `tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py`, `tests/test_tz_check.py`

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

**Импортирует:** `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/providers/claude.py`, `orchestrator/runner.py`, `orchestrator/session.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/board.py`, `orchestrator/doctor/observations.py`, `orchestrator/knowledge_cards.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_watch.py`, `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_notification.py`, `tests/test_pytest_summary_pump.py`, `tests/test_watch.py`

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
- `wrapper_covers`
- `wrapper_file_on_disk`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/answer.py`, `orchestrator/appendix_tree.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/artifact_cleanup.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/docs_fetch.py`, `orchestrator/doctor/__init__.py`, `orchestrator/dry_run.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/knowledge_cards.py`, `orchestrator/mutation_run.py`, `orchestrator/notes.py`, `orchestrator/plank_run.py`, `orchestrator/preflight.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/pull.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/suite_run.py`, `orchestrator/tz_check.py`, `orchestrator/watch.py`, `tests/components_outcome_sandbox.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/sandbox.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py`, `tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_doctor.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_worktree.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_auto_stop.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_envelope_run.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_external_refs.py`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_answer_gate.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_branch_freshness_gate.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_division_parent_cleanup.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_draft_mr_remote_base_args.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_autogate.py`, `tests/test_kill_cleanup.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_transitions.py`, `tests/test_merge_after_module.py`, `tests/test_multitarget_invariants.py`, `tests/test_network_address_gate.py`, `tests/test_outcome_gate_module.py`, `tests/test_plank_helper.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_reference_command.py`, `tests/test_review_package.py`, `tests/test_role_commit_by_pult.py`, `tests/test_step_autocommit.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`, `tests/test_workspace_clone_docs_refs.py`, `tests/test_workspace_wrapper_excludes.py`, `tests/test_worktree_db_files.py`

## orchestrator/yamlmini.py

**Назначение:** Подмножество YAML, которого достаточно системе: frontmatter и roles.yaml.

**Публичные функции:**
- `frontmatter`
- `mapping`
- `scalar`

**Импортирует:** —

**Импортируется:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/artifacts.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/conventions.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/gates.py`, `orchestrator/knowledge_cards.py`, `orchestrator/models.py`, `orchestrator/preflight.py`, `orchestrator/projects.py`, `orchestrator/pull.py`, `orchestrator/retro_corpus.py`, `orchestrator/roles.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_targets_migrate.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_stamp.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_entry.py`, `tests/test_canary_sets.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_model_sets.py`, `tests/test_roles_map_fixture.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_yaml_parsing.py`

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

**Импортирует:** `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/board.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/doctor/__init__.py`, `orchestrator/project_profile.py`, `orchestrator/runner.py`, `scripts/guard.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py`, `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_board_command.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_report_model.py`, `tests/test_auto_cycle.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_stack_zones_pull_section.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`

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
- `division_frame`
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
- `lint_errors_from_files`
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
- `pytest_style_errors_from_files`
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

**Импортирует:** `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/spend.py`, `orchestrator/stack.py`, `orchestrator/test_lint.py`, `orchestrator/yamlmini.py`, `orchestrator/zone_lock.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/advance_gates/review.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/amend.py`, `orchestrator/appendix_tree.py`, `orchestrator/artel.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/dry_run.py`, `orchestrator/epics.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/merge_after.py`, `orchestrator/preflight.py`, `orchestrator/project_profile.py`, `orchestrator/pull.py`, `orchestrator/retro.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py`, `orchestrator/tz_check.py`, `orchestrator/version.py`, `scripts/plan_appendix_ci.py`, `tests/prior_outcome_sandbox.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_guard.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_async_test_method.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_test_lint.py`, `tests/test_01m5n9wk9sgb7kdyjp736dp6cv_fixture_records.py`, `tests/test_01m5n9wk9sgb7kdyjp736dp6cv_plank_forms.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_texts.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_guard_frame.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_amend_long_lived.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_appendix_tree.py`, `tests/test_artifact_materialization.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_division_order_units.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_plank_rule.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_guard_artifact_branch_mode.py`, `tests/test_guard_artifact_disk_read.py`, `tests/test_guard_assertion_changes.py`, `tests/test_guard_division_section.py`, `tests/test_guard_extraneous_acceptance_files.py`, `tests/test_guard_helper_scope.py`, `tests/test_guard_helper_scope_modes.py`, `tests/test_guard_mutation_claim.py`, `tests/test_guard_parametrize_variants.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_plank_bans.py`, `tests/test_guard_plank_rule_parsing.py`, `tests/test_guard_pytest_fixtures.py`, `tests/test_guard_schema.py`, `tests/test_guard_split_signals.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_guard_test_ast.py`, `tests/test_guard_test_groups.py`, `tests/test_guard_zones.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_template_shape.py`, `tests/test_merge_after_module.py`, `tests/test_network_address_gate.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_project_profile.py`, `tests/test_project_protected_paths.py`, `tests/test_protected_test_settings.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_review_registry_gate.py`, `tests/test_role_commit_by_pult.py`, `tests/test_step_note_contract.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_version.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_line_parse.py`

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

**Импортируется:** `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`, `tests/test_epic_drafts_units.py`, `tests/test_plan_appendix_ci.py`

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

## tests/components_outcome_sandbox.py

**Назначение:** Песочница гейта исходов по компонентам: учебный проект из двух компонентов и задача на один из них (ComponentsOutcomeSandbox), планка чужого компонента (ForeignPlankSandbox).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_outcome_components_module.py`

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

**Импортируется:** `tests/report_outcome_sandbox.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_fd_wait.py`, `tests/test_report_outcome_module.py`

## tests/fixtures.py

**Назначение:** Фикстуры-песочницы в стиле pytest над классами `tests/sandbox.py` (ADR-0027, часть А1).

**Публичные функции:**
- `initialized_tmp_root`
- `light_transition`
- `origin_real_git`
- `real_git`
- `tmp_dir`
- `tmp_root`

**Импортирует:** `tests/sandbox.py`

**Импортируется:** `tests/test_01m5n9v4s984grrxsmbk5jx7v1_fixtures.py`, `tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py`, `tests/test_merge_after_module.py`, `tests/test_merge_outcome_module.py`, `tests/test_outcome_components_module.py`, `tests/test_outcome_gate_module.py`, `tests/test_outcome_prior_module.py`, `tests/test_report_outcome_module.py`

## tests/mandate_matrix.py

**Назначение:** Матрица неослабления во входах тестов, подающих `answer` мандат или

**Публичные функции:**
- `matrix`
- `matrix_file`
- `with_matrix`

**Импортирует:** —

**Импортируется:** `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_answer.py`, `tests/test_docs_ref_deleted_refusal.py`, `tests/test_mandate_matrix_form.py`, `tests/test_mandate_profile_scope.py`, `tests/test_mandate_test_id.py`

## tests/merge_outcome_sandbox.py

**Назначение:** Песочница гейта исходов на мерже: сквозной approve гейта мержа (MergeOutcomeSandbox) и двусторонний прогон (TwoSidedSandbox).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/outcome_gate_sandbox.py`, `tests/sandbox.py`

**Импортируется:** `tests/components_outcome_sandbox.py`, `tests/prior_outcome_sandbox.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_merge_outcome_module.py`

## tests/outcome_gate_sandbox.py

**Назначение:** Песочница гейта неослабления по исходам `OutcomeGateSandbox` с константами и помощниками стенда.

**Публичные функции:**
- `arg_value`
- `flow`
- `js_source`
- `py_source`
- `py_tests`
- `spec_text`
- `ulid`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/components_outcome_sandbox.py`, `tests/merge_outcome_sandbox.py`, `tests/prior_outcome_sandbox.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_merge_outcome_module.py`, `tests/test_outcome_components_module.py`, `tests/test_outcome_gate_module.py`, `tests/test_outcome_prior_module.py`

## tests/prior_outcome_sandbox.py

**Назначение:** Песочницы гейта исходов G3б-2: прежние версии, заменяемые тесты, строгий режим.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/answer.py`, `orchestrator/liveness.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_outcome_prior_module.py`

## tests/report_outcome_sandbox.py

**Назначение:** Песочница отчётов исходов компонента: сценарии подменённого раннера, установки и учебные записи проектов для тестов `orchestrator/reporters/outcome.py`.

**Публичные функции:**
- `block`
- `entry`
- `entry_values`
- `fld`
- `flipped`
- `junit`
- `quoted`
- `report_arg`
- `under`
- `vitest_report`
- `vitest_test`
- `writable`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `tests/fd_wait.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`, `tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py`, `tests/test_report_outcome_module.py`

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

**Импортируется:** `tests/components_outcome_sandbox.py`, `tests/fixtures.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/prior_outcome_sandbox.py`, `tests/report_outcome_sandbox.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`, `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`, `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`, `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py`, `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`, `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`, `tests/test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`, `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`, `tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py`, `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`, `tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`, `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`, `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`, `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`, `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py`, `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`, `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`, `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`, `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py`, `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`, `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`, `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`, `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`, `tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`, `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`, `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`, `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py`, `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`, `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`, `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`, `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_base_reuse.py`, `tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py`, `tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py`, `tests/test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py`, `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`, `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py`, `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_codebase_map_root.py`, `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_main_copy_watch.py`, `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`, `tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py`, `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`, `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`, `tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_brief_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`, `tests/test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter.py`, `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`, `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`, `tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`, `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_questions_matrix.py`, `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_01m4pmpmz7ppcn3jwx75rtjzqn_merge_base_choice.py`, `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py`, `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`, `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py`, `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_autocommit.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_brief.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`, `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_card_reading.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_freshness.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, `tests/test_01m4s24963r9h18an2xdp6r15b_cli.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m4v47bn2zq198jkmw7dwn3h6_note_layout.py`, `tests/test_01m4vkzr1ve6ks2hecj05abcyr_admit_pairs.py`, `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`, `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py`, `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`, `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py`, `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_required_artifact.py`, `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`, `tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py`, `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`, `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`, `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_missing_command.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py`, `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py`, `tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py`, `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py`, `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py`, `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py`, `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py`, `tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py`, `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`, `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`, `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`, `tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py`, `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`, `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`, `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`, `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_author_mission.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.py`, `tests/test_01m5enwtdd8np9smpfx3jn08j9_watch_report.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py`, `tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_wait_minutes.py`, `tests/test_01m5fghnb29qa254fm07qr55ab_zone_wait_exit.py`, `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`, `tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_01m5hj3yfbvk8tsr7vq7jpyj7c_amend_plank_only.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py`, `tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py`, `tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py`, `tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py`, `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`, `tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py`, `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py`, `tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py`, `tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py`, `tests/test_01m5n8asj63zkf3m9etc7a3p5v_durations_reader_failure.py`, `tests/test_01m5n9v4s984grrxsmbk5jx7v1_fixtures.py`, `tests/test_01m5n9wk9sgb7kdyjp736dp6cv_fixture_gate.py`, `tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py`, `tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py`, `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, `tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py`, `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py`, `tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py`, `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_doctor_layer.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py`, `tests/test_01m5scgsqn0at0b07h7m9803ra_targets_migrate.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py`, `tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_stamp.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_doctor.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_entry.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py`, `tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_worktree.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_closed_as.py`, `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_division_epic.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_epic_commands.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_alert.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_watch.py`, `tests/test_01m5tbcy7wtn121s136xp2c6sr_start_after_write.py`, `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_epic_ref.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_board_command.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_external_refs.py`, `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_report_model.py`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`, `tests/test_acceptance.py`, `tests/test_acceptance_collect.py`, `tests/test_acceptance_pycache.py`, `tests/test_acceptance_seed_repeat.py`, `tests/test_acceptance_suite_profile.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_alert_ack_bulk_parsing.py`, `tests/test_alerts_wave_breaker.py`, `tests/test_amend.py`, `tests/test_amend_remove.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_appendix_tree.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_approve_no_answer_units.py`, `tests/test_artel_guard_command_forms.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_artifact_branch_new_parent.py`, `tests/test_artifact_branch_push.py`, `tests/test_artifact_branch_read_node.py`, `tests/test_artifact_branch_server_retry.py`, `tests/test_artifact_escalation_marker.py`, `tests/test_artifact_materialization.py`, `tests/test_artifact_ref_sync.py`, `tests/test_auto_cycle.py`, `tests/test_auto_escalated_return_rework_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_budget_live_lease_and_escalation.py`, `tests/test_canary.py`, `tests/test_canary_child_row_write.py`, `tests/test_canary_detach_result.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_parallel.py`, `tests/test_canary_parallel_protection.py`, `tests/test_canary_run_task.py`, `tests/test_canary_runs.py`, `tests/test_canary_sets.py`, `tests/test_canary_synthetic_answer.py`, `tests/test_capacity_gate.py`, `tests/test_capacity_gate_map.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_fixture.py`, `tests/test_catalog_new_race.py`, `tests/test_catalog_spawn_subtask.py`, `tests/test_catalog_status_log.py`, `tests/test_catalog_tz_path_check.py`, `tests/test_catalog_wave_breaker_status.py`, `tests/test_catalog_zone_overlap.py`, `tests/test_checkpoint_external_step_artifacts.py`, `tests/test_ci_callers_project_repo.py`, `tests/test_ci_project_gh_address.py`, `tests/test_ci_rerun_command.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_codex_login_shell_path.py`, `tests/test_coldstart.py`, `tests/test_component_checks.py`, `tests/test_conventions.py`, `tests/test_cycle_hint.py`, `tests/test_detached_cycle.py`, `tests/test_diff_not_collected_alerts.py`, `tests/test_division_order_units.py`, `tests/test_division_parent_cleanup.py`, `tests/test_doc_commit_module.py`, `tests/test_docs_dir_layout.py`, `tests/test_doctor.py`, `tests/test_doctor_agent_roles.py`, `tests/test_doctor_artifact_branch_sync.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_doctor_fix_ignored_artifacts.py`, `tests/test_doctor_wave_breaker.py`, `tests/test_done_branch_cleanup.py`, `tests/test_draft_mr_commits.py`, `tests/test_dry_run.py`, `tests/test_epic_draft_promote_unsupported_project.py`, `tests/test_epic_supervisor_units.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_fsm_advance_gate_framework.py`, `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_advance_tests_writing_artifact_source.py`, `tests/test_fsm_advance_tests_writing_dry_collect.py`, `tests/test_fsm_advance_tests_writing_test_groups.py`, `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_env_refusal.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_draft_mr_reentry.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_merge_gate_remote_branch_cleanup.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`, `tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_review_rework_sha_gate.py`, `tests/test_fsm_spec_gate_path_check.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_full_suite_reuse.py`, `tests/test_git_fixation.py`, `tests/test_git_hooks.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_check_ignore.py`, `tests/test_gitcmd_fetch_ref_sha.py`, `tests/test_github_adapter.py`, `tests/test_guard_path_mentions.py`, `tests/test_guard_schema.py`, `tests/test_guard_task_root_subdirectory.py`, `tests/test_id_format_guard.py`, `tests/test_invariants.py`, `tests/test_journal_warning_once.py`, `tests/test_kill_cleanup.py`, `tests/test_kill_live_cycle_refusal.py`, `tests/test_knowledge_command.py`, `tests/test_launch_observation_refusals.py`, `tests/test_lease.py`, `tests/test_lease_pgid_store.py`, `tests/test_lease_run_task_command.py`, `tests/test_long_lived_manifest.py`, `tests/test_long_lived_step_end_to_end.py`, `tests/test_long_lived_transitions.py`, `tests/test_main_ci_line.py`, `tests/test_main_copy_watch.py`, `tests/test_merge_after_module.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock_module.py`, `tests/test_merge_queue.py`, `tests/test_merge_reference_step.py`, `tests/test_model_tariffs.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_mutation_claim_gate.py`, `tests/test_network_address_gate.py`, `tests/test_notes_module.py`, `tests/test_observation_acceptance_return.py`, `tests/test_observation_edges.py`, `tests/test_outcome_gate_module.py`, `tests/test_pair_suspension_units.py`, `tests/test_parallel_limit.py`, `tests/test_parent_task_division.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_pin.py`, `tests/test_pin_prune_orphan_guards.py`, `tests/test_pin_update_stale_cycles.py`, `tests/test_plan_appendix.py`, `tests/test_plank_helper.py`, `tests/test_preflight.py`, `tests/test_profile_layers_declared.py`, `tests/test_program_spend_reseed.py`, `tests/test_project_profile_gates.py`, `tests/test_protected_paths_gate.py`, `tests/test_provider_scoped_step_env.py`, `tests/test_providers.py`, `tests/test_providers_codex.py`, `tests/test_prune.py`, `tests/test_prune_abolished_rules.py`, `tests/test_pull.py`, `tests/test_pull_additive_conflict.py`, `tests/test_pull_conflict_marker_states.py`, `tests/test_pull_long_lived_plank.py`, `tests/test_pytest_own_result_ids.py`, `tests/test_pytest_summary_pump.py`, `tests/test_release.py`, `tests/test_repo_context.py`, `tests/test_report.py`, `tests/test_report_outcome_module.py`, `tests/test_report_project_label.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_review_package_map.py`, `tests/test_role_commit_by_pult.py`, `tests/test_roles_map_fixture.py`, `tests/test_rounds.py`, `tests/test_runner_model_preflight.py`, `tests/test_runner_pre_step_pull.py`, `tests/test_runner_role_model.py`, `tests/test_runner_wave_breaker.py`, `tests/test_sandbox.py`, `tests/test_sandbox_determinism_helpers.py`, `tests/test_sandbox_retry_pause.py`, `tests/test_sandbox_time_with_sleep.py`, `tests/test_session.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_snapshot_history.py`, `tests/test_spec_audit_gate.py`, `tests/test_spec_budget.py`, `tests/test_spent_estimate_store.py`, `tests/test_split_assessment_merge_gate.py`, `tests/test_stack.py`, `tests/test_stack_optional_tools.py`, `tests/test_stack_roles_tier_spread.py`, `tests/test_stale_cycles_start_precision.py`, `tests/test_stall_alerts.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_steps_task_id_index.py`, `tests/test_store_db_connection_close.py`, `tests/test_store_db_tracking.py`, `tests/test_store_journal.py`, `tests/test_suite_duration.py`, `tests/test_suite_lock.py`, `tests/test_suite_near_limit.py`, `tests/test_suite_run.py`, `tests/test_suite_run_deferred_journal.py`, `tests/test_task_component_places.py`, `tests/test_task_id_prefix_regression.py`, `tests/test_task_model_set_units.py`, `tests/test_test_author_long_lived_artifact.py`, `tests/test_test_integrity_gate.py`, `tests/test_test_integrity_helper_heirs.py`, `tests/test_timeout_checkpoint.py`, `tests/test_token_rate_divergence.py`, `tests/test_vitest_summary_pump.py`, `tests/test_watch.py`, `tests/test_workspace.py`, `tests/test_workspace_clone_docs_refs.py`, `tests/test_workspace_wrapper_excludes.py`, `tests/test_worktree_db_files.py`, `tests/test_yaml_parsing.py`, `tests/test_zone_lock.py`, `tests/test_zone_lock_forecast.py`, `tests/test_zones_approve.py`, `tests/test_zones_gate.py`

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

## tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py

**Назначение:** Удержание `approve` на гейте мержа по зависимостям `merge_after` (AC-6..AC-8).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Публичные функции:**
- `artel_only_entries`

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

**Назначение:** Бриф роли задачи внешнего проекта: конвенции проекта из файла пульта

**Публичные функции:**
- `call_text`
- `git_repo_of`
- `word`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `scripts/codebase_map.py`, `tests/sandbox.py`

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

**Назначение:** Ревью-пакет задачи внешнего проекта: конвенции проекта из файла пульта

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

**Назначение:** Переходной модуль: имена для `tests/test_invariants.py` — из `tests/report_outcome_sandbox.py`.

**Публичные функции:** (нет)

**Импортирует:** `tests/report_outcome_sandbox.py`

**Импортируется:** `tests/test_invariants.py`

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

**Импортируется:** `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`, `tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py`

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

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/answer.py`, `orchestrator/liveness.py`, `orchestrator/project_profile.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`, `tests/prior_outcome_sandbox.py`, `tests/sandbox.py`

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

## tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py

**Назначение:** Время каждого теста полного прогона `suite-run` по отметкам времени строк

**Публичные функции:**
- `durations_path`
- `read_durations`
- `slowest_path`
- `worker_name`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5mvg2b1ygvptzwkb18evghz_row_write_deadline.py

**Назначение:** Граница срока записи строки «оборвана сигналом» дочерним параллельного

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/liveness.py`

**Импортируется:** —

## tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py

**Назначение:** `amend-tests` проверяет правку линтом детерминизма, не отказывая за методы, залоченные до правки.

**Публичные функции:**
- `spec_text`
- `ulid`
- `word`

**Импортирует:** `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py

**Назначение:** Выход `tests_writing` проверяет планку и долгоживущие файлы линтом детерминизма до лока — только у артели.

**Публичные функции:**
- `fixture_source`
- `line_of`
- `spec_text`
- `ulid`
- `word`

**Импортирует:** `orchestrator/advance_gates/tests_writing.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_test_lint.py

**Назначение:** Модуль пульта `orchestrator/test_lint.py` и параметр `lint_base` узла `guard.long_lived_errors_from_files`.

**Публичные функции:**
- `class_source`
- `sleep_errors`
- `word`

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py

**Назначение:** Сброс удержанных записей (`note --flush`, `doc-commit --flush`, попутный

**Публичные функции:**
- `run_command`
- `write_hook`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5n8asj63zkf3m9etc7a3p5v_durations_reader_failure.py

**Назначение:** Сбой потока чтения времени тестов не меняет полный прогон в файл лога:

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/suite_durations.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py

**Назначение:** Самодостаточная часть выкладки планки в `orchestrator.plank_layout` и

**Публичные функции:**
- `import_target`
- `module_package`
- `private_accesses`

**Импортирует:** `orchestrator/acceptance.py`

**Импортируется:** —

## tests/test_01m5n9v4s984grrxsmbk5jx7v1_fixtures.py

**Назначение:** Фикстуры-песочницы `tests.fixtures` в стиле pytest (ADR-0027, часть А1).

**Публичные функции:**
- `config_snapshot`
- `finish`
- `is_temporary`
- `require_fixtures_module`
- `sandbox_class`
- `sandbox_root`
- `start`
- `test_ac1_fixture_yields_exact_sandbox_class`
- `test_ac2_tmp_dir_is_temporary_and_removed`
- `test_ac3_config_patched_then_restored_and_root_removed`
- `test_ac4_cleanup_runs_in_reverse_registration_order`
- `test_ac4_failed_cleanup_raises_runtime_error`
- `test_ac5_setup_failure_cleans_up_and_reraises`
- `test_ac6_import_does_not_touch_process_state`
- `test_ac7_fixtures_visible_to_plank_via_conftest`
- `test_ac8_sandbox_methods_work_through_fixture`
- `token`

**Импортирует:** `orchestrator/config.py`, `tests/fixtures.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5n9wk9sgb7kdyjp736dp6cv_fixture_gate.py

**Назначение:** Гейт неослабления тестов видит правку данных фикстуры pytest, которой

**Публичные функции:**
- `add_mandate`
- `commit_diff`
- `declare`
- `fixture_module`
- `function_test`
- `gate`
- `names_test`
- `seeded`
- `test_ac10_fixture_literal_edit_finding_and_its_removal`
- `test_ac13_swapping_fixture_literals_is_a_finding`
- `test_ac14_fixture_data_edits_in_test_file_are_findings`
- `test_ac14_shared_fixture_edit_reaches_test_outside_diff`
- `test_ac15_gate_handles_fixture_record_next_to_unmatched_assertion`
- `two_values`
- `uncovered_lines`
- `word`
- `write`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5n9wk9sgb7kdyjp736dp6cv_fixture_records.py

**Назначение:** Данные фикстур pytest в разборе утверждений guard: запись данных

**Публичные функции:**
- `fixture_file`
- `fixture_text`
- `multiset`
- `names_fixture`
- `records`
- `render`
- `seeded`
- `test_ac10_fixture_records_count_in_ratchet`
- `test_ac11_own_fixture_shadows_shared_one`
- `test_ac12_parametrize_argument_is_not_a_fixture`
- `test_ac13_swapping_two_fixture_literals_changes_records`
- `test_ac14_call_argument_and_sign_edits_change_records`
- `test_ac14_helper_called_by_fixture_is_traced_one_level`
- `test_ac15_fixture_record_passes_consumers_without_errors`
- `test_ac1_fixture_literal_edit_named_by_weakened_helpers_and_records`
- `test_ac2_every_request_way_gets_fixture_data_record`
- `two_values`
- `value_body`
- `word`

**Импортирует:** `orchestrator/advance_gates/test_integrity.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_01m5n9wk9sgb7kdyjp736dp6cv_plank_forms.py

**Назначение:** Отказы guard в файлах планки и долгоживущих файлах: скрытые пропуски,

**Публичные функции:**
- `addressed`
- `build_form`
- `clean_source`
- `errors`
- `header`
- `label_for`
- `line_of`
- `module_names`
- `seeded`
- `span`
- `styles`
- `test_ac3_each_form_refused_with_address`
- `test_ac4_clean_forms_give_no_refusal`
- `test_ac5_mixed_styles_refused_unless_locked_text_mixed`
- `test_ac6_foreign_project_gets_no_refusal`
- `test_ac7_locked_violation_excused_added_one_refused`
- `test_ac7_module_level_statement_excused_by_same_dump`
- `test_ac9_variants_do_not_change_test_count`
- `word`

**Импортирует:** `scripts/guard.py`

**Импортируется:** —

## tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py

**Назначение:** Общие фикстуры pytest: устойчивое подключение в корневом `conftest.py` и инвариант 42.

**Публичные функции:**
- `test_ac2_collect_without_tests_package_exits_zero`
- `test_ac3_tmp_root_visible_under_acceptance_tests_without_import`
- `test_ac4_invariant_green_on_unmutated_copy`
- `test_ac4_invariant_red_on_each_mutation`

**Импортирует:** `orchestrator/config.py`, `tests/sandbox.py`, `tests/test_invariants.py`

**Импортируется:** —

## tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py

**Назначение:** Команда пульта `mutation-run`: патчи мутаций против названных тестовых

**Публичные функции:**
- `commands_block`
- `file_diff`
- `junit`
- `move_diff`
- `new_file_diff`
- `numbered`
- `registry_keys`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py

**Назначение:** Прогон приёмочной планки после подтяжки main (`pull.evaluate`) — на дереве с приложениями PLAN, как на рубеже `in_dev -> verifying`.

**Публичные функции:**
- `word`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/projects.py`, `orchestrator/pull.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py

**Назначение:** Отчёт `mutation-run --wait` печатает строки таблицы «мутация → исход».

**Публичные функции:**
- `bench`
- `file_diff`
- `missing_lines`
- `numbered`
- `row_numbers`
- `test_ac1_finished_wait_prints_every_table_line_and_summary`
- `test_ac2_repeated_wait_after_end_prints_same_table_lines`
- `test_ac3_running_wait_prints_written_lines_and_running_mark`
- `test_ac4_limit_cut_wait_prints_cut_and_not_run_rows`
- `test_ac5_reset_refusal_wait_prints_header_and_written_rows`
- `test_ac6_exception_wait_prints_header_and_first_row`
- `test_ac7_dead_process_without_report_prints_table`
- `test_ac8_docs_dir_and_artifacts_ref_untouched`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py

**Назначение:** `mutation-run`: ожидание замка `--wait-lock`, копия таблицы `--copy-table`, число рабочих процессов `--workers`.

**Публичные функции:**
- `bench`
- `cpu_patch`
- `file_diff`
- `n_values`
- `numbered`
- `path_printed`
- `test_ac10_no_docs_dir_no_copy_and_one_no_copy_line`
- `test_ac11_without_copy_table_docs_dir_unchanged`
- `test_ac12_copy_table_leaves_ref_branch_and_worktree`
- `test_ac13_reports_print_copy_path`
- `test_ac16_report_of_run_without_copy_flag_creates_no_copy`
- `test_ac16_report_restores_copy_before_table`
- `test_ac17_report_only_with_run_flag_refused`
- `test_ac19_docs_dir_gains_only_copy_without_replace`
- `test_ac19_exception_before_table_leaves_docs_dir_as_is`
- `test_ac1_lock_released_in_time_waits_then_starts`
- `test_ac20_workers_value_is_last_n_of_every_run`
- `test_ac21_without_workers_no_other_n`
- `test_ac22_bad_workers_refused_without_run`
- `test_ac23_table_header_names_worker_count`
- `test_ac2_lock_busy_whole_term_refuses_after_term`
- `test_ac3_lock_checks_at_least_ten_seconds_apart`
- `test_ac4_lost_race_for_freed_lock_keeps_waiting`
- `test_ac5_waiting_takes_no_lock_and_sigint_leaves_nothing`
- `test_ac6_bad_wait_lock_refused_without_run`
- `test_ac7_without_wait_lock_busy_lock_refuses_at_once`
- `test_ac8_finished_run_copy_equals_table`
- `test_ac9_copy_equals_table_at_every_patch_run`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/suite_lock.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_texts.py

**Назначение:** Тексты команды `mutation-run`: справка, строка «Команды:», модульный докстринг, имя копии таблицы.

**Публичные функции:**
- `commands_entry`
- `flat`
- `test_ac14_copy_table_name_not_extraneous`
- `test_ac15_usage_and_commands_entry_name_flag`
- `test_ac18_module_docstring_describes_new_behaviour`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/mutation_run.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py

**Назначение:** Одна проверка remote при отправке документов и досылка в сверке с origin

**Публичные функции:**
- `break_origin`
- `commit`
- `commit_unsent`
- `git_spy`
- `journal_rows`
- `local_head`
- `make_env`
- `names_of`
- `no_remote`
- `origin_head`
- `reject_ref_pushes`
- `restore_origin`
- `synced`
- `test_push_without_remote_is_no_origin`
- `test_send_checks_remote_once_then_pushes`
- `test_send_with_other_remote_name_does_not_push`
- `test_sync_refusal_absent_and_push_rejected`
- `test_sync_refusal_absent_pushed_then_rechecked`
- `test_sync_refusal_diverged_after_push`
- `test_sync_refusal_local_ahead_pushes_then_rechecks`
- `test_sync_refusal_no_local_ref_without_push`
- `test_sync_refusal_synced_ref_not_pushed`
- `test_sync_refusal_unreachable_origin_without_push`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py

**Назначение:** Пакетное чтение документов задачи в `read_tree` и один `rev-parse` в начале `suite_tree_hash`.

**Публичные функции:**
- `as_dict`
- `blob`
- `build_commit`
- `case_entries`
- `cat_file_refusal`
- `combined_rev_parse_stub`
- `commit_all`
- `doc`
- `git_argv_spy`
- `git_version`
- `gitlink`
- `outside_files`
- `plain_files`
- `point_ref`
- `popen_spy`
- `prepare_suite_case`
- `random_text`
- `ref_sha`
- `reference_read_tree`
- `reference_suite_tree_hash`
- `seeded`
- `test_ac1_absent_ref_takes_the_old_path_by_ref_name`
- `test_ac1_empty_task_dir_starts_no_cat_file`
- `test_ac1_existing_ref_reads_in_at_most_three_git_calls`
- `test_ac2_no_repo_gives_an_empty_dict`
- `test_ac2_quotepath_false_non_utf8_path_raises_in_both`
- `test_ac2_result_equals_the_reference_on_a_still_ref`
- `test_ac3_ref_moves_between_head_and_ls_tree`
- `test_ac3_ref_moves_between_ls_tree_and_cat_file`
- `test_ac4_cat_file_failure_falls_back_to_the_reference_result`
- `test_ac4_every_ls_tree_refused_calls_the_old_ls_tree_files`
- `test_ac5_suite_tree_hash_runs_one_rev_parse`
- `test_ac6_suite_tree_hash_equals_the_reference`
- `test_ac7_git_2_30_fallback_runs_the_old_two_calls`
- `tree_a`
- `tree_b`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`, `orchestrator/retro.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py

**Назначение:** Одна отправка ссылки документов на команду пульта (SPEC

**Публичные функции:**
- `add_task`
- `area`
- `cmd_run_sandbox`
- `commit`
- `commit_fixed`
- `env`
- `git_spy`
- `is_ref_push`
- `journal`
- `local_head`
- `origin_head`
- `ref_pushes`
- `step`
- `test_area_sends_once_on_exit`
- `test_body_exception_still_sends_and_propagates`
- `test_commit_closing_sends_before_return`
- `test_dead_send_recovered_outside_area_and_by_sync`
- `test_doctor_fix_sends_unsent_closing_commit`
- `test_empty_set_exit_no_git_no_db`
- `test_ensure_draft_mr_docs_before_code`
- `test_ensure_head_in_origin_docs_before_code`
- `test_failing_send_during_body_exception_one_stderr_line`
- `test_failing_send_on_normal_exit_raises_after_other_pairs`
- `test_fetch_from_origin_and_fetch_all_not_diverged`
- `test_full_suite_not_needed_no_send`
- `test_long_merge_stage_sees_origin_synced`
- `test_nested_area_exit_sends_whole_set`
- `test_no_origin_area_silent`
- `test_outside_area_sends_each_commit_right_after_update_ref`
- `test_rejected_origin_one_failure_per_command_then_success`
- `test_send_pending_by_repo_and_by_task`
- `test_server_5xx_on_send_retried_attempts_two`
- `test_spawn_agent_sees_docs_sent`
- `test_sync_main_or_wait_docs_before_code`
- `test_sync_refusal_no_second_push_when_pending_send_failed`
- `test_sync_refusal_sends_once_in_area`
- `test_two_tasks_two_repos_first_write_order`
- `two_repos`
- `unsent`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/github_adapter.py`, `orchestrator/lease.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/snapshot.py`, `orchestrator/store.py`, `tests/sandbox.py`, `tests/test_review_package.py`

**Импортируется:** —

## tests/test_01m5s6m2mzv68qh9qhwy0xp0ya_vitest4.py

**Назначение:** Vitest 4 под пультом: флаг кэша `--no-cache`, хуки, `.only` и класс ошибки в отчётчике `pult-vitest`, «expected fail» итоговой строки, номер повтора `#1` у имени на `#<цифры>`.

**Публичные функции:**
- `box`
- `by_name`
- `case`
- `error`
- `fail_to_pass`
- `harness`
- `inputs`
- `module`
- `picked`
- `run_reporter`
- `suite`
- `test_ac10_table_end_to_end_with_parse_vitest`
- `test_ac11_summary_accepts_expected_fail_only`
- `test_ac12_explicit_n_unchanged`
- `test_ac12_random_names_round_trip`
- `test_ac12_test_id_adds_one_for_numbered_name_and_round_trips`
- `test_ac13_report_ids_number_first_occurrence_of_numbered_name`
- `test_ac14_not_passed_kind_repeat_from_two`
- `test_ac15_plank_gate_repeat_only_from_second_copy`
- `test_ac1_vitest4_entry_no_cache_flag_and_form`
- `test_ac2_no_cache_right_after_require_assertions_without_cache_dir`
- `test_ac3_version_refusals_keep_texts`
- `test_ac4_error_class_from_constructor_then_name`
- `test_ac5_test_hook_failed_by_run_or_fail`
- `test_ac6_collection_error_without_hooks_stays_file_level`
- `test_ac6_module_before_all_goes_to_tests_not_file_level`
- `test_ac6_skips_stay_skip_without_hook`
- `test_ac6_suite_before_all_fails_skipped_tests`
- `test_ac7_after_all_fails_passed_keeps_honest_failure_and_skip`
- `test_ac8_only_error_marks_mode_only_up_the_chain`
- `test_ac9_ordinary_records_unchanged`
- `test_ac9_output_file_without_env`

**Импортирует:** `orchestrator/advance_gates/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/config.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `tests/fixtures.py`, `tests/report_outcome_sandbox.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`

**Импортируется:** —

## tests/test_01m5scgsqn0at0b07h7m9803ra_doctor_layer.py

**Назначение:** Строка `doctor` `targets-local-layer`: локальный слой записей внешних проектов и записи внешних проектов в `targets.yaml` репозитория.

**Публичные функции:**
- `flat_entry`
- `layout`
- `local_command`
- `local_file`
- `pult`
- `test_ac13_broken_local_layer_fails_targets_yaml`
- `test_ac13_local_layer_line`
- `three_entry`

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py

**Назначение:** Локальный слой записей внешних проектов: место файла, формат трёх разделов, сведение в прежнюю запись, слияние со слоем репозитория.

**Публичные функции:**
- `artel_with_reference`
- `cache_dir`
- `component_three`
- `dump`
- `entries_text`
- `flat_loaded`
- `layers`
- `local_file`
- `profile_pair`
- `reference`
- `refusal`
- `seed`
- `test_ac10_unknown_name_text_tail`
- `test_ac11_broken_local_entry_keeps_artel_reference`
- `test_ac11_core_reference_layer_choice`
- `test_ac1_local_path_follows_targets`
- `test_ac2_no_local_file_keeps_repo_output`
- `test_ac3_policy_sandbox_moves_to_top_level`
- `test_ac3_sled_three_sections_merge_to_pin_entry`
- `test_ac4_two_components_get_own_path_and_scopes`
- `test_ac5_format_refusal_names_file_entry_field`
- `test_ac5_repo_check_text_unchanged`
- `test_ac6_absolute_value_refused`
- `test_ac6_machine_absolute_values_accepted`
- `test_ac7_cache_placeholder_outside_env_refused`
- `test_ac7_machine_path_without_own_runner_names_machine_path`
- `test_ac8_broken_repo_copy_still_refused`
- `test_ac8_merge_order_and_local_wins`
- `test_ac9_broken_local_layer_refused`
- `write_local`
- `write_repo`
- `yaml_scalar`

**Импортирует:** `orchestrator/canary.py`, `orchestrator/config.py`, `orchestrator/targets.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5scgsqn0at0b07h7m9803ra_targets_migrate.py

**Назначение:** Команда `targets-migrate <имя>`: перенос записи внешнего проекта в локальный слой, отказы, отказ процессу роли; линт пути к локальному слою.

**Публичные функции:**
- `cli`
- `flow`
- `local_file`
- `seed`
- `sled_pin`
- `test_ac12_artel_or_missing_refused_no_file`
- `test_ac12_existing_layer_kept_verbatim`
- `test_ac12_foreign_absolute_env_refused`
- `test_ac12_quoted_values_survive_round_trip`
- `test_ac12_repeat_refused_file_unchanged`
- `test_ac12_sled_pin_migrates_and_loads_same`
- `test_ac12_two_components_with_different_paths`
- `test_ac12_unrepresentable_value_refused_no_file`
- `test_ac15_lint_live_local_layer_path`
- `test_ac15_role_environment_refused_before_run`
- `three_section_text`
- `two_components_text`
- `write_repo`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/targets.py`, `orchestrator/test_lint.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5scgsqn0at0b07h7m9803ra_watch_layer.py

**Назначение:** Надзор главной копии пульта за локальным слоем `.artel/targets.yaml`: сумма файла на старте шага и сверка после шага.

**Публичные функции:**
- `layer_text`
- `local_file`
- `seed`
- `test_ac14_layer_change_raises_watch_alert`
- `test_ac14_old_constructor_form_has_no_digest`
- `test_ac14_unchanged_layer_no_alert_no_extra_calls`
- `watch_alerts`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py

**Назначение:** Конвенции внешнего проекта в брифе ролей и пакете ревьювера — из файла

**Публичные функции:**
- `broken_text`
- `built_text`
- `has_journal`
- `header_block`
- `header_of`
- `hex40`
- `journal_lines`
- `scene`
- `seed`
- `spoil_conventions`
- `test_ac14_unresolved_context_marked_unread_with_conventions`
- `test_ac1_pult_conventions_single_component_in_five_points`
- `test_ac2_unreadable_conventions_marked_unparsed`
- `test_ac3_broken_stamp_header_marked_unparsed`
- `test_ac4_size_limit_counts_text_without_header`
- `test_ac5_wrapper_paths_skipped_in_knowledge`
- `test_ac7_missions_name_pult_conventions_not_project_files`
- `word`

**Импортирует:** `orchestrator/config.py`, `orchestrator/context_package.py`, `orchestrator/repo_context.py`, `orchestrator/role_prompt.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_stamp.py

**Назначение:** Отметка разбора конвенций внешнего проекта (`artel.py conventions-stamp`),

**Публичные функции:**
- `assert_stamped`
- `header_block`
- `hex40`
- `scene`
- `seed`
- `split_stamp`
- `test_ac10_doctor_drift_by_base_ref_only`
- `test_ac11_artel_has_no_project_conventions_row`
- `test_ac11_doctor_warns_with_reason_and_never_raises`
- `test_ac13_stamp_and_doctor_without_network`
- `test_ac8_stamp_reads_base_ref_not_head_or_worktree`
- `test_ac9_stamp_refuses_without_touching_file`
- `word`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_doctor.py

**Назначение:** Строка `doctor` `target-wrapper-worktrees`: файлы обвязки на диске рабочих копий задач внешнего проекта; у артели — `ok` «рабочие копии артели полные по замыслу».

**Публичные функции:**
- `doctor_lines`
- `local_command`
- `sb`
- `test_ac23_worktree_wrapper_warn_then_ok_after_ensure`

**Импортирует:** `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_entry.py

**Назначение:** Обвязка внешнего проекта в формуле защищённых путей и в его записи: запись `**/<каталог>/`, поле `agent_wrapper`, перечень `protected_paths`, отказ записи по `knowledge` компонента.

**Публичные функции:**
- `component_extra`
- `flat_entry`
- `flat_profile`
- `flow`
- `local_entry`
- `perimeter`
- `seed`
- `test_ac14_knowledge_into_wrapper_refused`
- `test_ac14_knowledge_outside_wrapper_loads`
- `test_ac3_dir_mask_fixed_paths`
- `test_ac3_dir_mask_random_names`
- `test_ac6_agent_wrapper_field_loads_in_both_layers`
- `test_ac6_agent_wrapper_not_list_refused`
- `test_ac7_targets_migrate_moves_agent_wrapper_to_policy`
- `test_ac8_external_perimeter_fixed_cases`
- `test_ac8_external_perimeter_random_order_and_duplicates`
- `test_ac9_artel_perimeter_is_protected_paths`
- `write_layers`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/repo_context.py`, `orchestrator/targets.py`, `orchestrator/yamlmini.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_flow.py

**Назначение:** Сквозной ход задачи внешнего проекта на рабочей копии без обвязки: планка (`plank-run`), `suite-run`, гейт зон на `in_dev -> verifying` и сборка диффа ревью.

**Публичные функции:**
- `in_process_background`
- `stand`
- `test_ac25_plank_run_green_on_worktree_without_wrapper`
- `test_ac25_suite_run_zones_gate_and_review_diff`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/review.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_gates.py

**Назначение:** Обвязка внешнего проекта в местах сверки перечня защищённых путей: гейт зон на выходе из `in_dev`, гейт диффа на мерже, подсветка Draft MR, зоны ТЗ, SPEC и `guard.protected_zones`.

**Публичные функции:**
- `highlight`
- `in_dev_refusal`
- `refusal_lines`
- `stand`
- `test_ac10_wrapper_paths_refused_on_in_dev_exit`
- `test_ac11_wrapper_paths_escalate_on_merge_gate`
- `test_ac12_draft_mr_names_wrapper_and_its_source`
- `test_ac13_guard_protected_zones_with_project_perimeter`
- `test_ac13_spec_gate_zones_under_wrapper_dir_refused`
- `test_ac13_tz_zones_under_wrapper_dir_refused`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_worktree.py

**Назначение:** Рабочая копия задачи внешнего проекта без обвязки: `workspace.ensure` исключает пути действующего списка обвязки с диска (sparse-checkout без конусов), приводит исключения к текущему списку, убирает неотслеживаемые и игнорируемые файлы под ними; ветка и дифф задачи не меняются; у артели копия полная.

**Публичные функции:**
- `failing_sparse`
- `on_disk`
- `stand`
- `test_ac15_ensure_checks_out_without_wrapper`
- `test_ac16_step_checkpoint_keeps_wrapper_in_branch`
- `test_ac17_ensure_idempotent_and_fixes_full_worktree_only`
- `test_ac18_ensure_follows_current_wrapper_list`
- `test_ac19_ensure_removes_untracked_and_ignored_under_wrapper`
- `test_ac20_checkpoint_with_untracked_wrapper_file_commits_step`
- `test_ac21_sparse_failure_is_named_refusal_and_step_not_started`
- `test_ac22_artel_worktree_is_full`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py

**Назначение:** Сторож единой точки запуска git: пять модулей пульта, чтения git которых

**Публичные функции:**
- `raw_git_launches`
- `test_ac2_guard_allows_subprocess_import_and_non_git_launch`
- `test_ac2_guard_turns_red_on_each_original_place`
- `test_ac2_guard_turns_red_on_random_raw_git_launch`
- `test_ac2_modules_launch_git_only_through_gitcmd`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/brief.py`, `orchestrator/reference_cache.py`, `orchestrator/tz_check.py`

**Импортируется:** —

## tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_closed_as.py

**Назначение:** Признак поделённого родителя `closed_as`: миграция прежних делений и

**Публичные функции:**
- `all_rows`
- `all_steps`
- `as_previous_version`
- `new_task`
- `note`
- `raw_connection`
- `set_state`
- `stand`
- `status_line`
- `steps_of`
- `test_ac17_status_counts_merged_parts_of_divided_parent`
- `test_ac2_migration_marks_only_divided_and_is_idempotent`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/schema.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py

**Назначение:** Деление на гейте SPEC доводится до конца: признак поделённого родителя,

**Публичные функции:**
- `apply_part_spec_budget`
- `assert_refused`
- `baseline_part`
- `chain_orders`
- `dependent_of`
- `deps`
- `divide`
- `divide_parent`
- `divide_with_titles`
- `division_lines`
- `frame_records`
- `frame_value`
- `journal`
- `last_refusal`
- `last_step_id`
- `make_parent`
- `names_part`
- `new_task`
- `next_zone`
- `normalized`
- `note`
- `parent_spec`
- `parts_by_title`
- `put_on_gate`
- `refusal_scenario`
- `row`
- `run`
- `stand`
- `tasks_snapshot`
- `test_ac10_refused_division_writes_nothing`
- `test_ac11_part_without_after_gets_warning_naming_it`
- `test_ac12_frame_becomes_operator_ceiling_of_part`
- `test_ac14_bad_frame_refused_on_approve`
- `test_ac14_frame_equal_to_cap_accepted`
- `test_ac18_part_without_frame_keeps_todays_ceiling`
- `test_ac19_successor_is_last_part_by_graph`
- `test_ac1_divided_parent_marked_killed_task_not`
- `test_ac3_chain_resolves_order_into_merge_after`
- `test_ac4_part_number_out_of_range_refused`
- `test_ac5_self_reference_refused`
- `test_ac6_cycle_between_parts_refused`
- `test_ac7_parent_as_dependency_refused`
- `test_ac8_cycle_through_dependent_of_parent_refused`
- `test_ac9_task_id_element_resolved_or_refused`
- `titles`
- `unique_prefix`
- `warning_template`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/idgen.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_guard_frame.py

**Назначение:** Проверка поля «Рамка:» частей деления в `scripts/guard.py`.

**Публичные функции:**
- `frame_value`
- `names_part`
- `scenario`
- `spec_text`
- `test_ac13_bad_frame_is_guard_error_naming_part`
- `test_ac13_frame_at_cap_or_absent_is_not_error`

**Импортирует:** `orchestrator/config.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_terminal_literal_guard.py

**Назначение:** Сторож одного списка окончательных состояний: литерала из ровно

**Публичные функции:**
- `literal_text`
- `terminal_literals`
- `test_ac16_no_terminal_literal_outside_fsm_and_sentinel_catches_one`

**Импортирует:** —

**Импортируется:** —

## tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py

**Назначение:** Модель доски `board().build_model(conn, project)`: ключи модели, элементы

**Публичные функции:**
- `board`
- `card`
- `cli`
- `edge_shape`
- `epic_item`
- `epic_new`
- `epics`
- `expected_waiting`
- `insert_task`
- `model`
- `no_zone_wait`
- `note`
- `stand`
- `test_ac20_top_level_keys_and_columns`
- `test_ac21_epic_and_card_elements`
- `test_ac22_waiting_on_for_every_state`
- `test_ac23_zone_wait_turns_role_into_dependency`
- `test_ac24_build_is_repeatable_and_read_only`
- `test_ac33_epic_spent_counts_and_nodes`
- `test_ac38_pin_is_head_of_pult_root`
- `write_git`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/idgen.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbbdfs6dwqy6ms263t1kpy_division_epic.py

**Назначение:** Деление на гейте SPEC и эпик: наследование эпика частями, `approve

**Публичные функции:**
- `cli`
- `epic_new`
- `epics`
- `in_epic`
- `next_zone`
- `note`
- `parent_on_gate`
- `parts_of`
- `refusal_parent`
- `row`
- `snapshot`
- `spec_text`
- `stand`
- `test_ac11_parts_inherit_parent_epic`
- `test_ac12_as_epic_creates_epic_from_parent`
- `test_ac13_as_epic_refused_without_any_write`
- `test_ac14_cli_flag_is_not_taken_for_sha`
- `test_ac36_soft_gate_refusal_creates_no_epic`
- `test_ac37_refusal_after_spec_read_writes_no_steps`
- `test_ac37_unreadable_parent_spec_refused`
- `words`

**Импортирует:** `orchestrator/advance_gates/spec_audit.py`, `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbbdfs6dwqy6ms263t1kpy_epic_commands.py

**Назначение:** Эпик как сущность пульта: команды `epic new|edit|close|add|remove|show`,

**Публичные функции:**
- `artifact_ref_recorder`
- `assert_new_epic_refused`
- `bound`
- `cli`
- `closed_epic`
- `deps`
- `epic_new`
- `epic_of`
- `epics`
- `foreign_lease`
- `insert_task`
- `interleave_at`
- `is_pause_point`
- `last_step_id`
- `lease_spies`
- `leased_ids`
- `new_cli`
- `non_terminal_states`
- `note`
- `set_state`
- `snapshot`
- `stand`
- `steps_since`
- `task`
- `task_ids`
- `test_ac10_tz_order_line_and_after_are_merged`
- `test_ac15_close_refused_while_task_not_terminal`
- `test_ac18_foreign_live_lease_refuses_add_and_remove`
- `test_ac18_no_command_takes_lease_by_epic_id`
- `test_ac1_epic_new_creates_open_epic_with_journal`
- `test_ac30_journal_of_epic_commands_carries_epic_and_project`
- `test_ac31_add_to_second_epic_and_remove_from_foreign_refused`
- `test_ac32_prefix_dedup_and_after_without_epic`
- `test_ac35_unknown_epic_refused_before_lease`
- `test_ac39_close_and_add_are_mutually_exclusive`
- `test_ac3_epic_edit_changes_title_and_goal`
- `test_ac4_epic_add_and_remove_with_journal`
- `test_ac5_binding_to_other_project_epic_refused`
- `test_ac6_binding_to_closed_epic_refused`
- `test_ac7_new_with_epic_and_after`
- `test_ac8_after_unknown_task_refused`
- `test_ac9_epic_id_is_not_a_task_id`
- `tz_file`
- `unique_prefix`
- `words`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/idgen.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbbdfs6dwqy6ms263t1kpy_migration.py

**Назначение:** Миграция схемы под эпики: таблица `epics`, колонка `tasks.epic_id`, одна

**Публичные функции:**
- `all_steps`
- `config_strings`
- `connect`
- `migrate_interleaved`
- `note`
- `previous_version`
- `schema_dump`
- `stand`
- `test_ac19_migration_adds_epics_once_with_one_system_record`
- `test_ac34_migration_without_steps_table`
- `test_ac34_two_connections_in_sequence_leave_one_record`
- `test_ac34_two_connections_interleaved_leave_one_record`
- `touches_epics`

**Импортирует:** `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/schema.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py

**Назначение:** Виды из модели доски: `epic show` (таблица задач эпика) и `status` с

**Публичные функции:**
- `block_header`
- `board`
- `carries_id`
- `cell`
- `cli`
- `count_near`
- `divide`
- `epic_header`
- `epic_new`
- `epics`
- `insert_task`
- `insert_task_state`
- `line_index`
- `lines_of`
- `money`
- `note`
- `stand`
- `table_cells`
- `task_line`
- `test_ac16_all_terminal_shows_ready_and_close_closes`
- `test_ac17_empty_epic_is_not_ready`
- `test_ac25_views_take_title_and_counts_from_model`
- `test_ac26_status_epic_group_header_and_order`
- `test_ac27_task_line_in_group_equals_line_after_remove`
- `test_ac28_status_project_blocks`
- `test_ac2_epic_show_table_names_parent_and_dependency`
- `words`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/idgen.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbcy7wtn121s136xp2c6sr_auto_stop.py

**Назначение:** Остановка `auto <id>` на отказе `run` по конверту эпика и по `start_after` — своя причина и подсказка.

**Публичные функции:**
- `journal_text`
- `pult`
- `test_ac11_auto_stops_on_envelope_with_its_hint`
- `test_ac17_auto_stops_waiting_for_start_after`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** —

## tests/test_01m5tbcy7wtn121s136xp2c6sr_envelope_run.py

**Назначение:** Проверка старта первого шага роли: конверт бюджета эпика и зависимость запуска `start_after`.

**Публичные функции:**
- `assert_envelope_refusal`
- `epic_with_start_after`
- `exhausted_epic`
- `header_numbers`
- `mentions`
- `pult`
- `rows_text`
- `split_spent`
- `status_shape`
- `test_ac10_refusal_record_does_not_count_as_first_step`
- `test_ac12_started_task_gets_next_step_and_keeps_ceiling`
- `test_ac13_envelope_command_raise_lower_and_refusals`
- `test_ac15_epic_without_envelope_has_no_envelope_checks`
- `test_ac16_first_step_waits_for_start_after`
- `test_ac22_killed_start_after_refuses_with_hint`
- `test_ac24_epic_spent_is_the_single_source`
- `test_ac26_task_without_epic_runs_unchanged`
- `test_ac28_start_after_checked_only_before_first_step`
- `test_ac8_first_step_refused_when_envelope_exceeded`
- `test_ac9_spent_equal_to_envelope_refuses`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** —

## tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_alert.py

**Назначение:** Алерт 80 % конверта эпика после начисления стоимости шага: обе ветви учёта `runner` и `pause --now`.

**Публичные функции:**
- `charging`
- `cli`
- `epic_alerts`
- `new_epic`
- `open_epic_alerts`
- `pausing`
- `result_event`
- `test_ac3_charge_step_raises_one_alert_per_envelope`
- `test_ac4_missing_result_branch_raises_alert`
- `test_ac5_pause_now_partial_charge_raises_alert`
- `test_ac6_new_envelope_restarts_alert_count`
- `usage_event`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/artel.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_view.py

**Назначение:** Показ конверта эпика: «потрачено / конверт» и предупреждение 80 % в `status` и `epic show`, предупреждение `new --epic`, `waiting_on` модели доски.

**Публичные функции:**
- `db_dump`
- `epic_header`
- `numbers`
- `shape`
- `test_ac14_new_with_exhausted_envelope_creates_task_and_warns`
- `test_ac1_status_shows_spent_envelope_and_warning_without_writing`
- `test_ac25_epic_show_and_board_waiting_on_dependency`
- `test_ac2_status_warns_at_exact_threshold`
- `viewer`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/board.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m5tbcy7wtn121s136xp2c6sr_epic_watch.py

**Назначение:** Строка предупреждения 80 % по эпику в сессии `watch` — по событиям начисления стоимости шага.

**Публичные функции:**
- `cli`
- `session`
- `test_ac27_session_started_above_threshold_prints_nothing`
- `test_ac29_partial_and_estimated_are_charge_events`
- `test_ac7_one_warning_line_on_crossing`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbcy7wtn121s136xp2c6sr_start_after_write.py

**Назначение:** Запись `start_after`: проверки элемента, подстановка поделённой задачи и цикл по объединённому графу `merge_after` ∪ `start_after`.

**Публичные функции:**
- `bad_dependency`
- `test_ac18_bad_start_after_refused_value_kept`
- `test_ac19_merge_after_cycle_through_start_after_refused_in_all_channels`
- `test_ac20_divided_dependency_replaced_by_last_part`
- `test_ac21_division_chain_resolved_to_undivided`
- `test_ac23_replace_divided_updates_start_after`
- `writer`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py

**Назначение:** Надзирающий процесс эпика `auto --epic`: запуск дочерних `auto`, лимиты, гейты, остановки, `epic parallel|stop|retry`, наблюдение и самостоятельное завершение (AC-1 … AC-33).

**Публичные функции:**
- `cycle_records`
- `epic_stop_scenario`
- `final_epic`
- `is_pult_launch`
- `pult`
- `ready_epic`
- `run_command_line`
- `stale_lock_takeover`
- `supervisor_ends_itself`
- `test_ac10_task_with_foreign_live_lease_skipped`
- `test_ac11_spec_gate_task_not_launched_not_approved_supervisor_waits`
- `test_ac12_gate_stopped_task_relaunched_after_approve`
- `test_ac13_not_on_gate_stop_holds_task_and_supervisor`
- `test_ac14_resume_after_pause_stop_relaunches`
- `test_ac15_resume_without_pause_does_not_reopen`
- `test_ac16_epic_retry_records_and_relaunches_and_refuses_outsider`
- `test_ac17_manual_stop_holds_until_operator_action`
- `test_ac18_abnormal_child_exit_holds_until_operator_action`
- `test_ac19_observation_choice_and_child_in_its_set`
- `test_ac1_only_first_task_launched_with_parallel_one`
- `test_ac20_foreign_session_observation_refused_and_not_chosen`
- `test_ac21_no_observation_by_rule_refused`
- `test_ac22_stale_observation_ends_supervisor_with_record_and_alert`
- `test_ac23_epic_stop_supervisor_first_then_children_by_sigterm`
- `test_ac24_epic_stop_spares_operator_auto`
- `test_ac25_epic_stop_with_dead_supervisor`
- `test_ac26_exhausted_envelope_only_started_tasks_launched`
- `test_ac27_all_tasks_final_supervisor_ends_itself`
- `test_ac28_start_after_on_killed_supervisor_ends_itself`
- `test_ac29_exhausted_envelope_unstarted_only_supervisor_ends_itself`
- `test_ac2_third_after_place_freed_second_only_after_first_done`
- `test_ac30_watch_delivers_attention_alert_and_end_record`
- `test_ac31_escalated_task_not_launched_and_holds_supervisor`
- `test_ac32_global_limit_refusal_requeues_without_operator`
- `test_ac33_place_counted_by_child_pid`
- `test_ac3_live_children_never_exceed_epic_limit`
- `test_ac4_invalid_parallel_refused_and_limit_kept`
- `test_ac5_foreign_live_leases_take_global_places`
- `test_ac6_second_supervisor_refused_with_live_pid`
- `test_ac7_dead_pid_lock_removed_with_record_and_supervisor_started`
- `test_ac8_lock_of_process_started_later_is_dead`
- `test_ac9_supervisor_records_lock_row_and_no_lease`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/pause.py`, `orchestrator/store.py`, `orchestrator/watch.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_drafts.py

**Назначение:** Черновики и решения эпика: `epic draft add|edit|drop|promote`,

**Публичные функции:**
- `binding`
- `cli`
- `decision_rows`
- `decision_text`
- `draft_add`
- `draft_titled`
- `drafts_of`
- `epic_new`
- `epic_rows`
- `epics`
- `frame`
- `has_number`
- `ids_in`
- `insert_task`
- `ints`
- `marker`
- `noise_drafts`
- `note`
- `promote`
- `rows`
- `set_state`
- `snapshot`
- `stand`
- `task`
- `task_ids`
- `test_ac16_unknown_list_elements_refused_with_full_listing`
- `test_ac17_decision_for_unknown_task_refused`
- `test_ac18_number_after_drop_is_max_plus_one`
- `test_ac19_promoted_frame_is_operator_ceiling_not_overridden_by_spec`
- `test_ac1_draft_add_numbers_text_title_frame_and_refusals`
- `test_ac20_draft_in_draft_state_blocks_ready_and_close`
- `test_ac2_promote_creates_task_with_epic_frame_and_dependencies`
- `test_ac3_promote_waits_for_referenced_draft_then_resolves_it`
- `test_ac5_edit_and_drop_change_draft_then_non_draft_refused`
- `test_ac6_decision_text_is_byte_exact_and_carries_binding`
- `tz_file`
- `words`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_epic_ref.py

**Назначение:** Копия эпика в ссылке `refs/artifacts/epic-<id>` репозитория проекта

**Публичные функции:**
- `build_restore_source`
- `changing_command`
- `cli`
- `column_holding`
- `draft_add`
- `empty_db`
- `epic_artel_refs`
- `epic_new`
- `epic_pushes`
- `epic_ref`
- `epic_rows`
- `epic_state`
- `failed_pushes`
- `git_calls`
- `insert_task`
- `lines_in`
- `local_head`
- `marker`
- `normalized`
- `note`
- `origin_head`
- `promote`
- `ref_file`
- `ref_paths`
- `reject_epic_refs`
- `rows`
- `rows_of`
- `set_state`
- `snapshot`
- `stand`
- `task_ids`
- `test_ac10_export_prints_every_ref_file_verbatim_in_order`
- `test_ac12_restore_recreates_rows_equal_to_source`
- `test_ac13_second_restore_changes_nothing`
- `test_ac14_restore_refuses_on_divergence_and_keeps_db`
- `test_ac21_each_listed_command_sends_ref_once`
- `test_ac21_push_failure_journal_has_epic_id_and_project`
- `test_ac22_write_failure_without_clone_keeps_db_and_next_command_writes`
- `test_ac4_promote_refused_by_new_tz_check`
- `test_ac7_every_changing_command_writes_and_sends_ref_once`
- `test_ac8_refused_and_read_only_commands_keep_ref_head`
- `test_ac9_unavailable_origin_then_next_command_sends`
- `tz_file`
- `words`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_migration.py

**Назначение:** Миграция схемы под черновики и решения эпика: таблицы `epic_drafts` и

**Публичные функции:**
- `cli`
- `columns`
- `connect`
- `fresh_columns`
- `note`
- `other_rows`
- `previous_version`
- `schema_dump`
- `stand`
- `tables`
- `test_ac15_migrate_creates_both_tables_and_keeps_other_rows`
- `test_ac15_migrated_tables_carry_fields_of_drafts_and_decisions`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/schema.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py

**Назначение:** Ссылка эпика `refs/artifacts/epic-<id>` рядом со ссылкой документов

**Публичные функции:**
- `both_in_origin`
- `both_local`
- `cli`
- `commit_tree`
- `db_rows`
- `drop`
- `local_ref`
- `note`
- `place`
- `stand`
- `test_ac11_cleanup_inventory_ignores_epic_ref`
- `test_ac11_docs_fetch_all_brings_both_refs_without_epic_line`
- `test_ac11_doctor_ref_sync_has_no_epic_finding`
- `test_ac11_history_snapshots_dry_run_ignores_epic_ref`
- `test_ac11_new_clone_brings_both_refs_silently`
- `test_ac11_plan_appendix_ci_refs_skip_epic`
- `test_ac11_retro_cache_has_no_epic_row`
- `without_epic`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/retro_corpus.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/plan_appendix_ci.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_epic_ref_scan_filters.py`

## tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_board_command.py

**Назначение:** Команда `board --project <имя> [--json | --md | --html]`: вывод модели

**Публичные функции:**
- `board`
- `board_json`
- `card`
- `cli`
- `epic_new`
- `epics`
- `has_ref`
- `insert_task`
- `link`
- `note`
- `parse_json`
- `plain`
- `populated`
- `ref_key`
- `stand`
- `test_ac14_board_json_waiting_on_from_zone_queue`
- `test_ac15_old_db_gets_external_refs_on_open`
- `test_ac1_json_carries_top_fields_and_card_fields`
- `test_ac2_two_json_runs_are_equal_but_generated_at`
- `test_ac3_board_and_report_do_not_touch_network`
- `test_ac3_board_does_not_change_db`
- `test_ac4_default_view_equals_md`
- `test_ac4_md_and_html_are_built_from_the_model`
- `test_ac4_unknown_project_refused_with_its_name`
- `words`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_external_refs.py

**Назначение:** Внешние ссылки задач и эпиков: `new --ref`, `link` и `link --remove`,

**Публичные функции:**
- `artifact_ref_recorder`
- `assert_new_refused_clean`
- `board`
- `card_refs`
- `cli`
- `created_one`
- `epic_new`
- `epic_refs`
- `epics`
- `insert_task`
- `link`
- `make_clone`
- `matching`
- `model`
- `new`
- `note`
- `policy_project`
- `ref_key`
- `ref_rows`
- `rows_of`
- `spec_text`
- `stand`
- `task_ids`
- `test_ac10_link_epic_shows_in_epic_refs`
- `test_ac10_link_task_with_url_in_write_order`
- `test_ac10_link_to_unknown_object_refused`
- `test_ac10_remove_link_and_refuse_missing`
- `test_ac10_repeated_link_adds_no_second_row`
- `test_ac11_canary_task_skips_ref_required`
- `test_ac11_ref_required_refuses_new_without_it`
- `test_ac11_remove_of_last_required_ref_refused`
- `test_ac12_any_nonempty_system_without_list`
- `test_ac12_empty_system_or_key_refused`
- `test_ac12_ref_systems_limits_new_and_link`
- `test_ac13_division_parts_copy_parent_refs`
- `test_ac9_new_ref_is_stored_and_shown_with_author_and_time`
- `test_ac9_new_with_two_refs_stores_both`
- `test_ac9_ref_is_split_on_first_colon`
- `test_ac9_ref_is_written_before_task_worktree`
- `test_ac9_ref_without_colon_refused_before_side_effects`
- `words`
- `written_at`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_report_model.py

**Назначение:** `report` из модели доски: группы эпиков внутри колонки, плитка из

**Публичные функции:**
- `board`
- `board_section`
- `cli`
- `columns`
- `counted`
- `counted_report`
- `epic_new`
- `epics`
- `insert_task`
- `note`
- `run_report`
- `seed_in_dev`
- `stand`
- `test_ac14_report_steps_queries_do_not_grow_with_tasks`
- `test_ac6_epic_groups_inside_column`
- `test_ac7_report_tile_takes_values_from_model`
- `test_ac8_card_carries_tile_fields`
- `text_of`
- `words`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/report.py`, `orchestrator/store.py`, `orchestrator/zone_lock.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py

**Назначение:** Проект с неподдержанным хостингом (`forge: gitlab`) или гейтом мержа людьми проекта (`merge_gate: target-human`): запись читается, а `new`, `run`, `auto`, `approve` отказывают именованной причиной `targets.unsupported_reason`; `doctor` выводит строку `project-support-<проект>`.

**Публичные функции:**
- `cli`
- `declare`
- `field_like`
- `flat_entry`
- `git_calls`
- `halted`
- `insert_task`
- `journal_with`
- `local_command`
- `project_name`
- `pult`
- `seed`
- `support_comparisons`
- `table`
- `test_ac1_entry_loads_and_reason_names_unsupported_value`
- `test_ac2_new_refuses_without_side_effects`
- `test_ac3_run_refuses_before_agent_and_git`
- `test_ac4_auto_refuses_at_entry`
- `test_ac5_approve_on_merge_gate_refuses_before_merge`
- `test_ac6_approve_on_spec_gate_refuses`
- `test_ac7_doctor_project_support_line`
- `test_ac8_supported_project_new_is_not_refused`
- `test_ac9_no_support_literals_outside_targets`
- `unsupported_project`
- `watched_literals`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/idgen.py`, `orchestrator/repo_context.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py

**Назначение:** Ветка задачи по шаблону `policy.branch_template`: `new --ref` строит имя по ключу ссылки, занятое или непроверенное имя отказывает `new` и деление до заведения задачи, при шаблоне по умолчанию сетевого вызова нет.

**Публичные функции:**
- `approve`
- `assert_refused_clean`
- `cli`
- `created_branch`
- `division_parent`
- `epics`
- `insert_task`
- `key`
- `ls_remote_rest`
- `new`
- `note`
- `part_titles`
- `parts_of`
- `project`
- `render`
- `snapshot`
- `spec_text`
- `stand`
- `taken`
- `task_ids`
- `task_row`
- `test_ac3_new_ref_builds_branch_by_template`
- `test_ac3_new_ref_refused_without_trace`
- `test_ac4_default_template_division_without_ls_remote`
- `test_ac4_default_template_new_without_ls_remote`
- `test_ac4_ls_remote_failure_refuses_new`
- `test_ac4_taken_branch_name_refuses_new`
- `test_ac5_division_refused_before_any_part`
- `test_ac5_id_template_parts_get_checked_names`
- `words`
- `write_spec`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** —

## tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py

**Назначение:** Поля записи проекта для доставки через MR: проверка формы при загрузке записи локального слоя, отказ называет поле, плоская запись без новых ключей и `ci_required_jobs` в плоской записи.

**Публичные функции:**
- `assert_refused_by_field`
- `load`
- `project_name`
- `render`
- `sections`
- `seed`
- `test_ac1_record_rule_refused_with_field_name`
- `test_ac2_ci_required_jobs_in_flat_record`
- `test_ac2_field_form_refused_with_field_name`
- `test_ac2_record_without_new_fields_keeps_flat_shape`
- `write_record`

**Импортирует:** `orchestrator/config.py`, `orchestrator/targets.py`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

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

## tests/test_board_refs_units.py

**Назначение:** Юниты внешних ссылок и вида `board --md` (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/board.py`, `orchestrator/targets.py`

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

## tests/test_canary_child_row_write.py

**Назначение:** Запись строки «оборвана сигналом» дочерним `canary run-task` и её отчёт

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_conventions.py

**Назначение:** Конвенции внешнего проекта из файла пульта (`orchestrator/conventions.py`):

**Публичные функции:**
- `header`

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/conventions.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_division_order_units.py

**Назначение:** Модульные свойства проверки порядка и рамки частей деления (SPEC

**Публичные функции:**
- `new_task`
- `order`
- `test_division_frame_accepts`
- `test_division_frame_refuses_empty_and_non_positive`
- `test_parent_prefix_is_dead_dependency`
- `test_repeated_part_and_empty_list_refused`
- `test_successor_is_last_when_nobody_depends_on_it`
- `test_successor_of_two_tops_is_greater_number`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_division_parent_cleanup.py

**Назначение:** Юнит-тесты уборки хвостов поделённого родителя на гейте SPEC

**Публичные функции:**
- `failing_branch_delete`

**Импортирует:** `orchestrator/artifact_branch.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_doc_commit_module.py

**Назначение:** Тесты `doc-commit` и сверки удержанной записи по базе

**Публичные функции:**
- `advance_pin_and_origin`
- `assert_both_arrived`
- `assert_nothing_sent`
- `assert_refused`
- `break_fetch`
- `close_silence_window`
- `close_window`
- `commit_config`
- `config_source`
- `doc_box`
- `doc_commit`
- `held_box`
- `held_doc_commit`
- `held_origin_git`
- `held_origin_head`
- `held_origin_show`
- `held_source`
- `hold_both_kinds`
- `hold_config_without_base`
- `hold_doc_commit`
- `hold_legacy`
- `hold_note`
- `invalid_text`
- `journal_text`
- `kc_origin_head`
- `kc_origin_show`
- `kc_origin_subject`
- `knowledge_box`
- `main_copy_snapshot`
- `msg`
- `name`
- `note_row`
- `open_silence_window`
- `open_window`
- `origin_blob`
- `origin_commits_touching`
- `origin_has`
- `origin_head`
- `origin_run`
- `origin_show`
- `origin_show_bytes`
- `origin_subject`
- `pending_dir`
- `pending_files`
- `pending_ids`
- `pending_paths`
- `push_foreign_change_past_the_pin`
- `push_foreign_config_change`
- `push_foreign_past_the_pin`
- `push_main`
- `refuse_config`
- `reseed_suite`
- `run_command`
- `run_command_exited`
- `source_file`
- `spy_suite`
- `stale_scenario`
- `string_values`
- `test_absolute_dotdot_empty_and_bare_docs_dir_refused`
- `test_ac14_invalid_form_refused_without_commit_or_hold`
- `test_ac14_knowledge_paths_not_in_config_paths`
- `test_ac14_nested_and_non_yaml_paths_refused`
- `test_ac14_previous_paths_behave_as_before`
- `test_ac14_role_environment_refused`
- `test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite`
- `test_ac1_held_record_stores_pin_blob_or_absent_mark`
- `test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others`
- `test_ac2_note_flush_refuses_stale_base`
- `test_ac2_opportunistic_flush_refuses_stale_base`
- `test_ac3_base_matching_origin_is_sent`
- `test_ac4_new_file_absent_in_origin_is_sent`
- `test_ac4_new_file_appeared_in_origin_is_refused`
- `test_ac5_immediate_send_still_refuses_on_pin`
- `test_ac6_legacy_record_pin_differs_is_refused_with_warning`
- `test_ac6_legacy_record_pin_matches_is_sent_with_warning`
- `test_ac7_pending_lists_each_record_with_truncated_content`
- `test_ac8_drop_pending_removes_exactly_one_and_journals`
- `test_ac9_pending_and_drop_pending_refuse_under_role`
- `test_accept_red_commits_and_journal_carries_path_and_reason`
- `test_accept_red_record_is_sent_by_the_opportunistic_flush`
- `test_accept_red_skips_the_run_entirely`
- `test_accept_red_without_reason_refuses_by_substance_not_argparse`
- `test_artel_dispatches_doc_commit_with_rest_argv`
- `test_backlog_is_refused_naming_note`
- `test_backlog_path_refused_origin_keeps_backlog`
- `test_bytes_preserved_crlf_not_translated`
- `test_code_tests_skills_templates_tasks_refused_with_named_text`
- `test_config_path_gets_config_prefix_docs_path_gets_docs_prefix`
- `test_content_lands_in_origin_output_names_sha_main_copy_untouched`
- `test_dirty_work_tree_is_forced_to_origin_before_the_next_record`
- `test_doc_commit_flush_sends_both_kinds`
- `test_docs_path_accept_red_writes_no_bypass_journal_row`
- `test_docs_path_does_not_run_the_suite_at_all`
- `test_docs_paths_and_operator_config_are_allowed`
- `test_empty_pending_says_so`
- `test_explicit_flush_warns_about_missing_base_of_config_record`
- `test_flush_does_not_need_source_file_anymore`
- `test_flush_ignores_open_window_but_new_record_is_still_held`
- `test_foreign_path_refused_without_commit_or_hold`
- `test_green_suite_lets_the_commit_through`
- `test_green_suite_with_accept_red_still_journals_the_bypass`
- `test_half_written_record_does_not_become_batch_head_for_next`
- `test_help_text_names_doc_commit`
- `test_identical_content_refused_instead_of_hanging_in_pending`
- `test_leftover_file_in_the_work_tree_is_not_read_as_origin_content`
- `test_missing_message_refused_without_commit_or_hold`
- `test_missing_or_absent_source_file_refused`
- `test_multiline_content_stays_one_line_and_truncated`
- `test_network_hold_stores_head_blob`
- `test_new_path_absent_everywhere_is_committed`
- `test_no_journal_row_for_doc_commit`
- `test_note_flush_sends_both_kinds`
- `test_note_hold_texts_unchanged`
- `test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change`
- `test_open_window_holds_json_with_kind_and_flush_after_close_pushes`
- `test_open_window_holds_the_record_and_the_gate_fires_on_flush`
- `test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks`
- `test_opportunistic_flush_still_skips_config_record_silently_on_base`
- `test_origin_diverged_from_pin_refuses_naming_pin_update`
- `test_path_added_in_origin_after_pin_refuses`
- `test_prefix_by_path_kind_without_truncation`
- `test_red_suite_refuses_naming_the_failed_test`
- `test_repeat_after_fixing_the_suite_commits_the_same_change`
- `test_role_environment_markers_from_env_are_honoured`
- `test_role_environment_refused_before_work_repo_exists`
- `test_suite_runs_on_the_tree_with_the_change_already_applied`
- `test_target_rel_is_own_path_for_doc_commit_and_backlog_for_note`
- `test_unknown_or_traversal_id_refuses_without_removal`
- `test_unrunnable_suite_refuses_the_same_way`
- `unit_box`
- `valid_text`
- `via_command`
- `via_content`
- `word`
- `words`
- `work_status`
- `write_pending`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/knowledge_cards.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_epic_draft_promote_unsupported_project.py

**Назначение:** `epic draft promote` черновика эпика неподдержанного проекта (`forge: gitlab` или `merge_gate: target-human`) отказывает причиной `targets.unsupported_reason`: проверка стоит в `catalog.cmd_new`, а не в CLI-обёртке `new`, и путь черновика её не обходит (SPEC 01M5W27CY7K7NR9347NKD8F0NX, требование 3; решение гейта SPEC).

**Публичные функции:**
- `cli`
- `declare`
- `table`
- `test_draft_promote_of_unsupported_project_refuses`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/epics.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_epic_drafts_units.py

**Назначение:** Черновики эпика: свойства вне долгоживущих файлов задачи

**Публичные функции:**
- `cli`
- `test_ci_script_epic_prefix_matches_config`
- `test_data_line_round_trips_and_keeps_comment_closed`
- `test_draft_edit_refuses_self_reference`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/epics.py`, `orchestrator/store.py`, `scripts/plan_appendix_ci.py`

**Импортируется:** —

## tests/test_epic_ref_scan_filters.py

**Назначение:** Фильтр ссылки эпика `refs/artifacts/epic-<id>` в местах перебора ссылок

**Публичные функции:**
- `test_cleanup_execute_keeps_branch_backed_only_by_epic_ref`
- `test_doctor_origin_refs_skip_epic_ref`
- `test_history_snapshots_epic_ref_is_no_docs_ref_of_dir`

**Импортирует:** `orchestrator/config.py`, `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`

**Импортируется:** —

## tests/test_epic_supervisor_units.py

**Назначение:** Юнит-тесты надзора эпика `auto --epic` (SPEC 01M5TBF7JRZ6FGRR4K53KPAJDS)

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_epics_board_units.py

**Назначение:** Юнит-тесты эпиков и модели доски вне долгоживущих файлов задачи

**Публичные функции:**
- `test_epic_order_keeps_tasks_of_a_dependency_cycle`
- `test_epics_migration_on_steps_without_target_and_session`

**Импортирует:** `orchestrator/board.py`, `orchestrator/config.py`, `orchestrator/schema.py`

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

## tests/test_fixtures_plugin_conditional.py

**Назначение:** Условное подключение `tests.fixtures` корневым `conftest.py` (ADR-0027,

**Публичные функции:**
- `mirror_conftest`
- `test_mirror_collects_with_and_without_fixtures_module`

**Импортирует:** —

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

## tests/test_gitcmd_push_point.py

**Назначение:** Единая точка отправки `gitcmd` (SPEC 01M5WDB7F14SQ30QVWJY2XYBG2, требование 3): белый список проекта не `operator`, журнал «ветка отправлена», опции `policy.push_options`.

**Публичные функции:**
- `git_in`
- `project`
- `sent`
- `spy`
- `task`
- `test_operator_push_gets_options_and_record`
- `test_whitelist_lease_checked_against_last_sent_sha`
- `test_whitelist_refuses_base_push_with_alert`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/repo_context.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_gitcmd_reads.py

**Назначение:** Чтения git со сроком, своим окружением и потоком: `gitcmd.read`,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/gitcmd.py`

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

## tests/test_guard_pytest_fixtures.py

**Назначение:** Разрешение фикстур pytest в разборе утверждений guard и отказы стиля —

**Публичные функции:**
- `helpers_source`
- `multiset`
- `records`
- `records_with_helpers`
- `test_class_fixture_shadows_module_fixture_for_its_methods`
- `test_fixture_helper_imported_from_other_tests_module_is_traced`
- `test_indirect_in_module_pytestmark_refused_at_module_address`
- `test_indirect_parametrize_name_stays_a_fixture`
- `test_own_fixture_overriding_shared_one_traces_the_shared`
- `test_weakened_helpers_names_fixture_requesting_changed_fixture`
- `test_weakened_helpers_names_module_function_with_changed_literal`

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

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/artel.py`, `orchestrator/artifact_branch.py`, `orchestrator/board.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/epics.py`, `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitcmd.py`, `orchestrator/idgen.py`, `orchestrator/merge_after.py`, `orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/test_lint.py`, `scripts/guard.py`, `tests/sandbox.py`, `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`, `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`, `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`

**Импортируется:** `tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py`, `tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_review_registry_gate.py`, `tests/test_verifying_ceiling.py`

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

## tests/test_merge_after_module.py

**Назначение:** Тесты `orchestrator/merge_after.py` и его опор: зависимости мержа

**Публичные функции:**
- `answer_accepted`
- `answer_answers`
- `answer_assert_refused`
- `answer_deps`
- `answer_element`
- `answer_insert`
- `answer_journal_since`
- `answer_last_step_id`
- `answer_mandate_line`
- `answer_note`
- `answer_role_env`
- `answer_run_answer`
- `answer_set_state`
- `answer_stand`
- `answer_unique_prefix`
- `declared_insert`
- `declared_path_note`
- `declared_path_stand`
- `declared_task`
- `divide`
- `division_sandbox`
- `division_spec`
- `division_stand`
- `guard_element`
- `guard_field_errors`
- `guard_note`
- `guard_stand`
- `ids_of`
- `journal`
- `live_task`
- `loss_stand`
- `merge_after_db_insert`
- `merge_after_stand`
- `meta_of`
- `msg`
- `new_declares_all_ids`
- `new_declares_assert_refused_without_traces`
- `new_declares_declared`
- `new_declares_deps`
- `new_declares_element`
- `new_declares_insert`
- `new_declares_journal`
- `new_declares_live_task`
- `new_declares_missing_id`
- `new_declares_note`
- `new_declares_run_new`
- `new_declares_set_state`
- `new_declares_stand`
- `new_declares_status_line`
- `new_declares_suffix`
- `new_declares_tz`
- `new_declares_unique_prefix`
- `new_task`
- `no_code_tree`
- `plan_advance_with_plan`
- `plan_approve_spec`
- `plan_branch_not_behind`
- `plan_deps`
- `plan_element`
- `plan_field_line`
- `plan_journal_since`
- `plan_last_step_id`
- `plan_new_task`
- `plan_note`
- `plan_prepared_task`
- `plan_rejected_case`
- `plan_set_task_state`
- `plan_stand`
- `plan_state_of`
- `plan_unique_prefix`
- `plan_write_doc`
- `refusal`
- `run_cmd`
- `set_deps`
- `spec_gate_all_ids`
- `spec_gate_approve_spec`
- `spec_gate_assert_refused`
- `spec_gate_declared_refusal_spec_text`
- `spec_gate_deps`
- `spec_gate_element`
- `spec_gate_insert`
- `spec_gate_journal_since`
- `spec_gate_last_step_id`
- `spec_gate_new_task`
- `spec_gate_note`
- `spec_gate_row`
- `spec_gate_set_task_state`
- `spec_gate_stand`
- `spec_gate_unique_prefix`
- `spec_gate_write_spec`
- `spec_text`
- `status_show_dependency_scenario`
- `status_show_element`
- `status_show_new_task`
- `status_show_note`
- `status_show_set_state`
- `status_show_stand`
- `status_show_status_line`
- `status_show_wait_suffix`
- `status_show_with_dependencies`
- `stored_deps`
- `task`
- `test_ac10_rejected_plan_value_keeps_db_and_transition`
- `test_ac11_escalated_answer_sets_and_clears_value`
- `test_ac11_merge_gate_answer_outside_role_env_accepted`
- `test_ac12_invalid_mandate_element_refused_before_commit`
- `test_ac12_merge_gate_without_line_or_from_role_env_refused`
- `test_ac13_no_suffix_in_other_state`
- `test_ac13_no_suffix_without_field_or_all_done`
- `test_ac13_status_suffix_lists_unfinished_and_disappears_after_done`
- `test_ac14_show_lists_all_dependencies_with_states`
- `test_ac14_show_without_dependencies_has_no_line`
- `test_ac1_element_not_in_task_id_format_is_a_form_error`
- `test_ac1_order_line_declares_full_ids_in_line_order`
- `test_ac1_parent_replaced_by_last_subtask_in_every_dependent`
- `test_ac1_repeated_element_is_a_repeat_error`
- `test_ac1_self_reference_names_field_and_element`
- `test_ac1_valid_list_and_missing_field_pass`
- `test_ac2_ambiguous_prefix_keeps_spec_gate_and_column_empty`
- `test_ac2_dependent_journal_names_old_and_new_value`
- `test_ac2_list_ends_at_parenthesis_or_dot`
- `test_ac2_missing_task_keeps_spec_gate_and_column_empty`
- `test_ac3_dependency_of_other_target_refused`
- `test_ac3_killed_dependency_refused`
- `test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent`
- `test_ac3_order_line_without_after_declares_nothing`
- `test_ac3_prefix_resolving_to_own_id_refused`
- `test_ac4_cycle_through_existing_values_refused`
- `test_ac4_unparsed_element_refused_without_traces`
- `test_ac5_prefixes_written_as_full_ids_in_spec_order`
- `test_ac5_repeated_order_line_refused_without_traces`
- `test_ac5_spec_without_field_leaves_column_empty`
- `test_ac6_invalid_dependency_refused_without_traces`
- `test_ac7_path_refusal_and_order_refusal_printed_together`
- `test_ac8_loss_refusal_leads_through_reject_and_escalated_answer`
- `test_ac8_status_and_show_carry_declared_dependencies`
- `test_ac9_empty_plan_value_clears_dependencies`
- `test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged`
- `test_ac9_justified_plan_value_replaces_db_value`
- `test_ac9_plan_without_field_keeps_db_value`
- `test_dependency_missing_from_db_refuses_with_answer_channel`
- `test_done_dependency_is_valid`
- `test_empty_list_is_refused`
- `test_exact_match_wins_over_longer_ids_with_same_prefix`
- `test_explicit_target_of_new_task_is_used`
- `test_form_accepts_ids_prefixes_and_legacy_rejects_rest`
- `test_label_must_start_line_and_word_must_be_whole`
- `test_migrate_adds_merge_after_to_old_tasks_table`
- `test_no_check_after_spec_gate_was_passed`
- `test_none_word_mixed_with_ids_refused`
- `test_plan_value_equal_to_db_after_resolution_is_silent`
- `test_prefix_and_full_id_of_same_task_is_a_repeat`
- `test_short_prefix_inside_other_id_is_not_justification`
- `test_task_not_depending_on_parent_is_untouched`
- `test_two_mandate_lines_refused`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/answer.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/idgen.py`, `orchestrator/merge_after.py`, `orchestrator/schema.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/fixtures.py`, `tests/sandbox.py`

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

## tests/test_merge_lock_module.py

**Назначение:** Тесты `orchestrator/merge_lock.py`: мьютекс merge-окна (SPEC T053),

**Публичные функции:**
- `acquire_release_seed`
- `assert_fresh`
- `clear`
- `foreign_pid`
- `live_holder`
- `lock_row`
- `lock_stand`
- `locks`
- `msg`
- `new_project`
- `new_task`
- `ownership_stand`
- `process_ownership_seed`
- `project_mutex_actions`
- `project_mutex_new_task`
- `project_mutex_seed_lock`
- `project_mutex_stand`
- `project_pairs`
- `project_stand`
- `race_stand`
- `refusal_pattern`
- `seed_lock`
- `session`
- `test_ac11_set_merge_lock_keeps_other_project_row`
- `test_ac16_artel_holder_excludes_empty_null_and_missing_target`
- `test_ac16_empty_or_null_target_holder_excludes_artel_task`
- `test_ac17_touch_heartbeat_without_args_keeps_old_behaviour`
- `test_ac1_other_project_holder_does_not_block_acquire`
- `test_ac3_live_holder_of_same_project_refuses_with_old_text`
- `test_ac4_dead_holder_of_other_project_is_left_intact`
- `test_ac4_dead_holder_of_same_project_is_taken_over`
- `test_ac5_release_removes_only_own_process_row`
- `test_ac6_touch_heartbeat_renews_only_callers_project_row`
- `test_ac7_touch_heartbeat_does_not_renew_intercepted_row`
- `test_concurrent_acquire_on_free_lock_exactly_one_wins`
- `test_dead_process_of_own_session_is_intercepted_and_journalled`
- `test_foreign_dead_pid_on_a_different_host_is_not_taken_over`
- `test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat`
- `test_foreign_fresh_lock_refuses_and_names_holder_and_task`
- `test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled`
- `test_fresh_acquire_on_empty_table_takes_the_lock`
- `test_live_other_process_of_same_session_is_refused_with_holder_pid`
- `test_mutex_is_released_even_when_the_body_raises`
- `test_no_args_with_several_projects_renews_only_current_session`
- `test_own_process_re_enters_and_refreshes_the_row`
- `test_own_session_re_enters_without_refusal`
- `test_refusal_exits_without_running_the_body`
- `test_refusal_text_for_own_session_equals_foreign_session_text`
- `test_release_from_holder_process_removes_the_mutex`
- `test_release_from_non_holder_process_keeps_the_mutex`
- `test_release_removes_only_the_matching_session`
- `test_store_release_merge_lock_requires_both_session_and_pid`
- `test_success_runs_body_and_releases_the_mutex_afterwards`
- `token`

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/merge_lock.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_merge_outcome_module.py

**Назначение:** Тесты гейта неослабления по исходам на гейте мержа: доказательство для

**Публичные функции:**
- `box`
- `no_gate_refusal`
- `test_ac10_component_without_python_has_section_except_canary`
- `test_ac11_only_check_failure_is_failure_on_check`
- `test_ac12_passed_with_retry_is_side_failure_retry`
- `test_ac13_retried_on_base_rerun_is_red_base`
- `test_ac14_test_profile_and_multi_component_keep_prior_results`
- `test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record`
- `test_ac1_passed_record_carries_head_base_key_and_mandate`
- `test_ac2_finding_without_mandate_escalates_merge`
- `test_ac2_merge_refusal_action_is_operator_class_key`
- `test_ac3_prepare_failures_keep_merge_gate_without_push`
- `test_ac4_same_quadruple_proves_without_run`
- `test_ac5_other_base_key_or_mandate_runs_gate`
- `test_ac6_record_without_proof_line_runs_gate`
- `test_ac7_base_is_merge_base_with_fetched_main_not_diff_base`
- `test_ac7_canary_from_db_and_in_dev_base_is_diff_base`
- `test_ac7_doc_only_lag_runs_gate_with_merge_base`
- `test_ac7_gate_after_fresh_and_before_acceptance_locks`
- `test_ac8_review_section_carries_outcome_gate_lines_for_head`
- `test_ac9_no_record_for_current_head_says_not_run`
- `two_sided_box`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/refusal_classes.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/store.py`, `tests/fixtures.py`, `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`

**Импортируется:** —

## tests/test_merge_queue.py

**Назначение:** Тесты `orchestrator/merge_queue.py`: очередь FIFO ожидания мьютекса

**Публичные функции:**
- `clear`
- `enqueue`
- `foreign_pid`
- `live_holder`
- `locks`
- `msg`
- `new_project`
- `new_task`
- `project_mutex_actions`
- `project_mutex_enqueue`
- `project_mutex_new_task`
- `project_mutex_seed_lock`
- `project_mutex_stand`
- `project_pairs`
- `project_stand`
- `queue_stand`
- `queue_task_ids`
- `refusal_pattern`
- `rows_by_pid`
- `run_wait`
- `seed_lock`
- `session`
- `test_ac10_single_project_texts_are_unchanged`
- `test_ac10_wait_texts_name_holder_of_waiting_task_project`
- `test_ac2_other_project_holder_does_not_delay_wait_for_window`
- `test_ac8_head_is_earliest_entry_of_own_project`
- `test_ac8_same_project_tasks_enter_in_fifo_order`
- `test_ac9_dead_entry_of_project_does_not_hold_its_head`
- `test_ceiling_expiry_dequeues_and_exits_without_touching_state`
- `test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it`
- `test_dead_pid_on_own_host_is_pruned`
- `test_dequeue_removes_only_the_row_of_that_process`
- `test_earlier_entry_of_other_project_does_not_delay_entry`
- `test_empty_queue_has_no_head`
- `test_free_mutex_registers_then_immediately_takes_the_window`
- `test_head_is_earliest_by_enqueued_ts`
- `test_label_names_task_and_pid_of_the_holder`
- `test_live_entry_survives_pruning`
- `test_names_the_holder_task`
- `test_no_holder_degrades_to_placeholder`
- `test_no_holder_degrades_to_the_same_placeholder`
- `test_non_head_process_of_the_same_session_does_not_take_the_window`
- `test_not_queued_returns_none_and_empty_suffix`
- `test_queue_entry_journal_names_the_holder_pid`
- `test_queued_reports_minutes_waited_and_the_current_holder`
- `test_stale_heartbeat_on_foreign_host_is_pruned`
- `test_texts_name_own_project_holder_in_every_insertion_order`
- `test_touch_heartbeat_updates_only_the_row_of_that_process`
- `test_two_processes_of_one_session_live_as_two_rows_in_fifo_order`
- `token`
- `wait_texts`

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

## tests/test_notes_module.py

**Назначение:** Тесты `orchestrator/notes.py`: копилка и бэклог `note`, окно тишины,

**Публичные функции:**
- `appended_cell`
- `apply_box`
- `apply_draft`
- `assert_pushed`
- `cells`
- `draft_refusal`
- `draft_with_extra_row`
- `draft_without_dropped_rows`
- `held_reason`
- `insert_project_task`
- `insert_task_in_state`
- `inserted_row`
- `journal_text`
- `live_lock`
- `main_copy_snapshot`
- `no_role`
- `open_silence_window`
- `origin_backlog`
- `origin_commit_count`
- `origin_head`
- `origin_message`
- `origin_run`
- `push_foreign_backlog_change`
- `refusal`
- `schema_root`
- `set_live_merge_lock`
- `set_state`
- `silence_box`
- `silence_origin_backlog`
- `source_file`
- `task_id`
- `test_append_multiple_matches_refuses_without_changing_text`
- `test_append_unique_key_appends_to_last_column_only`
- `test_append_zero_matches_refuses_without_changing_text`
- `test_apply_document_changed_in_origin_past_the_base_refuses`
- `test_apply_draft_becomes_the_document_in_one_commit`
- `test_apply_draft_equal_to_origin_refuses_instead_of_hanging_in_pending`
- `test_apply_draft_with_section_heading_but_no_table_refuses`
- `test_apply_draft_with_widened_header_refuses`
- `test_apply_draft_without_a_section_refuses_before_commit`
- `test_apply_held_record_is_self_sufficient_without_the_source_file`
- `test_apply_journal_names_dropped_row_count_and_truncated_rows`
- `test_apply_missing_message_and_missing_file_refuse_naming_the_flag`
- `test_apply_open_window_holds_apply_until_flush`
- `test_apply_origin_changed_while_the_record_was_held_refuses_on_flush`
- `test_apply_own_note_commit_past_the_pin_does_not_block_apply`
- `test_apply_untouched_draft_counts_zero_dropped_rows`
- `test_check_pending_notes_ok_when_nothing_pending`
- `test_check_pending_notes_warn_when_something_pending`
- `test_cmd_note_append_without_text_refuses`
- `test_cmd_note_flush_with_nothing_pending_is_a_noop`
- `test_cmd_note_no_arguments_at_all_refuses`
- `test_cmd_note_role_refuses_every_form_before_parsing`
- `test_cmd_note_section_without_text_refuses`
- `test_cmd_note_set_priority_without_text_refuses`
- `test_cmd_note_set_state_without_text_refuses`
- `test_drop_multiple_matches_refuses_without_changing_text`
- `test_drop_removes_matched_row_only_neighbours_untouched`
- `test_drop_zero_matches_refuses_without_changing_text`
- `test_insert_column_count_mismatch_refuses_naming_expected_count`
- `test_insert_right_after_separator`
- `test_insert_unknown_section_heading_refuses`
- `test_notes_module_declares_no_rudiment_exception`
- `test_pending_notes_empty_by_default`
- `test_pending_notes_hold_then_read_back_round_trips`
- `test_pending_notes_two_holds_are_both_visible`
- `test_project_ac1_external_task_in_every_window_state_does_not_hold`
- `test_project_ac2_live_holder_with_external_task_does_not_hold`
- `test_project_ac3_artel_task_in_every_window_state_holds_with_old_text`
- `test_project_ac3_live_holder_with_artel_task_holds_with_old_text`
- `test_project_ac3a_external_holder_does_not_mask_artel_task`
- `test_project_ac3b_earlier_external_task_does_not_mask_artel_task`
- `test_project_ac4_unresolved_project_holds_naming_task_and_reason`
- `test_project_ac5_unresolved_project_outside_window_does_not_hold`
- `test_row_cell_count_is_checked_after_unframing`
- `test_row_cells_strips_outer_pipes_and_whitespace`
- `test_row_date_shaped_cell_of_another_column_is_untouched`
- `test_row_empty_and_dash_cells_get_no_leading_separator`
- `test_row_filled_cell_keeps_old_text_and_gets_dated_separator`
- `test_row_framed_and_bare_text_give_the_same_row`
- `test_row_letter_and_digit_forms_both_give_the_digit`
- `test_row_second_append_keeps_the_first_one_whole`
- `test_row_section_without_priority_column_is_not_normalized`
- `test_row_set_priority_both_forms_write_the_digit`
- `test_row_set_priority_range_is_not_widened_by_the_letter_form`
- `test_row_set_priority_section_without_priority_column_refuses_instead_of_cell_zero`
- `test_row_single_leading_pipe_is_not_treated_as_framing`
- `test_row_state_and_append_build_the_same_request`
- `test_row_state_without_text_refuses_naming_the_flag_that_was_used`
- `test_row_unrecognized_priority_refuses_naming_a_valid_form`
- `test_row_year_is_dropped_short_form_and_non_dates_survive`
- `test_set_priority_non_numeric_value_refuses_without_changing_text`
- `test_set_priority_replaces_first_column_with_valid_value`
- `test_set_priority_value_above_range_refuses_without_changing_text`
- `test_set_priority_value_below_range_refuses_without_changing_text`
- `test_set_state_multiple_matches_refuses_without_changing_text`
- `test_set_state_replaces_last_column_entirely_not_appends`
- `test_silence_ac1_live_merge_lock_alone_without_any_task_state_opens_window`
- `test_silence_artel_task_and_holder_not_resolved_through_targets`
- `test_silence_dead_merge_lock_holder_does_not_open_window`
- `test_silence_escalated_state_does_not_open_window`
- `test_silence_no_holder_and_no_task_in_set_closes_window`
- `test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev`
- `test_window_ac3_hold_message_prefix_and_suffix`
- `test_window_ac4_unmatched_key_refuses_before_hold_even_with_window_open`
- `test_window_ac5_no_window_pushes_immediately_unchanged`
- `test_window_ac6_flush_pushes_held_note_while_window_stays_open`
- `test_window_ac7_now_pushes_immediately_and_does_not_hold`
- `test_window_ac8_closed_window_still_flushes_previously_held_note`
- `test_window_ac8_open_window_leaves_previously_held_note_untouched`
- `test_window_ac9_held_note_uses_existing_pending_json_shape`
- `token`
- `window_box`
- `window_note`
- `window_origin_backlog`

**Импортирует:** `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_outcome_components_module.py

**Назначение:** Тесты гейта исходов у записи из нескольких компонентов: компоненты по

**Публичные функции:**
- `box`
- `broken_consumer`
- `foreign_box`
- `mandate_answer`
- `review_section`
- `test_ac13_path_mandate_on_consumer_lifts_finding`
- `test_ac14_id_mandate_on_consumer_lifts_finding`
- `test_ac16_component_change_runs_only_its_component`
- `test_ac16_diff_read_failure_refuses_preparation`
- `test_ac17_all_out_of_bounds_skip_record_and_review_lines`
- `test_ac17_first_refusal_names_component`
- `test_ac17_out_of_bounds_component_line`
- `test_ac18_out_of_bounds_task_shows_consumer_lines`
- `test_ac18_package_shows_consumer_records`
- `test_ac19_foreign_file_in_bounds_refused`
- `test_ac19_task_out_of_bounds_still_refused`
- `test_ac22_in_dev_outcome_gate_by_frontend`
- `test_ac22_merge_gate_outcome_by_frontend`
- `test_ac22_tests_writing_exit_by_frontend_rule`
- `test_ac23_seed_change_runs_both_components`
- `test_ac25_backend_file_on_frontend_task`
- `test_ac27_foreign_out_of_bounds_not_checked`

**Импортирует:** `orchestrator/advance_gates/mandate.py`, `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/answer.py`, `orchestrator/project_profile.py`, `orchestrator/review.py`, `tests/components_outcome_sandbox.py`, `tests/fixtures.py`, `tests/outcome_gate_sandbox.py`

**Импортируется:** —

## tests/test_outcome_gate_module.py

**Назначение:** Тесты гейта неослабления по исходам `orchestrator/advance_gates/outcome_integrity.py`

**Публичные функции:**
- `added_repo`
- `arg_value`
- `assert_no_gate`
- `assert_prepare`
- `box`
- `broken_task`
- `commit`
- `files`
- `flow`
- `gate_refusal`
- `git`
- `id_box`
- `id_no_gate_refusal`
- `id_spec_text`
- `js_names`
- `js_source`
- `junit`
- `no_gate_refusal`
- `prepared`
- `refusal`
- `test_ac10_findings_order_and_one_line_each`
- `test_ac11_class_prefix_mandate_covers`
- `test_ac11_file_and_prefix_mandate_cover_findings`
- `test_ac11_method_prefix_mandate_covers_variants`
- `test_ac11_other_file_mandate_does_not_cover`
- `test_ac11_prefix_needs_separator_after_it`
- `test_ac11_role_autocommitted_answer_does_not_cover`
- `test_ac11_role_autocommitted_id_mandate_does_not_cover`
- `test_ac12_exact_id_with_n_covers_other_variant_does_not`
- `test_ac13_passed_gate_journal_counts`
- `test_ac13_refusal_hint_names_both_markers`
- `test_ac1_artel_and_test_profile_no_gate`
- `test_ac1_decide_skip_refusal_and_canary_no_gate`
- `test_ac2_outcome_refusal_stops_before_review_rework_gate`
- `test_ac2_text_gate_refusal_first_no_outcome_runs`
- `test_ac3_full_suite_on_base_and_head_checkouts_fresh`
- `test_ac4_git_base_checkout_failure_refuses`
- `test_ac4_git_head_checkout_failure_refuses`
- `test_ac4_git_head_not_read_refuses`
- `test_ac4_git_preparation_failures_refuse`
- `test_ac4_side_base_timeout_refuses_naming_base`
- `test_ac4_side_head_timeout_refuses_naming_head`
- `test_ac4_side_head_unknown_refuses_naming_head`
- `test_ac4_side_not_started_or_timeout_refuses_naming_side`
- `test_ac5_no_tests_on_base_empty_pass_to_pass`
- `test_ac5_retried_on_base_not_in_pass_to_pass`
- `test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit`
- `test_ac6_skipped_on_branch_not_rerun`
- `test_ac7_branch_rerun_error_is_red`
- `test_ac7_branch_rerun_missing_is_red`
- `test_ac7_branch_rerun_red_kinds`
- `test_ac7_branch_rerun_retried_is_red`
- `test_ac7_branch_rerun_skipped_is_red`
- `test_ac7_rerun_base_record_missing_refuses`
- `test_ac7_rerun_base_skipped_refuses`
- `test_ac7_rerun_preparation_refusals`
- `test_ac7_rerun_timeout_refuses`
- `test_ac7_rerun_unknown_outcome_refuses`
- `test_ac8_broken_unstable_and_flaky_on_base`
- `test_ac8_flaky_on_base_no_refusal`
- `test_ac8_neighbour_red_in_same_file_does_not_redden_rerun`
- `test_ac8_unstable_after_change_general_refusal`
- `test_ac9_junit_records_findings`
- `test_ac9_one_finding_per_id_senior_kind`
- `test_ac9_vitest_records_findings_and_non_findings`
- `test_compare_junit_became_skipped_from_each_outcome`
- `test_compare_vitest_findings_and_non_findings`
- `test_covered_ids_round_trip_every_finding_kind`
- `test_deleted_file_header_dev_null_is_not_refusal`
- `test_fingerprint_sorted_unique_or_none`
- `test_mandate_prefix_needs_separator`
- `test_noprefix_config_does_not_hide_added_lines`
- `test_quoted_path_latin1_text_and_no_final_newline`
- `test_red_on_branch_kinds`
- `test_rename_between_test_paths_is_not_checked`
- `test_rename_from_test_path_to_code_path_is_checked`
- `test_retried_pass_on_base_not_in_pass_to_pass`
- `test_skip_growth_line`
- `test_unexpected_header_is_prepare_refusal`
- `ulid`
- `vitest`

**Импортирует:** `orchestrator/advance_gates/outcome_integrity.py`, `orchestrator/answer.py`, `orchestrator/checkpoint.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/github_adapter.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/fixtures.py`, `tests/outcome_gate_sandbox.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_outcome_prior_module.py

**Назначение:** Тесты гейта неослабления по исходам G3б-2 на стенде `PriorSandbox`:

**Публичные функции:**
- `box`
- `conftest_case`
- `grant`
- `no_gate_refusal`
- `passed`
- `refusal`
- `test_ac10_empty_set_no_third_checkout`
- `test_ac11_third_checkout_failure_refuses_prepare`
- `test_ac11_third_run_failure_refuses_prepare`
- `test_ac12_diff_failures_refuse_prepare`
- `test_ac13_third_checkout_in_scratch_with_marker_and_removed`
- `test_ac30_test_profile_no_outcome_gate`
- `test_ac32_added_conftest_under_scope_without_tests_removed`
- `test_ac32_added_conftest_under_test_support_removed`
- `test_ac32_added_conftest_under_tests_masks_removed`
- `test_ac33_prior_skipped_or_missing_is_red`
- `test_ac3_green_prior_version_passes_with_prior_line`
- `test_ac4_prior_red_thrice_refuses_outcome`
- `test_ac5_prior_mixed_is_unstable_finding`
- `test_ac5_red_base_rerun_is_flaky_line_not_finding`
- `test_ac6_old_kind_finding_wins_single_line`
- `test_ac7_test_support_change_runs_full_suite`
- `test_ac7_tests_change_runs_only_changed_files`
- `test_ac8_deleted_file_restored_and_judged`
- `test_ac8_renamed_file_old_path_restored_new_stays`
- `test_ac8_type_changed_file_in_set`
- `test_ac9_changed_base_file_and_file_level_record_in_set`
- `test_ac9_code_only_and_new_file_no_third_checkout`

**Импортирует:** `tests/fixtures.py`, `tests/outcome_gate_sandbox.py`, `tests/prior_outcome_sandbox.py`

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

## tests/test_report_outcome_module.py

**Назначение:** Итог тестов компонента из отчёта: `junit-xml`, отчётчик пульта `pult-vitest`, окружение и установка пультом, сторож зависших тестов; прежний разбор у артели.

**Публичные функции:**
- `approve`
- `artel_unchanged_channels`
- `assert_unknown`
- `box`
- `check`
- `check_script`
- `checked_case`
- `checks_stand`
- `install_and_deps_full_vitest`
- `journal`
- `key_case`
- `main_head`
- `merge`
- `profile`
- `pytest_output`
- `selected`
- `suite`
- `test_ac10_preparation_refusals_command_and_report_args`
- `test_ac10_subset_by_select_and_refusal_without_select`
- `test_ac11_unknown_is_never_green_at_any_place`
- `test_ac12_suite_run_no_report_non_pytest_refusal_as_main`
- `test_ac15_install_once_per_lock_content_from_task_branch`
- `test_ac15_install_without_lock_and_failed_install_refuse`
- `test_ac16_node_modules_read_only_shared_and_substitution_refused`
- `test_ac18_component_key_follows_tools_lock_command_name_and_artel_key_is_main`
- `test_ac19_watchdog_knows_component_commands_only`
- `test_ac1_outcome_follows_report_not_runner_output`
- `test_ac20_constants_and_texts_as_main`
- `test_ac20_parsing_digest_journal_and_suite_run_lines_as_main`
- `test_ac2_empty_or_unreadable_report_is_unknown`
- `test_ac2_per_test_record_id_from_repo_root_outcome_kind_reason_time`
- `test_ac3_report_path_outside_tree_workdir_and_clean_env`
- `test_ac4_ac6_pult_pytest_argv_and_outcome_as_main`
- `test_ac4_ac6_sled_record_default_report_args_outcome_from_report`
- `test_ac4_explicit_report_args_win_over_default`
- `test_ac5_unknown_outcome_form_and_log`
- `test_ac6_pult_pytest_and_no_report_records_by_code_and_text`
- `test_ac6_vitest_component_without_runner_outcome_from_report`
- `test_ac7_failure_kinds_assertion_type_timeout_hook`
- `test_ac8_modes_fails_todo_skip_only_and_retries`
- `test_ac9_run_conditions_argv_env_cache_and_flags`
- `test_ac9_timeout_kills_group_not_green`
- `test_ac9_version_refusals_require_assertions_and_unconfirmed_cache`
- `test_accept_red_refuses_unknown_even_with_failing_check`
- `test_check_runs_after_any_source_and_reddens_only_green`
- `test_components_chosen_by_branch_diff_and_appendix_paths`
- `test_each_component_runs_with_its_own_limit`
- `test_empty_install_neither_installs_nor_refuses`
- `test_failing_check_keeps_unknown_outcome_on_both_paths`
- `test_failures_of_reported_output_come_only_from_report`
- `test_merge_gate_and_suite_run_keys_match_with_tools`
- `test_merge_gate_without_appendices_runs_record_checks_local`
- `test_parallel_first_installs_run_once_without_refusal`
- `test_pytest_args_only_for_pytest_command`
- `test_record_checks_local_runs_in_acceptance_suite`
- `test_vitest_component_with_workdir_gets_exact_pult_argv`
- `two_components`
- `vitest_reporter_full_vitest`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/project_profile.py`, `orchestrator/reporters/outcome.py`, `orchestrator/stack.py`, `orchestrator/store.py`, `orchestrator/suite_run.py`, `tests/fd_wait.py`, `tests/fixtures.py`, `tests/report_outcome_sandbox.py`, `tests/sandbox.py`

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

**Импортируется:** `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`

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

## tests/test_start_after_units.py

**Назначение:** Зависимость запуска `start_after`: запись каналом `new --start-after`,

**Публичные функции:**
- `add_task`
- `cli`
- `sandbox`
- `test_epic_start_after_none_clears_value`
- `test_new_start_after_records_value_with_journal`
- `test_start_after_blocks_only_before_first_step`
- `test_start_after_refusal_names_its_channel`

**Импортирует:** `orchestrator/artel.py`, `orchestrator/config.py`, `orchestrator/merge_after.py`, `orchestrator/store.py`

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

## tests/test_suite_durations.py

**Назначение:** Блок «самые медленные» `suite_durations.slowest_block` меньше среза.

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/suite_durations.py`

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

## tests/test_workspace_wrapper_excludes.py

**Назначение:** Свой игнор рабочей копии без обвязки (`core.excludesFile` её

**Публичные функции:**
- `sb`
- `test_global_ignore_survives_own_excludes_file`
- `test_unresolved_entry_excludes_standard_markers_without_refusal`

**Импортирует:** `orchestrator/config.py`, `orchestrator/idgen.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

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
