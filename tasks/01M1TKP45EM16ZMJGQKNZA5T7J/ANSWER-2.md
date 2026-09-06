---
task: 01M1TKP45EM16ZMJGQKNZA5T7J
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

# ANSWER-2: ответ Оператора

## Ответы

1. Эскалация «конфликт подтяжки main»: конфликтные файлы
   `scripts/guard.py` (один участок), `tests/test_fsm_map_conflict_
   autoresolve.py` (один участок, импорты) и `docs/codebase-map.md`.
   Пока шла задача, в main смержена «рабочие файлы роли не доезжают до
   артефактной ветки и main» (01M1TNN4TMWAQSQ9Y1PW37J5H0): в том же блоке
   `guard.py` она собирает второй список посторонних файлов корня задачи
   (`EXTRANEOUS_TASK_ROOT_FILE_REASON`, `task_root_extraneous`).
   Сделай: `git merge main` в worktree; в `guard.py` сохранить обе правки
   — список ошибок из main (`extraneous` + `task_root_extraneous`) и
   твой сбор предупреждений `sandbox_reuse_check` по каталогам задач;
   в тесте — импорты эталона (`LightTransitionSandbox`) поверх версии
   main, лишние имена из main убрать, если после перевода они не нужны;
   карту взять из main и перегенерировать `python3 scripts/codebase_map.py`.
   Проверь планку задачи, оба переведённых теста, `tests/test_guard*.py`
   и планку 01M1TNN4TMWAQSQ9Y1PW37J5H0 (в main,
   `tasks/<id>/acceptance_tests`). Полный `tests/` не запускай.
   Бюджет поднят до $45.
