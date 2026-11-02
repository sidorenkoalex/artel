## Выяснено
- ТЗ достаточно, SPEC.md написан (status: ready, 12 AC, budget 40 = рамка деления), guard ок.
- Сигнал объёма — только AC ≥ 10; дано обоснование монолита (почти всё в project_checks.py), решение — за Оператором на гейте.
- Трактовка: строка защит п.1 ТЗ = `project-base-protection-<имя>`, строка workflow = `project-ci-pull-request-<имя>` (ТЗ п.2 это прямо говорит). Три новые строки (файл CI в no_paths, перезапуски в ci_job, подмодули) — имён ТЗ не задаёт, выбирает разработчик в форме `project-<вид>-<имя>`.
- `--sha` в forge-probe: в forge уже есть `pipeline_status(target, sha)` с jobs; `--ref` — `branch_pipeline(target, branch)`.
- Литерал «gitlab» в выборе проверки запрещён — развилка через `forge.ci_by_pipeline`/`hasattr(implementation, ...)`, образец `misc_checks.check_base_branch`.

## Не сработало
- Ничего.

## Где остановился
- SPEC сдан, merge_after нет (ТЗ: «без зависимостей»).

## Чего не хватило
- Имён новых строк doctor в ТЗ; где лежит шаблон ветки задачи — `catalog.branch_template`.
