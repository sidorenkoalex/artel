---
task: 01M3PYMQ6N4SCAJ9WWTTKH6XNG
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Клон канарейки берёт модели из боевого слоя пульта; набор может перевести одну роль

## Подход

Монолит, как предложено в SPEC: `role_models:` без канареечного
потребителя Оператору ничего не даёт.

**Раздел `role_models:` (требование 2).** `models.ROLE_MODELS_KEY` стоит
рядом с `ROLE_PROVIDERS_KEY`, разбор идёт по образцу `_role_providers`,
поле `role_models` добавлено в `models.LocalLayer`. `resolve_role` сначала
читает ярус роли (роль вне карты — прежний отказ), затем, если у роли есть
запись в `role_models:`, разрешает её через `_resolve_role_model`: модель
записи, провайдер из `role_providers:`, иначе провайдер модели по каталогу.
Именованные отказы — `RoleModelNotInCatalogError` (подкласс
`ModelNotInCatalogError`) и `RoleModelExperimentalError` (подкласс
`ExperimentalNotAllowedError`); оба называют роль и модель. Прежние
`except` по классам звена продолжают их ловить. `roles.provider` тоже идёт
за моделью записи, если `role_providers:` для роли пуст. Без этого шаг
ушёл бы CLI из `roles.yaml` с моделью чужого провайдера. `doctor` —
`check_role_models` (`doctor/model_catalog.py`): по строке `role-models` на
каждую запись, ставится в `all_checks` сразу за `models-local`.

**Слой клона (требования 1, 3).** `canary._set_plan` теперь собирает слой
клона и для набора по умолчанию. Основа — `models.load_local()` пульта,
если его не удалось прочитать — `models.local_template_layer()`. Поверх
основы кладутся записи набора в `role_models:`/`role_providers:`
(`_clone_layer`). Ярусы всегда берутся из основы. Разрешения
`experimental` и тарифы основы переносятся только для моделей, на которые
ссылается слой клона (ярусы и `role_models:`); модель набора со статусом
`experimental` разрешается сама, как раньше. `canary_sets:` в `LocalLayer`
не попадает, поэтому и в текст слоя клона тоже. Если слой пульта не
прочитан и набора нет, `layer_text=None`: клон остаётся шаблоном из
`cmd_init`, как раньше. Проверки набора стоят до клона
(`_check_set_entries_or_exit`), отказ «две разные модели ярусу» удалён
вместе со сдвигом яруса (`_set_tiers_or_exit`, `_roles_of_tiers`,
`_set_summary`, `_codex_roles`, `_pult_overrides` удалены). Роли Codex
плана — роли, которые в слое клона идут провайдером `codex` по
`models.resolve_role` на слое клона (`_roles_in_clone`), поэтому
проверка входа и перенос указателя касаются только роли набора.

**Сводка (требование 4).** `plan.summary` = «роль → модель» для каждой
агентской роли в порядке `roles.yaml` плюс `; источник: <слой пульта |
набор <имя> | шаблон — слой пульта не прочитан: <причина>>`. Сводка
попадает в первую строку, строку итога задачи и `models_summary`. Подпись
кода в строке итога — «код клона <head результата клона>». Первая строка
вместо `_sha_label` получает `_target_origin_note` («голова origin/main» /
«явный --sha» / «HEAD главной копии — origin не ответил»), поэтому «код
пина» больше не печатается. Саму функцию `_sha_label` я не трогал: её
напрямую зовут `tests/test_canary.py` и залоченные планки других задач
(SPEC «Не входит»).

**Базовая линия (требование 5).** В `_baseline_deviation_note` добавлен
параметр `models_summary`. Функция сравнивает модели этого прогона (часть
сводки до `; источник:`, `_summary_models`) с моделями последнего
зелёного прогона той же пары, исключая текущую задачу
(`_previous_run_models` через `store.green_canary_runs`; `store.py` вне
зон). Если моделей нет, строки нет или модели разные: алерт не
поднимается, линия перезаписывается, возвращается предупреждение «базовая
линия несравнима — модели ролей сменились». `models_summary=None`
(`_run_one_task` без плана, залоченная планка 01M1SC3Y20YBTTJVQDJBF2NDQW)
оставляет прежнее поведение. `_DEFAULT_SET_PLAN` остаётся только для этих
вызывающих: `cmd_canary` его не использует.

Бюджет SPEC ($35) не пересматриваю.

## Шаги

1. `orchestrator/models.py`, `orchestrator/roles.py`,
   `orchestrator/doctor/{model_catalog,__init__,cli,canary_sets}.py` —
   раздел `role_models:`, разрешение и отказы, провайдер роли, строка
   `doctor`.
2. `orchestrator/canary.py` — слой клона из слоя пульта, набор по ролям,
   сводка всех ролей с источником, подпись «код клона», несравнимая
   базовая линия.
3. Тесты `tests/`: переписаны тесты прежнего поведения (перечень ниже),
   добавлены два новых, регенерирована `docs/codebase-map.md`.

Переписанные тесты (AC-14; ни один метод не удалён, ни один файл не
удалён):

