---
task: 01M4PMR5EVFK4KQDPWB1KEGM7V
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Команда Оператора pull-main — подтяжка main на verifying без возврата к роли

## Фаза A: план

- Таблица покрытия полна (1–15), шаги размером с MR, подход (один ключевой
  параметр `operator_pull` с умолчанием `False`, прежние пять вызывателей
  его не передают) не конфликтует с архитектурой узла подтяжки.
- «Влияние на систему» соответствует диффу: `pull.py`, `fsm.py`,
  `pull_main.py`, `artel.py`, `docs/stack.md`, `tests/test_pull_conflict_marker_states.py`,
  карта. Вне зон SPEC ничего не тронуто; путь отката назван.
- Пробел плана: строка «15» таблицы опирается только на перечень мутаций
  требования 15 и не учитывает, что свойство требования 6 на пути команды
  держит лишь разовая планка (см. R1-F1).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/pull_main.py`, строка справки, абзац, таблица диспетчера `artel.py` |
| 2 | OK | `pull_main._cmd_pull_main`: `store.get_task` под lease; долгоживущий AC-2 (свежее чтение) зелёный |
| 3 | OK | `lease.run_locked` без `same_host_ok` |
| 4 | OK | `run_plank=True, operator_pull=True` |
| 5 | OK | `pull.evaluate`: `_doc_only_main_advance` не зовётся при `operator_pull` |
| 6 | OK по коду, без сторожа в `tests/` | `pull.Unavailable` → `"unavailable"` → `_refuse`; прежние вызыватели — `Fresh()`. Сторож пути команды — только разовая планка (R1-F1) |
| 7 | OK | `ensure_head_in_origin`, канарейка не отправляет, запись `PULL_MAIN_ACTION` |
| 8 | OK | `store.update_task(conn, task_id, updated_at=store.now())` только при `pushed` |
| 9 | OK | `sys.exit` с обеими подстроками; журнал подтяжки пишется до проверки `pushed` |
| 10 | OK | `"fresh"` → печать `PULL_MAIN_ALREADY_FRESH`, без эффектов |
| 11 | OK | эскалации из `pull.evaluate`, исход `"escalated"` → `sys.exit` без push/сброса |
| 12 | OK | `verifying` в `PULL_CONFLICT_MARKED_STATES`, `docs/stack.md` обновлён |
| 13 | OK | (а) `Refused` до слияния → `_refuse`; (б) на `operator_pull` — `set_state(escalated)` с `UNVERIFIED_HEAD_REASON`; прежние пути — `Refused` |
| 14 | OK | нет в `_ROLE_ALLOWED_COMMANDS` |
| 15 | OK | семь мутаций держит долгоживущий файл задачи |

Изменённое утверждение `MarkedStatesSetTest::test_marked_states_are_exactly_the_three_returning_to_in_dev`
сверено с base: тот же `assertEqual` на точный кортеж, `+ "verifying"` — ровно
мандат ANSWER-1 п.1; докстринг обновлён. Замена по ANSWER-1 п.2
(`VerifyingPullMainReturnGivesDeveloperItsStepTest`) добавлена, её свойство
(возврат → `in_dev`, `auto` отдаёт шаг developer без предварительного advance)
долгоживущий файл не держит — не повтор. Сужения фикстур/`setUp` не нашёл.

## Замечания

- major — orchestrator/pull.py:756-762 (+ orchestrator/pull_main.py:76-80) —
  свойство требования 6 на пути команды («неполученная вершина origin main и
  `commits_behind` → `None` — именованный отказ, а не “main уже в ветке”»)
  держит только планка `acceptance_tests/test_pull_main_node.py::UnavailableOriginTest::test_ac6_unavailable_origin_or_behind_is_named_refusal`,
  помеченная `Группа: разовый`; в `tests/` сторожа нет. Проверено временной
  мутацией: обе ветки `Unavailable` в `pull.evaluate` заменены на `Fresh()` —
  `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`, `test_pull_conflict_marker_states.py`,
  `test_pull.py`, `test_branch_freshness_gate.py` — 55 passed (зелёные), планка —
  2 failed. После мержа планку не гоняет ни CI, ни автогейт (ADR-0018 п.3):
  регрессия «сбой git отвечает Оператору “main уже в ветке”» — ровно тот
  дефект, ради которого написано требование 6, — пройдёт незамеченной.
  Предложение: добавить в `tests/` тест пути команды (через `artel.main()`
  или `pull_main.cmd_pull_main`) на оба случая (а)/(б) с заявкой «Ловит
  мутацию: на пути `operator_pull` исход `Unavailable` заменён на `Fresh()` —
  вывод содержит `PULL_MAIN_ALREADY_FRESH`, отказа нет». Это не повтор
  долгоживущего файла задачи (он AC-6 не проверяет), требование 15 добавление
  не запрещает. Прежние вызыватели (`Fresh()`/`"refused"`) в `tests/` держатся
  — проверено обратной мутацией (см. «Проверено исполнением»).
- minor — orchestrator/pull_main.py:76-80 — запись журнала отказа
  `pull-main отклонён` на исходе `"unavailable"` не несёт причины (какой из
  двух случаев): причина `Unavailable.reason` только печатается в stdout
  (`fsm.py:262`), а текст отказа отсылает «строкой выше». В журнале задачи
  Оператор потом не различит «origin не ответил» и «нет ветки». Предложение:
  при желании вернуть причину до команды (например, печать в
  `fsm._pull_main_or_escalate` дополнить записью журнала либо передать
  `reason`), не блокирует.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/pull.py:756-762; orchestrator/pull_main.py:76-80 | требование 6 на пути `pull-main` держит только разовая планка, в `tests/` сторожа нет (временная мутация `Unavailable`→`Fresh()` — `tests/` зелёные) | после мержа регрессия «сбой git = “main уже в ветке”» пройдёт CI | тест в `tests/` на случаи (а)/(б) пути команды с заявкой «Ловит мутацию» |
| R1-F2 | open | orchestrator/pull_main.py:76-80 | журнал отказа `"unavailable"` без причины | Оператор по журналу не различит случаи (а)/(б) | записать причину в журнал (minor; можно `rejected` с обоснованием) |

## Вердикт

changes_requested — исправить R1-F1 (сторож требования 6 на пути команды в
`tests/`); R1-F2 — minor, на усмотрение разработчика (`fixed` либо `rejected`
с обоснованием).

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4PMR5EVFK4KQDPWB1KEGM7V` — 7 passed, код 0.
- `python3 -m pytest -q tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py tests/test_pull_conflict_marker_states.py tests/test_stack_zones_pull_section.py tests/test_pull.py tests/test_branch_freshness_gate.py tests/test_pull_long_lived_plank.py tests/test_ci_rerun_command.py` — 78 passed, 34 subtests passed.
- Временная мутация 1 (R1-F1): в `pull.evaluate` ветки `Unavailable` → `Fresh()`;
  `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py tests/test_pull_conflict_marker_states.py tests/test_pull.py tests/test_branch_freshness_gate.py` — 55 passed (мутация не поймана);
  планка — 2 failed. Код возвращён `git checkout -- orchestrator/pull.py`, `git status` чист.
- Временная мутация 2 (прежние вызыватели): эскалация «голова не проверена» и
  `Unavailable` при `behind is None` включены для всех вызывателей;
  `tests/test_pull.py tests/test_branch_freshness_gate.py tests/test_pull_long_lived_plank.py tests/test_acceptance_tests_flow.py tests/test_git_fixation.py` — 4 failed (прежние исходы в `tests/` держатся). Код возвращён, `git status` чист.

## Предложения системе

- Планка этой задачи (`acceptance_tests/test_pull_main_node.py`) помечена
  `Группа: разовый`, хотя проверяет свойства кода (AC-4, AC-6, AC-13 «прежним
  путём»), — граница групп ADR-0020 нарушена автором тестов, а разработчику
  она видна только как «свойство уже закрыто планкой»; стоит проверять
  метку группы на гейте лока планки (`skills/test-authoring.md`, гейт `tests_writing`).
