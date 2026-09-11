---
task: 01M29284PTCJXGERV5262E9XMM
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: поделённый родитель при killed — parent_task_id, добавки в status, RETRO «поделена», штатный исход канарейки

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (колонка `parent_task_id`, заполнение в `spawn_subtask`) | OK | Колонка есть и в базовом `CREATE TABLE` (`orchestrator/schema.py:38`), и в `migrate()` (`orchestrator/schema.py:185`) — оба пути дают одну и ту же схему свежей/догоняемой БД (проверено `SchemaHasParentTaskIdColumnTest` и запуском `tests.test_store_schema_migration_parity` — зелёный). Заполнение — `orchestrator/catalog.py:272` через существующий `store.update_task`, без правки `store.py`. |
| 2 (`cmd_status`: `[поделена: ...]` / `[часть N/M родителя ...]`) | OK | `orchestrator/catalog.py:367-382` (`_division_suffix`) — добавкой в конец строки, тем же приёмом, что `_lease_holder_suffix`/`_zone_wait_suffix`. Покрыто AC-2 (родитель/подзадачи/несвязанная задача) — приёмочные тесты зелёные. |
| 3 (`retro.build_killed`: ветка «поделена») | OK | `orchestrator/retro.py:295-314` — отдельная ветка без раздела эскалации, со списком подзадач (id/title/state) и стоимостью РОДИТЕЛЯ (не суммирует подзадачи — проверено юнит-тестом `RetroDividedParentCostIsolationTest`). Ветка без подзадач (`orchestrator/retro.py:316-336`) не изменена — AC-4 зелёный. |
| 4 (`canary._kill_outcome_note`: «поделена» как штатный исход) | OK | `orchestrator/canary.py:657-662` (`_has_subtasks`) проверяется первой в `_kill_outcome_note` (строка после докстринга, до старой логики по `steps`); `normal_outcome = metrics["kill_note"] in ("штатно", "поделена")` (`orchestrator/canary.py:1000`); печать строкой исхода (`orchestrator/canary.py:1055`) не имеет hardcoded-списка значений — «поделена» отображается корректно и отличимо. AC-5 зелёный. |
| 5 (без нового состояния FSM, без правки fsm.py/fsm_postmerge.py/snapshot.py) | OK | Diff подтверждён `git diff --stat` — только 7 файлов (`canary.py`, `catalog.py`, `retro.py`, `schema.py`, `docs/codebase-map.md`, `tests/test_canary.py`, `tests/test_parent_task_division.py`); `fsm*.py`/`snapshot.py` не тронуты. |

AC-1..AC-5 — зелёные (см. «Проверено исполнением»). AC-6 — легальный `manual` (класс «ci-covered» из скила review-checklist: критерий о неослаблении существующего покрытия, уже гоняемого полным `tests/` в CI на каждый пуш) — подтверждено собственным прогоном перечисленных модулей.

## Замечания

- minor — `tests/test_parent_task_division.py:50` (`DivisionSuffixSingleSubtaskTest.test_single_subtask_shows_one_of_one`), `tests/test_parent_task_division.py:80` (`RetroDividedParentCostIsolationTest.test_cost_block_shows_only_the_parents_own_spend`), `tests/test_parent_task_division.py:107` (`HasSubtasksTest.test_task_without_subtasks_is_not_flagged_as_divided`) — три из шести тестов нового файла не несут в докстринге заявку `Ловит мутацию: …` (skills/test-authoring.md, обязательное поле для нового/изменённого теста). У первого есть только докстринг КЛАССА («Один родитель с ОДНОЙ подзадачей — «часть 1/1», не «1/2»…») без заявки о ловимой мутации на самом методе; у второго и третьего докстринга нет вовсе. Для сравнения — остальные 3 теста этого же файла (`SchemaHasParentTaskIdColumnTest.test_fresh_schema_carries_the_column:19`, `RetroDividedParentCostIsolationTest.test_divided_outcome_line_replaces_killed_reason:98`) и ВСЕ акцептанс-тесты задачи (`tasks/01M29284PTCJXGERV5262E9XMM/acceptance_tests/test_ac1_*.py:31`, `test_ac2_*.py:51,66,82` и др.) конвенцию соблюдают — разрыв только в этих трёх местах одного файла. Последствие: следующий ревьювер/разработчик не может свериться, какую мутацию тест ловит, не читая тело теста и не гадая по имени метода. Предложение: дописать в докстринг каждого из трёх методов явную заявку `Ловит мутацию: …` (сценарий + наблюдаемое свойство), по образцу соседних тестов того же файла.

