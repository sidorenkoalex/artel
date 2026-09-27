---
task: 01M3H5FEXH5M9HGZYT3BCDX5C4
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Тесты манифеста стека не зависят от ярусов настоящего roles.yaml

## Подход

Локальный слой моделей, который песочница пишет рядом с `_roles_yaml_text`,
называет модель у КАЖДОГО яруса перечня `orchestrator/models.py::TIERS`, а
не только у яруса роли под тестом (требование 1). Приём заведён одним
помощником `tests/test_runner_role_model.py::_tiers_text` — там же, где
живёт `_roles_yaml_text`, которым эти песочницы строят карту исполнителей;
остальные файлы импортируют его оттуда, как уже импортируют
`_roles_yaml_text`. Одно место — потому что дефект класса, а не
экземпляра: его повторили бы три файла независимо.

Все ярусы получают ОДНУ модель — ту, которую назвал тест. Это
конфигурация настоящего пульта: шаблон локального слоя
(`orchestrator/models.py::LOCAL_TEMPLATE`) называет `claude-opus-5` у
каждого из трёх ярусов. Различающая сила сценариев при этом не теряется:
«ярус читается тот, который просили» держит отдельный сценарий
`tests/test_runner_model_preflight.py::TierWithoutModelTest` (слой
называет `cheap`, роль стоит на `strong` — отказ), и он остаётся
однорядным сознательно.

Второй вариант ТЗ (нормализация ярусов всех agent-ролей к ярусу теста)
отклонён основаниями требования 2 SPEC; к ним добавилось наблюдение с
кода: `tests/test_providers.py:499` передаёт вторым аргументом
`_roles_yaml_text` идентификатор модели (`claude-opus-5`, сценарий
незарегистрированного провайдера) — нормализация разнесла бы это значение
как «ярус» по ролям, которых тест не называет.

Сценарии, чей предмет — непокрытый или неразрешимый ярус (требование 3),
помощником не пользуются и остаются как есть; у каждого дописано, почему
однорядный слой там намеренный, — иначе следующая правка «причешет» их
под общий приём и молча снимет проверку.

Бюджет SPEC ($25) не переоценивается: зона одна, файлов четыре.

## Шаги

1. Помощник `_tiers_text(model)` в `tests/test_runner_role_model.py` и
   перевод на него трёх песочниц, строящих карту исполнителей из
   настоящего `roles.yaml`:
   - `tests/test_runner_role_model.py::ModelFlagJournalTest.set_tier_model`
     (параметр `tier` снят — ярус называется каждый, 7 вызовов обновлены);
   - `tests/test_runner_model_preflight.py::_StepSandbox.set_model` и
     `BrokenLocalLayerTest` (там однорядный слой был побочным: предмет —
     несхемный `overrides:`);
   - `tests/test_stack_optional_tools.py::_ManifestSandbox.use_tier`
     (константа `LOCAL` распалась на `_tiers_text` + `ALLOW_EXPERIMENTAL`).
2. Регрессия `tests/test_stack_roles_tier_spread.py`: карта исполнителей,
   где ровно одна agent-роль стоит на ярусе, отличном от яруса остальных,
   и `check_stack()` на ней — ни одной строки `model-<роль>` со статусом
   `fail`, все строки моделей ролей зелёные. Ярус-одиночка выбирается по
   факту боевого файла, а не литералом: распределение ролей по ярусам —
   крутилка Оператора, и прибитый литерал перестал бы давать разброс в
   день её поворота.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (раздел «Подход»: основание выбора способа) |
| 3 | 1 (сценарии-исключения перечислены ниже, не тронуты) |
| 4 | 1, 2 |
| 5 | 1 (перечень потребителей ниже) |
| 6 | 2 |

| Критерий | Шаг |
|---|---|
| AC-1 | 1 |
| AC-2 | 1 |
| AC-3 | 1 |
| AC-4 | 1, 2 |
| AC-5 | 2 |

### Требование 5: все тесты с той же зависимостью

Потребители `_roles_yaml_text` (карта исполнителей строится из настоящего
`roles.yaml`) и файлы с собственной копией приёма — найдены
`grep -rn "_roles_yaml_text\|MODELS_LOCAL\|config.ROLES" tests/`:

| Файл | Что делает | Зависимость от ярусов чужих ролей |
|---|---|---|
| `tests/test_runner_role_model.py` | определяет `_roles_yaml_text`, пишет свой слой (`set_tier_model`) | была — снята шагом 1 |
| `tests/test_runner_model_preflight.py` | `_roles_yaml_text` + свой слой (`set_model`, `BrokenLocalLayerTest`) | была — снята шагом 1 |
| `tests/test_stack_optional_tools.py` | `_roles_yaml_text` + свой слой (`use_tier`) | была — снята шагом 1; на ней и покраснела главная ветка 27.09 |
| `tests/test_providers.py` | `_roles_yaml_text` (строки `doctor`, шаг с незнакомым провайдером) | нет: своего слоя не пишет, работает на шаблонном слое `tests/sandbox.py` (все ярусы) |
| `tests/test_agent_prompt.py` | `sandbox.SANDBOX_ROLES_TEXT` (настоящая карта) | нет: слой — `models.ensure_local_template()`, все ярусы названы |
| `tests/sandbox.py` | `SANDBOX_ROLES_TEXT` + `models.ensure_local_template()` в `TmpRootTest.setUp` | нет: шаблон называет модель у каждого яруса — ровно то свойство, которое шаг 1 переносит в песочницы, пишущие слой сами |
| `tests/test_yaml_parsing.py` | читает настоящий `roles.yaml` | нет: предмет — разбор YAML и состав скилов, цепочка моделей не резолвится |
| `tests/test_stack.py`, `tests/test_models.py`, `tests/test_models_doctor.py`, `tests/test_model_tariffs.py`, `tests/test_canary_sets.py`, `tests/test_doctor_canary_sets.py` | пишут СВОЙ синтетический `roles.yaml` во временном каталоге | нет: настоящая карта не читается, ярусы задаёт сам файл теста |

