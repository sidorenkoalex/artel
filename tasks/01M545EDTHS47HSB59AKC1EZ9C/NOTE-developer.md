# Записка developer

## Выяснено
- Механизм — в `gitcmd.git` (`_hosting_project`: разбор `-C`/подкоманды, проект по пути `.artel/projects/<имя>/<…>` или URL аргумента push) + `gitcmd.hosting_token(name, entry)` (общий для git, `ci.gh`, doctor). Помощник: `GIT_CONFIG_COUNT/KEY/VALUE` (`credential.helper=` + `!f…` с паролем из `$ARTEL_HOSTING_TOKEN`).
- `gh api` не принимает `--repo` — 5.4 зовёт `gh` напрямую через `doctor.subprocess.run`; `doctor.gh_env` (misc_checks) даёт окружение.
- Проверки п.5 — `orchestrator/doctor/project_checks.py::project_entry_checks`, зовутся из `all_checks` после `check_base_branch`. Имена строк `project-<вид>-<проект>`.
- Песочница до задачи НЕ снимала `ARTEL_ROLE` и не подменяла `keychain.token` — `isolate_keychain_and_role` в `TmpRootTest.setUp`/`RealGitSandbox.setUp`.
- Подмодули doctor не импортируют коллаборантов напрямую — только через фасад; `brief`, `project_profile` добавлены в фасад.

## Не сработало
- Функция `project_checks` с именем подмодуля затенила подмодуль в фасаде — переименована в `project_entry_checks`.
- Адреса `https://…` в tests/ красят инвариант `NoNetworkAddressesInTestsTest` — только `file://`.
- `pytest -n` из шага роли отказывает сторож; `BaseBranchCheckTest` локально из роли красен (признак роли по HOME), в suite-run зелёный.

## Где остановился
- Всё сделано: долгоживущий файл 18 passed, планка 1 passed, suite-run №1 (1 падение — исправлено) + №2 --failed зелёный. PLAN.md status: ready, guard ок. Карта регенерирована.

## Чего не хватило
- Что песочница не нейтрализует признак роли, хотя SPEC (требование 9) описывает это как данность — выяснилось только чтением `tests/sandbox.py`.
