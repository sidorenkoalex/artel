# Записка spec_auditor — 01M6EZXVFGCHB1S4W45AWJ0QH6

## Выяснено
- Сверки окружения под белым списком УЖЕ есть: `gitcmd.py:660-664` (GIT_DIR, GIT_WORK_TREE, GIT_COMMON_DIR, GIT_CONFIG_COUNT/PARAMETERS/KEY_/VALUE_), конфигурации — `:719-723` (remote.origin.pushurl/push/mirror, push.pushOption). Контекст SPEC «сверок нет» неверен.
- `_whitelist_refusal` отказывает любой глобальной опции, кроме `-C` (`gitcmd.py:653-657`): `-c core.hooksPath=` пульт должен добавлять внутри `_push_plan` (как PUSH_RESET_CONFIG, `:966-971`), не у вызывающего.
- Клон проекта идёт БЕЗ слота токена: `clone` нет в `HOSTING_SUBCOMMANDS` (`gitcmd.py:41`), `ensure_clone` (`workspace.py:106`). Клона подмодулей в коде нет вовсе. AC-14 «тот же слот, что у клона проекта» выполним вхолостую (оба без слота).
- Общий хук `scripts/git-hooks/pre-push` один на все клоны; SPEC не говорит, как хук отличит клон target-human без файла политики (AC-4: отказ) от клона operator без файла (AC-5: как прежде). Имя/путь файла политики и имя строки doctor не названы — планка пишется до кода.
- Существующие тесты target-human `tests/test_gitcmd_push_point.py:105-133` отправляют из клона без core.hooksPath и ждут успеха (`:123`, `:131`): «нет core.hooksPath» = «иной»? — не решено; требование 12 покрывает только artel/github+operator.
- Ссылка `gitcmd.py:640` (переменные окружения) неверна — там `_explicit_source`; верно `:189-193`, `:660-664`.
- Часть 1 (01M6EZXVFGXC6WBDA9QJESAZRW) клон с токеном не вводит (её ТЗ в refs/artifacts).

## Не сработало
- Составные bash-команды с `cd`/пайпами требуют подтверждения — только одиночные grep по абсолютным путям.

## Где остановился
- Вердикт fail (Д-1…Д-7), SPEC-AUDIT.md записан, status: ready; guard — ок.

## Чего не хватило
- Где пульт ставит токен клону (искал `token_slot` в ensure_clone) — его там нет: `HOSTING_SUBCOMMANDS` в `gitcmd.py:41`.
