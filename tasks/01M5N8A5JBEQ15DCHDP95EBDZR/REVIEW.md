---
task: 01M5N8A5JBEQ15DCHDP95EBDZR
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Сброс удержанных записей копилки, бэклога и doc-commit — одним пушем

## Фаза A — план
- Таблица покрытия PLAN полна (требования 1–10). Шаг 4 добавлен под
  замечания итерации 1. Шаги — единицы размера MR.
- «Влияние на систему» совпадает с инкрементальным диффом df307e57..4c4b5bc6:
  `orchestrator/notes.py` (`_flush_batch`, ветка `except OSError`;
  `_flush_pending`, порядок проверки базы) и новый
  `tests/test_notes_batch_flush_edges.py`. Существующие тесты и долгоживущий
  файл задачи не тронуты. Карта кодовой базы свежая:
  `python3 scripts/codebase_map.py` меняет только `built_at_sha`.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1: коммиты по порядку `_pending_paths()`, один `push` (AC-1). |
| 2 | OK | без изменений с итерации 1: `ref=head` пакета, `known_first` до `_fresh_main`, `knowns.setdefault`. |
| 3 | OK | R1-F1 исправлено. Попутный сброс пропускает правку конфигурации прежней строкой (`notes.py:1469–1474`). При явном флаше `NO_BASE_WARNING` печатается до разделения на пакет и конфигурацию (:1475–1481), затем запись уходит в `config_records` → `_attempt`. Поведение такое же, как в базе 2b187a3d. |
| 4 | OK | `SystemExit` → `_refused_print`, запись выбывает. Ветка `OSError` снимает правку с дерева (R1-F2). |
| 5 | OK | перестройка через `_build_*` от `_fresh_main`, не больше `MAX_PUSH_ATTEMPTS`. |
| 6 | OK | `unlink` только после успешного push и только у `batch`. |
| 7 | OK | `_sent_line`, три вида строк (AC-6). |
| 8 | OK | `_journal_commit` после push, со sha своей записи. |
| 9 | OK | `_run`, `_fetch_and_build`, `_commit_and_push`, `_attempt` не тронуты. |
| 10 | OK | долгоживущий файл задачи. Новые тесты `tests/test_notes_batch_flush_edges.py` не повторяют его: предупреждение о базе и `OSError` записи пакета в нём не проверяются. Заявки «Ловит мутацию» у всех трёх методов наблюдаемы и подтверждены мутацией (см. ниже). |

## Замечания
Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/notes.py:1468-1485 | явный флаш правки конфигурации без `held_base` не печатал `NO_BASE_WARNING` | нарушено требование 3 SPEC | Принято. Проверка `HELD_BASE_KEY` теперь идёт до разделения на пакет и конфигурацию, попутный пропуск остаётся раньше неё. Тест `ConfigRecordNoBaseWarningTest` покрывает оба входа `--flush` и попутный сброс. Мутация «`continue` для конфигурации до проверки базы» краснит оба подтеста. Мутация «предупреждение и при попутном пропуске» краснит тест попутного сброса. |
| R1-F2 | accepted | orchestrator/notes.py:1402-1408 | `OSError` записи пакета оставлял правку в дереве | следующая запись того же пути строилась от грязного дерева | Принято. В ветке стоят `reset` и `_restore_tree(work_dir, _target_rel(request))`. Тест `BatchWriteFailureTest` краснеет на мутации «голый `continue`». |

## Вердикт
approved. Оба замечания итерации 1 исправлены по сути и закрыты тестами в
`tests/`. Сторожа проверены временной мутацией. Новых дефектов в
инкрементальном диффе нет.

## Проверено исполнением
- `python3 -m pytest -p no:cacheprovider -q tests/test_notes_batch_flush_edges.py
  tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py tests/test_notes.py
  tests/test_doc_commit.py tests/test_doc_commit_suite_gate.py
  tests/test_notes_apply.py tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py
  tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py`: 136 passed, 11 subtests.
- Временная мутация R1-F2: из `except OSError` в `_flush_batch` убраны
  `reset`/`_restore_tree`. Результат: `BatchWriteFailureTest` FAILED (1
  failed, 2 passed). Код возвращён.
- Временная мутация R1-F1: `config_records.append` + `continue` перед
  проверкой `HELD_BASE_KEY`. Результат: оба подтеста `entry=note` и
  `entry=doc-commit` SUBFAILED. Код возвращён.
- Временная мутация: печать `NO_BASE_WARNING` при попутном пропуске.
  Результат: `test_opportunistic_flush_still_skips_config_record_silently_on_base`
  FAILED. Код возвращён, `git status` чист.
- `python3 scripts/codebase_map.py`: дифф карты без строки `built_at_sha`
  пуст. Изменение откачено.
- Планки нет: тесты задачи долгоживущие, лежат в `tests/` (см. итерацию 1).

## Предложения системе
- Пакет ревью итерации 2 не нёс полного diff `_flush_pending` вокруг правки,
  только хунк. Для проверки порядка «попутный пропуск → предупреждение →
  разделение» понадобилось читать `notes.py:1460–1500`. Контекст хунка в
  пакете стоит расширять до тела изменённой функции.
