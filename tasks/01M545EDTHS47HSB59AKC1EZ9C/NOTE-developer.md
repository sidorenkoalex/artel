# Записка developer

## Выяснено
- Механизм — в `gitcmd.git` (`_hosting_project`: разбор `-C`/подкоманды, проект по пути `.artel/projects/<имя>/<…>` или URL аргумента push) + `gitcmd.hosting_token(name, entry)` (общий для git, `ci.gh`, doctor). Помощник: `GIT_CONFIG_COUNT/KEY/VALUE` (`credential.helper=` + `!f…` с паролем из `$ARTEL_HOSTING_TOKEN`).
- Проверки п.5 — `orchestrator/doctor/project_checks.py::project_entry_checks`, зовутся из `all_checks`.
- ANSWER-1: П-2 закрыт правкой `setUp` у `tests/test_doctor.py::BaseBranchCheckTest` (подмена `config.ROLE_HOME` + `sandbox.isolate_keychain_and_role`); Ф-2, Р-1, Ф-3 уже были реализованы прошлым шагом — сверено с кодом, ссылки в PLAN.md «ANSWER-1».
- Подмены одного `config.ROLE_HOME` мало: из шага роли стоит и `ARTEL_ROLE` — нужно снимать оба.

## Не сработало
- `env | …` в одной команде Bash требует подтверждения — не цепочкой.

## Где остановился
- Тесты затронутых модулей 135 passed, планка 1 passed, карта регенерирована; suite-run №3 зелёный (5601/0/2). PLAN.md status: ready, guard ок. Шаг закончен.

## Чего не хватило
- Ничего существенного: ANSWER-1 назвал файл и строку.
