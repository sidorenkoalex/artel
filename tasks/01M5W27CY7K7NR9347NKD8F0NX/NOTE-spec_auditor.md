# Записка аудитора SPEC

## Выяснено
- Факты SPEC сходятся: targets.py:23-24, 622-628; github_adapter.py:133; fsm.py:1611 _approve_merge_gate; cmd_approve fsm.py:931 -> _cmd_approve :1744; cmd_new catalog.py:678, первый рубеж _checked_target :755, клон :829, id :838.
- auto: cmd_auto auto.py:622 -> _auto_cycle :1037 — сначала _pre_advance_step (fsm.cmd_advance), verifying-опрос :1087; AC-4 со шпионом только spawn_agent не ловит проверку «только в cmd_run».
- AC-2 считает только строки tasks/steps — не ловит проверку после workspace.ensure_clone (побочный эффект клона).
- Создание задач: catalog.cmd_new (вызывают artel.py:2025, epics.py:796, canary_drive), spawn_subtask (fsm.py:1070 на approve spec_gate).
- Мерж только через cmd_approve -> _approve_merge_gate -> fsm_merge_gate._cmd_approve_merge_gate_cycle.
- Тесты с gitlab/target-human только как данные (insert_task, check_base_branch); "gitlab-issue" — система ссылок, не forge.

## Не сработало
- grep с `cd` и пайпами в Bash требует подтверждения — только абсолютные пути, одна команда.

- Обход: epic draft promote (epics.py:796) зовёт catalog.cmd_new — проверка в new_cli_target (catalog.py:491) его пропустит.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок. Шесть отклонений (AC-2, AC-4, AC-9, место отказа new, бюджет $25 против $15, буква ADR-0029 п.8).

## Чего не хватило
- Дольше всего искал, где цикл auto зовёт advance до run (auto.py:1104 _pre_advance_step) — в карте у auto.py нет описания порядка шагов цикла.
