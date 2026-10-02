---
task: 01M3YCHS4F08VTV6XX10VF92H3
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Набор задачи: new --set, модель и стоимость с учётом задачи, set-models

## Подход

Набор задачи хранится в строке задачи двумя колонками: `model_set` (имя) и
`model_set_members` (JSON «роль → модель» на момент `new --set`/
`set-models`). Шаг читает записанный состав, а не `model_sets.yaml`, —
правка файла задачу в работе не двигает (AC-8); снятие допуска пары
сверяется по разделу `pairs:` файла на старте шага (AC-9).

Одна точка разрешения с учётом задачи — `models.resolve_task_role(role,
task)` → `TaskModel(resolution, source, from_set, withdrawn)`:

- роль вне состава / задача без набора — `resolve_role` как раньше,
  источник `role_models` либо `ярус <ярус>`;
- роль в составе, пара снята (`state` ≠ `допущена`, записи нет,
  файл не читается) — боевая модель + текст `withdrawn` для журнала; пара
  на боевой модели допуска не требует (то же правило, что `set_admitted`);
- иначе модель набора теми же звеньями fail-closed, что `role_models:`
  (каталог → `SetModelNotInCatalogError`, `experimental` без
  `allow_experimental` → `SetModelExperimentalError`), провайдер и CLI —
  модели в каталоге.

Проверка допуска для `new --set` и `set-models` — одна функция
`models.admitted_set_members` поверх `set_admitted` части 1; текст пары
вынесен в `_pair_refusal`, общий для допуска набора и сверки на старте шага.

Шаг (`runner`): провайдер шага — `_step_provider` (провайдер модели
набора, иначе `providers.for_role` как раньше); модель — `resolve_task_role`
в `_refuse_before_start` (отказ fail-closed тем же действием журнала
«run отклонён: модель роли не разрешена»; откат снятой пары — запись
«модель набора снята: шаг на боевой модели»). `run_agent_once` (сигнатуру
не трогаем) резолвит то же заново и передаёт провайдер в `role_env(...,
provider=)`, `_spawn_and_wait` (argv и разбор вывода), `_numbered_with_model`
и учёт. Запись «agent run started» дополнена «роль <роль>, источник
модели: <источник>». Задача без набора проходит прежним путём: провайдер
= `None` → прежний `for_role` в каждой фазе.

Стоимость: `charge_step` уже получает модель шага; путь PARTIAL
(`charge_missing_result`) и `partial_cost_usd`/`role_tariff` получили
необязательную строку задачи — тариф модели набора.

Видимость: `status` — `набор <имя>` сразу за `$spent/budget`; `show` —
строка набора; подсказки `approve` — хвост `[набор задачи: <имя>]`
(`models.task_set_hint`) в `auto.auto_stop_advice` и в подсказках входа в
`merge_gate` (`fsm._approve_acceptance`, `fsm_autogate`). Автогейт: первое
условие `_autogate_conditions` — задача с набором остаётся в `acceptance`
с причиной, называющей набор.

`set-models <id> <набор>|--default` — `fsm.cmd_set_models`: допустимые
состояния `SET_MODELS_STATES` + пометка `pause`; отказ перечисляет их;
lease не берётся (у задачи на паузе идущий шаг держит lease до конца).

Стек: `stack.model_providers` добавляет провайдеров моделей наборов
незакрытых задач (`models.live_task_set_providers`, без создания БД, если
её нет). `stack._model_checks` (сверка модели яруса с CLI для `doctor`)
не тронут: модель набора сверяется с CLI на старте её шага
(`provider.model_verdict` в `_refuse_before_start`).

Бюджет SPEC ($50) не переоцениваю: объём совпал с оценкой SPEC.

## Шаги

1. Схема и хранение: колонки `model_set`/`model_set_members` в `SCHEMA` и
   `migrate`; `store.insert_task` пишет их тем же INSERT.
2. `models.py`: `resolve_task_role`, `TaskModel`, `task_set_name`/
   `task_set_members`/`task_set_hint`/`members_text`,
   `admitted_set_members`, `live_task_set_providers`, классы отказов,
   `_pair_refusal`.
3. `new --set`: `artel._new_set_arg` + `catalog.cmd_new(model_set=)` —
   допуск до id/ветки/строки; запись журнала «набор моделей задачи».
