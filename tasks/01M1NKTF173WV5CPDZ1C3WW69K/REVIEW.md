---
task: 01M1NKTF173WV5CPDZ1C3WW69K
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 3
---

# REVIEW: Артефакты роли — из артефактной ветки на старте шага (регрессия A7 №9)

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (материализация `tasks/<id>/` на старте шага) | OK | Не тронуто этой итерацией; happy path подтверждён в итерациях 1-2 (AC-1/AC-2/AC-8 зелёные). |
| 2 (бриф несёт SPEC/PLAN/REVIEW, без «прочитай ...SPEC.md») | OK | Не тронуто этой итерацией; AC-3/AC-4 зелёные. |
| 3 (роли не коммитят `tasks/<id>/` в кодовую ветку) | OK | R1-F1 закрыт: `commit_abnormal_checkpoint` (`orchestrator/checkpoint.py:230-290`) и `commit_pause_now_checkpoint` (`orchestrator/checkpoint.py:293-346`) теперь несут дословно то же мандат-ветвление, что уже было у `commit_timeout_checkpoint` — `developer` коммитит код-worktree с `exclude=f"tasks/{task_id}"`, остальные роли идут через `_discard_out_of_mandate_changes`; `tasks/<id>/` переносится в артефактную ветку `_commit_external_step_artifacts` безусловно, для ЛЮБОЙ роли. Точная репродукция замечания итерации 2 (материализованный `role_cwd` SPEC.md роли `reviewer` больше не коммитится в кодовую ветку) подтверждена собственным прогоном (см. «Проверено исполнением»), а не только текстом PLAN. |
| 4 (конфликт-гвард автокоммита) | OK | Не тронуто этой итерацией; сохранён поверх подтяжки main, AC-6/AC-7 зелёные. |
| 5 (существующие тесты зелёные без ослабления) | OK | Полный `tests/` — 1487, все зелёные (было 1481, +6 новых тестов R1-F1); ничего не удалено и не ослаблено. |
| 6 (эскалация только статусом escalate) | OK | Не тронуто этой итерацией; `RULES["plan"]["statuses"]` содержит `escalate`, `escalation_status_errors` на месте (`scripts/guard.py:54-62,599+`). |
| 7 (лок удаления `acceptance_tests/` до фиксации) | OK | Не тронуто этой итерацией; ветка `deletable` сохранена в `_commit_external_step_artifacts`. |
| 8 (требования 6/7 покрыты тестами) | OK | Покрыты приёмочными и `tests/test_artifact_materialization.py`, не тронуты этой итерацией. |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/checkpoint.py:230-346 (`commit_abnormal_checkpoint`, `commit_pause_now_checkpoint`) | материализованный `tasks/<id>/` безусловно коммитился в кодовую ветку двумя из трёх WIP-чекпоинтов (мандат-ветвление было только у `commit_timeout_checkpoint`) | нарушение требования 3/AC-9 на путях аварийного завершения и `pause --now`, для ЛЮБОЙ роли | подтверждено закрытым: обе функции получили то же мандат-ветвление, что несёт `commit_timeout_checkpoint` (проверено чтением кода, строка в строку); собственная репродукция ревьювера (материализация `role_cwd` роли `reviewer` без мандата кода → `commit_abnormal_checkpoint`/`commit_pause_now_checkpoint` → `git ls-tree HEAD` кодовой ветки) больше НЕ содержит `tasks/<id>/SPEC.md` — воспроизведено прогоном новых тестов `test_materialized_spec_is_absent_from_the_code_branch_after_{abnormal_end,pause_now}` (`tests/test_timeout_checkpoint.py:479,616`), оба зелёные; докстринги обоих тестов несут корректную заявку «Ловит мутацию»/точное описание сценария. Полный набор (1487) и приёмочные (19) зелёные, `guard.py` без нарушений — см. «Проверено исполнением». |
| R1-F2 | accepted | orchestrator/store.py:40 (CREATE TABLE tasks) | закрыт в итерации 2, повторно не тронут | — | без изменений с итерации 2, `accepted` подтверждён ранее |

## Вердикт

