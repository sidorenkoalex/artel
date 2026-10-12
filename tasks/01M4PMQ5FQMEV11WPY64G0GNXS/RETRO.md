---
operator: Alexander Sidorenko
model: unknown
artel_sha: 3a1be8b04e84c819dfba5ec686efbc555847615a
---

# RETRO: 01M4PMQ5FQMEV11WPY64G0GNXS — Итог прогона и провал внутри subTest — в отчёте suite-run и перечнях упавших

Итог: done, sha 4499bee674c4601d2c92e6540569f51af2f0ca48
Адрес артефактов: refs/artifacts/01M4PMQ5FQMEV11WPY64G0GNXS
Суть: Итог прогона и провал внутри subTest — в отчёте suite-run и перечнях упавших — Прогон 11.10 (задача 01M4M67SGN, прогоны №3 и №4) завершился итогом pytest `1 failed, 4936 passed, 2 skipped, 2144 subtests passed in 436.40s` и строкой короткого итога `SUBFAILED[merge_gate] tests/test_invariants.py::ManualGatesNeedTheOperatorTest::test_operator_approve_passes_each_gate - …`, а отчёт `suite-run` сказал «красный прогон, прошло: 1, упало: 0», `failed.json` — `{"run": 4, "failed": []}`.

Стоимость итого: $14.52
  analyst: $2.45, токенов 2598444 (input=60, output=27830, cache_write=177219, cache_read=2393335), провайдер claude, модель claude-opus-5-5
  spec_auditor: $4.40, токенов 6490127 (input=116, output=56007, cache_write=255468, cache_read=6178536), провайдер claude, модель claude-opus-5-5
  test_author: $3.75, токенов 5841198 (input=84, output=56859, cache_write=186285, cache_read=5597970), провайдер claude, модель claude-opus-5-5
  developer: $2.71, токенов 4883802 (input=76, output=29369, cache_write=147472, cache_read=4706885), провайдер claude, модель claude-opus-5-5
  reviewer: $1.21, токенов 1140412 (input=28, output=16774, cache_write=82882, cache_read=1040728), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
