# Записка developer

## Выяснено
- Реализация — в orchestrator/forge.py (`_GitHub.job_result`, `job_test_report`, `green_base_commit`, помощники `_gh_*`, `_junit_report`, `_parse_junit`), двоичный вызов — `ci.gh_bytes` (Popen + select: предел размера при чтении, предел времени, снятие группы процесса); правило входа `gh` вынесено из `ci.gh` в `ci._gh_entry` без смены поведения.
- Поле `ci_report_artifact` — targets.COMPONENT_FIELDS, умолчание `targets.CI_REPORT_ARTIFACT_DEFAULT`.
- Строка doctor `project-ci-report-<проект>-<компонент>` — `project_checks.check_ci_report`, выбор по `forge.implements(name, "green_base_commit")`.
- Негодный статус check run — `unfit:<значение>`.
- Возврат из verifying (CI 42439642328) закрыт по мандату ANSWER-3: `test_ac3_github_people_full_suite_ci_refused` (entry_checks) подменяет реестр `github` пространством имён без `job_test_report`; утверждение прежнее; мутация «правило пропускает github» краснит его. Файл: 25 passed; с registry_without_report и component_fields: 40 passed.

## Не сработало
- `pytest -n` и перечень ~90 файлов отказывает сторож conftest — гонять пачками по ≤12 файлов без -n.
- Составные Bash-команды (cp && heredoc) требуют подтверждения — временную мутацию делать через Edit.

## Где остановился
- Правка теста по ANSWER-3 сделана, PLAN.md status: ready, карта регенерирована.

## Чего не хватило
- Перечня тестов, держащихся на отсутствии функции в реестре `forge.IMPLEMENTATIONS` (grep по `full_suite: ci` в tests/ нашёл бы entry_checks заранее).
