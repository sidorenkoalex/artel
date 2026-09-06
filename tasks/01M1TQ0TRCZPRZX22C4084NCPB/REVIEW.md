---
task: 01M1TQ0TRCZPRZX22C4084NCPB
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: CI кодовой ветки до ревью: порядок in_dev -> verifying -> review (ADR-0015)

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (порядок состояний; семь рубежей переезжают на `in_dev -> verifying` целиком, без дублирования) | Частично | Шесть рубежей переехали корректно (проверено чтением + прогоном тестов). Седьмой — «сверка головы на origin» — ДОБАВЛЕН в `in_dev` (`orchestrator/fsm_advance.py:1127-1129`), но НЕ убран со старого места в `review()` (`orchestrator/fsm_advance.py:301-303`) — прямое нарушение «без дублирования», см. замечание R1-F1. |
| 2 (`verifying -> review` только по зелёному CI) | OK | `orchestrator/fsm_advance.py:334-336`; `test_ac01_ac09_state_order.py::test_ac9_...`, `test_verifying_ceiling.py::test_green_ci_moves_on_regardless_of_elapsed_time` — зелёные. |
| 3 (`changes_requested` -> `in_dev`; повторный вход в review снова через `verifying`; счётчики без изменений) | OK | `_review_changes_requested` не тронута; `test_ac10_ac12_review_return_cycle.py` (AC-10..12) — зелёные; `test_invariants.CountersNeverResetTest` — зелёный. |
| 4 (ревью-пакет несёт строку статуса CI из журнала `verifying`, без нового опроса) | OK | `orchestrator/review.py:289-296`, `test_ac13_review_package_ci_status_line.py` — зелёный. |
| 5 (`auto`: `verifying` остаётся опрашивающим состоянием; подсказка после красного CI называет `reject` в `in_dev`) | OK | `orchestrator/auto.py` не тронут (обоснованно — `AUTO_STOP_VERIFYING_RED`/`_cmd_reject` уже вели в `in_dev` до этой задачи); `test_ac14_ac16_auto_verifying_loop.py` — зелёный. |
| 6 (`docs/invariants.md`, `docs/roadmap.md`, `artel.py --help`) | OK | Инвариант 36 добавлен, 27/34 поправлены; roadmap — абзац ADR-0015; `artel.py` docstring — новая схема, `cmd_help` печатает именно её (`artel.py:443`). `test_ac17_ac19_docs_state_order.py` — зелёный. |
| 7 (планки закрытых задач не гоняются/не правятся; R2/R3 дождались мержа) | OK | ANSWER-1.md подтверждает мандат Оператора; PLAN честно фиксирует, что реализация шла поверх уже смерженных R2/R3. |

## Замечания

