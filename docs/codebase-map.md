---
built_at_sha: 35af54d49f180411032c9809461c060f86762c3c
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
- `run`
- `run_full_suite`
- `summary`

**Импортирует:** `orchestrator/config.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_acceptance.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_branch_freshness_gate.py`, `tests/test_fsm_map_conflict_autoresolve.py`

## orchestrator/agent_log.py

**Назначение:** Наблюдаемость шага: файлы логов прогонов и перекачка вывода агента.

**Публичные функции:**
- `last_agent_log`
- `log_tail`
- `new_agent_log`
- `render_agent_line`
- `render_block`
- `stream_to_log`
- `tee_lines`

**Импортирует:** `orchestrator/config.py`, `orchestrator/spend.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_auto_cycle.py`, `tests/test_kill_cleanup.py`, `tests/test_pause_now.py`, `tests/test_step_cost.py`

## orchestrator/alerts.py

**Назначение:** Таблица alerts: несущий носитель порогов/инцидентов/триггеров (A3,

**Публичные функции:**
- `ack`
- `auto_ack`
- `open_alerts`
- `raise_alert`

**Импортирует:** `orchestrator/store.py`

**Импортируется:** `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/doctor.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`, `tests/test_prune.py`

## orchestrator/answer.py

**Назначение:** Команда `answer`: канал ответа Оператора на эскалацию (SPEC T075).

**Публичные функции:**
- `cmd_answer`

**Импортирует:** `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_answer.py`

## orchestrator/artel.py

**Назначение:** Артель, Фаза 0 — FSM-оркестратор (CLI).

**Публичные функции:**
- `main`

**Импортирует:** `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/fsm.py`, `orchestrator/pause.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/release.py`, `orchestrator/runner.py`, `orchestrator/version.py`, `orchestrator/workspace.py`

**Импортируется:** `tests/test_analyst_role.py`, `tests/test_invariants.py`

## orchestrator/artifacts.py

**Назначение:** Чтение артефактов задачи: frontmatter и свежесть вердикта ревьювера.

**Публичные функции:**
- `fresh_verdict_iteration`
- `frontmatter`

**Импортирует:** `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `tests/test_review_freshness.py`, `tests/test_yaml_parsing.py`

## orchestrator/auto.py

**Назначение:** Цикл `auto`: run+advance, пока в шаге работает агент.

**Публичные функции:**
- `auto_stop`
- `auto_stop_advice`
- `cmd_auto`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`

## orchestrator/brief.py

**Назначение:** Бриф роли одним документом: SPEC/TZ + карта кодовой базы + конвенции

**Публичные функции:**
- `advance_refusal_history`
- `analyst_map_component`
- `component_hash`
- `developer_brief`
- `fresh_map_text`
- `test_author_answer_component`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/runner.py`, `tests/test_advance_refusal_history.py`, `tests/test_answer_branch_reads.py`, `tests/test_brief.py`

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

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/lease.py`, `orchestrator/retro.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_invariants.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_program_spend_reseed.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`

## orchestrator/canary.py

**Назначение:** Команда `canary`: синтетический прогон конвейера (tasks/T065/SPEC.md).

**Публичные функции:**
- `cmd_canary`

**Импортирует:** `orchestrator/artifacts.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

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

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_answer_gate.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_canary.py`, `tests/test_catalog_new_race.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_merge_lock.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parallel_limit.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_prune.py`, `tests/test_release.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_slugify.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_workspace.py`

## orchestrator/ci.py

**Назначение:** Статус CI головного коммита ветки задачи — условие merge (SPEC T017, 6).

**Публичные функции:**
- `branch_status`
- `check_runs`
- `check_runs_page`
- `find_run_id`
- `gh`
- `head_sha`
- `status_kind`
- `trigger_rerun`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_ci_status.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_invariants.py`

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

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/retro.py`, `tests/test_done_branch_cleanup.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget_invariants.py`, `tests/test_retro.py`

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

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/projects.py`, `orchestrator/prune.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/version.py`, `orchestrator/workspace.py`, `tests/sandbox.py`, `tests/test_acceptance.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_canary.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_ci_status.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_done_branch_cleanup.py`, `tests/test_failure_classification.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_retro.py`, `tests/test_gates.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_merge_lock.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parallel_limit.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_program_spend_reseed.py`, `tests/test_prune.py`, `tests/test_release.py`, `tests/test_retro.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_version.py`, `tests/test_workspace.py`, `tests/test_yaml_parsing.py`

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
- `check_leases`
- `check_merge_lock`
- `check_orphans`
- `check_remote_empty`
- `check_target_layout`
- `check_target_wrapper`
- `check_task_counters`
- `check_token`
- `cli_version`
- `cmd_alert_ack`
- `cmd_doctor`
- `isolation_smoke`
- `live_smoke`
- `preflight_checks`
- `recovery_check`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/liveness.py`, `orchestrator/projects.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/runner.py`, `orchestrator/version.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_version.py`

## orchestrator/fixation.py

**Назначение:** Hash-фиксация артефактов на переходах FSM (ADR-0003 п.15, п.17; tasks/T021).

**Публичные функции:**
- `check_integrity`
- `fix`
- `read`
- `refixate_after_rejected_transition`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/catalog.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/test_git_fixation.py`, `tests/test_step_autocommit.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/fsm.py

**Назначение:** Переходы автомата: advance по артефактам, approve/reject Оператора.

**Публичные функции:**
- `cmd_advance`
- `cmd_approve`
- `cmd_reject`
- `confirm_fixation`
- `guard_refuses`

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/alerts.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gates.py`, `orchestrator/gitcmd.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`

## orchestrator/gates.py

**Назначение:** Политика гейтов из `gates.yaml` (ADR-0007, SPEC T066).

**Публичные функции:**
- `policy`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_gates.py`

## orchestrator/gitcmd.py

**Назначение:** Вызовы git в корне репозитория, вопросы к ветке задачи и к произвольному

**Публичные функции:**
- `branch_exists`
- `branch_head_sha`
- `branch_merged`
- `commit_committer_dates`
- `commits_behind`
- `current_branch`
- `diff_paths`
- `git`
- `has_no_remote`
- `head_sha`
- `in_repo`
- `is_clean`
- `list_branches`
- `ls_tree_files`
- `on_foreign_branch`
- `show`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/brief.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/projects.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/workspace.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_catalog_new_race.py`, `tests/test_doctor.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_spec_budget.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`

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
- `release`
- `resolve_session_id`
- `run_locked`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/cleanup.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/workspace.py`, `tests/test_lease.py`

## orchestrator/liveness.py

**Назначение:** Возраст heartbeat и адресуемость pid — общие для lease/merge_lock/doctor.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** `orchestrator/doctor.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/release.py`

## orchestrator/merge_lock.py

**Назначение:** Мьютекс merge-окна: один держатель на весь пульт (SPEC T053).

**Публичные функции:**
- `acquire`
- `release`
- `run_window`

**Импортирует:** `orchestrator/config.py`, `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_merge_lock.py`

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

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/liveness.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/runner.py`, `tests/test_auto_cycle.py`, `tests/test_pause.py`, `tests/test_pause_now.py`

## orchestrator/projects.py

**Назначение:** Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

**Публичные функции:**
- `artifact_repo_has_no_remote`
- `cmd_target_init`
- `init_artifact_repo`
- `init_project`
- `project_dir`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_multitarget.py`

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

**Импортирует:** `orchestrator/liveness.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_release.py`

## orchestrator/retro.py

**Назначение:** Детерминированная генерация содержимого `docs/retro/<id>.md` (SPEC T043).

**Публичные функции:**
- `build_done`
- `build_killed`
- `parse_total_cost`
- `retro_path`
- `retro_rel_path`

**Импортирует:** `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/budget.py`, `orchestrator/fsm.py`, `tests/test_canary.py`, `tests/test_fsm_retro.py`, `tests/test_retro.py`

## orchestrator/review.py

**Назначение:** Ревью-пакет: вход ревьювера собирает оркестратор, а не сам агент.

**Публичные функции:**
- `artifact_part`
- `artifact_text`
- `git_diff_part`
- `package_note`
- `previous_verdict_sha`
- `review_package`
- `truncate_diff`
- `truncate_package`

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/runner.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`

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
- `classify_attempt_failure`
- `close_pump`
- `cmd_run`
- `commit_abnormal_checkpoint`
- `commit_pause_now_checkpoint`
- `commit_step_artifacts`
- `commit_timeout_checkpoint`
- `git_identity`
- `role_cmd`
- `role_cwd`
- `role_env`
- `role_token`
- `run_agent_once`
- `spawn_agent`
- `step_role`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/lease.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/review.py`, `orchestrator/roles.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/canary.py`, `orchestrator/doctor.py`, `orchestrator/pause.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_failure_classification.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_pause_now.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_timeout_checkpoint.py`

## orchestrator/spend.py

**Назначение:** Стоимость шага: разбор чисел, событие потока, учёт в spent_usd.

**Публичные функции:**
- `charge_missing_result`
- `charge_step`
- `cli_number`
- `cost_note`
- `json_number`
- `parse_cost_event`
- `partial_tokens_from_log`
- `step_tokens`
- `stream_usage_tokens`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/doctor.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `tests/test_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_step_cost.py`

## orchestrator/store.py

**Назначение:** Состояние задач: БД, миграции схемы, журнал шагов, смена состояния.

**Публичные функции:**
- `ack_alert`
- `add_column`
- `alerts_older_than`
- `all_leases`
- `all_tasks`
- `archive_alert`
- `charge`
- `counter_targets`
- `create_schema`
- `db`
- `enable_wal`
- `get_alert`
- `get_task`
- `insert_alert`
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
- `seed_task_counters`
- `set_merge_lock`
- `set_state`
- `table_columns`
- `task_branch`
- `task_exists`
- `task_number`
- `task_steps`
- `task_target`
- `total_spent`
- `update_lease`
- `update_task`

**Импортирует:** `orchestrator/coldstart.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/alerts.py`, `orchestrator/answer.py`, `orchestrator/auto.py`, `orchestrator/brief.py`, `orchestrator/budget.py`, `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/coldstart.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/lease.py`, `orchestrator/merge_lock.py`, `orchestrator/parallel_limit.py`, `orchestrator/pause.py`, `orchestrator/prune.py`, `orchestrator/release.py`, `orchestrator/retro.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/workspace.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_canary.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_ci_status_kind_gate.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_merge_lock.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parallel_limit.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_program_spend_reseed.py`, `tests/test_prune.py`, `tests/test_release.py`, `tests/test_retro.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_spec_budget.py`, `tests/test_step_autocommit.py`, `tests/test_step_cost.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`, `tests/test_workspace.py`

## orchestrator/targets.py

**Назначение:** Декларация целевых проектов из targets.yaml: запись target'а читается кодом.

**Публичные функции:**
- `check`
- `load`
- `target`

**Импортирует:** `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/doctor.py`, `orchestrator/projects.py`, `orchestrator/store.py`, `tests/test_multitarget.py`

## orchestrator/version.py

**Назначение:** Команда `version`: пин CLI, фактическая версия, версия схемы артефактов

**Публичные функции:**
- `cmd_version`

**Импортирует:** `orchestrator/config.py`, `orchestrator/doctor.py`, `scripts/guard.py`

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

**Импортируется:** `orchestrator/answer.py`, `orchestrator/artel.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_answer_gate.py`, `tests/test_branch_freshness_gate.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_git_fixation.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget_invariants.py`, `tests/test_workspace.py`

## orchestrator/yamlmini.py

**Назначение:** Подмножество YAML, которого достаточно системе: frontmatter и roles.yaml.

**Публичные функции:**
- `frontmatter`
- `mapping`
- `scalar`

**Импортирует:** —

**Импортируется:** `orchestrator/artifacts.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/gates.py`, `orchestrator/roles.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/test_guard_schema.py`, `tests/test_yaml_parsing.py`

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
- `check`
- `check_content`
- `count_test_methods`
- `has_redness_marker`
- `main`
- `module_docstring`
- `redness_marker_errors_from_files`
- `requires_ac_markup`
- `review_evidence_errors`
- `scan_ac_content`
- `scan_acceptance_tests`
- `scan_redness_markers`
- `schema_errors`
- `section_body`
- `spec_ac_errors`
- `traceability_errors_from_content`

**Импортирует:** `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/canary.py`, `orchestrator/fsm.py`, `orchestrator/retro.py`, `orchestrator/version.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`, `tests/test_guard_schema.py`, `tests/test_invariants.py`, `tests/test_version.py`, `tests/test_yaml_parsing.py`

## tests/__init__.py

**Назначение:** нет docstring

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## tests/sandbox.py

**Назначение:** Общая тестовая песочница (SPEC T037, требование 1; SPEC T061 —

**Публичные функции:**
- `capture`
- `claude_only_popen`
- `claude_only_run`
- `fake_git`
- `fake_git_for`
- `seed_developer_brief_fixtures`
- `sync_spec_from_worktree`

**Импортирует:** `orchestrator/config.py`

**Импортируется:** `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_advance_refusal_history.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_answer_branch_reads.py`, `tests/test_answer_gate.py`, `tests/test_auto_cycle.py`, `tests/test_branch_freshness_gate.py`, `tests/test_brief.py`, `tests/test_canary.py`, `tests/test_cas_set_state.py`, `tests/test_catalog_new_race.py`, `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`, `tests/test_fsm_retro.py`, `tests/test_git_fixation.py`, `tests/test_gitcmd_branch_reads.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_lease.py`, `tests/test_merge_lock.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_parallel_limit.py`, `tests/test_pause.py`, `tests/test_pause_now.py`, `tests/test_program_spend_reseed.py`, `tests/test_prune.py`, `tests/test_release.py`, `tests/test_retro.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_workspace.py`

## tests/test_acceptance.py

**Назначение:** Юнит-тесты orchestrator/acceptance.py::run_full_suite (ADR-0007,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_acceptance_tests_flow.py

**Назначение:** Тесты A4 — роль test_author, приёмочные тесты до кода (tasks/T023/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

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

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_agent_prompt.py

**Назначение:** Тесты канала промпта роли (см. tasks/T017/SPEC.md, требование 4).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_analyst_role.py

**Назначение:** Тесты A5 — роль analyst: SPEC из свободного ТЗ Оператора (tasks/T025/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_answer.py

**Назначение:** Юнит-тесты `orchestrator/answer.py` (SPEC T075): счётчик номера

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/answer.py`, `orchestrator/fsm.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/test_git_fixation.py`

**Импортируется:** —

## tests/test_answer_branch_reads.py

**Назначение:** Юнит-тесты ветко-корректного чтения ANSWER/QUESTIONS (SPEC T075):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_answer_gate.py

**Назначение:** Юнит-тест гейта возврата из эскалации (SPEC T075, AC-3/AC-4): второй

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_auto_cycle.py

**Назначение:** Тесты команды `auto` — цикла до ближайшего гейта (см. tasks/T014/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/brief.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_canary.py

**Назначение:** Юнит-тесты `orchestrator/canary.py` (tasks/T065/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/canary.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_cas_set_state.py

**Назначение:** Юнит-тесты `orchestrator.store.set_state` (SPEC T050).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_catalog_new_race.py

**Назначение:** Регресс-тест на замечание major REVIEW T048 итерации 2:

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_doctor.py

**Назначение:** Тесты doctor: pre-flight, recovery-сверка, сироты, alerts, смоуки

**Публичные функции:**
- `result_event`

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_done_branch_cleanup.py

**Назначение:** Юнит-тесты `cleanup.drop_merged_task_branch` (tasks/T073/SPEC.md,

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/cleanup.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_failure_classification.py

**Назначение:** Юнит-тесты классификатора ошибок агента (SPEC T082, требования 1-2).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/runner.py`

**Импортируется:** —

## tests/test_fsm_branch_correct_status_reads.py

**Назначение:** Юнит-тесты ветко-корректных чтений SPEC.md/REVIEW.md/QUESTIONS.md в

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_map_conflict_autoresolve.py

**Назначение:** Юнит-тесты авторазрешения конфликта подтяжки, где единственный

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_map_regen.py

**Назначение:** Юнит-тесты регенерации/коммита карты кодовой базы на merge_gate

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_fsm_retro.py

**Назначение:** Юнит-тесты обвязки RETRO в orchestrator/fsm.py (SPEC T043):

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/retro.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_gates.py

**Назначение:** Юнит-тесты orchestrator/gates.py: политика гейтов из gates.yaml

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gates.py`

**Импортируется:** —

## tests/test_git_fixation.py

**Назначение:** Git-первичка артефактов и approve-по-sha (tasks/T021/SPEC.md, критерии 1–7).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_answer.py`, `tests/test_step_autocommit.py`, `tests/test_step_refixation.py`, `tests/test_timeout_checkpoint.py`

## tests/test_gitcmd_branch_reads.py

**Назначение:** Юнит-тесты ветко-корректных примитивов `orchestrator/gitcmd.py`

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_guard_schema.py

**Назначение:** Тесты версии схемы артефактов (см. tasks/T017/SPEC.md, требование 3).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_invariants.py

**Назначение:** Тесты системных инвариантов (см. tasks/T010/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/artel.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`, `tests/sandbox.py`

**Импортируется:** `tests/test_ci_status_kind_gate.py`

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

**Импортирует:** `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_multitarget_invariants.py

**Назначение:** Инварианты мультитаргета — реестр docs/invariants.md (tasks/T020/SPEC.md).

**Публичные функции:**
- `fake_git_config`

**Импортирует:** `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/workspace.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/pause.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

**Импортирует:** `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/sandbox.py`

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

## tests/test_step_autocommit.py

**Назначение:** Юнит-тесты `runner.commit_step_artifacts` (tasks/T059/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/test_git_fixation.py`

**Импортируется:** —

## tests/test_step_cost.py

**Назначение:** Тесты учёта стоимости шага и потолка бюджета (см. tasks/T007/SPEC.md).

**Публичные функции:**
- `assistant_event`
- `event`
- `result_event`
- `timeout_then_killed_proc`

**Импортирует:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `tests/sandbox.py`

**Импортируется:** —

## tests/test_step_refixation.py

**Назначение:** Юнит-тесты перефиксации sha на пути отклонённого перехода FSM (SPEC

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `tests/test_git_fixation.py`

**Импортируется:** —

## tests/test_timeout_checkpoint.py

**Назначение:** Юнит-тесты `runner.commit_timeout_checkpoint` (tasks/T041/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/test_git_fixation.py`

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
