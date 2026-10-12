---
operator: Alexander Sidorenko
model: unknown
artel_sha: 3a1be8b04e84c819dfba5ec686efbc555847615a
---

# RETRO: 01M4PMPMZ7PPCN3JWX75RTJZQN — База сравнения джоба защищённых путей — первый родитель merge-коммита PR

Итог: done, sha 6e9fef362551d1b1b46c01777905738ae5565a4d
Адрес артефактов: refs/artifacts/01M4PMPMZ7PPCN3JWX75RTJZQN
Суть: База сравнения джоба защищённых путей — первый родитель merge-коммита PR — Джоб `protected-paths` (`.github/workflows/ci.yml:290-318`) передаёт `BASE_SHA` = `github.event.pull_request.base.sha` в `scripts/ci_protected_paths.py`, а тот берёт перечень `PROTECTED_PATHS` из `orchestrator/config.py` базы (`base_protected_paths`, `scripts/ci_protected_paths.py:123`) и дифф `git diff --name-only <base>...HEAD` (`changed_files`, `:135`). `base.sha` события фиксируется при открытии/обновлении PR и устаревает: коммит Оператора в main по защищённому пути после этого (11.10.2026: 9002a77d, `docs/adr/0022-handoff-audit.md`) попадает в дифф как изменение PR, и джоб красный у всех открытых PR (прогон 38124848279, PR #259). `ci-rerun` несёт тот же payload события и не лечит.

Стоимость итого: $11.57
  analyst: $2.66, токенов 1903817 (input=56, output=18881, cache_write=244103, cache_read=1640777), провайдер claude, модель claude-opus-5-5
  spec_auditor: $5.02, токенов 5509387 (input=136, output=63153, cache_write=342230, cache_read=5103868), провайдер claude, модель claude-opus-5-5
  test_author: $1.83, токенов 2105764 (input=52, output=33470, cache_write=95159, cache_read=1977083), провайдер claude, модель claude-opus-5-5
  developer: $1.28, токенов 1628729 (input=38, output=13777, cache_write=87226, cache_read=1527688), провайдер claude, модель claude-opus-5-5
  reviewer: $0.79, токенов 663854 (input=22, output=11335, cache_write=55103, cache_read=597394), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 1 тест(ов), 0 manual, 0 skip
