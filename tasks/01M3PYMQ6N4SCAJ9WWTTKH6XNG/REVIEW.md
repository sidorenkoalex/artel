---
task: 01M3PYMQ6N4SCAJ9WWTTKH6XNG
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Клон канарейки берёт модели из боевого слоя; набор может перевести одну роль

## Фаза A: план

- Таблица покрытия полна: требования 1–6 → шаги 1–3, AC-1..AC-13 разнесены
  по двум долгоживущим файлам задачи; перечень переписанных тестов (AC-14)
  есть, по каждому методу сказано, что изменилось.
- Шаги размера MR: models/roles/doctor → canary → тесты.
- Подход согласован с архитектурой. `role_models:` разбирается по образцу
  `role_providers:`, отказы — подклассы прежних звеньев
  (`RoleModelNotInCatalogError(ModelNotInCatalogError)`,
  `RoleModelExperimentalError(ExperimentalNotAllowedError)`), так что
  прежние `except` их ловят. Решение не трогать `_sha_label` обосновано:
  её зовут залоченные планки (SPEC «Не входит»).
- «Влияние на систему» сверено с diff: затронуты
  `orchestrator/{canary,models,roles}.py`, `orchestrator/doctor/*`, два
  файла `tests/` и карта. Защищённые пути, `store.py`, guard, гейты не
  тронуты. Первая после мержа несравнимость базовой линии заявлена и
  прямо требуется требованием 5.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_set_plan` берёт за основу `models.load_local()` пульта и для набора по умолчанию; `_clone_layer` переносит ярусы, разрешения `experimental` и тарифы моделей, на которые ссылается слой клона, а также `role_providers:` и `role_models:`. `canary_sets:` в `LocalLayer` не попадает, значит и в текст слоя клона тоже. Если слой пульта нечитаем — шаблон, и `_layer_source` называет «шаблон — слой пульта не прочитан: <причина>». |
| 2 | OK | `ROLE_MODELS_KEY` стоит рядом с `ROLE_PROVIDERS_KEY`. `resolve_role` → `_resolve_role_model`; ярус читается первым, поэтому роль вне карты даёт прежний отказ. Провайдер берётся из `role_providers:`, иначе из каталога; `roles.provider` делает то же. `doctor.check_role_models` печатает строку на каждую запись. |
| 3 | OK | Набор кладётся записями `role_models:`/`role_providers:` только своих ролей, ярусы остаются ярусами основы. Проверки набора стоят до клона (`_check_set_entries_or_exit` до `_resolve_target_sha`/`_ephemeral_clone`), отказ «две модели ярусу» удалён. `codex_roles` считается по разрешению ролей в слое клона. |
| 4 | OK | `_plan_summary` выдаёт «роль → модель» каждой агентской роли и источник; сводка стоит в первой строке, в строке итога и в `models_summary`. Строка итога несёт «код клона {code_sha}», первая строка — `_target_origin_note` без «код пина». |
| 5 | OK | `_baseline_deviation_note(..., models_summary)` сравнивает модели этого прогона (без источника) с последним зелёным прогоном той же пары, исключая текущую задачу. При несравнимой линии: алерта нет, линия перезаписана, предупреждение выдано, вердикт не тронут. |
| 6 | OK | Переписанные тесты перечислены в PLAN, методы не удалены (`test_canary_sets.py` 47 → 49, `test_canary_codex_clone_auth.py` — прежнее число). Удалена только константа `STRONG_ROLES`, не тест. Заявка «Ловит мутацию: слой клона из шаблона» есть в AC-1 и в переписанном `test_default_set_plan_carries_no_clone_layer_and_no_summary`. |

Тесты. Изменённые методы `tests/` несут заявки «Ловит мутацию: …» с
наблюдаемым расхождением: другая модель/провайдер в `role_models:`, другой
состав `codex_roles`, отсутствие источника в сводке. Повторов
долгоживущих файлов задачи среди них нет: тесты разработчика проверяют
`_set_plan`/`roles.provider` на уровне единицы, а долгоживущие —
`cmd_canary` целиком. Группы долгоживущих файлов проставлены верно: оба
проверяют свойства кода, а не факты задачи. Ослабления ассертов в diff
`tests/` нет. Прежние ассерты старого поведения (сдвиг яруса) заменены
ассертами нового поведения по требованию 6.

Наблюдения ниже порога замечания (сценария поломки нет, в реестр не
заношу):
- `orchestrator/canary.py:2318` — `_record_canary_run` по-прежнему считает
  `sha_label`, а `_run_one_task` его отбрасывает (`_label`). Это мёртвое
  вычисление, оставленное ради сигнатуры, которую зовут залоченные
  планки.
- `tests/test_canary.py:652` — докстринг говорит, что `cmd_canary` идёт
  через `_sha_label`. Это больше не так, ассерт при этом верен.
- `_clone_layer` переносит тариф модели любого яруса основы, даже если на
  этом ярусе нет ни одной агентской роли. SPEC говорит о «моделях, на
  которых идут роли прогона». На стоимость это не влияет: тариф
  применяется только к модели шага.

## Замечания

Замечаний уровня blocker/major нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py tests/test_canary_sets.py tests/test_canary_codex_clone_auth.py tests/test_canary.py tests/test_models.py tests/test_doctor_canary_sets.py` — 238 passed, 21 subtests passed.
- `python3 -m pytest -q tests/test_canary_budget_ceiling.py tests/test_canary_drive.py tests/test_canary_synthetic_answer.py tests/test_canary_template_flag.py tests/test_doctor.py tests/test_doctor_agent_roles.py tests/test_doctor_canary_pool.py tests/test_model_tariffs.py tests/test_models_doctor.py tests/test_roles_map_fixture.py tests/test_runner_model_preflight.py tests/test_runner_role_model.py tests/test_stack_roles_tier_spread.py` — 303 passed, 39 subtests passed.
- Временная мутация «слой клона из шаблона»: в `orchestrator/canary.py:569` условие `if pult is None and not entries:` заменено на `if not entries:`. Покраснели 4 теста: AC-1, AC-10 (без набора) и AC-12 долгоживущего файла, а также `test_canary_sets.py::DefaultSetPlanTest::test_default_set_plan_carries_no_clone_layer_and_no_summary`. Код возвращён, `git status` чист, кроме `tasks/`.
- Точечно прочитан `store.green_canary_runs` (сортировка «свежие первыми»; `_previous_run_models` опирается на неё) и `_record_canary_run` (запись `models_summary` для набора по умолчанию, судьба `sha_label`).
- CI коммита e2bad07e зелёный (из пакета). Полный набор `tests/` в шаге не запускал.

## Предложения системе

- Залоченные планки смерженных задач, закрепляющие поведение, которое
  отменила более поздняя SPEC (здесь
  `tasks/01M2B6K02YVJBWE1JDWP85EJH0/acceptance_tests/test_ac8_report_pin_source_label.py`
  против требования 4), сейчас держат мёртвый код в продуктиве
  (`_sha_label`, `sha_label` в `_record_canary_run`). Поддерживаю
  предложение PLAN о механизме пометки «планка X отменена SPEC Y».
