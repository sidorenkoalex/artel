---
built_at_sha: 9aa09468bbd06905f2c9ddeeebeaedce0eebf39e
---

# Codebase-map пульта

Автосгенерировано `scripts/codebase_map.py` — правки руками теряются при следующем запуске.

## orchestrator/__init__.py

**Назначение:** Пакет оркестратора Артели. Точка входа — `orchestrator/artel.py`.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/alerts.py`, `orchestrator/artel.py`, `orchestrator/artifacts.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/review.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`, `tests/test_ci_status.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_guard_schema.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_yaml_parsing.py`

## orchestrator/acceptance.py

**Назначение:** Прогон и сводка приёмочных тестов задачи: tasks/<id>/acceptance_tests/

**Публичные функции:**
- `run`
- `summary`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_acceptance_tests_flow.py`

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

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/spend.py`

**Импортируется:** `orchestrator/auto.py`, `orchestrator/runner.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_auto_cycle.py`, `tests/test_kill_cleanup.py`, `tests/test_step_cost.py`

## orchestrator/alerts.py

**Назначение:** Таблица alerts: несущий носитель порогов/инцидентов/триггеров (A3,

**Публичные функции:**
- `ack`
- `open_alerts`
- `raise_alert`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/doctor.py`, `tests/test_doctor.py`

## orchestrator/artel.py

**Назначение:** Артель, Фаза 0 — FSM-оркестратор (CLI).

**Публичные функции:**
- `main`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/fsm.py`, `orchestrator/projects.py`, `orchestrator/runner.py`

**Импортируется:** `tests/test_analyst_role.py`

## orchestrator/artifacts.py

**Назначение:** Чтение артефактов задачи: frontmatter и свежесть вердикта ревьювера.

**Публичные функции:**
- `fresh_verdict_iteration`
- `frontmatter`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/catalog.py`, `orchestrator/fsm.py`, `tests/test_review_freshness.py`, `tests/test_yaml_parsing.py`

## orchestrator/auto.py

**Назначение:** Цикл `auto`: run+advance, пока в шаге работает агент.

**Публичные функции:**
- `auto_stop`
- `auto_stop_advice`
- `cmd_auto`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`

## orchestrator/budget.py

**Назначение:** Потолок задачи: значение из SPEC, блокировка `run`, реакция после шага.

**Публичные функции:**
- `apply_spec_budget`
- `budget_block`
- `check_program_spend`
- `cmd_budget`
- `enforce_budget`
- `spec_budget`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_invariants.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`

## orchestrator/catalog.py

**Назначение:** Каталог задач: заведение, список, карточка задачи, журнал шагов.

**Публичные функции:**
- `cmd_init`
- `cmd_log`
- `cmd_new`
- `cmd_show`
- `cmd_status`
- `slugify`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/alerts.py`, `orchestrator/artifacts.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_slugify.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`

## orchestrator/ci.py

**Назначение:** Статус CI головного коммита ветки задачи — условие merge (SPEC T017, 6).

**Публичные функции:**
- `branch_status`
- `check_runs`
- `check_runs_page`
- `gh`
- `head_sha`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`

**Импортируется:** `orchestrator/fsm.py`, `tests/test_ci_status.py`, `tests/test_invariants.py`

## orchestrator/cleanup.py

**Назначение:** kill switch и уборка хвостов задачи: каталог артефактов и ветка.

**Публичные функции:**
- `artifacts_in_main`
- `artifacts_tracked_here`
- `cleanup_killed_task`
- `cmd_kill`
- `drop_task_branch`
- `drop_task_dir`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget_invariants.py`

## orchestrator/config.py

**Назначение:** Пути и константы оркестратора — один адрес на весь пакет.

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/agent_log.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/review.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`, `tests/test_ci_status.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`, `tests/test_yaml_parsing.py`

## orchestrator/doctor.py

**Назначение:** doctor: pre-flight, recovery-сверка, сироты, живой и офлайн-смоук CLI

**Публичные функции:**
- `all_checks`
- `check_backup_age`
- `check_base_branch`
- `check_cli_found`
- `check_cli_version`
- `check_disk_space`
- `check_git_identity`
- `check_orphans`
- `check_remote_empty`
- `check_target_layout`
- `check_token`
- `cli_version`
- `cmd_alert_ack`
- `cmd_doctor`
- `isolation_smoke`
- `live_smoke`
- `preflight_checks`
- `recovery_check`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/alerts.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/roles.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/runner.py`, `tests/test_doctor.py`

## orchestrator/fixation.py

**Назначение:** Hash-фиксация артефактов на переходах FSM (ADR-0003 п.15, п.17; tasks/T021).

**Публичные функции:**
- `check_integrity`
- `fix`
- `read`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `tests/test_git_fixation.py`

## orchestrator/fsm.py

**Назначение:** Переходы автомата: advance по артефактам, approve/reject Оператора.

**Публичные функции:**
- `cmd_advance`
- `cmd_approve`
- `cmd_reject`
- `confirm_fixation`
- `guard_refuses`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/acceptance.py`, `orchestrator/artifacts.py`, `orchestrator/budget.py`, `orchestrator/ci.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`