Сценарии-исключения требования 3 (однорядный слой оставлен намеренно, в
каждом дописан комментарий с причиной):
`tests/test_runner_model_preflight.py::TierWithoutModelTest` (ярус роли не
назван в слое) и
`tests/test_stack_optional_tools.py::OptionalToolManifestTest::test_unreadable_layers_demand_nothing_instead_of_raising`
(неразрешимая цепочка и нечитаемая карта исполнителей).

## Влияние на систему

- Зона — только `tests/`. Код `orchestrator/`/`scripts/` не тронут:
  проверяемое поведение то же, менялся способ, которым песочница
  описывает окружение сценария.
- Ни одна проверка не ослаблена и не удалена (требование 4, AC-4): число
  тестовых методов в каждом изменённом файле прежнее (8 / 15 / 15,
  сверено `guard.qualified_test_methods` против HEAD), маркеров
  `skip`/`skipIf`/`skipUnless`/`expectedFailure` нет ни одного
  (`guard.test_skip_markers` — пусто), ассерты и сценарии не трогались.
  Различающая сила «ярус читается тот, который просили» сохранена
  отдельным сценарием `TierWithoutModelTest`, который под общий приём
  сознательно не заводится.
- Гейт заявки мутации: у трёх новых тестов регрессии есть строка «Ловит
  мутацию» (`guard.test_functions_without_mutation_claim` — пусто).
- Карта кодовой базы регенерирована тем же коммитом
  (`python3 scripts/codebase_map.py`): правились `*.py` в `tests/`.
- `roles.yaml` не менялся: перевод роли analyst на ярус `standard` и
  возврат роли на Codex — решение Оператора отдельным MR, «Не входит»
  SPEC. Для проверки AC-1/AC-2 ярус analyst подменялся на диске временно
  и возвращён `git checkout -- roles.yaml`; в диффе ветки файла нет.
- Откат — revert одного merge-коммита: четыре файла `tests/` и карта.

Прогоны (все — в переднем плане, таймаут 120 с; полный набор `tests/` в
шаге не гоняется, его гоняет CI):

- планка задачи `tasks/01M3H5FEXH5M9HGZYT3BCDX5C4/acceptance_tests` —
  5 passed, 10 subtests (все пять критериев, включая прогоны на
  подменённой карте исполнителей в копии дерева);
- AC-1/AC-2 воспроизведены и вручную, правкой `roles.yaml` на диске
  (analyst -> `standard`): до правки
  `test_stack_optional_tools.py::CheckStackLinesTest::test_missing_unused_tool_gives_no_line_at_all`
  красный строкой `model-analyst` (1 failed, 37 passed) — тот самый отказ
  27.09; после правки 86 passed на файлах
  `test_stack_optional_tools.py`, `test_runner_role_model.py`,
  `test_runner_model_preflight.py`, `test_providers.py`,
  `test_models_doctor.py`, `test_stack_roles_tier_spread.py`;
- AC-3 (настоящий `roles.yaml`): 55 passed на
  `test_stack_optional_tools.py`, `test_runner_role_model.py`,
  `test_runner_model_preflight.py`, `test_models_doctor.py`,
  `test_stack_roles_tier_spread.py`;
- соседние модули: 264 passed, 244 subtests (`test_stack.py`,
  `test_providers.py`, `test_invariants.py`, `test_guard_mutation_claim.py`,
  `test_guard_test_ast.py`, `test_canary_sets.py`, `test_models.py`,
  `test_model_tariffs.py`, `test_agent_prompt.py`);
- заявка мутации регрессии проверена подменой `_tiers_text` на однорядный
  слой: `tests/test_stack_roles_tier_spread.py` — 3 failed.

## Риски

- Регрессия выбирает ярус-одиночку из свободных ярусов `models.TIERS`.
  Если Оператор когда-нибудь разведёт agent-роли по ВСЕМ трём ярусам
  сразу, свободного не останется — тест берёт боевую карту как есть (в
  ней разброс уже есть) и всё равно проверяет своё свойство; предпосылка
  «ярусов у agent-ролей больше одного» проверяется ассертом с внятным
  текстом, а не молча.
- Помощник `_tiers_text` живёт в `tests/test_runner_role_model.py` — том
  же файле, что и `_roles_yaml_text`. Файл становится де-факто общим
  модулем песочницы для четырёх соседей. Переносить оба в
  `tests/sandbox.py` — правка вне предмета задачи; отмечено ниже.

## Предложения системе

- `tests/test_runner_role_model.py` де-факто работает общим модулем
  песочницы: `_roles_yaml_text` (и теперь `_tiers_text`) импортируют
  `test_runner_model_preflight.py`, `test_stack_optional_tools.py`,
  `test_providers.py`, `test_stack_roles_tier_spread.py`. Место для
  такого кода — `tests/sandbox.py`; сейчас общий приём прячется в файле,
  чьё имя про флаг `--model`, и находится только grep'ом.
- Класс «тест строит окружение из боевого конфигурационного файла и
  описывает ЧАСТЬ его» повторился: сначала `tests/sandbox.py`
  дописывал `model_tier` ролям, у которых его нет (переходная мера), теперь
  — слой с одним ярусом. `skills/coding-standards.md` про этот класс
  молчит: тест, читающий защищённый файл (`roles.yaml`, `models.yaml`),
  обязан описывать его ЦЕЛИКОМ либо не зависеть от неописанной части —
  иначе краснеет решение Оператора, а не предмет проверки.
