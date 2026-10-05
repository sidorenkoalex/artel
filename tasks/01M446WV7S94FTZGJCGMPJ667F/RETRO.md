---
operator: Alexander Sidorenko
model: unknown
artel_sha: 09c724f9f5fb4422d0d5fc967d92d23d8f1ad2f5
---

# RETRO: 01M446WV7S94FTZGJCGMPJ667F — Клон проекта получает ссылки документов задач; doctor не шумит на свежем клоне

Итог: done, sha 09c724f9f5fb4422d0d5fc967d92d23d8f1ad2f5
Адрес артефактов: refs/artifacts/01M446WV7S94FTZGJCGMPJ667F
Суть: Клон проекта получает ссылки документов задач; doctor не шумит на свежем клоне — После сдвига пина на этап 2 ADR-0021 клон проекта (`orchestrator/workspace.py::ensure_clone`) заводится без ссылок `refs/artifacts/*`: `git clone` их не приносит, отдельного fetch нет.

Стоимость итого: $8.71
  analyst: $1.01, токенов 846622 (input=20, output=10032, cache_write=82824, cache_read=753746), провайдер claude, модель claude-opus-5-5
  test_author: $2.58, токенов 3683037 (input=82, output=45425, cache_write=121186, cache_read=3516344), провайдер claude, модель claude-opus-5-5
  developer: $4.36, токенов 7697488 (input=132, output=42710, cache_write=253379, cache_read=7401267), провайдер claude, модель claude-opus-5-5
  reviewer: $0.75, токенов 581600 (input=18, output=8693, cache_write=58876, cache_read=514013), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 5 тест(ов), 0 manual, 0 skip
