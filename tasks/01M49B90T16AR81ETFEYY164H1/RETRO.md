---
operator: Alexander Sidorenko
model: unknown
artel_sha: d75f27aef4215d8739db191328a23987cb120bec
---

# RETRO: 01M49B90T16AR81ETFEYY164H1 — CI ветки задачи — полный набор tests/ один раз на sha

Итог: done, sha d75f27aef4215d8739db191328a23987cb120bec
Адрес артефактов: refs/artifacts/01M49B90T16AR81ETFEYY164H1
Суть: CI ветки задачи — полный набор tests/ один раз на sha — Каждый push ветки `task/**` с открытым черновиком PR запускает workflow `ci` дважды — на событие `push` и на событие `pull_request`, — и задания полного набора `python` и `python-min` (`.github/workflows/ci.yml`, ~179 и ~232) идут в обоих прогонах: условие на них только `needs.changes.outputs.code != 'false'`.

Стоимость итого: $10.36
  analyst: $1.75, токенов 1217125 (input=28, output=11788, cache_write=163040, cache_read=1042269), провайдер claude, модель claude-opus-5-5
  test_author: $2.91, токенов 3408820 (input=56, output=52782, cache_write=151767, cache_read=3204215), провайдер claude, модель claude-opus-5-5
  developer: $3.33, токенов 9989337 (input=462552, output=51329, cache_write=0, cache_read=9475456), провайдер codex, модель gpt-6-sol
  reviewer: $2.37, токенов 2075166 (input=62, output=27329, cache_write=180930, cache_read=1866845), провайдер claude, модель claude-opus-5-5

Ревью: 1 итераций; приёмка: 1 отказ(ов)

Эскалации: 1 (последняя): эскалация от разработчика: - **Вопросы** — Нужен мандат на смену утверждения `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py::CiStatusNamesRunEventTest::test_ac8_parsers_keep_outcomes_on_the_new_text`: в зелёном раскладе `build({x: "success"}, {x: "success", y: "skipped"})` метод безусловно требует `VERIFYING_GREEN`, но `y` случайно выбирается в том числе именем задания полного набора. Вариант А (предпочтительный): ограничить зелёный расклад этого метода именами проверок вне перечня полного набора, сохранив все проверки текста и парсеров; вариант Б: разрешить изменение ожидаемого исхода в этом подслучае на `VERIFYING_RUNNING`. По умолчанию при молчании — не менять существующий тест и оставить задачу на эскалации.…

Приёмочные тесты: 1 тест(ов), 3 manual, 0 skip
