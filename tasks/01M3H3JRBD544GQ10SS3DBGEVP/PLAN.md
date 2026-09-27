---
task: 01M3H3JRBD544GQ10SS3DBGEVP
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: doctor предполётит роль analyst и вход провайдера Codex

## Подход

Одна смена источника перечня ролей, всё остальное — следствие.

**`agent_roles()` читает карту исполнителей, а не `config.STATE_ROLE`**
(`orchestrator/doctor/preflight.py:531`). Было
`sorted(set(config.STATE_ROLE.values()))` — словарь «состояние FSM → роль»,
в который `spec_writing` не входит намеренно
(`orchestrator/runner.py:91`, `orchestrator/auto.py:557`: роль analyst
исполняет это состояние только при наличии ТЗ). Стало
`sorted(role for role, entry in roles.load().items() if entry.get("executor")
== "agent")`. `config.STATE_ROLE` и его читатели (`runner`, `auto`, `pause`,
`doctor/leases.py:97`) не тронуты — они отвечают на другой вопрос
(«кто работает в ЭТОМ состоянии»), и дописывание туда `spec_writing: analyst`
поменяло бы поведение FSM там, где задача обещала не трогать ничего.

Все зависимые от роли строки предполёта (`provider_preflight_checks`,
`check_role_providers`, `check_models_local`, тариф моделей,
`model_provider_mismatches`, `check_foreign_provider_secrets`) уже
перебирают именно этот перечень — добавлять им кода не нужно, analyst
получает свои строки от провайдера, который назван у него в карте (или в
`role_providers:` локального слоя): на Codex — `codex-chatgpt-auth` и
`codex-role-home`, на Claude — прежние `token` и `role-home-reference`.
Склейка `provider_preflight_checks` по ИМЕНИ строки не меняется, поэтому
не зависящие от роли строки (`cli-found`, `cli-version`, дом роли)
остаются по одной на провайдера.

**Два перечня вместо одного, потому что деградация нужна разная**
(требование 4). До задачи перечень жил словарём в коде и `roles.yaml` не
читал вовсе; теперь от файла зависит каждая строка, перебирающая роли.
`agent_roles()` отдаёт `RolesError` наружу — только так строка
`role-providers` сохраняет свой прежний именованный WARN («файл не
разобран»): она зовёт перечень ВНУТРИ обработки отказа, и подставить туда
молчаливый дефолт значило бы утверждать прочитанным файл, которого не
читали (тот же довод, что у `providers.role_providers`). Остальным строкам
падать нельзя — трейсбек унёс бы с собой диск, сирот, lease: для них
добавлен `agent_roles_or_empty()`, деградирующий до пустого перечня. Это
прямо разрешённая приёмочной планкой развилка
(`acceptance_tests/test_ac4_unreadable_roles_map.py:79-84`).

Бюджет SPEC ($25) не переоценивается: правка — один узел и его читатели,
поле `budget_usd` во frontmatter не заводится.

## Шаги

1. **`agent_roles()` — из карты исполнителей; `agent_roles_or_empty()` —
   деградирующий перечень** (`orchestrator/doctor/preflight.py`,
   `orchestrator/doctor/__init__.py` — связывание в фасаде).
2. **Читатели перечня переведены на деградирующий вариант там, где
   падение недопустимо**: `check_models_local`
   (`orchestrator/doctor/model_catalog.py`), `_resolved_roles`
   (`orchestrator/doctor/model_tariffs.py`),
   `check_foreign_provider_secrets` (`orchestrator/doctor/isolation.py`),
   `provider_preflight_checks` (`preflight.py`). В
   `model_provider_mismatches` чтение перечня перенесено ВНУТРЬ уже
   существовавшего `except RolesError` — ни строки новой обработки.
   `check_models_local` на пустом перечне отвечает честной строкой «ярусы
   не сверены», а не зелёным списком цепочек из нуля элементов — тем же
   текстом-приёмом, что соседняя `check_models_catalog` при непрочитанном
   слое.
