# RETRO: 01M48WTP12VC8MY2BNE5JSVXKA — Вынос повторяющейся подготовки тестов в tests/sandbox.py (ревизия тестов TR-23..25)

Итог: done, sha ac07b8843afbc00c9efee0cedd09f3d6a917ffbe
Адрес артефактов: ac07b8843afbc00c9efee0cedd09f3d6a917ffbe:tasks/01M48WTP12VC8MY2BNE5JSVXKA/
Суть: Вынос повторяющейся подготовки тестов в tests/sandbox.py (ревизия тестов TR-23..25) — Ревизия тестов 05.10 (`docs/audits/tests-revision-2026-10-05.md`, TR-3, TR-23, TR-24, TR-25, план п. 4) нашла, что основания песочницы `TmpRootTest` (~1 522 метода) и `RealGitSandbox` (~691) заново строят git-репозиторий в каждом `setUp`: `git init` заглушки клона — 34 мс, однокоммитный репозиторий `RealGitSandbox` — 119 мс, а копия готового репозитория `shutil.copytree` — 14 мс (оценка выигрыша ≈ 100 с работы процессов, ≈ 25 с по стене при `-n 4`).

Стоимость итого: $7.90
  analyst: $1.02, токенов 809291 (input=18, output=8522, cache_write=87980, cache_read=712771), провайдер claude, модель claude-opus-5-5
  test_author: $0.79, токенов 2218126 (input=80366, output=20128, cache_write=0, cache_read=2117632), провайдер codex, модель gpt-6-sol
  developer: $4.42, токенов 14739636 (input=520829, output=54711, cache_write=0, cache_read=14164096), провайдер codex, модель gpt-6-sol
  reviewer: $1.68, токенов 1829483 (input=54, output=19306, cache_write=119026, cache_read=1691097), провайдер claude, модель claude-opus-5-5

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: 1 (последняя): эскалация от разработчика: ### Вопросы…

Приёмочные тесты: 5 тест(ов), 0 manual, 0 skip
