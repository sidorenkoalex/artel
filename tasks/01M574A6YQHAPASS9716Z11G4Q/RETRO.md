---
operator: Alexander Sidorenko
model: unknown
artel_sha: 6019e42164a3846d57d665cae6ca56336a45acc3
---

# RETRO: 01M574A6YQHAPASS9716Z11G4Q — CI внешнего проекта при токене без права Checks: итог по Actions runs и проверка прав токена в doctor

Итог: done, sha 0bc8e3ee8127e54ad1609bad42a2f09f53621e9a
Адрес артефактов: refs/artifacts/01M574A6YQHAPASS9716Z11G4Q
Суть: CI внешнего проекта при токене без права Checks: итог по Actions runs и проверка прав токена в doctor — Живой случай 18.10 (задача sled 01M55SKHZ293CCAK0N7T4H7ZMR, пин 03fa6903): персональный токен проекта sled получает HTTP 403 «Resource not accessible by personal access token» на `GET /repos/{owner}/{repo}/commits/{sha}/check-runs` (`orchestrator/ci.py:224` `check_runs_page`, `:250` `check_runs`), а `gh run list` (Actions) ему доступен.

Стоимость итого: $20.60
  analyst: $3.83, токенов 3795593 (input=84, output=40888, cache_write=289485, cache_read=3465136), провайдер claude, модель claude-opus-5-5
  spec_auditor: $5.26, токенов 6596402 (input=122, output=59202, cache_write=354305, cache_read=6182773), провайдер claude, модель claude-opus-5-5
  test_author: $5.34, токенов 10340804 (input=134, output=79598, cache_write=217226, cache_read=10043846), провайдер claude, модель claude-opus-5-5
  developer: $5.21, токенов 8379148 (input=128, output=41604, cache_write=346893, cache_read=7990523), провайдер claude, модель claude-opus-5-5
  reviewer: $0.97, токенов 776731 (input=18, output=9636, cache_write=79868, cache_read=687209), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
