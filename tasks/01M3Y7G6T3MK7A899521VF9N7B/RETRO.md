---
operator: Alexander Sidorenko
model: unknown
artel_sha: 28b093892e0ac662389afb696efbb664e37d43fe
---

# RETRO: 01M3Y7G6T3MK7A899521VF9N7B — Прогоны pytest пульта не исполняют устаревший байткод из worktree

Итог: done, sha 28b093892e0ac662389afb696efbb664e37d43fe
Адрес артефактов: refs/artifacts/01M3Y7G6T3MK7A899521VF9N7B
Суть: Прогоны pytest пульта не исполняют устаревший байткод из worktree — 02.10 08:32Z автогейт приёмки задачи 01M3XTF1CEBXT4J7P0EKG5J342 дал «2 failed» на исправном коде: полный набор `tests/` в worktree исполнил устаревший `orchestrator/__pycache__/fsm_advance.cpython-313.pyc`.

Стоимость итого: $4.19
  analyst: $0.77, токенов 708888 (input=20, output=6144, cache_write=64690, cache_read=638034), провайдер claude, модель claude-opus-5-5
  test_author: $1.36, токенов 1701631 (input=48, output=20501, cache_write=78848, cache_read=1602234), провайдер claude, модель claude-opus-5-5
  developer: $1.50, токенов 1981888 (input=40, output=16141, cache_write=100065, cache_read=1865642), провайдер claude, модель claude-opus-5-5
  reviewer: $0.56, токенов 402649 (input=16, output=7138, cache_write=43496, cache_read=351999), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 1 тест(ов), 0 manual, 0 skip
