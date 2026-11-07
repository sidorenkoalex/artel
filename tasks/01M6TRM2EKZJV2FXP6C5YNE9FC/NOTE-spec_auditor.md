# Записка spec_auditor

## Выяснено
- Вердикт concerns, SPEC-AUDIT.md готов, guard зелёный.
- Проверено опытом: подменил `_await_main_ci` однократным чтением, а
  `_refuse_if_main_red` — ожиданием по треб. 2. Краснеют два теста:
  - `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py:776` `test_ac4_green_after_running_is_reported_green`;
  - `:831` `test_ac4_unfinished_ci_is_reported_after_15_to_20_minutes`.

  SPEC их не называет. По ТЗ это эскалация с именем теста.
- 16 прочих модулей гейта мержа (85 тестов) и `tests/test_main_ci_line.py::AwaitMainCiUnknownTest`
  зелёные. Последний — только если текст «неизвестно» по-прежнему
  содержит «не дождался».
- Образец подставных часов (`monotonic` двигает пауза) —
  `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py:201-211,231-234`.

## Не сработало
- В /tmp писать нельзя, heredoc в Bash не разбирается. Временный раннер
  положил в каталог документов и убрал командой `task-rm`.

## Где остановился
- Аудит завершён.

## Чего не хватило
- SPEC проверял только тесты из «только чтение» ТЗ. Тест, закрепляющий
  ожидание после мержа, нашёлся поиском по `MAIN_CI` в `tests/`
  (файл исходной задачи 01M3SF7DPFGEZ7VYEGGXGTX49E).
