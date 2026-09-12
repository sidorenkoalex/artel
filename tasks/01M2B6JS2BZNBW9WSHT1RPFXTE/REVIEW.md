---
task: 01M2B6JS2BZNBW9WSHT1RPFXTE
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: note — окно тишины (удержание строк во время живых циклов)

## Фаза A: гейт плана

1. Покрытие требований в PLAN.md — таблица «Покрытие требований» закрывает
   все 8 требований SPEC шагами 1-3 (регенерация карты — шаг 4, отдельным
   требованием не числится, что верно: это следствие правки `.py`, а не
   требование SPEC). Полно.
2. Шаги — проверяемые единицы (константа/функция+рефакторинг/тесты/карта),
   не микрооперации и не «сделать всё одним шагом». Размер MR разумный
   (458 строк, из них 293 — тесты).
3. Подход не конфликтует с конвенциями: `_silence_window_reason` переиспользует
   существующий признак живости `merge_lock._holder_is_dead` (тот же приём,
   что уже применяет `merge_queue.py:37` — не изобретение нового способа
   определять живость держателя). Разделение `_attempt` на
   `_fetch_and_build`/`_commit_and_push` — оправданный рефакторинг под общую
   точку валидации, не лишняя абстракция ради неё самой.

Гейт плана пройден без замечаний.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (окно: держатель ИЛИ состояние, именованная константа) | OK | `config.NOTE_SILENCE_WINDOW_STATES` (config.py:356), `notes._silence_window_reason` (notes.py:98) |
| 2 (валидация до окна) | OK | `_fetch_and_build` строит правку (и падает `sys.exit` при отказе валидации) ДО вызова `_silence_window_reason` в `_run` (notes.py:410-421) |
| 3 (удержание в `.artel/notes-pending/`, формат сообщения) | OK | `_hold_pending(request)` + печать точного текста сообщения (notes.py:417-420) |
| 4 (вне окна — как сегодня) | OK | ветка `sha = _commit_and_push(...)` при `reason is None`, тот же цикл повтора non-fast-forward, что и раньше |
| 5 (`--flush` обходит окно) | OK | `cmd_note`: `if args.flush or ...` — короткое замыкание не проверяет окно вовсе при explicit `--flush` |
| 6 (`--now` обходит окно) | OK | `--now <раздел>` → `_run(..., bypass_window=True)`, окно не проверяется совсем |
| 7 (оппортунистический флаш уважает окно) | OK | `if args.flush or _silence_window_reason() is None: _flush_pending()` |
| 8 (порядок отправки по имени файла) | OK | не менялось, `_pending_paths()` уже сортирует `glob` |

Все 8 требований и все 9 AC (SPEC) реализованы так, как описаны.

## Замечания

(пусто — блокеров и major не найдено)

## Реестр замечаний

(пусто — итерация 1, замечаний нет)

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_notes -v` — 40 тестов, все зелёные
  (включая новые `SilenceWindowReasonTest`, `WindowHoldsValidNoteTest`,
  `WindowBypassAndNoWindowTest` — AC-1..AC-9).
- Залоченные приёмочные тесты задачи (все 9 файлов
  `tasks/01M2B6JS2BZNBW9WSHT1RPFXTE/acceptance_tests/test_ac*.py`, каждый
  запущен отдельным модулем `python3 -m unittest tasks.01M2B6JS2BZNBW9WSHT1RPFXTE.acceptance_tests.test_acN_...`
  — 15 тестов суммарно, все зелёные.
- `python3 scripts/codebase_map.py` на HEAD ветки — сравнение
  `git diff docs/codebase-map.md` после регенерации показало расхождение
  только в строке `built_at_sha` (законное отставание метки, не дефект);
  содержимое карты идентично закоммиченному. Файл возвращён
  `git checkout -- docs/codebase-map.md` после сверки (артефакт сверки, не
  правка).
- Прочитан diff и код `orchestrator/notes.py`, `orchestrator/config.py`
  целиком; сверены сигнатуры `store.insert_task`/`store.set_merge_lock`/
  `store.merge_lock_row`/`store.all_tasks` и `merge_lock._holder_is_dead`
  с их фактическими определениями в `orchestrator/store.py`,
  `orchestrator/merge_lock.py` — использование в `notes.py` и в новых
  тестах им соответствует.
- Проверено, что диапазон правки не выходит за зону SPEC (zones:
  `orchestrator/notes.py`, `orchestrator/config.py`, `tests/`) —
  `git diff --stat` показывает только эти файлы плюс мандатную
  регенерацию `docs/codebase-map.md`; `store.py`/`pull.py`/
  `fsm_merge_gate.py` (SPEC «Не входит») не тронуты.
- Проверено (`grep -rln "notes.cmd_note" tests/`), что новое
  безусловное чтение БД в начале `cmd_note` не задевает другие тестовые
  файлы — вызовы `notes.cmd_note`/`notes._run` есть только в
  `tests/test_notes.py`, чья единственная фикстура без схемы БД
  (`CmdNoteArgumentValidationTest`) уже получила `store.create_schema`
  в этом же MR.

## Предложения системе

(пусто)
