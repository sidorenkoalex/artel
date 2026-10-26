# Записка developer

## Выяснено
- Реализовано: targets.SUPPORTED_*/unsupported_reason (TargetsError -> None); catalog.cmd_new — отказ сразу за _checked_target; runner.refuse_unsupported_project(conn, id, command) — журнал «отказ: проект не поддержан» + sys.exit; doctor/cli.project_support_check первой строкой цикла записей.
- Итерация 2 (возврат из verifying, CI 40330101818): вызов refuse_unsupported_project перенесён из публичных cmd_run/cmd_auto/cmd_approve внутрь тел под обвязкой — runner._cmd_run, auto._cmd_auto, fsm._cmd_approve, первым действием. Линтер tests/test_lease_run_task_command.py запрещает в теле публичной команды что-либо, кроме lease.run_task_command.
- Тесты: долгоживущий файл + 3 упавших в CI файла — 36 passed; 18 файлов approve/auto/catalog/fsm/runner + doctor + multitarget — 342 passed; plank-run 1 passed; guard ок.

## Не сработало
- Bash: `ls`, `cd X && …`, пайпы с sed, `$?` — требуют подтверждения; только одиночные команды.

## Где остановился
- Шаг закончен: карта регенерирована, PLAN status: ready.

## Чего не хватило
- Правило «новая проверка — внутрь _cmd_*, не в обвязку» живёт только в линтере тестов, не в скилах.
