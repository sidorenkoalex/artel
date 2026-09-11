---
task: 01M291EJMA995AZ61MEMDZKWRY
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Часть 1: мьютекс merge-окна держится на весь цикл approve merge_gate

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (мьютекс резервируется на весь цикл `_cmd_approve_merge_gate_cycle`, включая ожидание CI) | OK | `orchestrator/fsm_merge_gate.py:708-725` — `merge_lock.acquire` один раз до `while True`, `merge_lock.release` один раз в `finally` вокруг всего цикла; подтверждено `OneAcquireOneReleasePerCycleTest`/`OuterCycleDeadlineTest`. |
| 2 (держатель не меняется между заходами в тело) | OK | строка не пересоздаётся между заходами — `LockSurvivesWaitTest.test_ac1_...` наблюдает `session_id` держателя изнутри `_wait_for_branch_ci_green`. |
| 3 (heartbeat продлевается на каждой итерации опроса CI) | OK | `merge_lock.touch_heartbeat(conn)` вызывается на каждой итерации `_wait_for_branch_ci_green` (`fsm_merge_gate.py:268`), до любого раннего `return`/`sys.exit` этой итерации; `HeartbeatRenewedDuringCiWaitTest` считает записи в `merge_locks` через `set_trace_callback` и подтверждает 3 записи на 3 опроса. См. R1-F1 — сама функция продления не атомарна. |
| 4 (снятие мьютекса безусловно в `finally` внешнего цикла) | OK | `finally: merge_lock.release(conn, sid)` оборачивает весь `while True`, включая путь `return` изнутри `try` — питоновский `finally` срабатывает на любом исключении, в т.ч. `KeyboardInterrupt`. Подтверждено `test_ac5_lock_released_after_successful_cycle_completion`, `..._when_body_call_raises_sys_exit`, `..._when_ci_wait_ceiling_expires`. |
| 5 (перехват мёртвого держателя работает так же, включая время ожидания CI) | OK (с оговоркой) | `_holder_is_dead`/`acquire` не тронуты; `DeadHolderDuringWaitTest` подтверждает перехват протухшего heartbeat во время ожидания CI на смоделированном (последовательном) сценарии. Оговорка — R1-F1: сама функция продления heartbeat не разделяет атомарность гарантии `acquire`. |
| 6 (второй `approve` другой задачи получает тот же именованный отказ) | OK | `acquire()` не изменён; `ConcurrentApproveDuringWaitTest.test_ac3_...` подтверждает отказ и неизменность состояния второй задачи. |
| 7 (порядок состояний FSM/тело гейта не меняются; `merge_lock.py` не ослабляется) | OK | diff `_cmd_approve_merge_gate` (тело гейта, строки 660-677) не тронут; `merge_lock.py` дополнен только новой функцией `touch_heartbeat`, `acquire`/`release`/`run_window` не изменены — regression-тест `test_merge_lock_regression.py::test_ac6_...` гоняет весь `tests/test_merge_lock.py` как планку, зелёный. |

## Замечания

- minor — `orchestrator/merge_lock.py:77-92` (`touch_heartbeat`) — функция читает строку `merge_locks` (`store.merge_lock_row`) и переписывает её (`store.set_merge_lock`) БЕЗ `BEGIN IMMEDIATE`, в отличие от `acquire()`, которая явно оборачивает чтение+решение+запись одной атомарной транзакцией именно затем, чтобы закрыть окно между чтением и записью (см. собственный докстринг модуля, merge_lock.py:8-12, со ссылкой на ревью T044, итерация 1, замечание 1 — тот же класс дефекта). Между `row = store.merge_lock_row(conn)` и `store.set_merge_lock(conn, row["task_id"], ...)` в `touch_heartbeat` конкурентный `merge_lock.acquire()` другой сессии может атомарно перехватить мьютекс (если на его взгляд героld heartbeat уже протух) — тогда отложенная запись `touch_heartbeat` перезапишет строку обратно на старого (уже вытесненного) держателя со свежим `heartbeat_ts`, «воскресив» вытесненную сессию: обе сессии в этот момент будут считать, что владеют мьютексом. При текущих константах (`MERGE_GATE_CI_WAIT_POLL_SEC=90` vs `LEASE_STALE_AFTER_SEC=7200`, `orchestrator/config.py:111,265`) окно практически недостижимо (нужен разрыв в 2+ часа ровно между двумя соседними операторами SQL внутри одного вызова `touch_heartbeat`), поэтому не блокирую как major — но это тот же класс TOCTOU, который модуль уже один раз чинил, и который стоит закрыть тем же приёмом, а не полагаться на низкую вероятность. Предложение: обернуть чтение+запись в `touch_heartbeat` в `BEGIN IMMEDIATE`/`try...finally: rollback if in_transaction`, тем же паттерном, что `acquire()` (merge_lock.py:48-74), либо явно обосновать в докстринге функции, почему атомарность здесь не нужна.
- minor — `tests/test_merge_gate_ci_wait.py:186` (`OuterCycleDeadlineTest.test_mutex_acquired_once_and_held_across_both_body_calls`) — метод переписан под новое поведение (AC-7), но не несёт собственного докстринга с заявкой «Ловит мутацию: …» (skills/test-authoring.md, требование review-checklist «сверяй тест с ней, а не мысленным мутационным тестом по наитию... заявки нет вовсе → замечание»). Докстринг класса выше описывает СПЕК/AC, но не формулирует, какую мутацию ловит именно этот метод; заявки нет вовсе — ревьюверу приходится реконструировать её из имён переменных и текста assert-сообщений. Предложение: добавить методу докстринг вида «Ловит мутацию: если acquire/release снова вызываются вокруг каждого отдельного захода в тело (старое поведение), `acquire_calls`/`release_calls` станут длиной 2 вместо 1».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/merge_lock.py:77-92 (`touch_heartbeat`) | чтение+запись строки `merge_locks` не атомарны (нет `BEGIN IMMEDIATE`, в отличие от `acquire`) | TOCTOU-гонка с конкурентным `acquire()`: отложенная запись `touch_heartbeat` может «воскресить» уже вытесненного держателя поверх легитимного нового — тот же класс дефекта, что чинился в ревью T044 (см. докстринг модуля); при текущих константах (poll 90с / stale-порог 7200с) окно практически недостижимо, риск теоретический | обернуть `touch_heartbeat` тем же паттерном `BEGIN IMMEDIATE` + условный rollback, что `acquire()`, либо явно обосновать в докстринге, почему атомарность здесь не требуется |
| R1-F2 | open | tests/test_merge_gate_ci_wait.py:186 (`test_mutex_acquired_once_and_held_across_both_body_calls`) | переписанный под AC-7 тест не несёт докстринга с заявкой «Ловит мутацию: …» | следующий ревьювер не может свериться с заявленной мутацией — заявки нет вовсе | добавить методу докстринг с явной формулировкой мутации (пример в «Замечаниях» выше) |

