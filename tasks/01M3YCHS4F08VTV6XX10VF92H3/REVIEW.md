---
task: 01M3YCHS4F08VTV6XX10VF92H3
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Набор задачи: new --set, модель и стоимость с учётом задачи, set-models

## Фаза A: план

- Таблица покрытия PLAN полна: требования 1–12 привязаны к шагам 1–10.
- Шаги — единицы размера MR (схема, `models`, `new --set`, шаг, видимость,
  `set-models`, автогейт, стек, docs, тесты), не микрооперации.
- Подход не конфликтует с архитектурой: одна точка разрешения
  `models.resolve_task_role` поверх `resolve_role`, путь задачи без набора
  (`provider=None` → прежний `providers.for_role`) сохранён; сигнатура
  `run_agent_once` не тронута (ограничение AC-7 01M2CN3ZCSZ54TFJGTDCXTDHXD).
- Расширение зон до `orchestrator/auto.py` покрыто мандатом ANSWER-1/2/3;
  дифф `auto.py` — ровно импорт `models` и хвост `set_hint` в
  `auto_stop_advice` (orchestrator/auto.py:579–587), как разрешено ANSWER-1.
- «Влияние на систему» сверено с диффом: две nullable-колонки (`schema.py`
  SCHEMA + `migrate`), новое действие журнала, новое условие автогейта
  только для задач с набором, `set-models` вне белого списка ролей
  (`artel.py`, комментарий у записи диспетчера), один новый файл в
  `tests/`. Откат — revert, колонки NULL.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `catalog.cmd_new(model_set=)` → `models.admitted_set_members` до id/ветки/строки; имя и состав JSON пишутся тем же `store.insert_task`. Шаг читает `model_set_members` из строки (AC-8 зелёный). |
| 2 | OK | `resolve_task_role`: роль вне состава → `_combat_task_model` (`resolve_role`). |
| 3 | OK | Отказ `sys.exit` до побочных эффектов; текст `set_admitted` называет пару/набор и причину (AC-5..7 на настоящем git). |
| 4 | OK | `_step_provider` + `provider` в `role_env`/`command`/`OutputPump`/учёте; fail-closed через `SetModelNotInCatalogError`/`SetModelExperimentalError` → `MODEL_UNRESOLVED_REFUSAL_ACTION`. Предполёт `doctor/preflight.py` (вне зон) по-прежнему смотрит провайдера роли — заявлено в «Рисках» PLAN, см. «Предложения системе». |
| 5 | OK | KNOWN — модель шага из argv-пути; PARTIAL — `role_tariff(role, task)` в `charge_missing_result` и `partial_cost_usd`. |
| 6 | OK | Без набора: `task_set_members` → `{}`, `resolve_role`, `provider=None`; подсказки — пустой хвост. Изменилась только запись «agent run started» (добавлены роль и источник после `model=`; `spend.journal_model` не задет). |
| 7 | OK | `_set_pair_withdrawn` по `pairs:` (не `sets:`), откат на боевую + `SET_PAIR_WITHDRAWN_ACTION` в журнал и печать; модель = боевой пары не требует (как `set_admitted`). |
| 8 | OK | `status` — `набор <имя>` сразу за бюджетом; запись старта — роль + источник; подсказки в `auto_stop_advice` (все `APPROVE_NEEDS_SHA`, включая `escalated`), `fsm._approve_acceptance`, `fsm_autogate`. |
| 9 | OK | `fsm.cmd_set_models`: `SET_MODELS_STATES` + `pause.is_paused`, отказ перечисляет состояния и паузу; тот же `admitted_set_members`; журнал с прежним и новым набором. |
| 10 | OK | Первое условие `_autogate_conditions` — причина называет набор. |
| 11 | OK | `docs/stack.md` (раздел «Набор задачи…»), `docs/operator-session.md` (пункт `new … --set`). |
| 12 | OK | В `tests/` только новый файл `tests/test_task_model_set_units.py`; существующие тесты не изменены (diff --stat). `set_admitted` отрефакторен через `_pair_refusal` с тем же текстом отказа; `test_model_sets`/часть 1 зелёные. |

## Замечания

Блокирующих, major и minor-замечаний к диффу нет.

Проверенные и отведённые гипотезы:
- `live_task_set_providers` открывает `store.db()` на каждой сборке
  манифеста — `_AutoClosingConnection`, утечки нет; БД при отсутствии не
  создаётся (юнит-тест `test_absent_db_is_not_created`).
- Повторное разрешение в `run_agent_once` после `_refuse_before_start`
  читает ту же строку задачи и тот же `model_sets.yaml` — расхождение
  возможно только при правке файла в окне между ними, и тогда шаг
  идёт на боевой модели (безопасная сторона), а не на снятой паре.
- Тесты `tests/test_task_model_set_units.py` не повторяют долгоживущий файл:
  нечитаемый состав, пара на боевой модели, путь PARTIAL, провайдеры
  стека, `--set` без значения — свойства вне планки. Заявки «Ловит
  мутацию» называют наблюдаемое расхождение; две проверены временной
  мутацией (ниже).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в этой итерации не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py tests/test_task_model_set_units.py tasks/01M3YCHS4F08VTV6XX10VF92H3/acceptance_tests/` — 24 passed.
- `python3 -m pytest -q tests/test_models.py tests/test_model_sets.py tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py tests/test_runner_model_preflight.py tests/test_runner_role_model.py tests/test_step_cost.py tests/test_model_tariffs.py tests/test_catalog_status_log.py tests/test_new_argv_parsing.py tests/test_store_schema_migration_parity.py tests/test_multitarget.py tests/test_artel_role_restricted_commands.py tests/test_fsm_autogate*.py tests/test_stack*.py tests/test_auto_cycle.py tests/test_pause*.py` — 433 passed, 115 subtests passed.
- Временная мутация (код возвращён `git checkout`): `spend.charge_missing_result` → `role_tariff(role)` без задачи и снятый фильтр `_CLOSED_STATES` в `models.live_task_set_providers` — красные ровно `test_partial_cost_of_cut_step_uses_set_model_tariff` и `test_open_task_set_demands_its_provider_closed_does_not` (2 failed, 5 passed).
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой только в строке `built_at_sha` (не дефект), карта возвращена `git checkout`.
- CI коммита f4eeca4d — зелёный (14 проверок, по пакету).

## Предложения системе

- `orchestrator/doctor/preflight.py::preflight_checks(role, target)` и
  `doctor.check_model_provider_cli(role)` знают только провайдера роли: у
  задачи, где набор переводит роль на модель другого провайдера, предполёт
  сверяет CLI/токен чужого провайдера (ложный отказ, если CLI роли нет;
  пропуск, если нет токена провайдера набора). Стоит отдельной задачей
  передавать в предполёт провайдера шага (`runner._step_provider`) — то же
  предложение есть в PLAN.
