---
task: 01M5634E094QF7JX8HD3KSG4KN
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Бриф роли внешнего проекта: конвенции и карта проекта, а не пульта

## Фаза A: план
- Таблица покрытия полна: требования 1–13 разнесены по шагам 1–3; 12 и 13 честно помечены как «не правим» / «тесты test_author».
- Шаги размера MR: brief.py, role_prompt.py, прогон и регенерация карты.
- Подход (развилка `repo_context.is_artel(store.task_target(...))`, чтение базы через `reference_cache.branch_commit` + `ls-tree`/`show`) не конфликтует с архитектурой; правок вне зон (`repo_context.py`, `reference_cache.py`, `config.py`, `gitcmd.py`) нет — «Предложения системе» про третий исход `gitcmd.show` вынесено в копилку, а не сделано попутно.
- «Влияние на систему» совпадает с diff: изменены только `orchestrator/brief.py` и `orchestrator/role_prompt.py` (+ карта, + долгоживущий тест test_author).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `brief.is_artel_task` → `repo_context.is_artel(store.task_target(...))`; `task_target` не возвращает `None` (умолчание `DEFAULT_TARGET`, `store.py:701-707`). |
| 2 | OK | На ветке внешнего проекта у developer/spec_auditor/analyst нет ни `map_note`, ни `MAP_PROJECTION_NOTE`, ни проекции; у test_author карты не было и нет. AC-2…AC-5 зелёные. |
| 3 | OK | `_fresh_map_text_and_note`/`fresh_map_text`/`_handle_map_size_alert` вызываются только под `if artel`. AC-11 (нет git-вызова с `built_at_sha`, нет `codebase_map.py`, снимок пульта неизменен) и AC-12 (крупная стухшая карта — ни одного алерта карты) зелёные. |
| 4 | OK | `_read_project_conventions`: `branch_commit(ctx.path, ctx.base)` (локальная `refs/heads/<base>`, без fetch), `ls-tree <sha>`, `show <sha>:<файл>` байтами; по компоненту на файл. AC-6 подтверждает чтение именно версии базы (не рабочего дерева клона, не ветки/worktree задачи). |
| 5 | OK | `render` соседей: `_manifest_component` у developer/spec_auditor, `_journal_component` у analyst/test_author; справочник ядра test_author не тронут. AC-6 зелёный. |
| 6 | OK | Все четыре роли; у test_author внешнего проекта `conventions` всегда непуст (пометка или компонент) — добавка не `None` (AC-5). |
| 7 | OK | «файла нет в ls-tree» → `конвенции проекта: <файл> — файла нет (...)`; AC-7, AC-8 зелёные. |
| 8 | OK | Контекст не разрешён / нет клона / нет ветки / git не ответил / `ls-tree` не удался → одна пометка «конвенции проекта не прочитаны: <причина>» + `store.journal` с той же причиной; `_clone_git` ловит `OSError`/`TimeoutExpired`, `sys.exit` нет. Чтение SPEC.md (`_developer_spec_text`) идёт раньше развилки — отказ по нему сохранён. AC-9 (4 сценария × 4 роли) зелёный. |
| 9 | OK | Файл есть в `ls-tree`, `show` не удался → пометка «не прочитаны: <файл>: <причина>» + журнал. Проверено временной мутацией (см. ниже). |
| 10 | OK | `role_prompt.py`: тексты developer/analyst/spec_auditor разведены по `artel`; у внешнего developer — «конвенции проекта … правила работы роли — в скилах пульта». AC-13, AC-14 зелёные. |
| 11 | OK | Ветка артели — прежние строки в прежнем порядке; планка AC-1 (эталон с базы ветки, зафиксированный `run_id`, побайтное сравнение) зелёная. |
| 12 | OK | `git diff --stat 44228d98...HEAD -- tests/` — только новый долгоживущий файл задачи; планка AC-15 зелёная. |
| 13 | OK | Долгоживущий тест на `RealGitSandbox` без сети, зерно `random` печатается; все варианты фикстуры из требования есть. |

## Замечания

Блокирующих и major-замечаний нет. Наблюдения без влияния на вердикт (не заведены в реестр):
- minor — `orchestrator/role_prompt.py:38` — `artel` вычисляется для всех ролей (лишний SELECT для reviewer/прочих), используется только тремя миссиями; на поведение не влияет.
- minor — `orchestrator/brief.py` `_read_project_conventions` — `CLAUDE.md` символьной ссылкой в базе (mode 120000, тип `blob`) попадёт в бриф текстом цели ссылки; для фиксированного списка из двух файлов маловероятно, отдельной правки не требует.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 orchestrator/artel.py plank-run 01M5634E094QF7JX8HD3KSG4KN` (пульт) — `2 passed` (AC-1 побайтная неизменность брифа/миссий артели, AC-15), код выхода 0.
- `python3 -m pytest -q tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py tests/test_multitarget_invariants.py tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py` — `32 passed, 43 subtests passed`.
- `python3 -m pytest -q tests/test_brief.py tests/test_role_prompt_test_author_mission.py` — `27 passed`.
- Временная мутация (заявка AC-10): в `_read_project_conventions` сбой `show` записан как «файла нет» (`entries.append((rel, None, ""))`) → `test_ac10_failed_file_read_marked_unread_not_absent` красный (4 подтеста из 4 ролей упали); код возвращён `git checkout -- orchestrator/brief.py`, `git status` чист.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md | grep -v built_at_sha` — содержательных расхождений 0 (карта свежая); файл возвращён `git checkout`.
- `git diff --stat 44228d98...HEAD -- tests/` — только добавлен долгоживущий файл задачи, существующие тесты не изменены.

## Предложения системе
- Миссия ревьювера предписывает «не запускай полный набор», а сторож роли отклоняет и `pytest tests/ -k <фильтр>` как полный прогон — стоит назвать в скиле review-checklist допустимую форму (явный список файлов), чтобы не тратить попытку.
