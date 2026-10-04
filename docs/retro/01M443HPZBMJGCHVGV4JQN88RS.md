# RETRO: 01M443HPZBMJGCHVGV4JQN88RS — Тесты не подменяют time.sleep на весь процесс

Итог: done, sha 971ba997cd21c6c8079a8bb9582cf59fdd2783bb
Адрес артефактов: 971ba997cd21c6c8079a8bb9582cf59fdd2783bb:tasks/01M443HPZBMJGCHVGV4JQN88RS/
Суть: Тесты не подменяют time.sleep на весь процесс — Тесты в `tests/` подменяют паузу `time.sleep` модуля стандартной библиотеки `time` целиком: `mock.patch("time.sleep")`, `mock.patch.object(time, "sleep", …)` или `mock.patch.object(<модуль пульта>.time, "sleep", …)` (у модулей пульта `time` — сам модуль стандартной библиотеки).

Стоимость итого: $10.33
  analyst: $1.28, токенов 1142474 (input=26, output=16232, cache_write=92981, cache_read=1033235), провайдер claude, модель claude-opus-5-5
  test_author: $2.79, токенов 4150214 (input=90, output=52077, cache_write=119188, cache_read=3978859), провайдер claude, модель claude-opus-5-5
  developer: $5.24, токенов 10295341 (input=156, output=54410, cache_write=269334, cache_read=9971441), провайдер claude, модель claude-opus-5-5
  reviewer: $1.02, токенов 1277346 (input=34, output=10440, cache_write=71998, cache_read=1194874), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 4 тест(ов), 0 manual, 0 skip

Приложения Оператора применены: tests/test_invariants.py
