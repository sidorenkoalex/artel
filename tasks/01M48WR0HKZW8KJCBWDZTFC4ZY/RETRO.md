---
operator: Alexander Sidorenko
model: unknown
artel_sha: 73ce3329623c28c45df79a2dd363bde3b1e30b6d
---

# RETRO: 01M48WR0HKZW8KJCBWDZTFC4ZY — Тесты не спят в паузе повтора агента (ревизия тестов TR-1)

Итог: done, sha 73ce3329623c28c45df79a2dd363bde3b1e30b6d
Адрес артефактов: refs/artifacts/01M48WR0HKZW8KJCBWDZTFC4ZY
Суть: Тесты не спят в паузе повтора агента (ревизия тестов TR-1) — `orchestrator/runner.py::_run_attempts` между попытками агента вызывает `time.sleep(backoff_sec)`: пауза — `config.RETRY_BACKOFF_SEC * 2 ** (attempt - 1)` (`RETRY_BACKOFF_SEC = 5`) либо `config.TRANSIENT_SYSTEM_BACKOFF_SEC` (120) для системных классов сбоя; при `AGENT_ATTEMPTS = 3` неуспешный шаг в песочнице ждёт 5 + 10 с.

Стоимость итого: $9.50
  analyst: $1.81, токенов 1403161 (input=32, output=12132, cache_write=165266, cache_read=1225731), провайдер claude, модель claude-opus-5-5
  test_author: $3.83, токенов 7478527 (input=140, output=59841, cache_write=146939, cache_read=7271607), провайдер claude, модель claude-opus-5-5
  developer: $3.12, токенов 6375497 (input=94, output=31972, cache_write=155497, cache_read=6187934), провайдер claude, модель claude-opus-5-5
  reviewer: $0.74, токенов 736603 (input=26, output=9739, cache_write=51592, cache_read=675246), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 5 тест(ов), 0 manual, 0 skip
