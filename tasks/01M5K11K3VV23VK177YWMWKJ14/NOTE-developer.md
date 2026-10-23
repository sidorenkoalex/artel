# Записка developer — 01M5K11K3VV23VK177YWMWKJ14

## Выяснено
- Реализация: `cleanup.cmd_kill(reason=)` → `_cmd_kill` → `_kill_detail`; `cmd_kill` возвращает `bool(lease.run_locked(...))` (run_locked возвращает результат тела). Отказ пустой причины — первой строкой `cmd_kill`; отказ значения на `--` и подсказка — в `artel._cmd_kill(rest)`.
- Долгоживущий файл задачи 17/17 зелёный, plank-run 1 passed, 26 файлов tests/ про kill зелёные. Карта регенерирована.

## Не сработало
- Цепочки `cmd && ... | awk` в Bash требуют подтверждения — дроби команды.

## Где остановился
- PLAN.md status: ready, guard прогнан. Шаг завершён.

## Чего не хватило
- Ничего.