approved — реестр замечаний полностью закрыт (`accepted`), 0 blocker/major. R1-F1 закрыт по существу для всех трёх WIP-чекпоинтов (таймаут — итерация 1/подтяжка main, аварийное завершение и `pause --now` — эта итерация), подтверждён независимым прогоном тестов, а не только чтением PLAN. Требования 1-8 SPEC реализованы, существующие тесты не ослаблены, диф этой итерации ограничен заявленной зоной (`orchestrator/checkpoint.py`, `tests/test_timeout_checkpoint.py`, регенерация карты) плюс не связанная с задачей подтяжка main (калибровка `TOKEN_RATES`, `orchestrator/config.py`/`docs/roadmap.md` — вне зоны этой задачи, не затрагивает предмет ревью).

## Проверено исполнением

- `git checkout -- tasks/01M1NKTF173WV5CPDZ1C3WW69K/` — рабочее дерево снова показывало каталог задачи удалённым на старте ревью (та же память об инциденте, что и в прошлых итерациях); восстановлено из индекса.
- `python3 -m unittest tests.test_timeout_checkpoint -v` — **25 тестов, OK** (было 19 до этой итерации). В их числе оба новых регресс-теста точной репродукции замечания итерации 2: `CommitAbnormalCheckpointTest.test_materialized_spec_is_absent_from_the_code_branch_after_abnormal_end`, `CommitPauseNowCheckpointTest.test_materialized_spec_is_absent_from_the_code_branch_after_pause_now` — оба зелёные, подтверждают закрытие R1-F1 напрямую.
- `python3 -m unittest discover -s tests` (полный набор, передний план, ~203 с) — **1487 тестов, OK** (было 1481, +6 новых — совпадает с заявкой PLAN).
- `python3 -m unittest discover -s tasks/01M1NKTF173WV5CPDZ1C3WW69K/acceptance_tests` — 19 тестов, OK.
- `python3 scripts/guard.py tasks/01M1NKTF173WV5CPDZ1C3WW69K/{PLAN,REVIEW,SPEC}.md` — GUARD: ок (3 файлов).
- Чтение `orchestrator/checkpoint.py:230-346` — подтвердило, что `commit_abnormal_checkpoint` и `commit_pause_now_checkpoint` теперь дословно повторяют мандат-ветвление `commit_timeout_checkpoint` (`role == "developer"` → `_commit_worktree_change(wt, message, exclude=f"tasks/{task_id}")`, иначе → `_discard_out_of_mandate_changes(wt, task_id)`) и безусловно зовут `_commit_external_step_artifacts(conn, task_id, role, config.DEFAULT_TARGET)` после ветвления.
- `git diff c0cd1d93 31d1a8d4 --stat` (от коммита предыдущего вердикта до HEAD ветки) — диф этой итерации ограничен `orchestrator/checkpoint.py`, `tests/test_timeout_checkpoint.py`, `tasks/01M1NKTF173WV5CPDZ1C3WW69K/{PLAN,REVIEW}.md`, `docs/codebase-map.md` (регенерация) плюс не связанная с задачей подтяжка main (`orchestrator/config.py`, `docs/roadmap.md` — калибровка `TOKEN_RATES`, роль Оператора, вне зоны задачи); `git show 9ea05b26 -- orchestrator/config.py docs/roadmap.md` — пусто, эти файлы принесла отдельно только подтяжка (`31d1a8d4`), не разработчик этой задачи.
- `git show 9ea05b26 -- docs/codebase-map.md` и локальный прогон `python3 scripts/codebase_map.py` — содержимое карты (без строки `built_at_sha`) не изменилось; расхождение `built_at_sha` (указывает на предыдущий коммит, не на HEAD) — не дефект (см. `skills/review-checklist.md`), локальная регенерация отменена (`git checkout -- docs/codebase-map.md`), в рабочем дереве изменений не оставлено.

## Предложения системе

Нет новых. Предложение итерации 2 («структурный тест на одинаковое поведение трёх WIP-чекпоинтов относительно `tasks/<id>/`») остаётся актуальным ретроспективно — в этой итерации класс закрыт точечно для всех трёх функций, но общий инвариант по-прежнему не гарантирован структурно (только тремя параллельными наборами тестов).