4. Шаг: `runner` (провайдер, модель, откат снятой пары, источник в
   записи старта, провайдер в окружении/argv/учёте); `spend` — тариф
   модели набора на пути PARTIAL.
5. Видимость: `catalog.cmd_status`/`cmd_show`, `auto.auto_stop_advice`,
   подсказки `merge_gate` в `fsm`/`fsm_autogate`.
6. `set-models`: `fsm.cmd_set_models` + диспетчер `artel.py` (вне белого
   списка ролей).
7. Автогейт: условие «у задачи нет набора» первым в `_autogate_conditions`.
8. Стек: `stack.model_providers` + `models.live_task_set_providers`.
9. Документация: `docs/stack.md` (раздел «Набор задачи…»),
   `docs/operator-session.md` (пункт `new … --set`), справка `artel.py`.
10. Юнит-тесты `tests/test_task_model_set_units.py` (свойства вне
    долгоживущего файла), регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (`new --set`, имя и состав в БД, набор до закрытия) | 1, 2, 3 |
| 2 (роль без записи — боевая модель) | 2, 4 |
| 3 (недопущенный набор — отказ до заведения) | 2, 3 |
| 4 (провайдер, CLI, вход, тариф от модели набора, fail-closed) | 2, 4, 8 |
| 5 (стоимость по тарифу фактической модели) | 4 |
| 6 (задачи без набора как сейчас) | 2, 4 (путь `provider=None`, `resolve_role`) |
| 7 (снятая пара — боевая модель + журнал) | 2, 4 |
| 8 (видимость: status, запись старта, подсказки approve) | 4, 5 |
| 9 (`set-models` и допустимые состояния) | 6 |
| 10 (ручная приёмка задачи с набором) | 7 |
| 11 (документация) | 9 |
| 12 (существующие тесты не ослаблены) | 10 — ни один тест в `tests/` не правлен |

Проверено исполнением (передний план, таймаут 120 с на тест):

- `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py` — 16 passed
  (несколько прогонов, случайные зёрна);
- `tasks/01M3YCHS4F08VTV6XX10VF92H3/acceptance_tests/test_ac14_docs.py` +
  сторожа `docs/stack.md` — 13 passed;
- `tests/test_task_model_set_units.py` — 7 passed; каждая заявка
  «Ловит мутацию» проверена временной мутацией кода (7 мутаций — тест
  красный, код возвращён);
- затронутые модули: `test_models`, `test_model_sets`,
  `test_01m3ychp14179r32sfjvkqb32g_model_sets`, `test_runner_model_preflight`,
  `test_runner_role_model`, `test_step_cost`, `test_token_rate_divergence`,
  `test_model_tariffs`, `test_fsm_autogate*`, `test_catalog_status_log`,
  `test_new_argv_parsing`, `test_store_schema_migration_parity`,
  `test_01m3pymq6n4scaj9wwttkh6xng_role_models`,
  `test_01m3sa3anyz7036aagxzg753e3_models_roles`,
  `test_artel_role_restricted_commands` — 264 passed;
  `test_stack*`, `test_providers*`, `test_provider_scoped_step_env`,
  `test_runner_role_environment`, `test_codex_login_shell_path`,
  `test_agent_prompt`, `test_agent_log`, `test_agent_failure`,
  `test_cmd_approve_dispatch`, `test_pause*`, `test_catalog_*` — 308 passed;
  `test_auto_cycle`, `test_cycle_hint`, `test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint`,
  `test_approve_acceptance_full_suite`, `test_gates`, `test_canary`,
  `test_canary_acceptance_reason`, `test_01m3rwa2786hcac8pt3xsbkqt4_autogate`,
  `test_invariants`, `test_multitarget_invariants`, `test_runner_wave_breaker`,
  `test_timeout_checkpoint`, `test_01m3se87r3m7hgwx8hg1anakr0_role_environment`,
  `test_01m3xtf5506gf43hd51ece230t_role_refusal` — 333 passed.
  Полный набор `tests/` в шаге не запускался (решение Оператора 05.09) —
  его гоняет CI.

