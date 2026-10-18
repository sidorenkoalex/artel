# Записка analyst — 01M574A6YQHAPASS9716Z11G4Q

## Выяснено
- Сверка вызовов `check_runs` (требование 4 ТЗ), все в `orchestrator/ci.py` (зона):
  - :748 `verifying_status` — путь внешней задачи (fsm_advance:453, fsm_autogate:287, ci_rerun:123/158, acceptance:2260). Пустой/None → `_no_checks_by_branch` (:805) — источник инцидента («проверки идут» по `gh run list`).
  - :892 `failed_check_names` — ci_rerun:276/291 для внешнего проекта (голова и main), плюс `_inherited_from_main` (:611) на красном исходе.
  - :920 `branch_status` — гейт мержа внешней задачи (fsm_merge_gate:299, :353), фильтра is_artel нет.
  - :969 `accepted_full_suite` — для не-артели возврат до `check_runs` (:967): не на пути.
  - :1213 `main_line_status` — вызыватели только артель (pin.py:86 ROOT, fsm_merge_gate:583/:626 под `is_artel`, doctor/main_ci ROOT): не на пути.
  - :1326 `find_run_id` — на пути ре-рана; при None от check_runs деградирует на первый красный прогон, зелёным не читает — отдельной правки не требует.
- В tests/ нет тестов, закрепляющих исход 403 для CI → раздела «Меняемое поведение» нет.
- Понятия «триггер, которым CI проекта проверяет ветку» в ci.py нет; в ТЗ — отсылка к doctor `project-ci-pull-request` (разбор `on:` workflow клона, project_checks.py:104 `declares_pull_request`).

## Где остановился
SPEC.md написан (status: ready, budget_usd 35 = рамка ТЗ, 10 AC), `scripts/guard.py` — ок. Сигналы объёма (бюджет ≥30, 10 AC, инвариант 19) — в SPEC дано обоснование монолита по цене с запасным вариантом деления (CI → doctor); решать Оператору на гейте SPEC.

## Не сработало
- Bash с `cd`/переменной в составной команде отклоняется правилами — звать команды из рабочего каталога относительными путями, по одной.

## Чего не хватило
Ничего критичного; дольше всего — проверка, какие вызыватели main_line_status ограничены is_artel (fsm_merge_gate.py:583, :626).
