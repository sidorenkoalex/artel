---
task: 01M1TKNXX5YN5KT4WHG4T44JWV
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

# ANSWER-1: ответ Оператора

## Ответы

1. Эскалация «конфликт подтяжки main»: четыре конфликтных участка в
   `orchestrator/fsm_advance.py` (строки около 336–448, 647–671, 684–712,
   841–882 при пробном слиянии) плюс `docs/codebase-map.md`. Пока шёл
   рефакторинг, в main смержены две правки тех же гейтов: «гейты зон и
   ёмкости: база сравнения — точка расхождения с origin/main»
   (01M1SG9T962WJJ31S282GWM0EN, коммит 23074062: база сравнения диффа —
   merge-base с origin/main, полный дифф ревью) и «пометка критерия ci —
   guard распознаёт» (01M1SHJTT0V516BWHYXWS50F3G, коммит 1d8a1b6b).
   Сделай: `git merge main` в worktree, разреши конфликты так, чтобы
   поведение обеих правок main сохранилось байт-в-байт (база сравнения
   через merge-base, тексты отказов с «база сравнения …», пометка `ci`),
   а структура предикатов и каркаса из твоего коммита dc3f99f4 осталась.
   Карту (`docs/codebase-map.md`) взять из main и перегенерировать
   `python3 scripts/codebase_map.py`. Проверь: планка задачи, юнит-тесты
   каркаса, `tests/test_zones_gate.py`, `tests/test_capacity_gate*.py`,
   `tests/test_review_rework_gate.py`, планки 01M1SG9T962WJJ31S282GWM0EN
   и 01M1SHJTT0V516BWHYXWS50F3G (в main, `tasks/<id>/acceptance_tests`)
   — все зелёные. Полный `tests/` не запускай. Смоук-фикстура AC-9
   снята до правки — сценарии сверять с ней, не пересоздавать.
