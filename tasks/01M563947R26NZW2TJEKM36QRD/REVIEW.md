---
task: 01M563947R26NZW2TJEKM36QRD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Окно тишины note и doc-commit — только по задачам артели

## Фаза A: план
- Таблица покрытия полна (требования 1–4 → шаг 1); один шаг размера MR
  соответствует монолиту SPEC (одна функция + тесты).
- Подход согласован с архитектурой: `repo_context.is_artel` первым,
  `resolve` только для не-артели; строка держателя через
  `store.task_exists` + `store.get_task` без SQL вне store.py
  (инвариант `tests/test_multitarget.py::SqlOnlyInStoreTest` зелёный).
- «Влияние на систему» = diff: `orchestrator/notes.py`, `tests/test_notes.py`
  (+ перегенерированная карта). config/store/merge_lock/repo_context не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `notes.py:283-303`: держатель и задачи окна фильтруются через `_task_project` (`notes.py:312-321`): `is_artel(row)` первым (пустой/NULL `target` → артель, `repo_context.py:172-176`), `resolve` только для не-артели. Внешний держатель не делает `return None`, а проваливается к перебору; внешняя задача — `continue`-эквивалент (ни одна ветка не возвращает). Тексты артели прежние. |
| 2 | OK | Держатель без строки (`task_exists` ложно) и неразрешаемый проект → `None` → текст `«держатель … задача <id>): проект задачи не определён»` / `«задача <id> в состоянии <s>: проект задачи не определён»`. `store.task_target` не используется — молчаливого приравнивания к артели нет. Задачи вне `NOTE_SILENCE_WINDOW_STATES` проект не проверяют (`notes.py:296-297`). |
| 3 | OK | Существующие тесты `SilenceWindowReasonTest` не изменены (diff `tests/test_notes.py` — только добавленный метод); долгоживущий файл AC-3 зелёный. |
| 4 | OK | Долгоживущий `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py` покрывает AC-1…AC-5 через `cmd_note` на bare origin, без сети; детерминированность — случайное зерно печатается и входит в текст провала. |

## Замечания

Нет замечаний уровня blocker/major/minor.

Проверенные граничные случаи (без дефекта):
- `get_task` разрешает префикс (`store.py:1011`), но вызывается только после
  `task_exists` по точному id, а `resolve_task_id` проверяет точное
  совпадение первым — чужая задача по префиксу не подхватится.
- Пустой `task_id` держателя: `task_exists("")` ложно → «не определён»
  (осторожный исход), не `sys.exit`.
- Сломанный `targets.yaml`: `resolve` ловит `TargetsError` → `None` →
  окно открыто, как и до правки (риск из PLAN корректен).
- Новый тест `test_notes.py::test_artel_task_and_holder_not_resolved_through_targets`
  не повторяет долгоживущий: он фиксирует отдельное свойство (артель
  узнаётся без обращения к `resolve` при сломанных записях проектов),
  которое долгоживущий файл не изолирует; заявка мутации наблюдаема и
  подтверждена исполнением (ниже).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_notes.py tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py tests/test_multitarget.py`
  — 102 passed, 48 subtests passed.
- `artel.py plank-run 01M563947R26NZW2TJEKM36QRD` — отказ «планки нет: …
  нет файлов test_*.py»: зафиксированная планка задачи пуста, всё
  приёмочное — в долгоживущем файле `tests/` (прогнан выше).
- Временная мутация 1 (`_task_project`: `resolve` вызывается до `is_artel`)
  — красные `test_notes.py::test_artel_task_and_holder_not_resolved_through_targets`
  и долгоживущие AC-3 субтесты с `target=''`/`None` (задача и держатель).
- Временная мутация 2 (внешний держатель → досрочный `return None`) —
  красный `test_ac3a_external_holder_does_not_mask_artel_task`.
  Итого под мутациями 14 failed; код возвращён `git checkout -- orchestrator/notes.py`,
  повторный прогон — 51 passed, 34 subtests passed, `git status` чистый.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой
  только в строке `built_at_sha` (карта свежая); изменение откачено.

## Предложения системе
- Песочница шага отклоняет `cp`+heredoc-скрипт для временной мутации
  (требует подтверждения) — приём «временная мутация» из
  skills/review-checklist.md на практике выполним только через Edit +
  `git checkout --`; стоит назвать этот путь в скиле.
