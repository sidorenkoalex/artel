---
task: 01M2B6JWGS9HMR9XZJBASXVNSY
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: lease: живой держатель своей сессии не переписывается

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (ветка «своя сессия»: живой другой pid не переписывает lease; `same_host_ok`/отказ/`force`) | Реализовано не так | Основная логика верна и покрыта тестами (AC-1..AC-5 зелёные), но ветка не проверяет `row["hostname"]` перед `liveness._pid_alive(row["pid"])` — см. замечание R1-F1. |
| 2 (второй `run`/`auto` той же сессии отказывает до запуска роли) | OK | Следствие фикса требования 1 через единственную точку `lease.acquire`; AC-6 (`test_ac6_*`) проверяет это на уровне `runner.cmd_run`/`auto.cmd_auto` с замоканным телом — зелёный. |
| 3 (`catalog._lease_holder_suffix`: pid мёртв + pgid непуст → «жив (агент pgid N)») | OK | `orchestrator/catalog.py:368-377`, AC-7/AC-8 зелёные (`test_ac7_*`, `test_ac8_*`, `tests/test_catalog_status_log.py`). |
| 4 (заметка в PLAN про избыточность `guard-artel-bg.py`) | OK | `PLAN.md`, секция «Предложения системе», строки 114-119. |

## Замечания

- major — `orchestrator/lease.py:127-136` — ветка «своя сессия» вызывает
  `liveness._pid_alive(row["pid"])`, не сверяя `row["hostname"]` с
  текущим host. Pid — число, адресуемое только на СВОЁМ host (это же
  допущение явно проведено чуть ниже в этой же функции —
  `dead_on_own_host = (row["hostname"] == hostname and not
  liveness._pid_alive(row["pid"]))`, строки 138-139 — и в
  `catalog._lease_holder_suffix`/`foreign_live_lease`). Если lease своей
  же сессии (тот же `session_id`, что и вызывающий) был взят на ДРУГОМ
  host под pid N, а на ЭТОМ host pid N либо занят посторонним живым
  процессом, либо свободен, ветка ошибочно решает «жив»/«мёртв» по
  чужому host'у: в первом случае — ложный именованный отказ (AC-1) при
  живом чужом host'е с другим pid, во втором — тихая перезапись строки
  lease активного держателя на другом host'е, то есть ровно тот класс
  бага (незаметная порча lease живого держателя), который эта задача
  чинит, только для комбинации «своя сессия + чужой host». Сценарий не
  экзотичен архитектурно — `resolve_session_id` (`orchestrator/
  session.py:92-107`) допускает совпадение `session_id` двух хостов
  через явный `ARTEL_SESSION_ID`/персистентный файл сессии, скопированный
  между машинами, а сама функция уже полна прецедентов «другой Оператор
  физически» (докстринг `acquire`, строки 74-76). Собственный докстринг
  новой ветки (строки 78-85) заявляет «тем же приёмом, что и ветка
  «чужая сессия» ниже» — но приём «чужой» ветки как раз ЕСТЬ разбор
  host'а (`dead_on_own_host`), которого в «своей» ветке нет: реализация
  расходится с собственным заявленным намерением.
  Предложение: завести `pid_alive_on_own_host = (row["hostname"] ==
  hostname and liveness._pid_alive(row["pid"]))` (или симметрично
  `dead_on_own_host` ниже) и разрешать перезапись/отказ по нему, а не по
  голому `liveness._pid_alive(row["pid"])`; для чужого host'а — то же
  допущение «молча жив», что уже принято во всей остальной части
  модуля.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/lease.py:127-148 | ветка «своя сессия» не проверяет `row["hostname"]` перед `liveness._pid_alive(row["pid"])` | ложный отказ или тихая порча lease живого держателя другого host'а под тем же `session_id` | добавлена `dead_on_own_host_same_session = (row["hostname"] == hostname and not liveness._pid_alive(row["pid"]))`, ветка отказывает/перезаписывает по ней (не по голому `_pid_alive`) — держатель другого host'а теперь молча считается живым, как и в ветке «чужая сессия»/`foreign_live_lease`; докстринг функции обновлён; регресс-тесты `tests/test_lease.py::OwnSessionLiveOtherPidTest::test_holder_on_different_host_with_locally_dead_pid_refuses_without_overwriting` и `test_holder_on_different_host_with_same_host_ok_returns_none_false_without_mutation` |

## Вердикт

changes_requested — исправить R1-F1 (сверка host'а в ветке «своя
сессия» `lease.acquire`), остальное соответствует SPEC и покрыто
тестами без ослаблений.

## Проверено исполнением

- `python3 scripts/guard.py tasks/01M2B6JWGS9HMR9XZJBASXVNSY/SPEC.md tasks/01M2B6JWGS9HMR9XZJBASXVNSY/PLAN.md` — `GUARD: ок (2 файлов)`.
- `python3 -m pytest tasks/01M2B6JWGS9HMR9XZJBASXVNSY/acceptance_tests/ -v` — 11 passed (AC-1..AC-9, планка полностью зелёная).
- `python3 -m pytest tests/test_lease.py tests/test_catalog_status_log.py tests/test_budget_live_lease_and_escalation.py -v` — 64 passed (затронутые модули + `test_budget*`, явно упомянутый в AC-9).
- `git diff 9f156591..854f8702 -- tests/test_lease.py tests/test_catalog_status_log.py` — единственные удалённые строки — старые `import`, замещённые более широкими (новые хелперы `_alive_foreign_pid`/`_dead_pid`); ни один существующий `assert`/тест не удалён и не смягчён (AC-9).
- `git diff 9f156591..854f8702 -- docs/codebase-map.md | grep -v '^[+-]built_at_sha:'` — содержимое карты не изменилось помимо строки `built_at_sha` (новых модульных импортов нет; `runner`/`liveness` уже числились зависимостями `lease.py`/`catalog.py` до задачи) — карта актуальна.
- CI коммита 854f8702 (из ревью-пакета) — зелёный, 7 проверок.
- Прочитано целиком: `orchestrator/lease.py`, `orchestrator/catalog.py:330-378`, `orchestrator/liveness.py:53-66`, `orchestrator/store.py` (`get_task`, `update_lease`, `update_lease_pgid`), `orchestrator/session.py:92-107`, `orchestrator/runner.py:88-103` (`step_role`), все 7 вызывателей `lease.run_locked` (`amend.py`, `answer.py`, `budget.py`, `auto.py`, `cleanup.py`, `fsm.py`, `runner.py`, `workspace.py`) — точечно, чтобы подтвердить требование 2 (единственная точка отказа) и отсутствие пересечения `force`/`same_host_ok` у одного вызывателя; `tasks/01M2B6JWGS9HMR9XZJBASXVNSY/acceptance_tests/*` целиком (9 тестов + `_sandbox.py`) — подтвердить, что планка не менялась разработчиком и покрывает все AC.

## Предложения системе

