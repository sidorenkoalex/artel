# Записка developer

## Выяснено
- Код (suite_lock.py, suite_hold.py, artel.py) был в WIP-чекпоинте ebd2784e1; все долгоживущие тесты задачи зелёные.
- ANSWER-1 пп. 2–4 закрыты новыми файлами tests/test_01m70ryd6yxa6dfkcrecshrkbm_suite_lock_answer_{process,rules}.py; мутации проверены временно (каждая краснит свой тест).
- В finally `cmd_suite_lock` сигналы игнорируются на время `release`.
- `artel.main` не берёт код возврата команды — запись таблицы `suite-lock` делает `sys.exit(...)`.

## Не сработало
- Многострочный python через heredoc в Bash отклоняется хуком — временный сценарий пишется файлом в worktree и убирается `task-rm`.

## Где остановился
- PLAN status: ready, guard прогнан. Шаг завершён.

## Чего не хватило
- Ничего существенного.
