# NOTE test_author 01M6TRKY1A41QSZMCXY9TKYXG7

## Выяснено
- ANSWER-4: канал — аннотация `::notice title=plan-appendix-docs::ref=<X>; outcome=<applied|no-plan|no-appendices|no-ref>; diffs=<h1,…>` у проверки `FULL_SUITE_JOB`, чтение `gh api …/check-runs/<id>/annotations`; AC-13 считает список сам (sha256 hex UTF-8 `PlanAppendix.diff`).
- Все AC-1…AC-18 — тесты в двух долгоживущих файлах: `tests/test_01m6trky1a41qszmcxy9tkyxg7_ci_result.py` (приёмка, 41 вариант) и `tests/test_01m6trky1a41qszmcxy9tkyxg7_ci_publication.py` (сценарий CI, AC-13/AC-14). В `acceptance_tests/` — только `markers.py` без пометок (эскалации сняты).
- Стенд local: настоящий git (RealGitSandbox, workspace.ensure, checkpoint.commit_step_artifacts), узел `appendix_tree.suite_tree` + `acceptance.acceptance_suite`; подменены `ci.gh` (check-runs с `id`, actions/runs, `check-runs/<id>/annotations`) и шпион `acceptance.full_suite`. Стенд ci — light_transition + FakeForge.
- Автокоммит пульта (`commit_step_artifacts`) сам отправляет ссылку документов в origin; «ссылки нет» моделируется удалением её из origin.
- Валидация стабом: со стабом 46/46 зелёные; снятие каждого условия 3а–3з, свежести, исхода, чтения только FULL_SUITE_JOB, список как множество, хеш не UTF-8 — красит нужные тесты. Стаб откачен `git checkout --`, `git status` — только два новых файла.
- Без кода: 14 красных в ci_result (принятие), 5 красных в ci_publication; отказные тесты зелёные с рождения.
- `plank-run` без аргумента отказывает «нет файлов test_*.py» — у планки только долгоживущие файлы; гейт гоняет их вместе с каталогом планки (`acceptance.py:1851`). `plank-run <id> tests/<файл>` работает.

## Не сработало
- heredoc с `{'`… в Bash отклоняется инструментом — стаб вносил через Edit.
- Составные команды с `;`/`|` после основной требуют подтверждения.

## Где остановился
- Шаг готов: preflight пройден, тесты написаны и провалидированы.

## Чего не хватило
- Как пульт отправляет ссылку документов в origin (сам при автокоммите) — выяснил по провалу теста.
