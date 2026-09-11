---
task: 01M290PVYG2VJK6442H5BAX9MA
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: чекпоинты пульта коммитят только зоны задачи и tasks/<id>/; на подтяжке посторонний файл — отказ, не предупреждение; гейт зон видит неотслеживаемые файлы

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (все WIP-чекпоинты коммитят только зоны задачи) | OK | `_zone_paths`/`_stray_staged_paths`/новая сигнатура `_commit_worktree_change` — все четыре чекпоинта переведены, реальный `git show --name-only` подтверждает: посторонний файл не попадает в кодовый коммит (проверено исполнением, см. ниже) |
| 2 (одна запись журнала «посторонние файлы в worktree») | OK | `STRAY_WORKTREE_FILES_ACTION`, один вызов `store.journal` вне цикла — тест `test_ac2_multiple_stray_files_write_exactly_one_journal_entry` зелёный |
| 2/AC-3/AC-4 (подтяжка отказывает переходу целиком) | OK | `refuse_on_stray=True` в `commit_pull_checkpoint`, `pull._clean_worktree_before_merge`/`evaluate` возвращают `Refused` без `git merge`; `tests/test_pull.py::test_refused_when_worktree_carries_a_file_outside_the_task_zones` и `acceptance_tests/test_ac3_ac4_...` зелёные, HEAD/state неизменны подтверждено |
| 3/AC-5 (белый список `commit_step_artifacts` — источник guard) | OK | `_is_extraneous_task_root_file` делегирует `guard.is_extraneous_task_root_file` с единственным добавленным исключением `RETRO.md` (легитимный артефакт `orchestrator/snapshot.py`, вне списка guard по объёму задачи 01M28NX43E) |
| 4/AC-6 (гейт зон видит неотслеживаемые файлы) | OK | `_untracked_worktree_paths` (`git status --porcelain=v1 --untracked-files=all`) сливается с committed-диффом ДО проверки защищённых путей и зон; `test_ac6_zones_gate_untracked_files.py` и юнит-тесты парсинга porcelain зелёные |
| 5/AC-7 (`.gitignore` — черновики ролей) | OK | три новых шаблона с `/`-префиксом (граница на корень проверена тестом `test_ac7_role_scratch_pattern_does_not_reach_into_subdirectories`) |
| 6 (тесты покрывают класс, существующие наборы не ослаблены) | Реализовано не полностью | Покрыты `commit_timeout_checkpoint`, гейт зон, `commit_pull_checkpoint`, парсинг porcelain — но НЕ `commit_success_checkpoint` в сочетании «зона + посторонний файл»: именно этот пробел пропустил регрессию R1-F1 ниже. Существующие наборы (`test_timeout_checkpoint`, `test_step_autocommit`, `test_checkpoint_external_step_artifacts`, `test_checkpoint_stray_acceptance_files`, `test_zones_gate`, `test_guard_task_root_subdirectory`) прогнаны — зелёные, не ослаблены (сверено диффом: ни один существующий assert не удалён и не смягчён) |

## Замечания

