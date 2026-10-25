---
task: 01M5RHGRH3YJV8VBFH3QCHD8X0
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Сведение тестов, волна 3м-2б — шесть файлов merge_after в tests/test_merge_after_module.py

## Что изменилось с итерации 1
- 01fa9ab3 «подтяжка main»: принесла волну 2а-2б (outcome_components). `git diff --stat 8d6a6cb1 HEAD -- orchestrator scripts` пуст, поэтому деревья кода обеих шапок `mutation-run` по-прежнему совпадают (требование 13) и прогонять «до» заново не нужно.
- 390a47ca: в докстринге `test_ac1_self_reference_names_field_and_element` (`tests/test_merge_after_module.py:1230`, `:1237`) возвращено имя поля `task:` вместо `task_id:`. Это закрывает наблюдение итерации 1. Утверждения не менялись. Ещё в коммите — строка `built_at_sha` карты.

## Фаза A — план
Без изменений с итерации 1: таблица покрытия называет шаг на каждое из 17 требований, шаги проверяемые, подход не расходится с ADR-0020, ADR-0027 и ANSWER-1/2.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Патчи 001–050 и PLAN не менялись с итерации 1. Мутация 029 применена повторно, патч применяется. |
| 2 | OK | Таблицы «до» прежние. Планка `test_mutation_tables.py` зелёная. |
| 3 | OK | Как в итерации 1. |
| 4 | OK | Как в итерации 1. |
| 5 | OK | Как в итерации 1. Находки 026, «id сортируются» (ac5 spec_gate) и «склейка следующей строки» (ac2 new_declares) названы, тесты не удалены. |
| 6 | OK | Как в итерации 1. |
| 7 | OK | `git status --porcelain` пуст до и после прогонов шага. |
| 8 | OK | Дифф модуля против main — только добавления: 0 строк `-`, новых `skip`/`xfail` нет. |
| 9 | OK | Правка докстринга вернула имя поля фронтматтера `task:`. Переименование локальной `task`→`task_id` в коде осталось, как требует SPEC. |
| 10 | OK | Как в итерации 1. |
| 11 | OK | Как в итерации 1. |
| 12 | OK | Дублей не удалено, 53 теста. |
| 13 | OK | `orchestrator/` и `scripts/` после подтяжки main не изменились. |
| 14 | OK | Как в итерации 1. |
| 15 | OK | В диффе ветки против main удалены ровно шесть путей мандата, модуль изменён, карта перегенерирована. |
| 16 | OK | `git diff --name-status main...HEAD` — только семь путей задачи и `docs/codebase-map.md`. Перегенерированная карта отличается от закоммиченной только строкой `built_at_sha`. |
| 17 | — | Вне роли (сессия при Операторе). |

## Замечания
Замечаний уровня blocker/major нет. Наблюдение итерации 1 о докстринге закрыто коммитом 390a47ca. Неточность перечня PLAN (`spec_gate_declared_refusal_spec_text`) и форматирование висячих строк — прежние, на уровне вкуса.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: ни в итерации 1, ни сейчас замечаний blocker/major не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_merge_after_module.py -p no:cacheprovider -q` — 53 passed за 5.44 с.
- `artel.py plank-run 01M5RHGRH3YJV8VBFH3QCHD8X0` — 76 passed, код выхода pytest 0.
- Временная мутация `git apply mutation-029.diff` (`merge_after.py`: при отсутствии поля значение `"None"` вместо `None`) → модуль: 2 failed (`test_ac5_spec_without_field_leaves_column_empty`, `test_ac14_show_without_dependencies_has_no_line`), 51 passed. Код возвращён `git checkout -- orchestrator scripts`, `git status --porcelain` пуст.
- `git diff --stat 8d6a6cb1 HEAD -- orchestrator scripts` — пусто: подтяжка main код не тронула.
- `git diff main...HEAD -- tests/test_merge_after_module.py | grep -c '^-[^-]'` → 0.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md`: расхождение только в `built_at_sha`, после проверки сброшено `git checkout`.

## Предложения системе
- Итерация 2 понадобилась только потому, что гейт не принял повторно уже учтённый вердикт итерации 1. Это случилось после автокоммита пульта с правкой одного докстринга. Пакет не смог определить базу инкрементального диффа и показал полный дифф. Если бы пакет называл коммиты после прошлого вердикта, итерация сократилась бы до сверки этих коммитов.