- **blocker** — `orchestrator/fsm_advance.py:301-303` (внутри `review()`, ветка `status == "approved" and not t["is_canary"]`) — рубеж «сверка головы ветки на origin» (`_origin_push_gate`) оставлен на старом месте ПОСЛЕ того, как этот же рубеж уже добавлен на новое место в `in_dev()` (`orchestrator/fsm_advance.py:1127-1129`, комментарий на строке 1126 сам называет это «тем же исключением, что раньше стояло на входе `review()`» — то есть разработчик знал, что код должен переехать, но не удалил исходную копию). Это прямое нарушение SPEC требования 1 («переезжают… целиком, без дублирования») и TZ.md требования 1 (буквально то же слово «без дублирования») — и оно противоречит собственному PLAN.md, п.2 «Подхода»: «`fsm_advance.review`: ветка `status == "approved"` **лишена push-проверки** и прогона `acceptance.run`» — по факту push-проверка НЕ убрана, убран только прогон `acceptance.run`.
  Последствие: на каждом одобрении ревью (`review -> acceptance`) `github_adapter.ensure_head_in_origin` вызывается ВТОРОЙ раз за цикл (первый — на `in_dev -> verifying`), с реальным `git push -u origin <branch>`, если sha разошлись. Это (а) лишняя сетевая операция на каждый approved-вердикт; (б) новый, нигде не описанный в SPEC/PLAN путь отказа: если origin недоступен именно в этот момент (после того как CI уже проверен и ревью уже одобрено), переход `review -> acceptance` откажет с сообщением «переход отклонён: голова не в origin» — исход, которого требование 1 явно не предполагает после переноса рубежа. Ни один из 20 приёмочных тестов и ни один из юнит-тестов, добавленных/правленных этой задачей, этого не ловит: `test_ac02_ac08_gates_moved_to_verifying.py::test_ac8_...` останавливается на состоянии `review` и не пишет approved-вердикт, чтобы дойти до `review -> acceptance`; в лёгких песочницах (`fake_git`) `git push` любой подкоманде отвечает `rc=0` молча, поэтому дублирующий вызов не порождает видимого сбоя ни в одном прогнанном тесте.
  Сопутствующие следы того же недоделанного переноса — стал протухшим текст двух докстрингов, оба всё ещё описывают ТОЛЬКО старое место вызова: `orchestrator/fsm_advance.py:172-173` («предусловие входа в verifying… вызывается только для approved не-канареечных задач [через `review()`]») и `orchestrator/github_adapter.py:114-116` («предусловие входа в `verifying` (`fsm_advance.py::review`)») — обе нужно поправить одновременно с удалением дубля.
  Предложение: убрать блок строк 301-303 из `review()` целиком (сама сверка свежести вердикта — `_freshness_refuses`/`iteration = artifacts.fresh_verdict_iteration(...)` — не трогать, они не часть семи переехавших рубежей); поправить оба докстринга под новое (единственное) место вызова; прогнать `test_ac02_ac08_gates_moved_to_verifying.py`, дополнив сценарий шагом до `review -> acceptance` (write_review("approved") + advance), чтобы класс регрессии «рубеж не убран со старого места» ловился автоматически, раз он не ловится сегодняшним объёмом теста.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/fsm_advance.py:301-303 (дубль), 1127-1129 (новое место), 172-173 и orchestrator/github_adapter.py:114-116 (протухшие докстринги) | Рубеж «сверка головы на origin» не убран со старого места в `review()` после переноса в `in_dev()` — дублирование прямо запрещено SPEC требованием 1/TZ.md требованием 1 и противоречит собственному PLAN.md п.2 | Лишний `git push` на каждый approved-вердикт; новый, не описанный в SPEC путь отказа `review -> acceptance` из-за недоступности origin уже после прохождения CI и ревью | Удалить блок строк 301-303 из `review()`, поправить протухшие докстринги, расширить `test_ac02_ac08_gates_moved_to_verifying.py::test_ac8_...` до шага `review -> acceptance`, чтобы класс регрессии ловился автоматически |

## Вердикт
changes_requested — единственный пункт: `orchestrator/fsm_advance.py:301-303` (см. R1-F1). Остальная реализация (переходы, порядок, ревью-пакет, документация, зоны) проверена и соответствует SPEC/PLAN.

## Проверено исполнением
- `python3 -m unittest tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/{test_ac01_ac09_state_order,test_ac02_ac08_gates_moved_to_verifying,test_ac10_ac12_review_return_cycle,test_ac13_review_package_ci_status_line,test_ac14_ac16_auto_verifying_loop,test_ac17_ac19_docs_state_order,test_ac20_ac22_process_markers}` (запущено из каталога `acceptance_tests/`) — 20 тестов, все зелёные.
- `python3 -m unittest tests.test_acceptance_tests_flow tests.test_advance_guard tests.test_amend tests.test_auto_cycle tests.test_branch_freshness_gate tests.test_fsm_map_conflict_autoresolve tests.test_git_fixation tests.test_invariants tests.test_review_freshness tests.test_review_registry_gate tests.test_verifying_ceiling` — 266 тестов, все зелёные (176.9с).
- `python3 scripts/codebase_map.py --check` — карта свежая, расхождений нет.
- `python3 scripts/guard.py tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md tasks/01M1TQ0TRCZPRZX22C4084NCPB/PLAN.md` — «GUARD: ок (2 файлов)».
- Чтением кода (не тестом): `grep -n "_origin_push_gate" orchestrator/fsm_advance.py` — подтверждён факт двух точек вызова (строки 302, 1128) вместо одной; `grep -n "acceptance\.run\b" orchestrator/fsm_advance.py` — подтверждено, что для этого рубежа (в отличие от origin-push) дубля нет, только одна точка вызова.
- `git diff --stat` вне `tasks/` сверен построчно с `zones:` SPEC + мандатом ANSWER-2.md (`orchestrator/artel.py`) — расхождений нет; `.git-commit-msg.txt` и `baseline_fsm_advance_tmp.py` в рабочем дереве отсутствуют (убраны согласно ANSWER-2.md/PLAN п.7).

## Предложения системе
- Класс «рубеж не убран со старого места после переноса» (этот файл, R1-F1) — общий риск для задач-рефакторингов маршрута FSM: приёмочный тест, проверяющий «не дублируется на новом переходе», обязан идти ДО состояния, из которого рубеж раньше вызывался, а не только до непосредственно следующего перехода — иначе тест физически не может увидеть код, оставленный на старом месте по пути дальше. Стоит закрепить это как пункт чек-листа review для задач класса «перенос гейта/рубежа между переходами FSM».
