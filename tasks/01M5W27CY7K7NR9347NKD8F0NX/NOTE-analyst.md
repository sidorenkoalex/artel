# Записка analyst

## Выяснено
- Итерация 2 (возврат со spec_gate): в SPEC внесены пять решений гейта. Бюджет $25 принят. Отказ на действиях вместо загрузки записи — п. 8 ADR-0029, текст ADR не правится. AC-2: без побочных эффектов, проверка до workspace.ensure_clone (catalog.py:829) и до idgen.new_task_id (catalog.py:838); клона нет, шпион git пуст, tasks/steps не меняются. AC-4: отказ на входе cmd_auto/_cmd_auto (auto.py:622/1028) до _pre_advance_step (auto.py:1104); шпионы fsm.cmd_advance и git пусты. AC-9: сторож по всему orchestrator/ кроме targets.py.
- Исключения AC-9 (сравнения forge == "github" на main): github_adapter.py:62 _is_github_target; doctor/misc_checks.py:98 check_base_branch; cleanup.py:304 cleanup_project_remote через _forge_of. Третье в решении гейта не названо — добавлено с причиной (уборка безопасна, требование 2).
- Литерал "operator" массово стоит как актор store.journal — это не сравнение merge_gate; в SPEC оговорено.
- guard требует классифицировать голый `orchestrator/` — добавлена строка в «Не входит».

## Не сработало
- Составные команды Bash (`;`, `|`, `$W`) требуют подтверждения; ls/cat недоступны — работают Read и grep с абсолютными путями одной командой.

## Где остановился
- Шаг закончен: SPEC status ready, guard ок.

## Чего не хватило
- Ничего существенного.