## Вердикт

changes_requested — оба замечания minor и точечные: обернуть `touch_heartbeat` в ту же атомарную транзакцию, что `acquire` (или обосновать её отсутствие), и добавить докстринг «Ловит мутацию: …» переписанному тесту `OuterCycleDeadlineTest.test_mutex_acquired_once_and_held_across_both_body_calls`. Остальная реализация (AC-1..AC-7, требования 1-7 SPEC) корректна, тесты и приёмочные тесты зелёные, разрешение конфликта подтяжки main строго по ANSWER-1.

## Проверено исполнением

- `python3 -m pytest tests/test_merge_gate_ci_wait.py tests/test_merge_lock.py tests/test_fsm_merge_gate_scratch_worktree_cleanup.py tasks/01M291EJMA995AZ61MEMDZKWRY/acceptance_tests/ -q` — 31 passed.
- `python3 scripts/codebase_map.py` на текущем HEAD, сравнение с закоммиченной картой без строки `built_at_sha` — расхождений нет (карта свежая), diff отменён (`git checkout -- docs/codebase-map.md`) после сверки.
- `git diff origin/main HEAD --stat` — ровно 4 файла (`docs/codebase-map.md`, `orchestrator/fsm_merge_gate.py`, `orchestrator/merge_lock.py`, `tests/test_merge_gate_ci_wait.py`), совпадает с заявленным пакетом ревью — стороннего дрейфа нет.
- `git diff origin/main HEAD -- docs/backlog.md` — пусто: конфликт подтяжки main по `docs/backlog.md` разрешён строго версией main (`--theirs`), как предписывал ANSWER-1.
- `git log -1 --format=%P 4f991bab` и `git merge-base --is-ancestor origin/main HEAD` — подтверждают, что 4f991bab — настоящий merge-коммит `origin/main` в ветку задачи, ANSWER-1 выполнен (не просто переписан руками).
- `python3 -c "import ast; ..."` — синтаксис `fsm_merge_gate.py`/`merge_lock.py` корректен (доп. проверка, не замена прогона тестов).
- Прочитан код `_cmd_approve_merge_gate_cycle` (fsm_merge_gate.py:680-725), `_wait_for_branch_ci_green` (fsm_merge_gate.py:238-282), `merge_lock.py` целиком, `store.merge_lock_row`/`set_merge_lock`/`release_merge_lock` (store.py:663-692) построчно — не только по diff, но и по итоговому состоянию файлов.
- Полный набор `tests/` не прогонялся в шаге ревью (решение Оператора 05.09, скил review-checklist) — CI коммита 4f991bab зелёный (14 проверок), это условие гейта verifying уже выполнено.

## Предложения системе

- Скил review-checklist формулирует вердикт как «0 blocker/major → approved», но механический гейт `orchestrator/fsm_advance.py::_registry_gate` блокирует `approved` при ЛЮБОЙ незакрытой записи реестра независимо от severity (проверено чтением кода + примером `tasks/01M290PVYG2VJK6442H5BAX9MA/REVIEW.md`, где 1 major + 2 minor итерации 1 потребовали itration 2 для approved). Формулировка «0 blocker/major → approved» стоит уточнить в скиле: minor-замечания, занесённые в реестр, тоже требуют ещё одной итерации до `accepted` — иначе ревьювер тратит время на то же рассуждение, что и в этой задаче, каждый раз заново.
