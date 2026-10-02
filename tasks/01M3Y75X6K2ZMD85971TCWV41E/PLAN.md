---
task: 01M3Y75X6K2ZMD85971TCWV41E
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Удержанный doc-commit сверяется с базой сборки; note --pending / --drop-pending

## Подход
- База пишется в `_hold_pending` (`orchestrator/notes.py`), а не при сборке
  запроса в `cmd_doc_commit`: поле `held_base` (`notes.HELD_BASE_KEY`) —
  blob-sha `HEAD:<путь>` главной копии, JSON `null` — «файла не было».
  Так база есть у ЛЮБОГО удержания `doc-commit` (окно тишины и сетевой
  отказ в `_run`), а немедленная отправка поля не несёт и идёт по прежней
  пиновой сверке (требование 3). Удержание происходит в том же вызове
  `doc-commit`, HEAD главной копии за это время не двигается.
- `_build_doc_commit`: запись с полем `held_base` сверяет blob пути в
  `FETCH_HEAD` с базой (None == None — новый файл), расхождение —
  `sys.exit` с текстом «<путь>: файл изменился в origin после сборки
  записи (база <sha|файла не было>, origin <sha|файла нет>) — собери
  заново от origin». Без поля — пиновая сверка, как было.
- Отказ одной записи в `_flush_pending` уже ловится (`SystemExit` →
  печать, `continue`) — запись остаётся, остальные отправляются; сверка
  стоит в общей сборке, поэтому одинаково действует на попутном допуше,
  `note --flush` и `doc-commit --flush`.
- Предупреждение «база не сохранена» печатает `_flush_pending` для
  записи `doc-commit` без поля — до попытки, поэтому видно и при
  отправке, и при отказе.
- `note --pending` / `note --drop-pending <id>` — разбор в `_parse_args`,
  исполнение в `cmd_note` ПОСЛЕ рубежа `runner.in_role_environment()` и ДО
  попутного допуша (иначе допуш отправил бы запись, которую снимают).
  Время — из миллисекундной метки имени файла. `--drop-pending` ищет id
  среди файлов каталога (не склеивает путь), пишет `store.journal`
  (актор `operator`, action называет id, detail — строку записи).
- Справка CLI `orchestrator/artel.py` — две новые формы и абзац.

## Шаги
1. `orchestrator/notes.py`: поле базы, сверка, предупреждение, команды
   `--pending`/`--drop-pending`; `orchestrator/artel.py` — справка;
   `tests/test_doc_commit_held_base.py`; регенерация
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`_hold_pending`) |
| 2 | 1 (`_build_doc_commit`, `_flush_pending`) |
| 3 | 1 (ветка без поля в `_build_doc_commit`) |
| 4 | 1 (`_flush_pending`, `NO_BASE_WARNING`) |
| 5 | 1 (`_print_pending`, `_pending_line`) |
| 6 | 1 (`_drop_pending`) |
| 7 | 1 (ветки после рубежа роли в `cmd_note`) |
| 8 | 1 (`tests/test_doc_commit_held_base.py`) |

Проверка:
- `python3 -m pytest tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py -p no:cacheprovider -p timeout -o timeout=120` — 13 passed.
- `tests/test_doc_commit_held_base.py` — 4 passed; каждый тест краснеет на
  своей заявленной мутации (проверено временной правкой notes.py: база
  только на ветке окна, выдержка без замены перевода строки, пустой
  перечень без строки, снятие по склеенному пути — по 1 failed на каждую).
- Соседние модули: `test_doc_commit.py`, `test_notes.py`,
  `test_notes_apply.py`, `test_notes_row_format.py`,
  `test_doc_commit_suite_gate.py`, `test_artel_role_restricted_commands.py`
  — 140 passed вместе с двумя файлами задачи; `test_invariants.py`,
  `test_codebase_map.py` — 100 passed.

## Влияние на систему
- Формат `.artel/notes-pending/` расширен одним полем; старые записи
  читаются (ветка без поля = прежнее поведение плюс предупреждение).
  `doctor.check_pending_notes` читает только `pending_notes()` — не
  затронут.
- Немедленный `doc-commit` и `note --apply` (`base_blob`, своя сверка) не
  меняются; пиновая сверка не ослаблена — удержанная запись получает
  сверку строже (с базой сборки, а не с подвижным пином).
- Тесты, гейты, инварианты не трогаются. Откат — revert merge-коммита;
  записи с полем `held_base` после отката пойдут по пиновой сверке (поле
  игнорируется).

## Риски
- Запись, удержанная при сбое `git rev-parse` в главной копии, получит
  `held_base: null` («файла не было») — для существующего файла флаш
  откажет (fail-closed), снять — `note --drop-pending`.

## Предложения системе
- Песочница роли не даёт `rm`/`ls`/`cat` в Bash (только через python3) —
  уборка временного скрипта мутационной проверки потребовала обхода;
  скил coding-standards («сторож проверяй временной мутацией») стоит
  дополнить штатным способом (например, `git stash`-подобным помощником
  пульта) — адрес: `skills/coding-standards.md`, раздел «Тесты».