- major — `orchestrator/checkpoint.py:471-479` (`commit_success_checkpoint`) — `summary = _staged_change_summary(wt, exclude)` считает список файлов/строк ДО того, как `_commit_worktree_change` (вызванный следующей строкой) применит новый фильтр по зонам и снимет со стейджа посторонние пути. В результате `detail`, который идёт и в журнал (`store.journal(..., "код закоммичен пультом за роль", detail)`), и в возврат функции, перечисляет посторонний файл как ЗАКОММИЧЕННЫЙ — хотя тот же самый файл РЕАЛЬНО исключён из коммита и УЖЕ описан отдельной записью «посторонние файлы в worktree» от того же вызова. Проверено исполнением (см. ниже): при зоне `orchestrator/allowed_module.py` и постороннем `docs/stray_note.md` реальный коммит содержит только `orchestrator/allowed_module.py` (`git show --name-only` подтверждает), но `detail` == `"docs/stray_note.md, orchestrator/allowed_module.py (4 строк) (sha ...)"` — посторонний файл в списке, и количество строк («4») инфлировано его вкладом (сам зонный файл — 3 строки). Две журнальные записи одного и того же вызова прямо противоречат друг другу: одна называет файл «посторонним», другая — «закоммиченным». Это ломает ровно то, ради чего заведена вся задача (доверенная запись о том, что реально произошло с посторонним файлом) — Оператор/автодиагностика, читающие журнал, получат недостоверную картину. Docstring самой `_staged_change_summary` (строки 393-398) утверждает, что повторный `add -A`/`reset` внутри `_commit_worktree_change` «идемпотентен — тот же индекс», что было верно ДО этой задачи и перестало быть верным после вставки стрей-фильтра — комментарий не обновлён вслед за кодом.
  Предложение: считать `summary` уже ПОСЛЕ применения зонного фильтра — например, вынести вычисление `_zone_paths`/`_stray_staged_paths`/снятие стрей-путей со стейджа в отдельный шаг, общий для `_staged_change_summary` и `_commit_worktree_change` (либо пусть `_commit_worktree_change` возвращает набор РЕАЛЬНО закоммиченных путей, и `commit_success_checkpoint` строит `detail` из него, а не из предварительного `numstat`).

- minor — `orchestrator/checkpoint.py:906-914` (`_commit_worktree_change`, ветка `refuse_on_stray=True`) — обе ветки `if unstage_all.returncode != 0` возвращают буквально одно и то же (`False, "", stray`), различие в исходе `git reset` ни на что не влияет:
  ```
  if refuse_on_stray:
      unstage_all = gitcmd.in_repo(wt, "reset", "-q")
      if unstage_all.returncode != 0:
          return False, "", stray
      return False, "", stray
  ```
  Мёртвая ветка — упрости до двух строк (`gitcmd.in_repo(wt, "reset", "-q"); return False, "", stray`).

- minor — `orchestrator/checkpoint.py:915-917` (`_commit_worktree_change`, ветка `refuse_on_stray=False`) — на отказе `git reset -q -- *stray` возврат `(False, "", [])` теряет уже найденный `stray` (обнулён до `[]`), тогда как соседняя ветка (`staged.returncode != 1`, строка чуть ниже) на аналогичном отказе честно возвращает `stray`. Сейчас безвредно — все три вызывателя (`commit_timeout_checkpoint`/`commit_abnormal_checkpoint`/`commit_pause_now_checkpoint`) принимают третий элемент кортежа как `_stray` и игнорируют его — но это расхождение контракта возврата внутри одной и той же функции, ловушка для следующего вызывающего кода, который однажды начнёт читать третий элемент. Верни `stray` и здесь, для консистентности со всеми остальными return-точками функции.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/checkpoint.py:471-479 | `_staged_change_summary` считает файлы/строки ДО зонного фильтра `_commit_worktree_change` | журнал «код закоммичен пультом за роль» лжёт о составе коммита, противоречит соседней записи «посторонние файлы в worktree» о том же файле | пересчитать `summary` после применения зонного фильтра (или строить `detail` из фактически закоммиченных путей) |
| R1-F2 | open | orchestrator/checkpoint.py:906-914 | `_commit_worktree_change`, ветка `refuse_on_stray=True` — обе ветки `if unstage_all.returncode != 0` возвращают одно и то же | мёртвый код, лишняя когнитивная нагрузка при чтении | схлопнуть в две строки без ветвления |
| R1-F3 | open | orchestrator/checkpoint.py:915-917 | `_commit_worktree_change`, ветка `refuse_on_stray=False` — на отказе `git reset` возврат обнуляет `stray` до `[]`, в отличие от соседних return-точек той же функции | несогласованный контракт возврата, ловушка для будущего вызывающего кода, читающего третий элемент кортежа | вернуть `stray` вместо `[]` на этой ветке |

## Вердикт

