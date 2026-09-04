---
task: 01M1KT0792125J9ZNJNZJ86E9Q
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 3
---

# REVIEW: Hotfix A7 — маршрут analyst и канал ANSWER через источник артефактов

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`runner.step_role` читает TZ.md через `artifact_source.resolve`, поверх старой проверки, старый путь для прежнего флоу не тронут) | OK | Код (`orchestrator/runner.py:75-105`) байт-в-байт совпадает с одобренным в итерации 3 (`git diff 63c3d16..HEAD -- orchestrator/runner.py` пуст на этой функции; единственная правка файла между итерациями — не связанная с этой задачей `_cmd_run`/`brief.skills_text`, см. «Проверено исполнением»). `test_ac1_analyst_role_reads_artifact_branch.py` (2 теста), `test_ac2_legacy_flow_tz_on_code_branch.py` (1 тест) перепрогнаны — зелёные. |
| 2 (`answer` пишет `ANSWER-n.md` плотницки в артефактную ветку, кодовую ветку/worktree не трогает) | OK | Без изменений с итерации 3. `test_ac3_answer_writes_to_artifact_branch.py` (3 теста) перепрогнан — зелёный. AC-5 `skip` — обоснование не изменилось, легально. |
| 3 (`approve` в `escalated` видит ANSWER) | OK | Без изменений. `test_ac4_approve_returns_from_escalation_after_answer.py` (2 теста) перепрогнан — зелёный. |
| 4 (автокоммит артефактов шага переносит удаления) | OK | Без изменений в коде с итерации 3 (R1-F1 закрыт и принят). `test_ac6_checkpoint_propagates_deletions.py` (2 теста) перепрогнан — зелёный. |
| 5 (существующие тесты зелёные, поведение прежнего флоу не меняется) | OK | Полный `tests/` — 1329 тестов (было 1310 в итерации 3; +19 — тесты, добавленные ДВУМЯ подтянутыми в кодовую ветку задачами main, не этим хотфиксом, см. ниже), все зелёные. `test_ac7_full_suite_and_a7_tests_green.py` — зелёный. |

Код требований 1–5 (`orchestrator/runner.py`, `answer.py`, `artifact_branch.py`, `checkpoint.py`) не менялся с итерации 3 — эта итерация проверяет только последствия двух `подтяжка main` (`7bb54e3`, `7980bb8`), закоммиченных в кодовую ветку задачи ПОСЛЕ approved-вердикта итерации 3 (`63c3d16`), и переподтверждает регресс-набор.

## Замечания

Пусто — новых замечаний не найдено, реестр закрыт целиком в итерации 3.

### Проверка побочных эффектов двух подтяжек main (за пределы SPEC этой задачи, но в зоне «системная целостность»)

Между вердиктом итерации 3 (`63c3d16` на артефактной ветке; соответствующий код-коммит кодовой ветки — `87d8e8e`) и текущим HEAD кодовой ветки (`7980bb8`) в неё влиты две подтяжки `main`, несущие код ДВУХ других задач (`01M1K7KP0D8ZKRM9KTE75DCCYR` — скилы в брифе роли; `01M1KCSTBYF1CRJBSY4P6VYQEA` — детекция буксования). Проверил, что ни одна не задевает требования этого хотфикса:

- `orchestrator/runner.py` — правка `_cmd_run` (чтение текста скилов через `brief.skills_text` вместо диска, задача `01M1K7KP0D8ZKRM9KTE75DCCYR`) находится в ДРУГОЙ функции того же файла; секция `step_role` (строки 75-105, требование 1 этого хотфикса) не тронута — `git diff 87d8e8e..7980bb8 -- orchestrator/runner.py` показывает изменение только вне `step_role`.
- `orchestrator/store.py::set_state` (задача `01M1KCSTBYF1CRJBSY4P6VYQEA`) добавляет вызов `_close_attention_alert` в конец функции — аддитивно, не меняет прежнее поведение `record_fixation`/`_append_passport_line`, от которых зависит `checkpoint._commit_external_step_artifacts` (требование 4).
- `orchestrator/answer.py`, `orchestrator/artifact_branch.py`, `orchestrator/checkpoint.py` (требования 2-4) — не в diff двух подтяжек вовсе.
- Полный регресс-набор (1329 тестов) и все AC-1..AC-7 этой задачи зелёные после обеих подтяжек — прямое подтверждение отсутствия коллизии.

Blocker/major не завожу: подтяжки не входят в зону SPEC этой задачи (сторонний код чужих задач, влитый через main), сама интеграция не сломана — фиксирую находку как «проверено, коллизии нет», а не как замечание.

## Реестр замечаний

Пуст в этой итерации — обе записи предыдущих итераций (`R1-F1`, `R2-F1`, `R2-F2`) уже `accepted` в итерации 3 и не переоткрываются (восстановимы из истории `REVIEW.md`, git log по этому файлу). Новых записей в этой итерации не заведено — код не менялся, замечаний нет.

## Вердикт

approved — код требований 1-5 не менялся с одобренного в итерации 3 состояния; две подтяжки `main`, попавшие в кодовую ветку после итерации 3, проверены на отсутствие коллизии с этим хотфиксом (см. «Замечания»); полный регресс-набор (1329 тестов) и все приёмочные тесты этой задачи (AC-1..AC-7) перепрогнаны в этой итерации и зелёные; `docs/codebase-map.md` свежий (расхождение только в `built_at_sha`); `guard.py` без нарушений; рабочее дерево кодовой ветки чистое (артефакты задачи вне её индекса, R2-F1 не регрессировал).

