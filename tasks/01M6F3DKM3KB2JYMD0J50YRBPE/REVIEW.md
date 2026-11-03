---
task: 01M6F3DKM3KB2JYMD0J50YRBPE
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: GitLab В2 — профиль проверок `verify`: ручные проверки `human:<имя>`, команды `verify-ok` и `verify-fail`

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–8 → шаги 1–6; требование 6 закрыто отсутствием внешних вызовов в `orchestrator/verify.py`, это видно в diff.
- Шаги по размеру — MR-единицы (поле → схема → модуль ожидания/команд → потребители → свои тесты → приложение к инвариантам).
- Подход не спорит с архитектурой: предел `verify-fail` устроен так же, как `fsm_advance._review_changes_requested` (`fsm_advance.py:350-363`: `>= LIMIT_REVIEW_ITERS` → `escalated`, иначе `in_dev` + `_maybe_ensure_draft_mr`). Признак ожидания — журнал визита, тем же приёмом, что `ci_rerun`/`auto._verifying_poll_note` через `fsm.VERIFYING_STATUS_ACTION`.
- «Влияние на систему» сверено с diff: тронуты только модули зоны SPEC (без `brief.py`, `fsm.py`, `ci.py`, `outcome_integrity.py`). `_NOT_HOLDING_STOP_STATES` не изменён. В `auto.py` только две правки — остановка на ожидании и `_WAITING` в `_epic_view`, обе в рамках ANSWER-1 п. 3. Откат описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py`: `VERIFY_FIELD` в `LOCAL_FIELDS["description"]`, перенос в `_flatten`, `check(..., local=True)` только из `merge_local`; слой репозитория — отказ с именем поля; `_verify_error` закрывает `ci`, C4-типы, неизвестный тип, отсутствие типа, повтор, не список, имя вне `[a-z0-9-]+` (`fullmatch`, пустое имя отказывает). Плоская запись вне раздела — прежний отказ `merge_local`. AC-1/2/3 — `verify_record` зелёный. |
| 2 | OK | `fsm_advance.verifying`: `hold` до опроса CI — потолок к ожиданию не доходит; `enter_wait` — только после зелёного CI и `verifying_gate` (ветка `elif names` после `if verdict.wait`). Одна запись на визит и голову: `current_wait` — последняя из записей WAIT/статус CI после последнего `state -> verifying`. `board.waiting_on` → `operator`, `catalog._status_line` — первая неотмеченная, `watch` — `WAIT_ACTION` в `gates` и `_significant`. Алерта нет. |
| 3 | OK | `_verify_ok`: состояние, имя профиля, непустой итог, голова («отметка для другой головы»), ожидание текущего визита по этой голове («проверка не ожидается для этой головы»), повторная отметка — отказ. Отметка в `verify_marks` с `visit_step_id`, запись `OK_ACTION`, `review` от `operator`, когда отмечены все. |
| 4 | OK | `_verify_fail`: свой счётчик `tasks.verify_fails` (SCHEMA и `migrate` одним литералом), `>= LIMIT_REVIEW_ITERS` → `escalated` с причиной в тексте перехода; `review_iters` не тронут; эскалацией счётчик не сбрасывается (AC-15 зелёный). |
| 5 | OK | `_advance_verifying_poll`: `auto_stop(..., alert=False)` на ожидании; красный CI идёт прежним путём; `_epic_view` → `_WAITING` по `verify.waiting`. Подхват после команд — через автора `operator` у `state -> …` (`_operator_actions`). Команды из `auto`/надзора не зовутся (AC-19 зелёный). |
| 6 | OK | Внешних вызовов (стенд, конвейер) в `verify.py` нет. |
| 7 | OK | Приложение PLAN: `verify-ok`/`verify-fail` в `FsmTest.commands` через `verify_call` с профилем `human:stand`, ожиданием по голове и проверкой эффекта; планка AC-20 (`git apply --check` и прогон) зелёная. |
| 8 | OK | `artel.main` — обе команды с проверкой числа аргументов, справка дополнена. |

## Замечания
Нет замечаний уровня blocker/major/minor со сценарием поломки.

Наблюдения без последствий, в реестр не вносятся:
- `verify.hold` при всех отмеченных проверках уводит в `review` автором `fsm`. Это достижимо, только если профиль сузился между отметкой и опросом: обычный путь закрывает `verify-ok` автором `operator`.
- Нечитаемая запись проекта теперь держит в `verifying` до потолка и любой внешний проект, а не только проект с `verify`. Это сознательно строже и названо в «Рисках» PLAN.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в итерации 1 не заведено, прошлых итераций нет.

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M6F3DKM3KB2JYMD0J50YRBPE`: 2 passed (`test_ac20_invariants_appendix.py`), код выхода pytest 0.
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m6f3dkm3kb2jymd0j50yrbpe_verify_flow.py tests/test_01m6f3dkm3kb2jymd0j50yrbpe_verify_record.py tests/test_verify_profile.py tests/test_verifying_ceiling.py tests/test_store_schema_migration_parity.py`: 62 passed. С `-n 4` xdist в этой среде не стартовал («node down»), поэтому прогон последовательный.
- Временная мутация 1: в `verify.hold` убрана сверка `wait.sha != sha`. `tests/test_verify_profile.py::test_new_head_inside_visit_needs_new_wait_and_marks` покраснел, как заявлено. Код возвращён (`git checkout -- orchestrator/verify.py`, `git status` чистый).
- Временная мутация 2: автор перехода `review` в `_verify_ok` заменён на `fsm`. `test_operator_is_actor_of_verify_transitions` покраснел. Код возвращён.
- Сверка механизма предела: `fsm_advance.py:350-363` против `_verify_fail` — то же сравнение `>=` и тот же путь `in_dev` + `_maybe_ensure_draft_mr`.
- `grep VERIFYING_STATUS_ACTION orchestrator/`: эту запись пишет только `fsm_advance.verifying:475`, так что признак «последняя из WAIT/статус CI» снимается только опросом CI.
- Изменённых и удалённых утверждений существующих тестов в diff нет: `tests/` получил только новый файл `test_verify_profile.py`. Долгоживущие тесты правлены через `amend-tests` по ANSWER-2, и правка затронула только стенд (подмена `SUPPORTED_PAIRS`).

## Предложения системе
- Параллельный прогон `pytest -n` в шаге ревью на этой машине падает «node down: Not properly terminated» — стоит отметить в скиле, что тесты файлов задачи гоняются последовательно.
