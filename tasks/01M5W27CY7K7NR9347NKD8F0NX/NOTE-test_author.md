# Записка test_author

## Выяснено
- Планка: долгоживущий tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py (AC-1..AC-7, AC-9, позитив AC-8 по `new` проекта github+operator; 16 тестов) и разовый acceptance_tests/test_ac8_existing_tests_untouched.py (дифф ветки не правит существующие tests/test_*.py, разбор branch_diff по блокам, `new file mode` пропускается).
- Шпион git = `initialized_tmp_root.git_spy.calls` (SpyRun подменяет subprocess.run глобально); импорт orchestrator.gitcmd долгоживущему файлу guard запрещает. light_transition — только для позитивного `new` (там gitcmd.git = fake_git).
- `run`/`auto` гоняются через CLI с `--attach`; `runner.spawn_agent` и `fsm.cmd_advance` подменены и поднимают Halt.
- Ожидаемый вывод отказов: причина `unsupported_reason` в выводе (stdout/stderr/текст SystemExit) и в action или detail записи `steps` задачи.
- Валидация стабом: unsupported_reason в targets + отказ после `_checked_target` в cmd_new, до lease в runner.cmd_run / auto.cmd_auto / fsm.cmd_approve (после resolve_task_id), строка в doctor/cli.all_checks — все 16 зелёные; стаб откатан `git checkout -- orchestrator/`.
- До реализации: 14 красных (AttributeError unsupported_reason / нет отказа / нет строки doctor), AC-8 позитив и AC-9 зелёные.

## Не сработало
- `cd X; sed …` в Bash требует подтверждения — только абсолютные пути, одна команда.

## Где остановился
- Шаг закончен: plank-run 1 passed, preflight пройдена по всем проверкам.

## Чего не хватило
- Запрет gitcmd в долгоживущем файле при требовании SPEC «шпион git» — искал, через что видеть git без импорта gitcmd (ответ: git_spy песочницы TmpRootTest).
