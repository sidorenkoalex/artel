# Записка developer — 01M6HVPMYY2Q56JZ64KD28FTWK

## Выяснено
- Реализация: orchestrator/auto.py (надзор: _run_begins/_child_runs/_child_hold/_crash_streak/_SupervisorMemory, места _takes_place, EPIC_IDLE_POLL_SEC, EPIC_CRASH_LIMIT_ACTION; pid+сессия в «auto старт»; AUTO_LEASE_REFUSED_ACTION), pause.py (_last_cycle_stop_is_stop_command), answer.py (_cycle_waits_zone).
- Окно запуска: от записи запуска, сдвиг на «auto старт» с тем же pid (ANSWER-4 п.1); у последнего дочернего — точно по step_id строки epic_children (verify_flow зовёт auto ВНУТРИ launch_child: старт ложится до записи запуска с чужим pid).
- Позиция аварии для счёта: «цикл оборван» либо запись EPIC_CHILD_LOST_ACTION (пишется на опросе, заметившем выход); сбросы — по id записей.
- Планка зелёная: epic_restart 73/73 (3 прогона), answer_wait 7/7; старый файл надзора 44/44 после правки ac9/ac18/ac27/ac30 (ANSWER-1); test_auto_cycle — деталь «auto старт» с pid (ANSWER-3).
- Свой файл tests/test_epic_crash_series_units.py — 4 теста, каждая заявка мутации проверена.
- Карта регенерирована, PLAN.md status: ready, guard ок.

## Не сработало
- bash heredoc с f-строками отклоняется сторожем — правки только Edit/Write.
- pytest -n на стенде надзора: «node down» — гонять без xdist.
- plank-run: «планки нет» — каталог приёмки пуст, планка — долгоживущие файлы tests/.

## Где остановился
- Шаг завершён; код в worktree не закоммичен (коммитит пульт).

## Чего не хватило
- Публичного «состав очереди зоны» в zone_lock — надзор зовёт zone_lock._queue_members/_own_paths.
