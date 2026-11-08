# Записка developer

## Выяснено
- Реализация — в orchestrator/forge.py (`_GitHub.job_result`, `job_test_report`, `green_base_commit`, помощники `_gh_*`, `_junit_report`, `_parse_junit`), двоичный вызов — `ci.gh_bytes` (Popen + select: предел размера при чтении, предел времени, снятие группы процесса); правило входа `gh` вынесено из `ci.gh` в `ci._gh_entry` без смены поведения.
- Поле `ci_report_artifact` — targets.COMPONENT_FIELDS, умолчание `targets.CI_REPORT_ARTIFACT_DEFAULT`.
- Строка doctor `project-ci-report-<проект>-<компонент>` — `project_checks.check_ci_report`, выбор по `forge.implements(name, "green_base_commit")`.
- Негодный статус check run — `unfit:<значение>`.
- Долгоживущие файлы задачи: 67 passed; планка: 6 passed; 12 соседних файлов: 450 passed, 2 skipped (ровно мандат ANSWER-2).

## Не сработало
- `pytest -n` и перечень ~90 файлов отказывает сторож conftest — гонять пачками по ≤12 файлов без -n.

## Где остановился
- Прогон оставшихся соседних файлов (verifying_outcome_gate медленный, >300 с).

## Чего не хватило
- —
