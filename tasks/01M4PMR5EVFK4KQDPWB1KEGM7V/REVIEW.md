---
task: 01M4PMR5EVFK4KQDPWB1KEGM7V
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Команда Оператора pull-main — подтяжка main на verifying без возврата к роли

## Фаза A: план

- Таблица покрытия полна (1–15). Шаг 5 закрывает пробел итерации 1: у
  требования 6 на пути команды теперь есть сторож в `tests/` (R1-F1).
- «Влияние на систему» соответствует диффу итерации: `orchestrator/pull.py`
  (константа `UNAVAILABLE_ACTION`), `orchestrator/fsm.py` (запись журнала на
  исходе `Unavailable`), `orchestrator/pull_main.py` (текст отказа),
  новый `tests/test_pull_main_unavailable.py`. Прежние вызыватели
  `Unavailable` не получают (`pull.evaluate` выдаёт его только при
  `operator_pull`, `pull.py:762-769`), поэтому их журнал не меняется.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1 |
| 2 | OK | без изменений с итерации 1 |
| 3 | OK | без изменений с итерации 1 |
| 4 | OK | без изменений с итерации 1 |
| 5 | OK | без изменений с итерации 1 |
| 6 | OK | `Unavailable` → запись журнала `pull.UNAVAILABLE_ACTION` с причиной (`fsm.py:262-265`) → `_refuse` без `PULL_MAIN_ALREADY_FRESH` (`pull_main.py:75-79`); сторож — `tests/test_pull_main_unavailable.py`, проверен временной мутацией |
| 7 | OK | без изменений с итерации 1 |
| 8 | OK | без изменений с итерации 1 |
| 9 | OK | без изменений с итерации 1 |
| 10 | OK | без изменений с итерации 1 |
| 11 | OK | без изменений с итерации 1 |
| 12 | OK | без изменений с итерации 1 |
| 13 | OK | без изменений с итерации 1 |
| 14 | OK | без изменений с итерации 1 |
| 15 | OK | семь мутаций держит долгоживущий файл задачи |

Новый тестовый файл — два метода с докстрингами «Сценарий» и заявками «Ловит
мутацию», в которых названо наблюдаемое расхождение: в выводе
`PULL_MAIN_ALREADY_FRESH`, отказа нет, либо нет записи журнала. Обе заявки
проверены временной мутацией (см. ниже). Тест не повторяет долгоживущий
файл задачи: тот AC-6 не проверяет. Песочница импортируется, а не
копируется. У импортированного `PullMainSandbox` нет методов `test_*`, так
что повторного сбора тестов нет. Утверждения существующих тестов в этой
итерации не менялись. Смена кортежа в `MarkedStatesSetTest` с итерации 1
покрыта мандатом ANSWER-1 п.1.

## Замечания

Новых замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/pull.py:762-769; orchestrator/pull_main.py:75-79 | требование 6 на пути `pull-main` держала только разовая планка | после мержа регрессия прошла бы CI | Закрыто: `tests/test_pull_main_unavailable.py` (случаи (а) и (б)). Временная мутация `Unavailable`→`Fresh()` в обеих ветках `pull.evaluate` — 2 failed |
| R1-F2 | accepted | orchestrator/fsm.py:262-265; orchestrator/pull_main.py:75-79 | в журнале отказа `"unavailable"` не было причины | Оператор не различил бы случаи (а) и (б) | Закрыто: запись `pull.UNAVAILABLE_ACTION` с `reason`, тесты сверяют `detail` («в origin не получена» / «отставание ветки»). Временная мутация «запись не пишется» — 2 failed |

## Вердикт

approved — R1-F1 и R1-F2 закрыты, новых blocker/major нет.

## Проверено исполнением

- `python3 -m pytest -q tests/test_pull_main_unavailable.py tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py tests/test_pull_conflict_marker_states.py tests/test_stack_zones_pull_section.py tests/test_pull.py tests/test_branch_freshness_gate.py` — 62 passed, 30 subtests passed.
- Временная мутация 1: в `pull.evaluate` обе ветки `return Unavailable(...)` заменены на `return Fresh()`. `tests/test_pull_main_unavailable.py` — 2 failed (оба метода). Код возвращён (`git checkout -- orchestrator/pull.py`).
- Временная мутация 2: в `fsm._pull_main_or_escalate` удалён вызов `store.journal(... pull.UNAVAILABLE_ACTION ...)`. `tests/test_pull_main_unavailable.py` — 2 failed. Код возвращён (`git checkout -- orchestrator/fsm.py`), `git status` чист.
- `python3 scripts/codebase_map.py` — карта расходится только в строке `built_at_sha`, по содержимому свежая; файл возвращён.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4PMR5EVFK4KQDPWB1KEGM7V` — 7 passed, код выхода pytest 0.
