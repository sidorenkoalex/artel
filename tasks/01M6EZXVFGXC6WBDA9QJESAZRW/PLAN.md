---
task: 01M6EZXVFGXC6WBDA9QJESAZRW
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab Б2.3-1: отказ при сбое вместо пропуска

## Подход
Каждое место, где сбой чтения записи проекта (`targets.TargetsError`) или
БД (`sqlite3.Error`) сегодня глотается в «нет ограничения», превращается в
отказ с причиной для проекта вне артели; артель (`config.DEFAULT_TARGET`,
`repo_context.is_artel`) — прежним путём. Признак гейта — только
помощниками `targets.py` (`merged_by_project_people`, `push_whitelisted`):
новых сравнений `forge`/`merge_gate` с литералом нет, `EXEMPT` сторожа ac9
не растёт.

- `github_adapter`: функция-читатель записи `_people_entry_record` (только
  для `people_entry`); `people_entry` для артели запись не читает (`None`),
  иначе `TargetsError` пробрасывает. `ensure_forge_draft_mr` ловит его и
  возвращает причину «запись проекта не прочитана: …» — отказ гейта
  `_forge_draft_mr_gate` (`tests_writing.py` не меняется). Отказ пределом
  отправок узнаётся по коду `gitcmd.IN_FLIGHT_REFUSAL`, не по stderr.
- `fsm_merge_gate`: место вызова `people_entry` ловит `TargetsError` и
  отказывает `_people_refusal(PEOPLE_REFUSED_ACTION, …)` → `("stopped",)`;
  `_awaiting_limit_refuses` при `TargetsError` — отказ «предел
  awaiting_human не проверен: запись проекта не прочитана: …»;
  `_mr_incident_stops` — статус вне `opened`/`merged`/`closed` (в том
  числе `""`, `None`) — отказ `MR_REFUSED_ACTION`.
- `gitcmd`: отказ пределом несёт код `IN_FLIGHT_REFUSAL` (поле
  `_PushPlan.code`, `_refused(..., code=)`); `in_flight_refusal`,
  проверка `max_in_flight` в `_push_plan`, чтение `in_repo` (выделено
  `_destination_project` — проект назначения без чтения БД) — отказ при
  сбое вне артели; адрес-URL при непрочитанной записи, не совпадающий с
  `remote.origin.url` артели, — проект неизвестен → «гейт мержа неизвестен
  — targets.yaml не читается». Тексты причин сбоя не содержат
  `IN_FLIGHT_LIMIT_REASON`: `status` (`catalog.py:1363`) не покажет сбой
  очередью.
- `ci.py`/`targets.py`: реестр хостингов не подставляется импортом `ci` —
  `targets` берёт его сам лениво (`forge.IMPLEMENTATIONS`) в проверке
  `full_suite`.

Оценка SPEC ($40) не меняется.

## Шаги
1. `github_adapter.py` + `fsm_merge_gate.py`: читатель записи,
   отказ гейта мержа и чернового MR, предел awaiting, статус MR; код
   предела в `ensure_draft_mr`.
2. `gitcmd.py`: код отказа пределом, отказы при сбое в
   `in_flight_refusal`/`_push_plan`/`in_repo`, адрес-URL.
3. `ci.py`/`targets.py`: реестр без подстановки при импорте.
4. Тесты в `tests/` (долгоживущие свойства, не покрытые
   `tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py`), правка
   входа заглушки `test_mr_delivery_units.py::…::test_in_flight_refusal_is_not_an_incident`
   (код возврата — смена входа, утверждения прежние, SPEC «Материалы»),
   тест правила признака (а) `mr_sync` (требование 9); карта кодовой базы.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 4 |
| 2 | 2, 4 |
| 3 | 1, 4 |
| 4 | 2, 4 |
| 5 | 2, 4 |
| 6 | 2, 4 |
| 7 | 1, 2, 4 |
| 8 | 1, 4 |
| 9 | 4 |
| 10 | 3 |
| 11 | 1, 2 |
| 12 | 4 |
| 13 | 1, 4 |

## Влияние на систему
Изменение только ужесточает: прежние пропуски при сбое становятся отказами
для внешних проектов; пути артели и `github`+`operator` при читаемых
записи и БД прежние (AC-17). Гейты, лимиты, тесты не ослабляются; у
существующего теста меняется лишь вход заглушки (код возврата отказа
пределом). Потребитель вне зон `amend._refuse_in_flight` начинает
отказывать внешнему проекту при сбое (AC-8 — у артели нет). Откат —
revert одного merge-коммита.

## Риски
- Код `IN_FLIGHT_REFUSAL` — вызывающие, проверяющие `returncode == 1`
  для отказа пределом, перестанут его видеть; таких в `orchestrator/` нет
  (поиск по `IN_FLIGHT_LIMIT_REASON`/`returncode`).
- Отправка артели по URL при сломанном `targets.yaml` теперь проходит
  только в адрес `remote.origin.url` корня пульта.

## Закрытие ревью, итерация 1
R1-F1 (fixed): в `tests/test_fail_closed_on_read_failure.py` добавлены
четыре сторожа под мутации A–D из REVIEW; код не менялся.

| Место (мутация) | Сторож в `tests/` |
|---|---|
| A `fsm_merge_gate.py` ловля `TargetsError` у `people_entry` (треб. 1) | `test_merge_gate_unread_entry_refuses_external[target-human/operator]` |
| B `gitcmd.py` `plan.code = IN_FLIGHT_REFUSAL` (треб. 7) | `test_in_flight_limit_refusal_carries_code_from_git_and_in_repo` |
| C `gitcmd.py` `sqlite3.Error` счёта `max_in_flight` вне артели (треб. 5) | `test_push_plan_in_flight_db_error_external_refused` |
| D `gitcmd.py` `sqlite3.Error` в `in_repo` вне артели (треб. 6) | `test_in_repo_db_error_refuses_external_not_artel` |

Каждая мутация временно внесена по отдельности: краснеет ровно свой
сторож (A — 2 failed, B/C/D — по 1 failed из 20), код возвращён
`git checkout`.

## Проверка
- Планка `plank-run`: 42 passed (до и после коммита кода; после
  итерации 1 — 42 passed, код выхода 0).
- Итерация 1: `test_fail_closed_on_read_failure.py`,
  `test_mr_delivery_units.py`, долгоживущий файл задачи — 34 passed.
- Свои тесты `tests/test_fail_closed_on_read_failure.py` (15): мутации
  `return False` в `_awaiting_limit_refuses`, поиск строки предела в
  stderr `github_adapter`, `if True` в `mr_sync.py:356` — тесты красные,
  код возвращён.
- Затронутые модули (`test_mr_delivery_units`, `test_gitcmd_*`,
  `test_*merge_gate*`, `test_github_adapter`, доставка через MR, политика
  доставки, компоненты/`full_suite`, долгоживущий файл задачи и др.) —
  850 passed.

## Предложения системе
- Сторож роли отказывает `pytest -n` на перечне файлов как «полному
  прогону» (`conftest`/xdist): перечень затронутых модулей идёт только
  последовательно — 4–5 минут на шаг.
