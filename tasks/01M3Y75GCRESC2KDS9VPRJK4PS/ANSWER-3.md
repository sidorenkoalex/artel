---
task: 01M3Y75GCRESC2KDS9VPRJK4PS
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

Расширение зон разрешено: orchestrator/cycle_hint.py

1. Правка `orchestrator/cycle_hint.py` (функция `cycle_command`) принята по существу, но не закоммичена: пульт отказал переходу «посторонние файлы в worktree», потому что в PLAN.md нет раздела расширения зон, и БД зону не получила.
2. Добавь в PLAN.md раздел ровно в этом виде (строка «Пути:» разбирается кодом):

## Расширение зон

Пути: orchestrator/cycle_hint.py

Обоснование: инвариант SPEC 01M3XTFJCC5TG63FHW907GQM4D — строка запуска run/auto собирается только в cycle_hint.py; команда перезапуска stale_cycles строится функцией cycle_command оттуда (возврат Оператора из verifying, 02.10).

3. Код не менять — он уже готов в worktree; прогнать тесты, перечисленные в возврате, ещё раз; PLAN.md — `status: ready`.
