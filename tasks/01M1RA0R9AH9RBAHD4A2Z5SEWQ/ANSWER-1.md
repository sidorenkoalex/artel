---
task: 01M1RA0R9AH9RBAHD4A2Z5SEWQ
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

# ANSWER-1

Эскалация «приёмочные тесты красные после подтяжки main» — это не конфликт
подтяжки, а незавершённая реализация. Прогон планки на коде ветки
(8d3f2f11) даёт 3 падения из 7:

- `test_ac2_non_map_wip_committed_as_checkpoint_before_pull`
- `test_ac3_checkpoint_alone_does_not_escalate_the_transition`
- `test_ac5_non_map_wip_worktree_pulls_main_after_checkpoint`
  (все три: `AssertionError: 'in_dev' != 'review'`).

AC-1, AC-4, AC-6 (только карта грязная — сброс через checkout, инцидент
уборки) зелёные. Не реализована часть SPEC про НЕ-картовые незакоммиченные
правки кода в worktree: перед подтяжкой main они должны уходить WIP-коммитом
(тем же механизмом, что чекпоинт после таймаута), после чего подтяжка и
переход в review проходят без эскалации.

Доработай реализацию до зелёной планки целиком, PLAN.md обнови. Прогон
планки — `python3 -m unittest discover -s tasks/<id>/acceptance_tests` из
корня worktree; полный `tests/` не запускай (это делает CI).
