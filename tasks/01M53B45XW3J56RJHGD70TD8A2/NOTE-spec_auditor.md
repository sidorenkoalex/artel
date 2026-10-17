# Записка spec_auditor

## Выяснено
- Визит 3 (SPEC sha add88b4d…, после второго решения гейта). Оба решения
  Оператора внесены полностью. Вердикт: concerns, новые находки Т-1…Т-5.
- Т-5: `ci.gh` узнаёт внешний проект только по `repo=` (ci.py:57).
  Вызовы без `repo`: ci.py:369 (`_commit_workflow_runs`, из
  `verifying_status`), :1148 (`find_run_id`), :1207, :1240-1253
  (`trigger_rerun`).
- Т-4: `_push_closing_sha` из главной копии (artifact_branches.py:137,
  :174) — механизм «по `-C`» проект не узнаёт.
- Т-1: `ls-remote` (gitcmd.py:524, :538; artifact_cleanup.py:30;
  doctor/artifact_branches.py:22) и `push --delete` (artifact_cleanup.py:99)
  в перечне хостинговых операций SPEC не названы.
- Т-2: `in_role_environment` узнаёт роль и по `HOME` (runner.py:1067),
  AC-12 проверяет только `ARTEL_ROLE`.
- Т-3: `workspace.py:111` делает clone с `-C .artel/projects/<имя>`.

## Где остановился
SPEC-AUDIT.md написан, guard: ок.

## Чего не хватило
Перечня вызовов `gh` с признаком проекта: собирал grep по `gh(`.
