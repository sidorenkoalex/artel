---
operator: Alexander Sidorenko
model: unknown
artel_sha: 3a1be8b04e84c819dfba5ec686efbc555847615a
---

# RETRO: 01M4P9PHCTT7TXWF422E3Y9GXN — Стабилизация двух тестов, краснящих CI под нагрузкой (full_suite_limit_runs, test_liveness)

Итог: done, sha af46cc5617e2d639bb2963682b751ae2917c65d4
Адрес артефактов: refs/artifacts/01M4P9PHCTT7TXWF422E3Y9GXN
Суть: Стабилизация двух тестов, краснящих CI под нагрузкой (full_suite_limit_runs, test_liveness) — Два теста стабильно зелёные по отдельности (локально 3 из 3 за ~5 с), но краснят CI в полном наборе (~5000 тестов, xdist) на раннере GitHub (ubuntu) — 11.10.2026 четыре случая (CI ветки 01M4MQAGRWMWR0GFDM9086P3TD, прогон 38123982463; CI main 513ec5da, прогон 38168246062, обе попытки; CI ветки 01M4M67SGNEYMN9F1C7XVX24XE, 38139177114; CI main c47f3c9a, 38139914132), 10.10 — `test_ac3` того же файла на CI мержа 01M4KAYMW2YRFB7G0442WFVSHA.

Стоимость итого: $29.02
  analyst: $3.45, токенов 3011575 (input=82, output=30949, cache_write=286117, cache_read=2694427), провайдер claude, модель claude-opus-5-5
  spec_auditor: $7.72, токенов 7794483 (input=158, output=88281, cache_write=444687, cache_read=7261357), провайдер claude, модель claude-opus-5-5
  test_author: $4.41, токенов 6056805 (input=94, output=91232, cache_write=178315, cache_read=5787164), провайдер claude, модель claude-opus-5-5
  developer: $4.24, токенов 26303400 (input=522, output=15853, cache_write=895859, cache_read=25391166), провайдер claude, модель claude-opus-5-5
  reviewer: $0.51, токенов 309933 (input=12, output=5602, cache_write=43136, cache_read=261183), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 10 тест(ов), 3 manual, 0 skip
