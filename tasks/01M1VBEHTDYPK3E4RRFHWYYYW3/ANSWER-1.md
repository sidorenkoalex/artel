---
task: 01M1VBEHTDYPK3E4RRFHWYYYW3
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответ Оператора на эскалацию «конфликт подтяжки main» (06.09.2026).

Причина: кодовая ветка задачи стартовала от c4f89371 (пин на момент
`new`, 12:36Z), а в origin/main с тех пор смержен разрез
`orchestrator/doctor.py` на пакет `orchestrator/doctor/` (01M1TT9BPB,
merge 7759a248): монолит удалён, проверки живут в подмодулях, фасад —
`orchestrator/doctor/__init__.py`, список `all_checks` —
`orchestrator/doctor/cli.py`. Правка монолита (импорт `notes`,
`check_pending_notes`, строка в `all_checks`) конфликтует как
modify/delete; `docs/codebase-map.md` — содержимое.

Что сделать разработчику в этом ходе (кода задачи по существу не
менять, только перенос):
1. Завершить подтяжку: `git merge origin/main` в worktree, принять
   удаление `orchestrator/doctor.py` со стороны main (`git rm`).
2. Перенести `check_pending_notes` в `orchestrator/doctor/misc_checks.py`
   рядом с `check_backup_age`, в стиле пакета: коллаборанты лениво через
   фасад (`doctor.notes.pending_notes()`, `doctor.Check`), прямых
   импортов из `orchestrator` в подмодуле нет. В фасаде
   `orchestrator/doctor/__init__.py` добавить `notes` в список
   коллаборантов `from .. import (...)` и реэкспорт `check_pending_notes`
   из `misc_checks`. В `orchestrator/doctor/cli.py::all_checks` добавить
   `checks.append(doctor.check_pending_notes())` сразу после
   `check_canary_pool_drift()` — как было в монолите.
3. `docs/codebase-map.md` взять из origin/main и перегенерировать
   штатным `python3 scripts/codebase_map.py`, закоммитить.
4. В PLAN.md добавить раздел `## Расширение зон` со строкой
   `Пути: orchestrator/doctor/` и обоснованием (зона SPEC
   `orchestrator/doctor.py` — это тот же модуль до разреза; мандат ниже).
5. Прогнать `tests/test_doctor*.py`, `tests/test_notes.py` и планку из
   worktree (`python3 -m unittest discover -s
   tasks/01M1VBEHTDYPK3E4RRFHWYYYW3/acceptance_tests`), сдать шаг.

Планку не править. Бюджет $70 — запас есть.

Расширение зон разрешено: orchestrator/doctor/
