---
task: 01M6KWKZ8GKZZFABDG8QC9RDJF
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: approve --note на гейте SPEC — указание Оператора для test_author и ревьювера

## Фаза A: план
- Таблица покрытия полна: требования 1–10, у каждого есть шаг; требование 9 — два приложения.
- Шаги размером в MR: разбор флага, FSM, читатель, документация. Подход повторяет `--as-epic` (проверка до lease и повтор под lease), конвенциям не противоречит.
- Оба приложения (`skills/test-authoring.md`, `skills/review-checklist.md`) проходят `git apply --check` на чистом дереве ветки. Добавленные строки дословно совпадают с «Материалами» SPEC. Элемент review-checklist идёт с отступом в три пробела сразу после элемента об ANSWER-n, существующие строки не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `artel._approve_note_kwargs`: нет значения или значение `--…` — `sys.exit` до lease. `NOTE_FLAG` добавлен в `_approve_reason_indices`. Без флага — `{}`, тот же приём, что у `_approve_as_epic_kwargs`. `cmd_approve(note=None)` — только именованный параметр. Состояние проверяется первым в `fsm._spec_gate_note_text` и повторно под lease в `_cmd_approve`; в обоих отказах есть «допустим только в состоянии spec_gate». Чтение ловит `OSError`/`UnicodeDecodeError`, пустота — по `strip()`. |
| 2 | OK | `_spec_gate_note_content_refusal`: каждая строка проверяется по всем четырём `mandate.MANDATE_MARKERS` через `line_elements`; `mandate` импортируется по месту. Маркеры тестов дают подсказку `answer <id> <файл>`, зоны и зависимости мержа — «полями SPEC … reject». Заголовок файла решения проверяется через `spec_gate_decision.starts_with_header`. |
| 3 | OK | `_spec_gate_note_path_refusal` проверяет те же условия, что ветви `_approve_spec_gate` (fsm.py ~1561–1580): `parse_division_subsections`, `skip_tests`, `requires_ac_markup`. SPEC читается через `artifact_source.resolve` + `artifact_branch.show`, как в `_as_epic_goal`: тем же источником, что обработчик, потому что `resolve` всегда возвращает foreign=True. Проверка вызывается до lease и под lease; мягкие отказы прежние. |
| 4 | OK | `store.journal(... "operator", SPEC_GATE_NOTE_ACTION, note_text)` идёт сразу после `set_state(... "tests_writing")`. Предел — `len(read_bytes()) > CONTEXT_FILE_MAX_BYTES`, сравнение строгое. |
| 5 | OK | `brief.spec_gate_note` идёт по `store.task_steps` (ORDER BY id) и сбрасывает найденное на каждой `state -> spec_gate`. Учитываются только записи действия указания от `operator`. |
| 6 | OK | Раздел стоит после причины возврата и ANSWER, до конвенций. Преамбула — между заголовком и границей. Запись делает `_journal_component`. |
| 7 | OK | `review._spec_gate_note_part` вставляется сразу после цикла ANSWER-n, до долгоживущих файлов. Ключи словаря прежние. Запись «бриф: компонент» от `reviewer` той же формы, что у ANSWER (`label: sha256=…`). |
| 8 | OK | Без флага `partial` и вызовы прежние. Это сторожит `tests/test_approve_note_call_shape.py`, соседние тесты зелёные. |
| 9 | OK | Приложения в PLAN, см. Фазу A. |
| 10 | OK | В справке `[--note <файл>]` дописан в строку продолжения с отступом 11 пробелов. `docs/operator-gates.md` описывает флаг, `log` и `watch`. Карта свежая: после `scripts/codebase_map.py` расходится только `built_at_sha`. |

Сверка набора тестов: `git diff 92bdb87b...HEAD -- tests/` — только два новых файла (долгоживущий тест задачи и `tests/test_approve_note_call_shape.py`). Существующие файлы `tests/` не тронуты, ослаблений нет. Новые методы `tests/` несут заявки «Ловит мутацию» с наблюдаемым расхождением. Долгоживущий тест задачи не повторяют: он не сверяет отсутствие ключа `note`/`note_text` в вызовах.

Вне зоны изменений нет: в diff только `docs/operator-gates.md`, `orchestrator/{artel,brief,fsm,review}.py`, `tests/` и карта. Это совпадает с «Влиянием на систему» PLAN. Откат — revert merge.

## Замечания

Нет.

Наблюдение (не замечание, на вердикт не влияет): `_spec_gate_note_text` читает файл дважды — `read_bytes()` и `read_text()`. Можно было бы декодировать уже прочитанные байты и при этом сохранить CRLF→LF. Поведение от этого не меняется.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m6kwkz8gkzzfabdg8qc9rdjf_spec_gate_note.py tests/test_approve_note_call_shape.py` — 27 passed (99 с).
- `artel.py plank-run 01M6KWKZ8GKZZFABDG8QC9RDJF` — 1 passed (`test_ac13_note_isolation.py`), код выхода pytest 0.
- `python3 -m pytest -p no:cacheprovider -q -x tests/test_cmd_approve_dispatch.py tests/test_brief.py tests/test_review_package_map.py tests/test_task_component_places.py tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py` — 72 passed, 106 subtests passed.
- Временная мутация (заявки `tests/test_approve_note_call_shape.py`): `cmd_approve` всегда передаёт `note_text=note_text`, а `_approve_note_kwargs` без флага возвращает `{"note": None}`. Оба теста файла красные (2 failed), код возвращён `git checkout`, дерево чистое.
- `git apply --check` обоих diff-приложений PLAN — код 0. Добавленные строки дословно совпадают с «Материалами» SPEC.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расходится только `built_at_sha`, регенерация возвращена.

## Предложения системе
