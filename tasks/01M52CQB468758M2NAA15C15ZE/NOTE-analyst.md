# NOTE analyst — 01M52CQB468758M2NAA15C15ZE

## Выяснено
- ТЗ достаточно для SPEC. Места запуска pytest: acceptance.py:447 (run), :555 (collect), :664 (run_repeat), :931 (run_plank), :1323/:1344 (_run_full_suite_now, два пути), :1371 (_run_full_suite_to_log), two_sided.py:227-229 (_run_side).
- preflight.py и dry_run.py pytest не запускают (grep subprocess/_pytest пусто); их модулей нет в зонах ТЗ — в SPEC требование 5 для них записано как «без правки модуля».
- secret_env_names — метод провайдеров (providers/claude.py:213), набор чужих — runner.foreign_secret_env_names.
- Сигналы объёма: зон 14 (≥5), budget 50 (≥30) — предложена нарезка на 3 части (профиль+фиксация argv / раннер pytest-own в acceptance+two_sided / передача Profile вызывающими).

## Не сработало
- cat/ls в Bash недоступны (command not found) — читать Read/grep.
- Команда с `$?` в Bash отклонена («simple_expansion») — guard звать без `echo rc=$?`.

## Где остановился
- SPEC.md написан (status: ready, 10 требований, AC-1..AC-10, деление на 3 части без строк «Рамка:» — рамки за Оператором), guard: ок.

## Чего не хватило
- Нет готовой справки «какие команды пульта реально исполняют pytest» — собирал grep'ом по вызовам acceptance.*.