Функциональных дефектов (Фаза B: соответствие SPEC, корректность, безопасность, целостность) не найдено — код корректен, все запущенные тесты зелёные, guard проходит, ANSWER-1 (разрешение конфликта подтяжки main) исполнено в точности как предписано.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_parent_task_division.py:50,80,107 | 3 теста без заявки `Ловит мутацию: …` в докстринге | ревьювер/разработчик не может свериться, какую мутацию тест ловит, без чтения тела | дописать докстринг каждому из трёх методов по образцу соседних тестов файла/акцептансов задачи |

## Вердикт

changes_requested — единственное требуемое исправление: дописать докстринги `Ловит мутацию: …` трём тестам, перечисленным в R1-F1 (`tests/test_parent_task_division.py:50,80,107`). Функционально код готов к мержу — после правки докстрингов достаточно отметить R1-F1 `fixed` тем же id.

## Проверено исполнением

- `python3 -m unittest tests.test_parent_task_division tests.test_canary tests.test_retro -v` — 100 тестов, все зелёные.
- `python3 -m unittest tests.test_catalog_spawn_subtask tests.test_store_schema_migration_parity tests.test_catalog_status_log tests.test_catalog_wave_breaker_status -v` — 17 тестов, все зелёные (включая `MigrateIsANoopOnAFreshSchemaTest.test_every_migrated_tasks_column_already_lives_in_create_table`, прямую проверку класса мутации, заявленного в `SchemaHasParentTaskIdColumnTest`).
- `python3 -m unittest discover -s tasks/01M29284PTCJXGERV5262E9XMM/acceptance_tests -v` — 10 тестов (AC-1..AC-5), все зелёные.
- `python3 scripts/guard.py tasks/01M29284PTCJXGERV5262E9XMM/SPEC.md tasks/01M29284PTCJXGERV5262E9XMM/PLAN.md tasks/01M29284PTCJXGERV5262E9XMM/ANSWER-1.md` — «GUARD: ок (3 файлов)».
- `python3 scripts/guard.py --all` — «GUARD: ок (772 файлов)», предупреждения только по чужим задачам (01M1RA0R9AH9RBAHD4A2Z5SEWQ, T067), к этой задаче не относятся.
- `python3 scripts/codebase_map.py` в рабочем дереве + `git diff --stat`/`git diff` на `docs/codebase-map.md` — разошлось только поле `built_at_sha` (легитимное отставание, см. скил review-checklist), содержимое карты (модули из подтянутого main и новый `tests/test_parent_task_division.py`) полностью совпало с закоммиченным; файл возвращён `git checkout -- docs/codebase-map.md` в исходное состояние после проверки.
- `git diff HEAD 0607e5d6 -- docs/backlog.md` — пусто: `docs/backlog.md` в точности версия main, как предписано ANSWER-1.
- `git diff 2fd19394 b02f3dd9 --stat` — подтверждено, что мерж-коммит не тронул код задачи (`catalog.py`/`schema.py`/`retro.py`/`canary.py`/`tests/test_parent_task_division.py`), только `docs/backlog.md`, `docs/codebase-map.md` и независимые файлы main — соответствует ANSWER-1 («другие файлы в разрешении не трогать»).

Полный набор `tests/` не прогонялся (решение Оператора 05.09) — CI коммита b02f3dd9 зелёный (14 проверок, см. пакет).

## Предложения системе
