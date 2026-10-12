---
task: 01M4PMR5EVFK4KQDPWB1KEGM7V
type: plan
author_role: developer
status: escalate
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
   ожидаемый кортеж с `verifying` (см. «Эскалация»); регенерация
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 1 |
| 6 | 1, 2 |
| 7 | 2 |
| 8 | 2 |
| 9 | 2 |
| 10 | 2 |
| 11 | 1 (прежние пути `pull.evaluate`), 2 |
| 12 | 1, 3 |
| 13 | 1, 2 |
| 14 | 2 |
| 15 | — тесты долгоживущего файла `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py` держат все семь мутаций (заявки найдены проверкой AC-15 планки); новых тестов не дописано, повтор запрещён требованием 15 |

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
- `artel.py suite-run` отказал: на машине шёл прогон задачи
  01M4PMPMZ7PPCN3JWX75RTJZQN (одновременно — один полный прогон). Полный
  набор в этом шаге не прогнан.

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
- Существующий тест меняет ожидаемый кортеж — требует мандата Оператора
  (раздел «Эскалация»).
- Откат: revert merge-коммита задачи.

## Риски

- Запись `переход отклонён: …` из `_materialize_and_run_plank` при отказе
  после слияния на пути команды читается как «переход», хотя перехода нет;
  следом идёт эскалация с причиной `UNVERIFIED_HEAD_REASON`, так что
  Оператор видит обе. Текст прежних записей не менял (вне задачи).

## Эскалация

- **Вопросы**
  1. (блокирует сдачу) Мандат на смену ожидания существующего метода
     `tests/test_pull_conflict_marker_states.py::MarkedStatesSetTest::test_marked_states_are_exactly_the_three_returning_to_in_dev`.
     Было: `assertEqual(pull.PULL_CONFLICT_MARKED_STATES, ("in_dev",
     "acceptance", "merge_gate"))`; стало: `assertEqual(...,
     ("in_dev", "acceptance", "merge_gate", "verifying"))`, докстринг и
     заявка «Ловит мутацию» обновлены под четыре состояния (вид
     утверждения `assertEqual` прежний). Причина — требование 12 SPEC и
     раздел «Ожидаемая краснота существующих тестов», п.1: SPEC прямо
     называет мандат условием. Правка уже в рабочей копии. Варианты:
     (а) мандат строкой ANSWER `Ослабление тестов разрешено:
     tests/test_pull_conflict_marker_states.py::MarkedStatesSetTest::test_marked_states_are_exactly_the_three_returning_to_in_dev`;
     (б) иное решение Оператора на гейте. Дефолт при молчании — нет: без
     мандата рубеж неослабления откажет, и задача стоит.
- **Контекст** — реализация закончена целиком (шаги 1–3), планка и
  долгоживущий файл задачи зелёные; полный набор не прогнан (суперзамок
  `suite-run` занят другой задачей). После мандата следующий шаг
  разработчика — прогон `suite-run` и `status: ready`.
- **Блокирует** — выход из `in_dev` (рубеж неослабления тестов на
  изменённом методе).

## Предложения системе

- `artel.py suite-run` отказывает при чужом полном прогоне без
  очереди/ожидания — шаг разработчика, оказавшийся рядом с чужим прогоном,
  остаётся без полного набора; полезна форма «встать в очередь» (`suite_lock.wait_acquire` уже есть).
- Раздел SPEC «Ожидаемая краснота» с контейнерным значением заранее
  обрекает задачу на эскалацию разработчика ради мандата, который
  Оператор мог дать ещё на гейте SPEC: стоит дать гейту SPEC принимать
  строку мандата (`skills/analyst*`, `orchestrator/advance_gates/mandate.py`).
