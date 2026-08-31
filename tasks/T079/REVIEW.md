---
task: T079
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: B1b: GitHub-адаптер, Draft-MR и состояние verifying

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (Draft MR на первый вход в in_dev, один на цикл) | Реализовано не так | `ensure_draft_mr` и её идемпотентность (`draft_mr_created`) корректны сами по себе, но узел `_maybe_ensure_draft_mr` вызывается не на всех входах в `in_dev` — см. Замечание 1. |
| 2 (undraft на входе в merge_gate) | OK | `_cmd_approve` (fsm.py:1283-1287) зовёт `github_adapter.undraft_mr` сразу после `set_state(..., "merge_gate", ...)`; сбой адаптера — инцидент, не блокирует гейт (unit-тесты `UndraftMrTest`). |
| 3 (merge — побочный эффект локального push, не API-вызов) | OK | `_cmd_approve_merge_gate` не тронута; адаптер не несёт отдельного merge-вызова (ANSWER-1, вариант B) — подтверждено чтением `orchestrator/github_adapter.py` и diff `fsm.py` (нет новых вызовов в merge_gate-ветке `approve`, кроме undraft на входе). |
| 4 (verifying между review и acceptance) | Реализовано верно, с открытой эскалацией | `review -> verifying` — единственный исход по approved+зелёным acceptance_tests (fsm.py:826-835); AC-4 зелёный. Конфликт с `tests/test_invariants.py` (3 теста) — реален, подтверждён прогоном, корректно проанализирован и вынесен в PLAN «Эскалация»; см. «Проверено исполнением» и «Вердикт». |
| 5 (четыре исхода статуса CI в verifying) | OK | `ci.verifying_status`/`run_list` разбирают все 4 исхода корректно (`RunListTest`, `VerifyingStatusTest`, AC-5..AC-8 — все зелёные); тонкая развилка «check_runs вернул (None, why)» трактуется как «пусто» и уходит на `run_list` — согласуется с духом требования, не противоречит формулировке. |
| 6 (потолок ожидания → escalated) | OK | `LIMIT_VERIFYING_ATTEMPTS`, счётчик попыток, сброс на входе в verifying (fsm.py:832, 883) — AC-9 зелёный. |
| 7 (красный CI не выталкивает автоматически) | OK | Ветка `verifying` в `_cmd_advance` не имеет пути в `in_dev` без явного `reject`; AC-8 подтверждает. |
| 8 (reject расширен на verifying) | OK | `_cmd_reject` (fsm.py:1358-1370) — AC-10, AC-11 зелёные, счётчики не растут. |
| 9 (механизм периодического вызова advance вне объёма) | OK | Не реализовывался, контракт разового вызова соблюдён. |

## Замечания

- major — `orchestrator/fsm.py:1329-1333` (возврат из `escalated` в состояние `t["escalated_from"] or "in_dev"`) и `orchestrator/fsm.py:1371-1383` (`reject` из `acceptance` в `in_dev`, унаследованный путь T052) — оба являются легитимными повторными входами задачи в `in_dev`, но не зовут `_maybe_ensure_draft_mr`, в отличие от всех остальных 6 точек входа в `in_dev` в этом diff (fsm.py:848, 940, 1123, 1270, 1356, 1369). Само PLAN.md прямо формулирует намерение как «побочный эффект входа в `in_dev`» (не «побочный эффект НЕКОТОРЫХ входов») — это расхождение между декларируемым дизайном и фактическим покрытием точек вызова.
  Конкретный сценарий поломки: `ensure_draft_mr` падает на самом первом входе в `in_dev` (например, транзиентный сбой `git push -u origin <branch>` или `gh pr create`) — до этой задачи ветка задачи была локальной до самого merge (PLAN «Риски»), т.е. без успешного push ветка вообще не существует на GitHub и check-runs/`gh run list` НИКОГДА её не увидят (проверено: `.github/workflows/ci.yml` триггерится на `push`/`pull_request`, значит без реального push проверок не будет вовсе). Если после этого до входа в `review` не случится ни одной итерации `changes_requested` (обычный путь ретрая, fsm.py:848) — задача доходит до `verifying`, «проверок нет вовсе» держит её до истечения потолка (AC-9), она уходит в `escalated`. Оператор разрешает эскалацию (`approve`) — по коду `escalated_from` для этого класса эскалации не пишется (докстринг fsm.py:1324-1328), значит `back` = `"in_dev"` по умолчанию (fsm.py:1329) — но `_maybe_ensure_draft_mr` здесь не зовётся. Если новый цикл разработки снова доходит до `review -> approved` без `changes_requested`, Draft MR так и не заводится, и цикл эскалации по потолку `verifying` повторяется бесконечно без вмешательства вне FSM.
  Предложение: добавить `_maybe_ensure_draft_mr(conn, task_id)` в обеих точках, тем же приёмом, что и в уже покрытых шести местах (после `set_state` на `in_dev`, до `return`/до конца ветки).

