---
task: 01M2B6JWGS9HMR9XZJBASXVNSY
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 2
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: lease: живой держатель своей сессии не переписывается

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (ветка «своя сессия»: живой другой pid не переписывает lease; `same_host_ok`/отказ/`force`) | OK | R1-F1 закрыт коммитом 484841a0: `orchestrator/lease.py:138-148` теперь сверяет `row["hostname"] == hostname` (`dead_on_own_host_same_session`) прежде чем доверять `liveness._pid_alive(row["pid"])` — держатель своей сессии на ДРУГОМ host'е больше не считается мёртвым/живым по совпадению числа pid с локальным процессом; поведение AC-1..AC-5 (свой host) не изменилось. |
| 2 (второй `run`/`auto` той же сессии отказывает до запуска роли) | OK | Без изменений с итерации 1 — следствие фикса требования 1 через единственную точку `lease.acquire`; AC-6 зелёный. |
| 3 (`catalog._lease_holder_suffix`: pid мёртв + pgid непуст → «жив (агент pgid N)») | OK | Без изменений с итерации 1 — `orchestrator/catalog.py` не тронут этим диффом; AC-7/AC-8 зелёные. |
| 4 (заметка в PLAN про избыточность `guard-artel-bg.py`) | OK | Без изменений с итерации 1 — `PLAN.md`, секция «Предложения системе». |

## Замечания

Пусто — 0 blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/lease.py:138-148 | ветка «своя сессия» не проверяла `row["hostname"]` перед `liveness._pid_alive(row["pid"])` | ложный отказ или тихая порча lease живого держателя другого host'а под тем же `session_id` | исправлено: `dead_on_own_host_same_session = (row["hostname"] == hostname and not liveness._pid_alive(row["pid"]))`, отказ/перезапись решаются по ней; держатель другого host'а теперь молча считается живым (симметрично `foreign_live_lease`); докстринг `acquire` обновлён; два новых регресс-теста (`tests/test_lease.py::OwnSessionLiveOtherPidTest::test_holder_on_different_host_with_locally_dead_pid_refuses_without_overwriting` и `test_holder_on_different_host_with_same_host_ok_returns_none_false_without_mutation`) воспроизводят ровно сценарий замечания и оба зелёные; проверено запуском (см. «Проверено исполнением») и прочтением диффа `orchestrator/lease.py` целиком построчно — логика симметрична соседней ветке «чужая сессия» (`dead_on_own_host` ниже), расхождения с докстрингом не осталось |

## Вердикт

approved — R1-F1 закрыт корректно, регресс подтверждён тестами и
прогоном; новых замечаний нет.

## Проверено исполнением

- `python3 -m pytest tasks/01M2B6JWGS9HMR9XZJBASXVNSY/acceptance_tests/ tests/test_lease.py tests/test_catalog_status_log.py tests/test_budget_live_lease_and_escalation.py -v` — 77 passed (AC-1..AC-9 планки + оба новых регресс-теста R1-F1 + весь затронутый `test_lease.py`/зависимые модули).
- `python3 scripts/guard.py tasks/01M2B6JWGS9HMR9XZJBASXVNSY/SPEC.md tasks/01M2B6JWGS9HMR9XZJBASXVNSY/PLAN.md` — `GUARD: ок (2 файлов)`.
- `git diff 9f156591..HEAD -- tests/test_lease.py tests/test_catalog_status_log.py | grep -E '^-' | grep -v '^---'` — единственные удалённые строки этой и прошлой итерации вместе — старые `import`, замещённые более широкими; ни один существующий `assert` не удалён и не смягчён (AC-9 не ослаблена).
- `git show 484841a0 -- docs/codebase-map.md` — диф только строки `built_at_sha`, содержимое карты не изменилось (новых модульных зависимостей `lease.py` не приобрёл — `liveness` уже был зависимостью до задачи).
- Прочитано целиком: `orchestrator/lease.py` (весь `acquire`, с докстрингом), diff `tests/test_lease.py` коммита 484841a0 (оба новых теста и их докстринги).
- CI коммита 484841a0 (из ревью-пакета) — зелёный, 14 проверок.
- Ручной прогон логики фикса на все 5 комбинаций ветки «своя сессия» (тот же pid / свой host живой-другой-pid / свой host мёртвый pid / чужой host / `force`) — трассировка кода подтверждает совпадение с AC-1..AC-5 и с новым сценарием R1-F1, отдельно от прогона тестов.

## Предложения системе

- `scripts/guard.py:234` (`MUTATION_CLAIM = re.compile(r"Ловит мутацию:[^\S\n]*(\S.*)")`) требует литеральной подстроки «Ловит мутацию:» БЕЗ переноса строки между словами. В этой же итерации (`tests/test_lease.py`, оба новых теста R1-F1: `test_holder_on_different_host_with_locally_dead_pid_refuses_without_overwriting` — «...тоже мёртв. Ловит\nмутацию: если ветка...», и `test_holder_on_different_host_with_same_host_ok_returns_none_false_without_mutation` — заявка вовсе не содержит подстроки «Ловит мутацию:») докстринги написаны по-русски содержательно (сценарий и наблюдаемое свойство описаны), но из-за обычного переноса строк на ширине ~79 символов регэксп `test_functions_without_mutation_claim`/`_mutation_claim_gate` (`orchestrator/fsm_advance.py:1067`) их не находит — гейт `in_dev -> verifying`, судя по тому, что задача уже дошла до `review` с этими тестами в HEAD, эту пару не заблокировал, хотя локальный прогон `guard.test_functions_without_mutation_claim(base, head)` на этом же дифф-диапазоне (merge-base 9f156591..HEAD) возвращает обе функции как «без заявки». Не блокирую этой итерацией (содержательно заявка есть, человек её читает нормально) — но стоит проверить: либо сделать регэксп терпимым к переносу строки (`r"Ловит\s+мутацию:"`), либо разобраться, почему гейт в проде не сработал на этом дифф-диапазоне — иначе формулировка «Ловит мутацию:», случайно попавшая на границу переноса строки, тихо выключает и человеческую, и машинную проверку одновременно.