## orchestrator/gitcmd.py

**Назначение:** Вызовы git в корне репозитория, вопросы к ветке задачи и к произвольному

**Публичные функции:**
- `branch_exists`
- `branch_merged`
- `current_branch`
- `diff_paths`
- `git`
- `has_no_remote`
- `head_sha`
- `in_repo`
- `is_clean`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`

**Импортируется:** `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/projects.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_step_cost.py`

## orchestrator/keychain.py

**Назначение:** Чтение токенов из macOS keychain.

**Публичные функции:**
- `token`

**Импортирует:** —

**Импортируется:** `orchestrator/runner.py`

## orchestrator/projects.py

**Назначение:** Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

**Публичные функции:**
- `artifact_repo_has_no_remote`
- `cmd_target_init`
- `init_artifact_repo`
- `init_project`
- `project_dir`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/targets.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/doctor.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_multitarget.py`

## orchestrator/review.py

**Назначение:** Ревью-пакет: вход ревьювера собирает оркестратор, а не сам агент.

**Публичные функции:**
- `artifact_part`
- `artifact_text`
- `git_diff_part`
- `package_note`
- `review_package`
- `truncate_diff`
- `truncate_package`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`

**Импортируется:** `orchestrator/runner.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`

## orchestrator/roles.py

**Назначение:** Карта исполнителей из roles.yaml: состав скилов роли читается кодом.

**Публичные функции:**
- `load`
- `skills`
- `token_slots`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/doctor.py`, `orchestrator/runner.py`, `tests/test_yaml_parsing.py`

## orchestrator/runner.py

**Назначение:** Запуск агента шага: промпт роли, окружение, попытки, исход, стоимость.

**Публичные функции:**
- `close_pump`
- `cmd_run`
- `git_identity`
- `role_cwd`
- `role_env`
- `role_token`
- `run_agent_once`
- `step_role`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/gitcmd.py`, `orchestrator/keychain.py`, `orchestrator/review.py`, `orchestrator/roles.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/doctor.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_step_cost.py`

## orchestrator/spend.py

**Назначение:** Стоимость шага: разбор чисел, событие потока, учёт в spent_usd.

**Публичные функции:**
- `charge_step`
- `cli_number`
- `cost_note`
- `json_number`
- `parse_cost_event`
- `step_tokens`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/store.py`

**Импортируется:** `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/doctor.py`, `orchestrator/runner.py`, `tests/test_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_step_cost.py`

## orchestrator/store.py

**Назначение:** Состояние задач: БД, миграции схемы, журнал шагов, смена состояния.

**Публичные функции:**
- `ack_alert`
- `add_column`
- `all_tasks`
- `charge`
- `create_schema`
- `db`
- `enable_wal`
- `get_alert`
- `get_task`
- `insert_alert`
- `insert_task`
- `journal`
- `latest_fixed_sha`
- `migrate`
- `next_task_number`
- `now`
- `open_alert_exists`
- `open_alerts`
- `seed_task_counters`
- `set_state`
- `table_columns`
- `task_number`
- `task_steps`
- `task_target`
- `total_spent`
- `update_task`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/fixation.py`

**Импортируется:** `orchestrator/alerts.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/doctor.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/test_analyst_role.py`, `tests/test_auto_cycle.py`, `tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_invariants.py`, `tests/test_kill_cleanup.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/test_review_freshness.py`, `tests/test_review_package.py`, `tests/test_spec_budget.py`, `tests/test_step_cost.py`

## orchestrator/targets.py

**Назначение:** Декларация целевых проектов из targets.yaml: запись target'а читается кодом.

**Публичные функции:**
- `check`
- `load`
- `target`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/config.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/doctor.py`, `orchestrator/projects.py`, `tests/test_multitarget.py`

## orchestrator/yamlmini.py

**Назначение:** Подмножество YAML, которого достаточно системе: frontmatter и roles.yaml.

**Публичные функции:**
- `frontmatter`
- `mapping`
- `scalar`

**Импортирует:** —

