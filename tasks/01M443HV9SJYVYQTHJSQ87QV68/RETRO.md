---
operator: Alexander Sidorenko
model: unknown
artel_sha: 9acc222c40d47f8f35bccc0a98edec1b91384e99
---

# RETRO: 01M443HV9SJYVYQTHJSQ87QV68 — CI ветки задачи проверяет код вместе с приложениями PLAN

Итог: done, sha 9acc222c40d47f8f35bccc0a98edec1b91384e99
Адрес артефактов: refs/artifacts/01M443HV9SJYVYQTHJSQ87QV68
Суть: CI ветки задачи проверяет код вместе с приложениями PLAN — `verifying` ждёт зелёного CI головы ветки задачи (`orchestrator/fsm_advance.py::verifying`), а приложения PLAN к защищённым путям накладывают только ворота мержа (`orchestrator/fsm_merge_gate.py::_apply_plan_appendices`: `git apply` в рабочей копии мержа, затем полный прогон `tests/`).

Стоимость итого: $13.45
  analyst: $1.27, токенов 1097359 (input=24, output=13695, cache_write=99692, cache_read=983948), провайдер claude, модель claude-opus-5-5
  test_author: $6.90, токенов 14022300 (input=214, output=98384, cache_write=275327, cache_read=13648375), провайдер claude, модель claude-opus-5-5
  developer: $4.35, токенов 7979202 (input=116, output=42156, cache_write=246156, cache_read=7690774), провайдер claude, модель claude-opus-5-5
  reviewer: $0.93, токенов 835459 (input=22, output=10191, cache_write=72169, cache_read=753077), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 1 (последняя): test_author: критерий неисполним тестом — AC-7: AC-7 требует в PLAN приложение к docs/operator-session.md, но этот путь не входит в config.PROTECTED_PATHS: guard.plan_appendices отвергает такой блок ошибкой «путь docs/operator-session.md не защищённый — правь в ветке задачи», гейт выхода из in_dev и ворота мержа не пропускают PLAN с ошибкой разбора, а «Не входит» SPEC запрещает и приложения к путям вне защищённого списка, и правку docs/operator-session.md в ветке (её нет в зонах). Как быть с описанием в docs/operator-session.md? Варианты: (а) правка docs/operator-session.md в ветке задачи — путь добавляется в зоны, AC-7 проверяет приложение к ci.yml и правку документа в диффе ветки; (б) Оператор вносит docs/operator-session.md в config.PROTECTED_PATHS до задачи, AC-7 остаётся как есть; (в) описание в docs/operator-session.md из задачи убирается, AC-7 — только приложение к ci.yml. Дефолт при молчании — (а).

Приёмочные тесты: 3 тест(ов), 0 manual, 0 skip
