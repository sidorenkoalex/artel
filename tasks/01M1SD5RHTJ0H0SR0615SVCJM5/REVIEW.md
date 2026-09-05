---
task: 01M1SD5RHTJ0H0SR0615SVCJM5
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: R7 — `fsm_merge_gate._cmd_approve_merge_gate` разобрать на шаги

## Фаза A: проверка плана

Таблица покрытия требований в PLAN.md (1 шаг → все 7 требований) полна:
шаг 1 — единственная top-level правка модуля, соответствует
обоснованию SPEC «Оценка объёма и деление» (промежуточное состояние
декомпозиции не даёт независимо мержимого приращения — требование 6
проверяется только на завершённом разборе, поэтому монолит вопреки
`budget_usd`=$35 ≥ порога $30 оправдан текстом самого SPEC). Размер MR
(283 строки диффа, один файл + служебная карта) — проверяемая единица,
не микрооперация и не «сделать всё». Подход (top-level шаг-функции с
явным строковым/кортежным исходом вместо булевых флагов) не
конфликтует с существующей архитектурой модуля — переиспользует уже
существующие узлы (`_handle_merge_conflict`, `_ci_confirm_red_or_flake`,
`_wait_for_branch_ci_green`, `_overlay_artifact_snapshot` и др.)
нетронутыми, как и заявлено. Гейта плана отдельно нет — замечаний по
плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (8 ответственностей разнесены по именованным шагам) | OK | 9 новых top-level функций (`_ensure_branch_head_published` … `_cleanup_merged_task`), каждая — одна ответственность из списка PLAN |
| 2 (`_cmd_approve_merge_gate` — короткая композиция, порядок/отказы буквальны) | OK | тело — 10 операторов; порядок вызовов совпадает с прежней последовательностью строка в строку (сверено по diff) |
| 3 (явный исход без булевых флагов и новой вложенности) | OK | все шаги возвращают `"ok"`/`"refused"`/`"fresh"`/протокольные кортежи; `test_ac2_no_new_condition_nesting.py` подтверждает: макс. глубина вложенности осталась 2 |
| 4 (`_cmd_approve_merge_gate_cycle` не редактируется, сигнатура прежняя) | OK | функция не тронута diff'ом; `test_ac3_cycle_entrypoint_signature_unchanged.py` зелёный |
| 5 (тексты `journal`/`sys.exit`/`print` буквальны) | OK | AST-сверка всех строковых литералов в вызовах `journal`/`exit`/`print` до/после диффа — 50/50, единственное различие — имя переменной внутри f-строки (`note`→`confirmed_ci_note`), сама подставляемая строка идентична; `test_ac4_literal_texts_preserved_on_push_refusal.py` кроет путь, не покрытый тремя AC-5 сценариями |
| 6 (три смоук-сценария дают тот же журнал/вывод) | OK | `test_ac5_three_smoke_scenarios.py` — 3/3 зелёных (нормальный мерж, подтверждённо красный CI, конфликт на защищённом пути) |
| 7 (существующие тесты зелёные без правки `assert`) | OK | прогнаны все файлы, зацепленные модулем (список ниже) — 0 изменений в `tests/` по diff, все зелёные |

## Замечания

Замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M1SD5RHTJ0H0SR0615SVCJM5/acceptance_tests -v` — 9 тестов (AC-1..AC-5), все зелёные.
- `python3 -m unittest tests.test_fsm_merge_gate_done_snapshot tests.test_branch_freshness_gate tests.test_merge_gate_ci_wait -v` — 23 теста, все зелёные (AC-6, модули, прямо зацепленные диффом).
- `python3 -m unittest tests.test_ci_status tests.test_ci_status_kind_gate tests.test_fsm_map_conflict_autoresolve tests.test_gitcmd_branch_reads tests.test_github_adapter tests.test_invariants -v` — 159 тестов, все зелёные (остальные модули, ссылающиеся на предшествующие SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ/01M1GS5HZ1JXFGKVR95HEW0AEZ/01M1R9YEK08XEQWBFX0929WFVJ, найдены `git grep` по id задач).
- `python3 scripts/guard.py tasks/01M1SD5RHTJ0H0SR0615SVCJM5/SPEC.md tasks/01M1SD5RHTJ0H0SR0615SVCJM5/PLAN.md` — `GUARD: ок (2 файлов)`.
- `python3 scripts/codebase_map.py --check` — чисто (карта свежая после мержа коммитов `82c1089f`/подтяжки `195ff13a`; diff `docs/codebase-map.md` в самом MR — только строка `built_at_sha`, содержимое по функциям модуля не меняется, т.к. карта не перечисляет приватные top-level функции — сверено `grep -n fsm_merge_gate docs/codebase-map.md`).
- `python3 -c "compile(...)"` + разбор `ast` модуля `orchestrator/fsm_merge_gate.py` — 19 top-level функций (8 нетронутых + 9 новых шагов + `_cmd_approve_merge_gate`/`_cmd_approve_merge_gate_cycle`), синтаксис корректен.
- `git diff main...task/... --stat -- orchestrator/fsm.py orchestrator/fsm_advance.py` — пусто: файлы вне зон задачи не тронуты (SPEC «Не входит»).
- `git diff main...task/... --stat` целиком — только `docs/codebase-map.md` и `orchestrator/fsm_merge_gate.py`, зоны задачи соблюдены.

## Предложения системе

- Ревью-пакет этой задачи не показал SPEC.md/PLAN.md («не существует в
  ветке задачи») — ожидаемо (артефакты в кодовую ветку не коммитятся),
  но материализация `tasks/<id>/` в рабочем каталоге роли на старте шага
  (conventions-core) в этом воркtree отсутствовала: пришлось руками
  `git checkout artifact/<id> -- tasks/<id>` для доступа к SPEC/PLAN/
  приёмочным тестам. Тот же класс, что уже зафиксирован дважды в памяти
  (`feedback_task_dir_deletion_recovery`,
  `feedback_task_dir_missing_from_artifact_branch`) — стоит проверить,
  почему материализация для роли reviewer в этом шаге не сработала.