**Импортируется:** `orchestrator/artifacts.py`, `orchestrator/roles.py`, `orchestrator/targets.py`, `scripts/guard.py`, `tests/test_guard_schema.py`, `tests/test_yaml_parsing.py`

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
- `count_test_methods`
- `main`
- `requires_ac_markup`
- `scan_acceptance_tests`
- `schema_errors`
- `spec_ac_errors`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/yamlmini.py`

**Импортируется:** `orchestrator/acceptance.py`, `orchestrator/fsm.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_analyst_role.py`, `tests/test_guard_schema.py`, `tests/test_invariants.py`, `tests/test_yaml_parsing.py`

## tests/__init__.py

**Назначение:** нет docstring

**Публичные функции:** (нет)

**Импортирует:** —

**Импортируется:** —

## tests/test_acceptance_tests_flow.py

**Назначение:** Тесты A4 — роль test_author, приёмочные тесты до кода (tasks/T023/SPEC.md).

**Публичные функции:**
- `fake_git`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/acceptance.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_advance_guard.py

**Назначение:** Тесты guard на переходах FSM (см. tasks/T017/SPEC.md, требование 5).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_agent_failure.py

**Назначение:** Тесты провала шага по коду возврата агента (см. tasks/T006/SPEC.md).

**Публичные функции:**
- `fake_git`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_agent_log.py

**Назначение:** Тесты лога агента по ходу шага (см. tasks/T005/SPEC.md).

**Публичные функции:**
- `assistant_event`
- `event`
- `fake_git`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_agent_prompt.py

**Назначение:** Тесты канала промпта роли (см. tasks/T017/SPEC.md, требование 4).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_analyst_role.py

**Назначение:** Тесты A5 — роль analyst: SPEC из свободного ТЗ Оператора (tasks/T025/SPEC.md).

**Публичные функции:**
- `fake_git`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/artel.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_auto_cycle.py

**Назначение:** Тесты команды `auto` — цикла до ближайшего гейта (см. tasks/T014/SPEC.md).

**Публичные функции:**
- `fake_git`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/agent_log.py`, `orchestrator/auto.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_ci_status.py

**Назначение:** Тесты статуса CI ветки задачи (см. tasks/T017/SPEC.md, требование 6).

**Публичные функции:**
- `run`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/ci.py`, `orchestrator/config.py`

**Импортируется:** —

## tests/test_codebase_map.py

**Назначение:** Юнит-тесты функций scripts/codebase_map.py (tasks/T027/SPEC.md).

**Публичные функции:**
- `parse`

**Импортирует:** `scripts/codebase_map.py`

**Импортируется:** —

## tests/test_doctor.py

**Назначение:** Тесты doctor: pre-flight, recovery-сверка, сироты, alerts, смоуки

**Публичные функции:**
- `capture`
- `claude_only_popen`
- `claude_only_run`
- `result_event`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/alerts.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/doctor.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_git_fixation.py

**Назначение:** Git-первичка артефактов и approve-по-sha (tasks/T021/SPEC.md, критерии 1–7).

**Публичные функции:**
- `capture`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_guard_schema.py

**Назначение:** Тесты версии схемы артефактов (см. tasks/T017/SPEC.md, требование 3).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_invariants.py

**Назначение:** Тесты системных инвариантов (см. tasks/T010/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/ci.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/store.py`, `scripts/guard.py`

**Импортируется:** —

## tests/test_kill_cleanup.py

**Назначение:** Тесты уборки хвостов убитой задачи (см. tasks/T008/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/agent_log.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_multitarget.py

**Назначение:** Тесты мультитаргетного контура (см. tasks/T019/SPEC.md, критерии 1–8).

**Публичные функции:**
- `capture`
- `fake_git_config`
- `result_event`
- `silent_git`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/projects.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`, `orchestrator/targets.py`

**Импортируется:** —

## tests/test_multitarget_invariants.py

**Назначение:** Инварианты мультитаргета — реестр docs/invariants.md (tasks/T020/SPEC.md).

**Публичные функции:**
- `capture`
- `fake_git_config`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/cleanup.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_review_freshness.py

**Назначение:** Тесты свежести вердикта ревью (см. tasks/T004/SPEC.md).

**Публичные функции:**
- `fake_git`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/artifacts.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_review_package.py

**Назначение:** Тесты ревью-пакета — входа ревьювера (см. tasks/T011/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/gitcmd.py`, `orchestrator/review.py`, `orchestrator/runner.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_slugify.py

**Назначение:** Тесты для orchestrator.catalog.slugify (см. tasks/T003/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/catalog.py`

**Импортируется:** —

## tests/test_spec_budget.py

**Назначение:** Тесты бюджета задачи из frontmatter SPEC (см. tasks/T012/SPEC.md).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_step_cost.py

**Назначение:** Тесты учёта стоимости шага и потолка бюджета (см. tasks/T007/SPEC.md).

**Публичные функции:**
- `event`
- `fake_git`
- `result_event`

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/agent_log.py`, `orchestrator/budget.py`, `orchestrator/catalog.py`, `orchestrator/config.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/spend.py`, `orchestrator/store.py`

**Импортируется:** —

## tests/test_yaml_parsing.py

**Назначение:** Тесты разбора YAML и карты ролей (см. tasks/T017/SPEC.md, требования 1–2).

**Публичные функции:** (нет)

**Импортирует:** `orchestrator/__init__.py`, `orchestrator/artifacts.py`, `orchestrator/config.py`, `orchestrator/roles.py`, `orchestrator/yamlmini.py`, `scripts/guard.py`

**Импортируется:** —
