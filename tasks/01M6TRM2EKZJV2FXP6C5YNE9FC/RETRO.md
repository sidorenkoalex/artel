---
operator: Alexander Sidorenko
model: unknown
artel_sha: 8f5ee80ed80a6f967c8323471130ba958ba5d6a4
---

# RETRO: 01M6TRM2EKZJV2FXP6C5YNE9FC — Мерж не ждёт CI main под замком: цвет main сверяет следующий мерж, идущий CI main он дожидается

Итог: done, sha f7f5f75e279dd27669270d338a95cc5e97ed2800
Адрес артефактов: refs/artifacts/01M6TRM2EKZJV2FXP6C5YNE9FC
Суть: Мерж не ждёт CI main под замком: цвет main сверяет следующий мерж, идущий CI main он дожидается — После отправки мержа в `main` гейт мержа ждёт CI новой головы `main` под замком мержа: `fsm_merge_gate._await_main_ci` (`orchestrator/fsm_merge_gate.py:653-692`, вызов `:1570`), предел `MAIN_CI_WAIT_LIMIT_SEC` = 18 мин (`:56`), опрос `ci.main_line_status`, продление heartbeat замка, исход — запись журнала «CI main после мержа» (`MAIN_CI_AFTER_MERGE_ACTION`, `:63`).

Стоимость итого: $22.40
  analyst: $5.19, токенов 4627393 (input=98, output=37589, cache_write=451206, cache_read=4138500), провайдер claude, модель claude-opus-5-5
  spec_auditor: $9.85, токенов 13486664 (input=236, output=112012, cache_write=633048, cache_read=12741368), провайдер claude, модель claude-opus-5-5
  test_author: $4.38, токенов 8306522 (input=112, output=59986, cache_write=195769, cache_read=8050655), провайдер claude, модель claude-opus-5-5
  developer: $2.15, токенов 293289 (input=6, output=1384, cache_write=1339, cache_read=290560), провайдер claude, модель claude-opus-5-5
  reviewer: $0.83, токенов 697706 (input=20, output=9275, cache_write=64733, cache_read=623678), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
