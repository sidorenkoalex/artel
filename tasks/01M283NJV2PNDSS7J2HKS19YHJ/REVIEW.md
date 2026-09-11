---
task: 01M283NJV2PNDSS7J2HKS19YHJ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: регрессия №16 — планка на переходе `in_dev -> verifying` гоняется и при свежей ветке

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1. Материализация планки для собственного target ДО `acceptance.run`, независимо от исхода подтяжки | OK | `orchestrator/fsm_advance.py:1159-1163` — `elif workspace.on_task_branch(...)` теперь вызывает `acceptance.materialize_from_branch(task_id, branch, run_cwd)` тем же приёмом, что уже стоял на ветке внешнего target (строки 1153-1158). |
| 2. Именованный отказ «планка не найдена в источнике» вместо зелёного «не заведены» | OK | `_missing_plank_refuses()` (`fsm_advance.py:1131-1149`) читает SPEC.md артефактной ветки через `fsm._read_branch_text_or_refuse` и решает по `guard.requires_ac_markup(meta)` — тот же предикат, что у `pull.py::_materialize_and_run_plank`; текст отказа дословно «планка не найдена в источнике». |
| 3. Повторный прогон на `Pulled` не ослаблен | OK | Материализация звонится безусловно (не зависит от исхода подтяжки), `acceptance.run` вызывается тем же кодом ниже — второй прогон на `Pulled` (первый внутри `pull.evaluate`) сохранён. Подтверждено тестом AC-4 приёмочной планки (`acc_run.call_count == 2`). |
| 4. Тесты регрессии (Fresh + пустой `tasks/<id>` + лок → материализация и прогон; отсутствие в источнике при локе → отказ; `skip_tests` → переход проходит; существующие тесты без правки ассертов) | OK | Покрыто приёмочной планкой задачи `tasks/01M283NJV2PNDSS7J2HKS19YHJ/acceptance_tests/test_fresh_plank_materializes.py` (AC-1/AC-2/AC-3/AC-4/AC-5). Существующий тест `tests/test_git_fixation.py::ExternalTargetAdvanceIgnoresDirtyCheckTest` донастроен фикстурой SPEC-заглушки (`skip_tests`) без правки ассертов — см. «Проверено исполнением». |

## Замечания

Замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| — | — | — | замечаний в этой итерации не заведено | — | — |

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M283NJV2PNDSS7J2HKS19YHJ/acceptance_tests/test_fresh_plank_materializes.py -v` — 5 тестов (AC-1..AC-5), все зелёные.
- `python3 -m unittest tests.test_git_fixation tests.test_branch_freshness_gate tests.test_fsm_autogate tests.test_fsm_branch_correct_status_reads tests.test_fsm_map_conflict_autoresolve tests.test_id_format_guard tests.test_review_package tests.test_workspace -v` — 198 тестов, все зелёные (модули, затронутые диффом и вызывающие `_acceptance_run_refuses`/`workspace.on_task_branch`).
- Мутационная проверка вручную: временно откатил материализацию для собственного target в `_acceptance_run_refuses` (убрал вызов `acceptance.materialize_from_branch` на ветке `elif workspace.on_task_branch(...)`, вернул прежний `acc_tdir = run_cwd / "tasks" / task_id`) и перезапустил приёмочную планку — `test_ac1_...`, `test_ac2_...`, `test_ac5_...` покраснели ровно так, как заявлено в их докстрингах («Ловит мутацию»), `test_ac3_...`/`test_ac4_...` остались зелёными. Файл `orchestrator/fsm_advance.py` возвращён `git checkout --` (подтверждено `git status --short` — чисто).
- `docs/codebase-map.md`: перегенерировал `python3 scripts/codebase_map.py` и сравнил с версией в диффе построчно без `built_at_sha` (`grep -v '^built_at_sha:'`) — расхождений в содержимом нет, только легитимная метка коммита (правило скила: `built_at_sha` не признак дефекта). Файл возвращён `git checkout --`.
- Сверка diff `tests/`: изменения только в `tests/test_git_fixation.py` — добавлена фикстура `SPEC_SKIP_TESTS` и передача её в `commit_files` существующего теста `ExternalTargetAdvanceIgnoresDirtyCheckTest`; ни один существующий ассерт не тронут и не ослаблен (проверено построчно по diff и зелёным прогоном модуля).
- Проверено адресно: единственный вызов `_acceptance_run_refuses` — из `in_dev()` (`fsm_advance.py:1298`); соседний путь `_review_approved` (approve → acceptance, `fsm_advance.py:287-293`) не материализует планку для собственного target, но не задет тем же классом бага — `fsm_autogate._autogate_conditions` читает условие «а» (наличие/AC-разметка планки) напрямую из артефактной ветки (`gitcmd.ls_tree_files`/`gitcmd.show`), не с диска `acc_tdir` (см. докстринг `orchestrator/fsm_autogate.py:1-9,31-41` — уже вынесено отдельной задачей 01M1NBWWPJMHKJMYXRDCM0W0C5); побочных эффектов вне заявленного PLAN «Влияние на систему» нет.

## Предложения системе

Нет.
