---
task: 01M1SD5RHTJ0H0SR0615SVCJM5
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: R7 — `fsm_merge_gate._cmd_approve_merge_gate` разобрать на шаги

## Контекст итерации 2

Причина новой итерации — не правка кода, а свежесть ветки: гейт
`review -> verifying` отказал предыдущей попытке сдачи шага текстом
«вердикт REVIEW.md (status=approved, iteration=1) уже учтён — жду
новый прогон ревьювера с iteration: 2», так как HEAD ветки продвинулся
после фиксации вердикта итерации 1 (`fixed_sha` = `195ff13a`, коммит
сразу после `82c1089f` — самой правки) серией «подтяжка main»,
принёсших в ветку уже смерженные в main задачи 01M1SAA01YRRTWAVADT2F81RRQ,
01M1SC3Y20YBTTJVQDJBF2NDQW, 01M1SC40NT8T1WFKKKJ67CK96Z и правки
Оператора в docs/backlog.md.

Ревью-пакет строит diff инкрементально от `195ff13a` до HEAD (`d14adf66`)
— именно этот диапазон и показывает всю пришедшую с main историю
(auto.py, canary.py, checkpoint.py, workspace.py, guard.py,
codebase_map.py, docs/backlog.md, docs/retro/*, задачи tasks/01M1SAA01…,
01M1SC3Y20…, 01M1SC40NT…) как «изменения» — тот же класс ложного
сигнала, что уже отмечен в памяти ревью 01M1SC3Y20YBTTJVQDJBF2NDQW и в
записи бэклога о некорректной базе сравнения диффов (`docs/backlog.md`,
раздел «Наблюдения», строка про трёхточечный дифф, задача 01M1SG9T96 в
работе). Проверено вручную (`git merge-base --is-ancestor`,
`git diff main...HEAD`): `main` (`a9ab7291`) — предок HEAD (`d14adf66`),
т.е. все «подтянутые» файлы уже находятся в `main` через мерж других
задач; РЕАЛЬНЫЙ diff этой ветки относительно `main` —

```
docs/codebase-map.md           |   2 +-
orchestrator/fsm_merge_gate.py | 283 +++++++++++++++++++++++++----------------
```

— ровно та же правка, что была одобрена итерацией 1 (`82c1089f`), плюс
безусловный сдвиг `built_at_sha` в карте (не дефект, `skills/
review-checklist.md`). `git diff 195ff13a..HEAD -- orchestrator/
fsm_merge_gate.py orchestrator/fsm.py orchestrator/fsm_advance.py
tests/test_fsm_merge_gate*.py tests/test_branch_freshness_gate.py` —
пусто: ни зона задачи, ни защищённые «Не входит»-файлы, ни её тесты не
менялись НИ БАЙТОМ с момента одобрения итерации 1. Единственная
причина новой итерации — административная (подтяжка main для
свежести), не содержательная; повторная проверка ниже подтверждает,
что вывод итерации 1 остаётся в силе.

## Фаза A: проверка плана

Без изменений с итерации 1 — PLAN.md не менялся (см. выше). Таблица
покрытия требований полна, монолит обоснован SPEC, размер MR —
проверяемая единица. Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (8 ответственностей разнесены по именованным шагам) | OK | без изменений с итерации 1 — 9 новых top-level функций (`_ensure_branch_head_published` … `_cleanup_merged_task`), код не менялся (`git diff 195ff13a..HEAD -- orchestrator/fsm_merge_gate.py` пуст) |
| 2 (`_cmd_approve_merge_gate` — короткая композиция, порядок/отказы буквальны) | OK | без изменений; тело — 10 операторов |
| 3 (явный исход без булевых флагов и новой вложенности) | OK | без изменений; `test_ac2_no_new_condition_nesting.py` зелёный на текущем HEAD |
| 4 (`_cmd_approve_merge_gate_cycle` не редактируется, сигнатура прежняя) | OK | без изменений; `orchestrator/fsm.py`/`orchestrator/fsm_advance.py` тоже не тронуты — сверено этой итерацией отдельно (`git diff main...HEAD --stat -- orchestrator/fsm.py orchestrator/fsm_advance.py` пусто) |
| 5 (тексты `journal`/`sys.exit`/`print` буквальны) | OK | без изменений |
| 6 (три смоук-сценария дают тот же журнал/вывод) | OK | `test_ac5_three_smoke_scenarios.py` — 3/3 зелёных на текущем HEAD (перепрогнано этой итерацией) |
| 7 (существующие тесты зелёные без правки `assert`) | OK | перепрогнано этой итерацией на текущем HEAD (после подтяжки main) — зелёные; `git diff main...HEAD --stat` подтверждает, что ни один файл `tests/` не отличается от main |

## Замечания

Замечаний нет.

## Реестр замечаний

Пусто — в итерации 1 замечаний не заводилось, новых в этой итерации
тоже нет.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `git rev-parse main HEAD` + `git merge-base main HEAD` — `main` (`a9ab7291`) является предком HEAD (`d14adf66`), т.е. содержится в истории ветки целиком; расхождение — только неслитый пока коммит `82c1089f` (правка R7) плюс регенерация карты.
- `git diff main...HEAD --stat` — ровно 2 файла: `docs/codebase-map.md` (только `built_at_sha`) и `orchestrator/fsm_merge_gate.py` (283 строки, тот же дифф, что и в коммите `82c1089f`) — зона задачи не расширена, посторонних файлов из «подтянутых» задач в РЕАЛЬНОМ дифе относительно main нет.
- `git diff main...HEAD --stat -- orchestrator/fsm.py orchestrator/fsm_advance.py` — пусто (требование 4/«Не входит»).
- `git diff 195ff13a..HEAD --stat -- orchestrator/fsm_merge_gate.py orchestrator/fsm.py orchestrator/fsm_advance.py tests/test_fsm_merge_gate*.py tests/test_branch_freshness_gate.py` — пусто: с фиксации вердикта итерации 1 в зоне задачи и её тестах ничего не изменилось.
- `python3 -m unittest discover -s tasks/01M1SD5RHTJ0H0SR0615SVCJM5/acceptance_tests -v` — 9 тестов (AC-1..AC-5), все `ok`, перепрогнано на текущем HEAD (`d14adf66`).
- `python3 -m unittest tests.test_fsm_merge_gate_done_snapshot tests.test_branch_freshness_gate tests.test_merge_gate_ci_wait -v` — 23 теста, все `ok`, перепрогнано на текущем HEAD.
- `python3 scripts/guard.py tasks/01M1SD5RHTJ0H0SR0615SVCJM5/SPEC.md tasks/01M1SD5RHTJ0H0SR0615SVCJM5/PLAN.md` — `GUARD: ок (2 файлов)`.
- Материализация `tasks/01M1SD5RHTJ0H0SR0615SVCJM5/` в рабочем каталоге на старте этого шага сработала штатно (в отличие от итерации 1, где потребовался ручной `git checkout`) — предложение системе итерации 1 по этому поводу остаётся актуальным как наблюдение о нестабильности механизма, но в этом шаге дефект не воспроизвёлся.

## Предложения системе

- Ревью-пакет строит инкрементальный diff от sha предыдущего вердикта
  до HEAD буквально, не учитывая, что между вердиктом и HEAD может
  лечь серия «подтяжка main», приносящая в диапазон весь объём уже
  смерженных в main чужих задач (здесь — три задачи целиком, ~3800
  строк). Из-за этого diff, показанный в пакете, не имеет отношения к
  делу — реальный diff ветки относительно main меньше на два порядка
  и не менялся с итерации 1. Тот же класс уже отмечен ревью
  01M1SC3Y20YBTTJVQDJBF2NDQW (см. память `[[project_...]]`/
  `docs/backlog.md`) — стоит явно включить сценарий «после вердикта
  ветка подтягивала main N раз» в область фикса задачи о трёхточечном
  диффе гейтов (01M1SG9T96, уже в работе), раз он касается не только
  гейтов зон/ёмкости, но и генератора самого ревью-пакета.
