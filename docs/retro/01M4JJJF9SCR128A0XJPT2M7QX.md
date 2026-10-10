# RETRO: 01M4JJJF9SCR128A0XJPT2M7QX — Подсчёт членов группы процессов: сбой ps не равен пустой группе

Итог: done, sha 93feb647a619d1ed9564391578dcca4e29d2d247
Адрес артефактов: 93feb647a619d1ed9564391578dcca4e29d2d247:tasks/01M4JJJF9SCR128A0XJPT2M7QX/
Суть: Подсчёт членов группы процессов: сбой ps не равен пустой группе — `orchestrator/liveness.py::_group_member_count` (~70–83) считает членов группы через `ps -o pid= -g <pgid>` с `timeout=5` и при `OSError`, `TimeoutExpired` и ненулевом коде возврата отдаёт 0 — так же, как для пустой группы. `terminate_process_group` (~86–120) по этому числу решает, ждать ли дальше и слать ли `SIGKILL` (~112–116): сбой `ps` читается как «группа пуста», выжившим не посылается `SIGKILL`, а вызывающий получает 0 «снятых». 10.10.2026 в suite-run задачи 01M4JC58GZFHZ4PZHW254P22M2 (`-n auto`, load average 10–14) оба прогона упали на `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count` («0 not greater than or equal to 1»); отдельно тот же класс зелёный 3 из 3, полный прогон автогейта 01M4JD3SRN — зелёный: падение неустойчиво.

Стоимость итого: $4.79
  analyst: $1.10, токенов 1265991 (input=34, output=13983, cache_write=73240, cache_read=1178734), провайдер claude, модель claude-opus-5-5
  test_author: $1.56, токенов 1347097 (input=52, output=22955, cache_write=106957, cache_read=1217133), провайдер claude, модель claude-opus-5-5
  developer: $1.47, токенов 2318765 (input=56, output=16534, cache_write=87142, cache_read=2215033), провайдер claude, модель claude-opus-5-5
  reviewer: $0.66, токенов 578544 (input=22, output=8830, cache_write=47034, cache_read=522658), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
