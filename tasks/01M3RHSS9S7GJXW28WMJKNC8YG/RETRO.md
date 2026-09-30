---
operator: Alexander Sidorenko
model: unknown
artel_sha: 6925e43d85b52cd7375997e0e2aa7060c8424b0e
---

# RETRO: 01M3RHSS9S7GJXW28WMJKNC8YG — Тест таймаута прогона приёмочных тестов не зависит от порядка тестов

Итог: done, sha 6925e43d85b52cd7375997e0e2aa7060c8424b0e
Адрес артефактов: refs/artifacts/01M3RHSS9S7GJXW28WMJKNC8YG
Суть: Тест таймаута прогона приёмочных тестов не зависит от порядка тестов — `tests/test_acceptance_tests_flow.py::AcceptanceRunTest::test_timeout_blocks_the_transition_and_names_the_limit` (стр. 1037–1062 на пине 6925e43d) подменяет `subprocess.run` модуля `orchestrator/acceptance.py` целиком — это общий объект модуля `subprocess`, подмена действует на все вызовы процесса — и сверяет `timeout` ПОСЛЕДНЕГО вызова (`run_mock.call_args`) с `config.ACCEPTANCE_TIMEOUT_SEC`.

Стоимость итого: $3.60
  analyst: $0.72, токенов 610092 (input=18, output=5794, cache_write=61758, cache_read=542522), провайдер claude, модель claude-opus-5-5
  test_author: $1.09, токенов 1190883 (input=42, output=19746, cache_write=59161, cache_read=1111934), провайдер claude, модель claude-opus-5-5
  developer: $1.34, токенов 2108290 (input=48, output=11606, cache_write=88533, cache_read=2008103), провайдер claude, модель claude-opus-5-5
  reviewer: $0.44, токенов 366669 (input=18, output=5513, cache_write=33540, cache_read=327598), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 5 тест(ов), 0 manual, 0 skip
