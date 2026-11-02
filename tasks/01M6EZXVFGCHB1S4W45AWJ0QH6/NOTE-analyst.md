# Записка analyst

## Выяснено
- Итерация 2 (после аудита fail Д-1…Д-7). Решения SPEC:
  - отдельный каталог хуков `target-human`: `<config.ROOT>/scripts/git-hooks/target-human/` (pre-push с правилами + pre-commit с прежней защитой main) — так AC-4 (нет политики → отказ) не спорит с AC-5 (общий хук прежний);
  - файл политики `<git-common-dir клона>/artel-push-policy`, 4 строки key=value: project, base, branch_template, artifacts_prefix;
  - строка doctor `clone-push-hook` из `check_clone_hooks`/`_fix_project_clones` (уже подключены в doctor/cli.py:203,:261); `clone-hooks` — только прочие проекты;
  - «иной core.hooksPath» = задан и не равен; снятый не отказывает в gitcmd (пульт всё равно ставит `-c`), ловит doctor. Так `tests/test_gitcmd_push_point.py:123,:131` остаются зелёными (шпион push не исполняет, хук не запускается);
  - `-c core.hooksPath` вставляет `_push_plan` после сверок (как PUSH_RESET_CONFIG, gitcmd.py:966-971);
  - клон проекта и подмодулей — токеном слота (сейчас `clone` нет в HOSTING_SUBCOMMANDS, gitcmd.py:41);
  - прежние сверки (gitcmd.py:189-193, :660-664, :719-723) сохраняются и покрываются AC.
- Тесты проектов с GIT_CONFIG_GLOBAL (test_01m545edths…) — merge_gate operator, новой сверкой не задеты.

## Не сработало
- Составные bash-команды (ls, xargs, ;) требуют подтверждения — только одиночные grep/sed.

## Где остановился
- SPEC.md итерации 2 сдан (status: ready, 13 требований, AC-1..AC-15), guard ок. QUESTIONS не нужен: Д-4 решён буквальным чтением ТЗ («нет иного» ≠ «не задан») без правки тестов.

## Чего не хватило
- Где пульт ставит токен клону — нигде: `clone` вне HOSTING_SUBCOMMANDS (gitcmd.py:41).