3. **Постоянные тесты** — `tests/test_doctor_agent_roles.py` (новый файл,
   10 методов): источник перечня, карта против `STATE_ROLE`,
   `STATE_ROLE` не тронут, строгий перечень против деградирующего, строки
   analyst на Codex, отсутствие строк Codex на пульте без Codex, склейка
   по одной строке на провайдера, «повышение роли в карте добавляет только
   её строки», именованный WARN и отсутствие падений восьми функций на
   нечитаемой карте.
4. **Карта кодовой базы** — `python3 scripts/codebase_map.py` тем же
   коммитом.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (перечень), 3 (охват) |
| 3 | 1 (склейка не менялась), 3 |
| 4 | 1, 2 |
| 5 | 3 |

| Критерий приёмки | Чем закрыт |
|---|---|
| AC-1 | `preflight.py::agent_roles`; `tests/test_doctor_agent_roles.py::AgentRolesListTest` (3 метода) |
| AC-2 | `tests/test_doctor_agent_roles.py::AnalystPreflightLinesTest` — оба провайдера |
| AC-3 | `…::test_role_independent_lines_stay_one_per_provider`, `…::test_promoting_a_role_in_the_map_only_adds_lines_naming_it` |
| AC-4 | `preflight.py::agent_roles_or_empty`; `…::UnreadableRolesMapTest` (2 метода, 8 функций сабтестами) |
| AC-5 | `tests/test_doctor_agent_roles.py`; прогоны пяти названных файлов ниже |

## Влияние на систему

**Что затронуто за пределами правки.** Перечень ролей `doctor` стал шире
на одну роль (analyst), поэтому шире стали и все строки, которые по нему
перебирают: `token`/`codex-chatgpt-auth`, `models-local`, тариф моделей,
`role-providers`, `foreign-provider-secrets`, `check_model_provider_cli`.
Вывод `doctor` на пульте, где все роли на Claude, отличается от прежнего
РОВНО добавлением строк, называющих analyst — это отдельный тест
(`test_promoting_a_role_in_the_map_only_adds_lines_naming_it`), а не
утверждение. Предполёт конкретного шага (`preflight_checks(role, target)`)
не затронут вовсе: он всегда получал роль параметром.

**Инварианты и гейты рядом.** `config.STATE_ROLE` не изменён — инвариант
`STATE_ROLE ⊆ FSM_STATES` (`tests/test_invariants.py:401`) и
`tests/test_auto_cycle.py:349` остаются в силе; `tests/test_invariants.py`
не тронут (SPEC, «Не входит»). Ни один тест, гейт, лимит или guard не
ослаблен и не удалён: правок в `tests/` только две — новый файл и
фикстура, разобранная в «Рисках».

**Прогоны (передний план, таймаут явный).**
- `tests/test_doctor_agent_roles.py` — 10 passed, 14 subtests.
- `tests/test_doctor.py tests/test_models_doctor.py tests/test_providers.py
  tests/test_providers_codex.py tests/test_runner_model_preflight.py
  tests/test_model_tariffs.py tests/test_models.py` — 299 passed, 104
  subtests (пять файлов AC-5 внутри).
- `tests/test_invariants.py tests/test_canary_sets.py
  tests/test_doctor_canary_sets.py tests/test_doctor_canary_pool.py
  tests/test_provider_scoped_step_env.py tests/test_stack.py
  tests/test_yaml_parsing.py tests/test_doctor_wave_breaker.py
  tests/test_doctor_fix_ignored_artifacts.py` — 217 passed, 256 subtests.
- `tests/test_doctor_artifact_branch_ci.py
  tests/test_doctor_artifact_branch_sync.py tests/test_runner_role_model.py
  tests/test_runner_wave_breaker.py tests/test_multitarget.py
  tests/test_multitarget_invariants.py` — 89 passed, 14 subtests.
