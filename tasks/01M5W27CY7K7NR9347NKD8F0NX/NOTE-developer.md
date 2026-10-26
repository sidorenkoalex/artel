# Записка developer

## Выяснено
- Реализовано: targets.SUPPORTED_*/unsupported_reason (TargetsError -> None); catalog.cmd_new — отказ сразу за _checked_target; runner.refuse_unsupported_project(conn, id, command) — журнал «отказ: проект не поддержан» + sys.exit, зовут runner.cmd_run (до lease), auto.cmd_auto (до lease), fsm.cmd_approve (ленивый импорт runner, до _as_epic_goal); doctor/cli.project_support_check первой строкой цикла записей.
- Долгоживущий файл задачи: 16 passed.

## Не сработало
- Bash: `ls`, `cd X && …` — требуют подтверждения/недоступны; только одиночные команды с относительными путями.

## Где остановился
- Шаг закончен: тесты затронутых модулей зелёные (250 + 193), карта регенерирована, plank-run 1 passed, guard ок, PLAN status: ready.

## Чего не хватило
- —