changes_requested — один major (R1-F1, ложная запись журнала о составе коммита) и два minor (R1-F2/R1-F3, консистентность возврата `_commit_worktree_change`). Основная механика фильтра по зонам (AC-1/AC-2/AC-3/AC-4/AC-6/AC-7) реализована корректно и проверена исполнением; R1-F1 не ломает сам git-коммит, но ломает доверие к журналу — ровно тот класс проблемы (недостоверный след того, что случилось с посторонним файлом), ради которого заведена вся задача, поэтому не пропускаю его как minor.

## Проверено исполнением

- `python3 -m pytest tasks/01M290PVYG2VJK6442H5BAX9MA/acceptance_tests/ tests/test_checkpoint_zone_filter.py tests/test_pull.py tests/test_zones_gate.py tests/test_timeout_checkpoint.py tests/test_step_autocommit.py tests/test_checkpoint_external_step_artifacts.py tests/test_checkpoint_stray_acceptance_files.py tests/test_guard_task_root_subdirectory.py -q` — 120 passed, 19 subtests passed.
- `python3 -m pytest tests/test_guard_extraneous_acceptance_files.py tests/test_fsm_advance_gate_smoke.py tests/test_advance_guard.py tests/test_protected_paths_gate.py -q` — 30 passed, 13 subtests passed (соседние наборы, задетые переносом критерия на `guard`/защищённые пути, не ослаблены).
- `python3 scripts/codebase_map.py --check` — молча ок; `git diff docs/codebase-map.md` после прогона отличается только строкой `built_at_sha` (не дефект по конвенции), содержимое совпадает; локальную перегенерацию откатил (`git checkout -- docs/codebase-map.md`).
- `python3 -m scripts.guard --all` — «ок (773 файлов)», два предупреждения по `_sandbox.py` двух ДРУГИХ задач (01M1RA0R9AH9RBAHD4A2Z5SEWQ, T067) — не блокирующие, вне зоны этой задачи.
- Ручной репро (найдено R1-F1): `commit_success_checkpoint` на worktree с зоной `orchestrator/allowed_module.py`, зонным файлом (3 строки) и посторонним `docs/stray_note.md` (1 строка) — `git show --name-only` после вызова: только `orchestrator/allowed_module.py`; журнал: `посторонние файлы в worktree | посторонние файлы в worktree: docs/stray_note.md` СЛЕДОМ `код закоммичен пультом за роль | docs/stray_note.md, orchestrator/allowed_module.py (4 строк) (sha ...)` — противоречие подтверждено.
- `grep -rn "<<<<<<<\|=======\|>>>>>>>" orchestrator/checkpoint.py orchestrator/pull.py orchestrator/fsm_advance.py .gitignore` — пусто, конфликтных маркеров после подтяжки main (ANSWER-1) не осталось; `docs/backlog.md` не отличается от базы сравнения — разрешение конфликта по ANSWER-1 отработано.
- Расширение зон на `orchestrator/pull.py` — мандат ANSWER-2.md несёт маркер `Расширение зон разрешено:` НАЧАЛОМ строки (в отличие от многострочной формулировки ANSWER-1.md, которую сам PLAN «Предложения системе» отмечает как непарсящуюся) — раздел PLAN «## Расширение зон» покрыт мандатом корректно.

## Предложения системе

- `orchestrator/checkpoint.py::_staged_change_summary` docstring (строки 393-398) декларирует «повторный add -A/reset в `_commit_worktree_change` идемпотентен — тот же индекс», и это утверждение стало ложным именно в этой задаче, когда `_commit_worktree_change` обзавёлся зонным фильтром между вызовами. Проверка такого рода docstring-инвариантов («что предполагает вызывающий код о состоянии, которое меняет функция ниже») не входит ни в один пункт review-checklist явно — стоило бы явно называть в разделе «Корректность»: комментарий, описывающий побочный эффект чужой функции, — сигнал перепроверить этот эффект при любой правке той функции.
