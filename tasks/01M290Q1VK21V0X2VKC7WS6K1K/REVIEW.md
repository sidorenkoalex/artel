---
task: 01M290Q1VK21V0X2VKC7WS6K1K
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: note --drop, --set-state, --set-priority — снятие и правка строк копилки/бэклога тем же циклом fetch/правка/push

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`--drop <ключ>`) | OK | `_apply_drop` (orchestrator/notes.py:175-180) снимает ровно одну строку через общий `_find_unique_row`, ноль/множество совпадений — `sys.exit` до записи (унаследовано от `_find_unique_row`, orchestrator/notes.py:157-163); сообщение коммита `_commit_message` (orchestrator/notes.py:231-232) — «оператор: <раздел> — снята: <80 симв.>»; проходит тем же `_attempt`/`_hold_pending` циклом (orchestrator/notes.py:290-292 внутри `_attempt`). AC-1..AC-4 проверены прогоном acceptance_tests (см. «Проверено исполнением»). |
| 2 (`--set-state`) | OK | `_apply_set_state` (orchestrator/notes.py:183-189) заменяет последнюю колонку целиком (`cells[-1] = text`, не дописывание); `--append` сохраняет старое дописывающее поведение (`_apply_append`, orchestrator/notes.py:166-172, тест `AppendStillAppendsSameColumnTest`/ac5 зелёный). Сообщение коммита соответствует AC-6. |
| 3 (`--set-priority`) | OK | `_apply_set_priority` (orchestrator/notes.py:192-204) валидирует диапазон 1..4 ДО чтения/правки строк — отказ вне диапазона не меняет файл (AC-7, тесты `test_value_above/below_range_refuses_without_changing_text` и ac7 зелёные). Колонка «П» — первая ячейка таблиц `docs/backlog.md` (проверено: `grep "^| П "` — все три таблицы), `cells[0] = text` — верная колонка. |
| 4 (общий формат pending, `doctor` без правки) | OK | `_hold_pending`/`pending_notes`/`_pending_paths` (orchestrator/notes.py:61-85) не тронуты, кладут произвольный `dict` — новые `kind` проходят тем же путём; `orchestrator/doctor/misc_checks.py:35-44` читает `notes.pending_notes()` по длине списка, не фильтрует по `kind`, правок doctor в diff нет (подтверждено `git diff --stat`). AC-8 зелёный. |
| 5 (тестовый слой) | OK | `tests/test_notes.py`: `ApplyDropTest` (изоляция соседних строк, отказ при 0/2 совпадениях), `ApplySetStateTest` (замена vs дописывание), `ApplySetPriorityTest` (отказ вне 1..4, включая нечисловое значение), `CmdNoteArgumentValidationTest` (`--set-state`/`--set-priority` без `--text`) — все 27 юнит-тестов зелёные. Залоченные `acceptance_tests/test_ac1..ac8` покрывают полный цикл git (hold/flush/commit-message) — все зелёные. `test_ac9` — легитимная пометка `manual` (утверждение о диффе, не проверяемое прогоном текущего среза кода; см. «Приёмочные тесты» скила). Требование 5 «существующие тесты — без ослабления»: diff `tests/test_notes.py` — только добавления (новые классы `ApplyDropTest`/`ApplySetStateTest`/`ApplySetPriorityTest`/2 новых метода `CmdNoteArgumentValidationTest`), ни одна существующая строка/ассерт не удалены и не смягчены. |

## Замечания

(пусто — 0 blocker/major/minor)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| — | — | — | замечаний не заведено | — | — |

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_notes -v` — 27 тестов, все `ok` (включая новые `ApplyDropTest`, `ApplySetStateTest`, `ApplySetPriorityTest`, `CmdNoteArgumentValidationTest.test_set_state_without_text_refuses`/`test_set_priority_without_text_refuses`).
- `python3 -m unittest tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac1_drop_removes_matched_row_only.py -v` — 2 теста, ok.
- `python3 -m unittest tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac2_drop_match_count_refuses.py tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac3_drop_commit_message.py -v` — 4 теста, ok.
- `python3 -m unittest tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac4_drop_hold_and_flush.py tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac5_set_state_replaces_column.py tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac6_set_state_commit_message.py -v` — 7 тестов, ok.
- `python3 -m unittest tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac7_set_priority_range.py tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac8_pending_all_kinds_ordered_flush.py -v` — 4 теста, ok. Итого AC-1..AC-8 (17 тестов) зелёные, AC-9 — `manual` без методов (обоснование в докстринге проверено).
- `grep "^| П \|^|---|" docs/backlog.md` — подтверждён порядок колонок всех трёх таблиц (П — первая колонка, Состояние — последняя в «Копилке»), соответствует `_apply_set_priority`/`_apply_set_state`.
- `grep -rn "pending_notes" orchestrator/doctor/*` + чтение `orchestrator/doctor/misc_checks.py:35-44` — `check_pending_notes` считает по `len(pending)`, без ветвления по `kind`; правок в `orchestrator/doctor/` в diff нет.
- `git diff origin/main -- docs/codebase-map.md | grep -v built_at_sha` — пусто (расхождение только в строке `built_at_sha`, легальный лаг по скилу conventions-core). `python3 scripts/codebase_map.py` на слитом дереве (пробный прогон, откат `git checkout -- docs/codebase-map.md`) — тоже только `built_at_sha` отличается, публичная поверхность модуля не изменилась.
- `git show --stat a6c38592` — подтверждён настоящий merge-коммит (parents `3b78399b`, `2fac2761`), `docs/backlog.md` взят из main согласно ANSWER-1 (1 insertion — строка П1, добавленная origin/main после точки, от которой стартовала ветка).
- `git status --porcelain` / `git diff --stat 2fac2761...HEAD -- . ':!tasks'` — diff ветки ограничен `docs/codebase-map.md`, `orchestrator/notes.py`, `tests/test_notes.py`, совпадает с описью пакета; посторонних файлов нет.
- CI коммита `a6c38592` — зелёный, 14 проверок (по статусу пакета, полный `tests/` в шаге ревью не прогонялся согласно правилу «CI гоняет полный набор»).

## Предложения системе

(пусто)