Возврат из verifying (CI красный, `tests/test_multitarget.py::SqlOnlyInStoreTest::test_no_sql_outside_store`):
лексическая проверка ловит ключевые слова SQL в докстрингах вне `store.py`.
Закрыт класс, не экземпляр: кроме названного `orchestrator/catalog.py:464`
(«тем же INSERT») тот же тест ловил `orchestrator/fsm.py:1200` («одним
UPDATE» в `cmd_set_models`). Оба докстринга переформулированы ссылкой на
`store.insert_task`/`store.update_task`; код и тесты не менялись.
`tests/test_multitarget.py` + долгоживущий файл задачи +
`tests/test_task_model_set_units.py` — 74 passed; карта регенерирована.

## Расширение зон

Пути: orchestrator/auto.py

Причина: долгоживущий тест задачи
`tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py::VisibilityTest::test_ac10_approve_hints_on_gates_name_the_set`
читает подсказку гейта через `auto.auto_stop_advice` — «единственный
сборщик подсказки approve на остановке у гейта» (докстринг теста), а SPEC
не назвал `auto.py` в `zones:`. Правка — 3 строки в
`auto_stop_advice` (хвост `models.task_set_hint`) и `models` в импорте.

Мандат выдан: ANSWER-1, `zones-extend` (ANSWER-2), подтверждён ANSWER-3 —
«Расширение зон разрешено: orchestrator/auto.py». Вопрос закрыт, код на
этом шаге не менялся.

## Влияние на систему

- Схема БД: две новые nullable-колонки (`SCHEMA` и `migrate` одним
  составом — паритет держит `test_store_schema_migration_parity`).
  Старые строки — NULL = «без набора».
- Путь шага задачи без набора: модель — тот же `resolve_role`, провайдер —
  прежний `providers.for_role` в каждой фазе (`provider=None`). Изменение
  видно только в тексте записи «agent run started» (добавлены роль и
  источник модели после `model=`; разбор `spend.journal_model` по
  `model=` не задет).
- Гейты: автогейт приёмки получил новое условие отказа только для задач
  с набором — ослаблений нет. Новое действие журнала
  «модель набора снята: шаг на боевой модели». Причина отказа автогейта
  задачи с набором в правиле вины `autogate_refusal_blame` — «не
  установлена» (канареечные задачи наборов не несут, допуск пар это не
  задевает).
- Манифест стека: CLI провайдера модели из набора незакрытой задачи
  становится обязательным, как CLI модели яруса (`required_tools`); БД
  при её отсутствии не создаётся.
- `set-models` — вне белого списка команд роли (процесс роли получает
  отказ диспетчера).
- Тесты в `tests/` не правились и не удалялись; добавлен один новый файл.
- Откат — revert коммитов задачи; колонки остаются в БД (NULL), код без
  них их не читает.

## Риски

- Предполёт шага `doctor.preflight_checks(role, target)`
  (`orchestrator/doctor/preflight.py`, вне зон) знает только провайдера
  роли: у задачи, где набор переводит роль на модель другого провайдера,
  предполёт сверит CLI/токен провайдера роли, а не набора. Тихого запуска
  нет: отсутствие CLI набора даёт «agent run SKIPPED: CLI не найден» на
  `spawn`, а `stack.model_providers` делает CLI набора обязательным
  (сборка окружения отказывает раньше). Полная сверка — правка
  `doctor/preflight.py` отдельной задачей.
- `stack.model_providers` читает БД на каждой сборке манифеста
  (`check_stack` → `role_env`): лишнее открытие SQLite на шаг.

## Предложения системе

- `orchestrator/doctor/preflight.py::preflight_checks(role, target)` не
  принимает задачу — любой будущий «контекст задачи» в разрешении модели
  требует правки предполёта; стоит передавать провайдера шага параметром.
- Анализ зон SPEC: долгоживущий тест читает публичную поверхность модуля
  вне `zones:` (`auto.auto_stop_advice`) — сверка «модули, импортируемые
  планкой задачи, ⊂ zones» на выходе `tests_writing` поймала бы это до
  шага разработчика.
- Повторная эскалация (ANSWER-3): шаг после ответа Оператора закончился
  без снятия `status: escalate` в PLAN, и пульт прочёл старый статус как
  новый вопрос. Правило есть (`skills/escalation-rules.md`, п.4), но
  повтор случился — бриф шага после ANSWER мог бы явно напоминать снять
  статус.