## Проверено исполнением

- `git diff 87d8e8e 7980bb8 -- orchestrator/runner.py orchestrator/answer.py orchestrator/artifact_branch.py orchestrator/checkpoint.py` — только `runner.py`, изменение вне `step_role` (см. «Замечания»); `answer.py`/`artifact_branch.py`/`checkpoint.py` не тронуты.
- `git diff main...task/01m1kt0792125j9znjnzj86e9q-hotfix-a7-marshrut-analyst-i-k -- orchestrator/answer.py orchestrator/artifact_branch.py orchestrator/checkpoint.py orchestrator/runner.py` — прочитан целиком, соответствует требованиям 1/2/4 SPEC и содержанию, одобренному в итерациях 2-3.
- `git diff main...task/... -- tests/test_answer.py tests/test_checkpoint_external_step_artifacts.py` — прочитан целиком; докстринг `test_same_role_second_step_in_the_same_state_does_not_drop_an_untouched_file` несёт заявку `Ловит мутацию: …`, совпадающую с фактическим кодом (`checkpoint.py`, `_DELETABLE_ARTIFACT_TYPES`) — то же, что зафиксировано в итерации 3.
- `python3 -m unittest discover -s tests -q` (прямой прогон, полный вывод в файл, не через `tail`) — `Ran 1329 tests in 145.357s`, `OK`.
- `python3 scripts/guard.py --all` — `GUARD: ок (405 файлов)`.
- `python3 scripts/codebase_map.py` (локальный прогон) — `git diff docs/codebase-map.md` без строки `built_at_sha` пуст; локальная перегенерация отменена `git checkout -- docs/codebase-map.md`, в коммит не идёт.
- Материализовал `tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/` из артефактной ветки в рабочее дерево кодовой ветки (`git worktree add --detach` на `artifact/01m1kt0792125j9znjnzj86e9q`, покомандное копирование `.py`-файлов) и перепрогнал по одному (`pytest`):
  - `test_ac1_analyst_role_reads_artifact_branch.py` + `test_ac2_...` + `test_ac3_...` + `test_ac4_...` — 8 тестов, все `passed`.
  - `test_ac5_legacy_flow_answer_escalation.py` — легальный `skip` всего файла (0 тестов), без ошибок.
  - `test_ac6_checkpoint_propagates_deletions.py` — 2 теста, `passed`.
  - `test_ac7_full_suite_and_a7_tests_green.py` — 2 теста, `passed` (153с; внутри — полный `tests/` и приёмочные тесты задачи `01M1H224X5A8W159MKF1Q24R5Y`, оба зелёные).
- После проверок материализованный `tasks/01M1KT0792125J9ZNJNZJ86E9Q/` убран из рабочего дерева кодовой ветки (`rm -rf`, каталог был untracked) — `git status --short` там пуст.
- Пакет ревью снова не собрался (SPEC.md/PLAN.md — «не показан», stat/diff по невалидному `00e32aaf...` — тот же класс, что в итерациях 2 и 3, отмечаю в третий раз подряд в «Предложения системе»). Прочитано точечно сверх пакета — причина: без этого нельзя восстановить состояние задачи и посчитать реальный диф: `SPEC.md`/`PLAN.md`/`REVIEW.md` итераций 1-3 — с `artifact/01m1kt0792125j9znjnzj86e9q` (`git show <ветка>:<путь>`, `git log --oneline -- tasks/01M1KT0792125J9ZNJNZJ86E9Q/REVIEW.md`); реальный код-дифф этой задачи — `git diff main...task/01m1kt0792125j9znjnzj86e9q-hotfix-a7-marshrut-analyst-i-k` (12 файлов после двух подтяжек main; из них к этой задаче относятся 6 — `answer.py`, `artifact_branch.py`, `checkpoint.py`, `runner.py`, `test_answer.py`, `test_checkpoint_external_step_artifacts.py`, остальные 6 — сторонний код задач `01M1K7KP0D8ZKRM9KTE75DCCYR`/`01M1KCSTBYF1CRJBSY4P6VYQEA`, влитый через main, вне зоны этого ревью); `git log --all --grep`/`git branch --all --contains` — для восстановления, где на самом деле лежат артефакты этой задачи и что именно изменилось между итерациями 3 и 4.

## Предложения системе
- Сборщик ревью-пакета третий раз подряд (после итераций 2 и 3) не резолвит sha предыдущего вердикта и не показывает SPEC.md/PLAN.md для этой задачи — наблюдение итераций 2-3 («сборщик, похоже, всё ещё ищет артефакты в кодовой ветке, а не через `artifact_source.resolve`») не устранено ни разу за три итерации подряд. Стоит завести отдельную задачу на сборщик пакета явно, если её ещё нет — три независимых ревью одной и той же задачи начинали с одинакового ручного восстановления контекста.
- Инструкция ревьювера («Код НЕ правь — только REVIEW.md в ветке задачи») не различает кодовую и артефактную ветки явно, а после этого хотфикса REVIEW.md по факту обязан коммититься ИМЕННО в артефактную ветку (см. R2-F1 итерации 2 — тот же класс смешения, который сама задача устраняет). Формулировка инструкции роли reviewer стоит уточнить явным адресом (`artifact/<id>`), чтобы не полагаться на то, что ревьювер сам восстановит архитектуру по истории коммитов, как пришлось в этой итерации.
