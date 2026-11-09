# Записка developer — 01M6ZEMZB8Q1PKRXMJBJSTPR7T

## Выяснено
- Возврат ANSWER-3: обёртка `WRAPPER` в tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py — скрипт с `#!`,
  имя проходит `_INTERPRETER_NAME`; запрос/сборка шаблона запускали её.
- Правка: `acceptance._is_script` (первые 2 байта после realpath == `#!`, нечитаемый — тоже скрипт);
  `_warm_prefix` молча выходит. Новый тест — tests/test_acceptance_pycache_script.py (отдельный файл,
  долгоживущие залочены). Мутация (снять `_is_script`) — красный.
- suite_run целиком, template_rules/runs, pycache, acceptance_pycache — 124 passed. Карта перегенерирована.

## Не сработало
- `sed -i` в Bash требует подтверждения — мутации делать через Edit.

## Где остановился
- Шаг сдан: PLAN ready, раздел «Возврат из verifying (ANSWER-3)».

## Чего не хватило
- Ничего существенного.