- `tests/test_canary_sets.py` (методов было 47, стало 49):
  - `SetPlanRefusalsTest::test_two_roles_of_one_tier_with_different_models_are_refused`
    — вместо отказа проверяет, что набор принят и у каждой роли своя
    запись `role_models:` (требование 3, AC-7);
  - `DefaultSetPlanTest::test_default_set_plan_carries_no_clone_layer_and_no_summary`
    — слой клона набора по умолчанию: ярусы пульта, сводка всех ролей с
    источником «слой пульта» (требования 1, 4); это «Ловит мутацию: слой
    клона из шаблона»;
  - `CloneLocalLayerTextTest::test_named_tier_points_at_the_set_model_and_the_rest_at_the_template`
    — ярусы клона = ярусы пульта, роль набора в `role_models:`
    (требование 3);
  - `CloneLocalLayerTextTest::test_every_role_of_a_moved_tier_gets_the_set_provider`
    — провайдер набора получает только роль набора (требование 3);
  - `CloneLocalLayerTextTest::test_summary_names_every_role_that_really_goes_on_the_set_model`
    — сводка называет все роли и источник «набор <имя>» (требование 4);
  - докстринг `test_override_of_a_model_outside_the_set_is_not_carried_over`
    поправлен под новое основание, ассерт не менялся;
  - новые: `RoleProviderOverrideTest::test_role_models_entry_without_role_providers_takes_the_model_provider`,
    `DefaultSetPlanTest::test_set_over_an_unparseable_pult_layer_names_the_template_base`.
- `tests/test_canary_codex_clone_auth.py` (число методов прежнее):
  - `CodexRolesOfPlanTest::test_every_role_of_the_shifted_tier_counts_not_only_the_named_ones`
    и `::test_only_the_codex_tier_counts_when_the_set_shifts_two_tiers`
    — в перечне ролей Codex только роли набора (требование 3, AC-9);
  - `CodexCloneAuthTest::test_the_pointer_bytes_and_the_first_role_alphabetically_are_returned`
    и `::test_a_missing_pointer_is_refused_by_path_and_with_the_recipe` —
    проверку входа получает роль набора `developer`, а не сосед по ярусу
    `analyst`; константа `STRONG_ROLES` больше не используется и удалена.

Подпись «код пина» в сводке прогона `tests/` не закрепляли: `tests/test_canary.py::ShaLabelTest`
проверяет саму `_sha_label`, которая осталась как была, а
`tests/test_canary_template_flag.py` лишь подменяет её.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2, 3 (AC-1, AC-2 — долгоживущий `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`) |
| 2 | 1, 3 (AC-3..AC-5 — `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`) |
| 3 | 2, 3 (AC-6..AC-9) |
| 4 | 2 (AC-10, AC-11) |
| 5 | 2 (AC-12, AC-13) |
| 6 | 3 |

Прогоны в шаге (передний план, `-p timeout -o timeout=300`):

- оба долгоживущих файла задачи — 26 passed, прогонял несколько раз со
  случайными зёрнами;
- `test_canary*`, `test_models*`, `test_doctor_canary_sets`,
  `test_yaml_parsing`, `test_roles_map_fixture`, `test_catalog_fixture` —
  370 passed;
- `test_doctor*`, `test_providers*`, `test_runner_role_model`,
  `test_runner_model_preflight`, `test_stack*`, `test_pin`,
  `test_model_tariffs`, `test_step_cost`, `test_token_rate_divergence`,
  `test_provider_scoped_step_env`, `test_codex_login_shell_path`,
  `test_retro` — 474 passed.

Полный набор `tests/` в шаге не запускал (запрет скила), его прогоняет CI.
Сторожей проверил временными мутациями: семь мутаций (провайдер записи в
`roles.provider`, источник «поверх шаблона», шаблон вместо слоя пульта,
потеря записи `role_models:` набора, сводка только по роли набора, роли
Codex без сверки провайдера, провайдер набора всем ролям) — на каждой
тест красный, код возвращён.

## Влияние на систему

- Прогон канарейки без `--set` теперь идёт на моделях пульта, а не на
  шаблоне. Первый штатный прогон каждой пары после мержа получит
  несравнимую базовую линию: у прежних строк `canary_runs` нет сводки
  моделей всех ролей. Линия перезапишется, алерт `threshold` не
  поднимется, вердикт не изменится. Это требование 5, а не ослабление:
  гейт сдвига пина сравнивает только прогоны на тех же моделях.
- `resolve_role` для ролей без записи `role_models:` работает как раньше
  (AC-3). Для ролей с записью `roles.provider` возвращает провайдера
  модели записи, если `role_providers:` пуст. На сегодняшнем боевом слое
  раздела `role_models:` нет, поэтому поведение пульта не меняется.
- `doctor` получил новые строки `role-models`, только если раздел есть.
  Старые проверки не тронуты.
- Защищённые пути, гейты, guard и `store.py` не менялись. `_sha_label`
  сохранена для прямых вызывающих.
- Откат — revert коммита задачи.

## Риски

- Если в слое пульта роль переведена на Codex (через `role_providers:`
  или `role_models:`), прогон канарейки без набора тоже потребует входа
  Codex в клон (`_codex_clone_auth`). Это прямое следствие «клон =
  боевой слой»: раньше такой прогон шёл на шаблоне Claude и проверял не
  то.
- Сводка нечитаемого слоя пульта содержит текст причины с путём. Для
  сравнения базовой линии эта часть не используется: она стоит после
  `; источник:`.

## Предложения системе

- `tasks/01M2B6K02YVJBWE1JDWP85EJH0/acceptance_tests/test_ac8_report_pin_source_label.py`
  (залоченная планка смерженной задачи) требует «код пина»/«код
  origin/main» в выводе прогона, и эта SPEC прямо отменяет это поведение.
  Если такие планки гоняются где-то вне `tests/`, они покраснеют. Нужен
  явный механизм пометки «планка задачи X отменена SPEC Y», иначе каждая
  следующая задача заново решает, что делать с чужими залоченными
  планками.