- minor — `orchestrator/github_adapter.py:34-66` (`ensure_draft_mr`) — если `gh pr create --draft` падает с ошибкой «уже существует» (PR реально есть на GitHub, например из-за гонки push/create или предыдущей частично успешной попытки), функция помечает это инцидентом и НЕ выставляет `draft_mr_created=1` — при каждом следующем входе в `in_dev` она будет повторять ту же попытку `pr create` и снова падать с той же ошибкой, без способа обнаружить, что MR на самом деле уже заведён. Не блокирует эту задачу (узкий случай, покрыт инцидент-алертом, не ломает FSM), но стоит учитывать при последующей доработке адаптера.

## Вердикт

changes_requested — устранить пробел из Замечания 1 (два непокрытых входа в `in_dev`) и повторно прогнать `tests/test_github_adapter.py`/полный юнит-сьют.

Отдельно, вне рамок «исправь и подай снова»: конфликт SPEC-требования 4 (AC-4) с тремя тестами `tests/test_invariants.py` — подтверждён прогоном (см. «Проверено исполнением»), реализация соответствует SPEC буквально и корректно, конфликт вызван протекцией `no_paths` (AC-14) на файле, кодирующем СТАРЫЙ инвариант «review → acceptance за один advance», который требование 4 сознательно отменяет. Разработчик не имеет права править `tests/test_invariants.py` (ADR-0002) — решение (принять готовый минимальный патч из PLAN «Эскалация», вариант (а)/default, либо иное) остаётся за Оператором и этим REVIEW не блокируется: весь диапазон `tasks/T079/acceptance_tests/` (19/19, включая AC-4) зелёный без единой правки, AC-14 подтверждён отдельно (`test_ac14_path_scope.py`).

## Проверено исполнением

- `python3 -m unittest discover -s tests` — 1063 теста, 3 красных (все три — `tests/test_invariants.py::FreshVerdictGuardsAcceptanceTest`/`CountersNeverResetTest`, ассерт `state() == "acceptance"` после одного `advance` из `review`, вместо `"verifying"` — совпадает с заявленным в PLAN «Эскалация» конфликтом; фактическая красная тройка идентична названной).
- `cd tasks/T079/acceptance_tests && python3 -m unittest discover -s . -p "test_*.py"` — 19/19 зелёные (AC-1..AC-14 покрыты, включая manual-пометки AC-1/2/3/13 и AC-14 path-scope).
- `python3 -m unittest tests.test_merge_lock tests.test_advance_guard` — 18/18 зелёные (AC-13: T052/T053 не задеты).
- `python3 scripts/codebase_map.py` (регенерация вручную, изменения затем отменены `git checkout -- docs/codebase-map.md`) — diff свёлся только к строке `built_at_sha` (ветка успела уйти вперёд отдельным коммитом после того, как разработчик коммитил карту) — содержимое карты (без sha) идентично закоммиченному, регенерация не устарела.
- Прочитаны (без правки) для проверки конкретных замечаний: `orchestrator/fsm.py` (все точки перехода в `in_dev`, ветка `verifying` в `_cmd_advance`, `_cmd_reject`, `_cmd_approve`), `orchestrator/github_adapter.py`, `orchestrator/ci.py` (новые функции), `orchestrator/alerts.py` (сигнатура `raise_alert` — совпадает с вызовом в `_incident`), `orchestrator/targets.py` (сигнатура `target()`/`TargetsError` — совпадает с `_is_github_target`), `tests/test_invariants.py` (`FSM_STATES`, `STATE_ROLE` — «verifying» не входит в `STATE_ROLE`, поэтому `FsmStatesCoverTheCodeTest` не страдает от отсутствия «verifying» в защищённом `FSM_STATES`), `.github/workflows/ci.yml` (триггеры `push`/`pull_request` — обосновывает серьёзность Замечания 1).

## Предложения системе

- Класс «побочный эффект входа в состояние X реализован не на ВСЕХ фактических путях входа в X» — здесь у `_maybe_ensure_draft_mr` 6 из 8 точек входа в `in_dev` покрыты, 2 пропущены (Замечание 1). Стоило бы завести для этого класса такой же явный чек-лист-приём, как уже есть для «промежуточное состояние ломает свипы test_invariants.py» (PLAN этой же задачи, «Предложения системе»): при добавлении узла, который должен сработать «на каждом входе в состояние Y», разработчику стоит явно перечислить (и держать актуальным списком в комментарии/тесте) все `set_state(..., "Y", ...)` в модуле — иначе рефакторинг/новая ветка эскалации молча теряет побочный эффект.
