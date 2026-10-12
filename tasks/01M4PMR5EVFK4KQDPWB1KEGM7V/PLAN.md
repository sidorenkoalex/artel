---
task: 01M4PMR5EVFK4KQDPWB1KEGM7V
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Команда Оператора pull-main — подтяжка main в ветку задачи на verifying без возврата к роли

## Подход

Команда — новый модуль `orchestrator/pull_main.py` по образцу
`orchestrator/ci_rerun.py`: резолв префикса id до lease, тело под
`lease.run_locked` без `same_host_ok`, состояние — по свежему
`store.get_task` внутри тела, отказ — запись журнала `pull-main отклонён` +
`sys.exit`. Подтяжка — существующий узел `fsm._pull_main_or_escalate(...,
run_plank=True, operator_pull=True)`.

Различение исходов, нужное только команде, — один ключевой параметр
`operator_pull` (по умолчанию `False`) в `fsm._pull_main_or_escalate` и
`pull.evaluate`. При `True`:
- пропуск по документному диффу (`_doc_only_main_advance`) не вызывается
  (требование 5);
- пустая вершина origin main и `commits_behind` → `None` — новый исход
  `pull.Unavailable(reason)` → строка `"unavailable"` (требование 6);
- `Refused` из `_materialize_and_run_plank` (отказ ПОСЛЕ слияния) —
  эскалация `store.set_state(..., "escalated")` с причиной
  `pull.UNVERIFIED_HEAD_REASON` = «голова после подтяжки не проверена
  планкой» и исход `Conflict` → `"escalated"` (требование 13 (б)). Отказ до
  слияния (посторонние файлы) остаётся `Refused` → `"refused"`.
Прежние вызыватели (`fsm_advance`, `fsm_merge_gate`, `fsm`, `canary`,
`runner`) параметр не передают — их исходы байт-в-байт прежние.

Исход «подтянуто» в команде: отправка головы
`github_adapter.ensure_head_in_origin` (у `is_canary` — нет), запись журнала
`PULL_MAIN_ACTION` (есть и при сбое отправки), затем — только при успехе
отправки или у канарейки — `store.update_task(conn, id,
updated_at=store.now())`. Сбой отправки — `sys.exit` с подстроками
`PULL_MAIN_PUSH_FAILED` и `PULL_MAIN_PUSH_RETRY`, потолок не сброшен.

`verifying` дописан в `pull.PULL_CONFLICT_MARKED_STATES` (требование 12) и
в раздел `docs/stack.md`, который этот набор перечисляет.

Бюджет SPEC ($45) не пересматривается.

## Шаги

1. `orchestrator/pull.py`: `Unavailable`, `UNVERIFIED_HEAD_REASON`,
   параметр `operator_pull` у `evaluate`, `verifying` в
   `PULL_CONFLICT_MARKED_STATES`. `orchestrator/fsm.py`: параметр
   `operator_pull` у `_pull_main_or_escalate`, исход `"unavailable"`.
2. `orchestrator/pull_main.py` (команда, константы `PULL_MAIN_*`);
   `orchestrator/artel.py`: строка справки, абзац описания, импорт, строка
   таблицы диспетчера; `_ROLE_ALLOWED_COMMANDS` не трогается.
3. `docs/stack.md` — `verifying` в перечне помечаемых состояний;
   `tests/test_pull_conflict_marker_states.py::MarkedStatesSetTest::
   test_marked_states_are_exactly_the_three_returning_to_in_dev` —
   ожидаемый кортеж с `verifying` (мандат ANSWER-1 п.1); регенерация
   `docs/codebase-map.md`.
4. Обязательная замена по ANSWER-1 п.2: в
   `tests/test_pull_conflict_marker_states.py` — помощник
   `PullConflictCase.escalate_via_pull_main` (конфликт подтяжки из
   `verifying` целиком командой `pull_main.cmd_pull_main`) и класс
   `VerifyingPullMainReturnGivesDeveloperItsStepTest` по образцу
   `MergeGateReturnGivesDeveloperItsStepTest`: эскалация с меткой,
   `approve` с ANSWER → `in_dev`, следующий `auto` журналирует
   `auto.REWORK_REFUSAL_ACTION` и отдаёт шаг developer без
   предварительного advance. Проверен мутацией: `verifying` убран из
   `pull.PULL_CONFLICT_MARKED_STATES` — тест красный
   (`assertEqual(len(markers), 1)`), код возвращён.
5. Замечания REVIEW итерации 1:
   - R1-F1: `tests/test_pull_main_unavailable.py` — сторож требования 6 на
     пути команды (через `artel.main()`, песочница `PullMainSandbox`
     долгоживущего файла): (а) `fsm._origin_main_sha` → `None`, (б)
     `rev-list --count` с ошибкой git — отказ `pull-main`, без
     `PULL_MAIN_ALREADY_FRESH`, без слияния/планки/отправки/записи
     подтяжки/сброса потолка, задача в `verifying`. Не повтор
     долгоживущего файла — тот AC-6 не проверяет.
   - R1-F2: `pull.UNAVAILABLE_ACTION`; `fsm._pull_main_or_escalate` на
     исходе `Unavailable` пишет запись журнала с этим действием и
     `reason`, текст отказа `pull_main` ссылается на неё. Прежние
     вызыватели `Unavailable` не получают — для них журнал не меняется.
   Проверено мутациями (код возвращён `git checkout`): `Unavailable` →
   `Fresh()` в обеих ветках `pull.evaluate` — оба теста красные; запись
   журнала в `fsm` убрана — оба красные.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 1 |
