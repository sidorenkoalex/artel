# RETRO: 01M3NSZ4YWZW9SD5Y6H62ATGRV — amend-tests для долгоживущих файлов в tests/ и исключение их из диффа ревью (ADR-0020, задача 3)

Итог: done, sha 16ebe59244a9c1e981d6bc66877478a12504418c
Адрес артефактов: 16ebe59244a9c1e981d6bc66877478a12504418c:tasks/01M3NSZ4YWZW9SD5Y6H62ATGRV/
Суть: amend-tests для долгоживущих файлов в tests/ и исключение их из диффа ревью (ADR-0020, задача 3) — После задачи 2 внедрения ADR-0020 (01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ) долгоживущие приёмочные тесты задачи лежат в `tests/` кодовой ветки под префиксом `guard.long_lived_path_prefix(<id>)`, их суммы — в перечне `tasks/<id>/acceptance_tests/long_lived.sha256.txt` ветки документов под локом `tasks.tests_locked_sha`; сверка сумм стоит на переходах после `tests_writing` и на гейте мержа.

Стоимость итого: $20.96
  analyst: $1.83, токенов 2031711 (input=40, output=21600, cache_write=127701, cache_read=1882370), провайдер claude, модель claude-opus-5-5
  test_author: $6.07, токенов 12206654 (input=138, output=88512, cache_write=240531, cache_read=11877473), провайдер claude, модель claude-opus-5-5
  developer: $7.54, токенов 18310949 (input=254, output=123312, cache_write=637269, cache_read=17550114), провайдер claude, модель claude-opus-5-5
  reviewer: $1.91, токенов 2161247 (input=64, output=22387, cache_write=133084, cache_read=2005712), провайдер claude, модель claude-opus-5-5

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 21 тест(ов), 0 manual, 0 skip
