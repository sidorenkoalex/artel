---
task: 01M2B6JNFD381MZT70CVB5NJQC
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Гейт зон: собственный каталог задачи и уборка планки после подтяжки

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1/AC-2) | OK | `orchestrator/checkpoint.py:849` — новая `task_dir_zone(task_id)`, единый источник строки `tasks/<id>/`; `_zone_paths` (checkpoint.py:887) зовёт её вместо инлайна — поведение WIP-чекпоинтов байт-в-байт то же. `fsm_advance.py:907-911` — untracked-пути под `task_dir_zone` отфильтрованы из `untracked` ДО мержа в `files`; committed-дифф (`diff_names`) этим не затронут, `zones = declared + COMMON_ZONES` (fsm_advance.py:929) по-прежнему без каталога задачи — AC-2 сохранён. |
| 2 (AC-3/AC-4) | OK | `pull.py:299-334` — `tests_dir = wt_path/tasks/<id>/acceptance_tests`, `preexisting` фиксируется ДО `materialize_from_branch`, уборка `shutil.rmtree` в `finally` — отрабатывает на всех трёх исходах (`Pulled`, `Conflict` после красной планки, `Refused`). Путь `tests_dir` совпадает с тем, что пишет `acceptance.materialize_from_branch` (`acceptance.py:202-203`, `code_dir/tasks/<id>/acceptance_tests`) — убирается именно материализованное, не весь `tasks/<id>/`. |
| 3 (AC-5) | OK | Ни фильтр untracked в `_zones_gate`, ни `shutil.rmtree` в `pull.py` не журналируют — проверено по diff (новых вызовов `store.journal` в обоих местах нет). |
| 4 (AC-6) | OK | `tests/test_zones_gate.py::ZonesGateOwnTaskDirTest` (AC-1/AC-2), `tests/test_checkpoint_zone_filter.py::TaskDirZoneTest`/`ZonePathsTest.test_task_dir_zone_element_comes_from_shared_helper`, `tests/test_pull.py` (3 юнит-теста + `MaterializedPlankCleanupRealGitTest` на `RealGitSandbox`, AC-4) — все добавлены, ни один существующий тест не удалён/не смягчён (diff `tests/*` — только `+`, см. «Проверено исполнением»). |

## Замечания
(пусто — аппрув)

## Реестр замечаний
(пусто — замечаний не заведено)

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_zones_gate.py tests/test_checkpoint_zone_filter.py tests/test_pull.py -q` — 54 passed.
- `python3 -m pytest tests/test_guard_zones.py tests/test_timeout_checkpoint.py tests/test_checkpoint_stray_acceptance_files.py tests/test_checkpoint_external_step_artifacts.py tests/test_fsm_advance_gate_framework.py tests/test_fsm_advance_gate_smoke.py tests/test_zones_approve.py -q` — 87 passed, 25 subtests passed (смежные модули гейта зон/чекпоинта на предмет регрессий, включая `RealGitSandbox`-тесты).
- `python3 -m pytest tasks/01M2B6JNFD381MZT70CVB5NJQC/acceptance_tests -q` — 7 passed (собственная планка приёмки задачи, AC-1..AC-6).
- `python3 scripts/codebase_map.py` на чистом дереве (после — `git checkout -- docs/codebase-map.md`, дерево возвращено в исходное): diff содержал только строку `built_at_sha`, остальное содержимое совпало с уже закоммиченной картой — карта актуальна, регенерация коммитом задачи не требуется.
- `git diff --stat` по `tests/test_checkpoint_zone_filter.py`, `tests/test_pull.py`, `tests/test_zones_gate.py` — только добавления (28/158/66 строк, без `-`), существующие тесты не тронуты (проверка «не ослаблено» по AC-6).
- Полный набор `tests/` не гонялся в шаге ревью (решение Оператора 05.09) — CI коммита 124f3bc3 зелёный (7 проверок), это условие гейта verifying.

## Предложения системе
(пусто)