| 6 | 1, 2, 5 |
| 7 | 2 |
| 8 | 2 |
| 9 | 2 |
| 10 | 2 |
| 11 | 1 (прежние пути `pull.evaluate`), 2 |
| 12 | 1, 3 |
| 13 | 1, 2 |
| 14 | 2 |
| 15 | — тесты долгоживущего файла `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py` держат все семь мутаций (заявки найдены проверкой AC-15 планки); новых тестов не дописано, повтор запрещён требованием 15; сторож требования 6 (вне перечня мутаций требования 15) — шаг 5 |

Проверка в шаге:
- `python3 -m pytest tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py
  tests/test_pull_conflict_marker_states.py tests/test_stack_zones_pull_section.py`
  — 27 passed, 30 subtests passed.
- `artel.py plank-run 01M4PMR5EVFK4KQDPWB1KEGM7V` — 7 passed, код 0.
- Соседние модули узла подтяжки (`tests/test_pull.py`,
  `test_pull_additive_conflict.py`, `test_pull_long_lived_plank.py`,
  `test_pull_autoresolve_step_journal.py`, `test_runner_pre_step_pull.py`,
  `test_branch_freshness_gate.py`, `test_fsm_map_conflict_autoresolve.py`,
  `test_fsm_merge_conflict_note.py`, `test_long_lived_transitions.py`,
  `test_ci_rerun_command.py`, `test_codebase_map.py`) — 128 passed.
- Шаг после ANSWER-1: `python3 -m pytest
  tests/test_pull_conflict_marker_states.py` — 8 passed; `artel.py
  plank-run 01M4PMR5EVFK4KQDPWB1KEGM7V` — 7 passed, код 0; `artel.py
  suite-run 01M4PMR5EVFK4KQDPWB1KEGM7V` прогон №1 (полный набор) —
  «зелёный прогон», упало 0 (сводка печатает «прошло: 1» — см.
  «Предложения системе»).
- Шаг после REVIEW итерации 1: `python3 -m pytest
  tests/test_pull_main_unavailable.py tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py
  tests/test_pull_conflict_marker_states.py tests/test_stack_zones_pull_section.py
  tests/test_pull.py tests/test_branch_freshness_gate.py
  tests/test_pull_long_lived_plank.py tests/test_ci_rerun_command.py
  tests/test_codebase_map.py tests/test_runner_pre_step_pull.py` — 119
  passed, 34 subtests passed; `artel.py plank-run` — 7 passed, код 0;
  `artel.py suite-run` прогон №2 (полный набор) — «зелёный прогон», упало 0.

## Влияние на систему

- Узел подтяжки: новое поведение включается только параметром
  `operator_pull=True`, который передаёт одна точка — команда. Прежние пять
  вызывателей получают прежние `"fresh"`/`"refused"` (держат тесты планки
  AC-5, AC-6, AC-13 «прежним путём»).
- `PULL_CONFLICT_MARKED_STATES` расширен: метка «нужен шаг роли» теперь
  пишется и на конфликте из `verifying`. Прежде подтяжки из `verifying` не
  было, так что для существующих путей ничего не меняется; возврат из
  такой эскалации уходит в `in_dev` (`escalated_from` эта эскалация не
  пишет) — обещание метки выполняется.
- Lease, гейты, потолок `VERIFYING_CEILING_SEC`, `store.py` не меняются.
  Команда не в белом списке ролей.
- Существующий тест меняет ожидаемый кортеж — по мандату Оператора
  (ANSWER-1: `Ослабление тестов разрешено:` с именем метода); замена из
  матрицы ANSWER-1 — новый тест возврата из `verifying` (шаг 4).
- Откат: revert merge-коммита задачи.

## Риски

- Запись `переход отклонён: …` из `_materialize_and_run_plank` при отказе
  после слияния на пути команды читается как «переход», хотя перехода нет;
  следом идёт эскалация с причиной `UNVERIFIED_HEAD_REASON`, так что
  Оператор видит обе. Текст прежних записей не менял (вне задачи).

## Предложения системе

- `artel.py suite-run` отказывает при чужом полном прогоне без
  очереди/ожидания — шаг разработчика, оказавшийся рядом с чужим прогоном,
  остаётся без полного набора; полезна форма «встать в очередь» (`suite_lock.wait_acquire` уже есть).
- Раздел SPEC «Ожидаемая краснота» с контейнерным значением заранее
  обрекает задачу на эскалацию разработчика ради мандата, который
  Оператор мог дать ещё на гейте SPEC: стоит дать гейту SPEC принимать
  строку мандата (`skills/analyst*`, `orchestrator/advance_gates/mandate.py`).
- Сводка `suite-run --wait` зелёного полного прогона печатает «прошло: 1,
  упало: 0» при тысячах тестов в логе (`orchestrator/suite_run.py::render`)
  — счётчик, похоже, считает не тесты; по сводке не виден объём прогона.