- `tests/test_stack_optional_tools.py tests/test_stack.py
  tests/test_stack_ci.py` — 50 passed, 7 subtests.
- `tests/test_artel_role_restricted_commands.py tests/test_git_hooks.py
  tests/test_token_rate_divergence.py tests/test_canary.py` — зелёные.
- Приёмочная планка задачи — 13 passed, 10 subtests.
- Полный набор `tests/` в шаге не гонялся (skills/coding-standards.md); его
  гоняет CI на пуш ветки.

**Откат.** Revert одного merge-коммита: пять файлов `orchestrator/doctor/`,
один новый файл `tests/`, одна фикстура `tests/`, регенерированная карта.
Ни схемы БД, ни формата артефактов, ни состояний FSM правка не касается.

## Риски

- **Пре-существующий красный тест вне предмета задачи, починенный в зоне
  `tests/`.** `tests/test_stack_optional_tools.py::CheckStackLinesTest::
  test_missing_unused_tool_gives_no_line_at_all` красен НА ЧИСТОМ ДЕРЕВЕ
  ветки (проверено прогоном на дереве без правок этой задачи): фикстура
  `LOCAL` описывает только ярус `strong`, а с 27.09 (`roles.yaml`,
  коммит a6da0abe: analyst → `model_tier: standard`) `stack.check_stack()`
  печатает `model-analyst` красным — цепочка яруса `standard` в фикстуре не
  разрешается. Правка: фикстура дополнена строкой `standard:
  {claude_model}` (`tests/test_stack_optional_tools.py:64`) — ни один
  ассерт и ни один сценарий не изменён, проверка не ослаблена. Формально
  это выход за требования SPEC; альтернативой была эскалация с красным CI
  на ветке, то есть заблокированный merge этой же задачи при тривиальной
  починке фикстуры в собственной зоне. Решение о допустимости —
  за ревьювером.
- **Строки `doctor`, перебирающие роли, теперь зависят от `roles.yaml`.**
  Класс «нечитаемая карта роняет строку» закрыт по всем найденным
  читателям перечня, не по одному (grep по `agent_roles` — восемь точек
  вызова, все разобраны, все в сабтестах
  `test_no_line_that_walks_the_roles_crashes`). Читатель, добавленный
  будущей задачей, обязан взять `agent_roles_or_empty` — про это сказано в
  докстринге обеих функций.
- **Роль без яруса или с ярусом, не описанным в локальном слое, теперь
  краснит `models-local` и `role-providers`.** Это не регрессия, а
  собственный предмет этих строк: ровно так пробел и обнаруживается до
  шага, а не отказом запуска. На пульте Оператора analyst ярус несёт
  (`roles.yaml`, `model_tier: standard`).

## Предложения системе

- **Фикстура локального слоя моделей в тестах должна покрывать ВСЕ
  agent-роли карты, а не только роль под тестом.** Класс:
  `tests/test_stack_optional_tools.py` (`LOCAL` с одним ярусом),
  `tests/test_models_doctor.py` (своя карта из трёх ролей — уцелела
  случайно). Перевод одной роли на другой ярус в `roles.yaml` красит такие
  файлы, и покраснение не связано с их предметом. Совпадает со строкой
  бэклога П3 «Планка test-authoring: фикстура теста должна быть достижима
  хотя бы одним путём» (коммит b611ec19) — подтверждение класса вторым
  примером.
- **Смена защищённого пути (`roles.yaml`) не проходит прогон затронутых
  тестов.** Коммит a6da0abe (analyst → `model_tier: standard`) оставил
  `tests/test_stack_optional_tools.py` красным в main; заметила это роль
  разработчика соседней задачи, а не гейт. Стоит завести разработчику/
  Оператору правило «правка `roles.yaml`/`models.yaml` — прогон
  `tests/test_stack*.py tests/test_models*.py tests/test_providers*.py`»
  либо CI-джоб на защищённых путях.
