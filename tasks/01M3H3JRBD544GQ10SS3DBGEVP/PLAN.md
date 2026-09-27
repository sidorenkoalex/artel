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

**Итерация 2: тесты, читающие боевой `roles.yaml`, развязаны с его полем
`provider:`** (REVIEW.md итерации 1, R1-F1). Смена источника перечня сделала
провайдер РЕАЛЬНОЙ роли предметом четырёх постоянных тестов, которые про
провайдеры ролей ничего не утверждают: `provider: codex` у analyst — та самая
правка, ради которой задача существует, — красил их. Развязка одним общим
помощником песочницы `roles_text_on_default_provider()`
(`tests/sandbox.py:186`): реальная карта с СНЯТЫМИ строками `provider:` —
роли, ярусы и слоты остаются настоящими, подменяется одно поле, из-за
которого тест уезжал со своего предмета. Сценарий «на пульте один
исполнитель» теперь задаёт сам тест; ни один ассерт не ослаблен, ни один
метод не удалён, не переименован и не выключен пропуском. Пятая точка того
же класса найдена прогоном, а не глазом
(`tests/test_stack_optional_tools.py::PreflightGateTest`, строка
`model-provider-cli`), и закрыта тем же помощником.

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
   12 методов): источник перечня, карта против `STATE_ROLE`,
   `STATE_ROLE` не тронут, строгий перечень против деградирующего, строки
   analyst на Codex, отсутствие строк Codex на пульте без Codex, склейка
   по одной строке на провайдера, «повышение роли в карте добавляет только
   её строки», именованный WARN, текст обеих новых ветвей пустого перечня
   (`models-local`, `foreign-provider-secrets`) и отсутствие падений восьми
   функций на нечитаемой карте.
4. **Развязка тестов с полем `provider:` боевой карты** (итерация 2, R1-F1):
   общий помощник `tests/sandbox.py::roles_text_on_default_provider` и его
   применение в `tests/test_providers.py` (два теста),
   `tests/test_doctor.py::DoctorCommandTest` (карта класса в `setUp` —
   «здоровый пульт» этого класса по построению на одном исполнителе),
   `tests/test_providers_codex.py` (тест «пульт без роли на Codex»),
   `tests/test_stack_optional_tools.py::_ManifestSandbox.use_tier` (поле
   `provider:` в карте сценария ставит только сам тест).
5. **Карта кодовой базы** — `python3 scripts/codebase_map.py` тем же
   коммитом.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (перечень), 3 (охват) |
| 3 | 1 (склейка не менялась), 3 |
| 4 | 1, 2 |
| 5 | 3, 4 |

| Критерий приёмки | Чем закрыт |
|---|---|
| AC-1 | `preflight.py::agent_roles`; `tests/test_doctor_agent_roles.py::AgentRolesListTest` (4 метода) |
| AC-2 | `tests/test_doctor_agent_roles.py::AnalystPreflightLinesTest` — оба провайдера |
| AC-3 | `…::test_role_independent_lines_stay_one_per_provider` (две роли на одном провайдере — счёт дублей не вырожден), `…::test_promoting_a_role_in_the_map_only_adds_lines_naming_it` (сравнение МУЛЬТИмножеств, `line_counts`); обе заявки мутации проверены снятием дедупликации — файл краснеет |
| AC-4 | `preflight.py::agent_roles_or_empty`; `…::UnreadableRolesMapTest` (4 метода, 8 функций сабтестами, текст обеих ветвей пустого перечня) |
| AC-5 | `tests/test_doctor_agent_roles.py`; шаг 4 (пять названных файлов зелены и при `provider: codex` у analyst); прогоны ниже |

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
ослаблен и не удалён. Правки в `tests/` — шесть файлов: новый
`tests/test_doctor_agent_roles.py`, общий помощник песочницы
(`tests/sandbox.py`, только добавление функции) и четыре файла, где карта
сценария теперь задаётся тестом, а не боевым `roles.yaml`
(`test_providers.py`, `test_doctor.py`, `test_providers_codex.py`,
`test_stack_optional_tools.py`). Во всех четырёх менялись докстринги и
подготовка карты; ассерты, сценарии и имена методов — нет. Единственные
ДОБАВЛЕННЫЕ ассерты — два контроля вырожденности
(`assertGreater(len(...), 1)`): без них «одна строка на провайдера»
выполнялось бы и без дедупликации.

**Прогоны (передний план, таймаут явный, `-p timeout -o timeout=300`).**
- `tests/test_doctor_agent_roles.py` — 12 passed, 14 subtests.
- Пять файлов AC-5 плюс затронутые соседи:
  `tests/test_doctor_agent_roles.py tests/test_doctor.py
  tests/test_models_doctor.py tests/test_providers.py
  tests/test_providers_codex.py tests/test_runner_model_preflight.py
  tests/test_stack_optional_tools.py tests/test_provider_scoped_step_env.py
  tests/test_models.py tests/test_model_tariffs.py` — 333 passed, 122
  subtests.
- `tests/test_invariants.py tests/test_stack.py tests/test_stack_ci.py
  tests/test_canary_sets.py tests/test_doctor_canary_sets.py
  tests/test_doctor_canary_pool.py tests/test_yaml_parsing.py
  tests/test_doctor_wave_breaker.py
  tests/test_doctor_fix_ignored_artifacts.py
  tests/test_doctor_artifact_branch_ci.py
  tests/test_doctor_artifact_branch_sync.py` — 224 passed, 256 subtests.
- `tests/test_canary.py tests/test_token_rate_divergence.py
  tests/test_artel_role_restricted_commands.py` — 124 passed, 4 subtests.
- **То же на карте с `provider: codex` у analyst** (временная правка
  `roles.yaml`, снятая `git checkout --`; дерево чистое): раньше — 4 failed
  (R1-F1) и пятый провал `PreflightGateTest`; после развязки —
  `tests/test_doctor_agent_roles.py tests/test_providers.py
  tests/test_doctor.py tests/test_providers_codex.py
  tests/test_models_doctor.py tests/test_runner_model_preflight.py
  tests/test_stack_optional_tools.py tests/test_runner_role_model.py
  tests/test_auto_cycle.py` — 335 passed, 135 subtests, и соседний набор
  (`test_provider_scoped_step_env`, `test_stack*`, `test_models*`,
  `test_canary*`, `test_invariants`, `test_doctor_*`) — 384 passed, 279
  subtests.
- Мутационные проверки заявок (каждая — снятие кода, прогон, возврат):
  снята дедупликация склейки (`if check not in bucket`) — 4 failed в
  `tests/test_doctor_agent_roles.py` (R1-F2 закрыт: до правки файл
  оставался зелёным); снята ветка пустого перечня в `check_models_local` и
  в `check_foreign_provider_secrets` — 2 failed (R1-F4/R1-F5).
- Приёмочная планка задачи — 13 passed, 10 subtests.
- Полный набор `tests/` в шаге не гонялся (skills/coding-standards.md); его
  гоняет CI на пуш ветки.

**Откат.** Revert одного merge-коммита: пять файлов `orchestrator/doctor/`,
шесть файлов `tests/`, регенерированная карта. Ни схемы БД, ни формата
артефактов, ни состояний FSM правка не касается.

## Риски

- **Правка фикстуры локального слоя в `tests/test_stack_optional_tools.py`
  формально выходит за требования SPEC.** Итерация 1 дописала в фикстуру
  `LOCAL` литеральную строку `standard: {claude_model}`: тест краснел на
  чистом дереве, потому что `roles.yaml` держал analyst на ярусе `standard`
  (a6da0abe), а фикстура описывала только `strong`. Оператор откатил ярус
  коммитом d910c523 — предком этой ветки, — и обоснование «иначе CI красный»
  перестало существовать: тест зелёный и без той строки (проверено
  прогоном). Итерация 2 заменила литерал на сборку секции `tiers:` ПО КАРТЕ
  (`_tiers_block`, `tests/test_stack_optional_tools.py:78`): ярус роли под
  тестом — в модель сценария, ярус каждой остальной agent-роли карты — в
  модель Claude каталога. Обоснование теперь безусловное — фикстура покрывает
  ярусы всех agent-ролей при любом их наборе в `roles.yaml`, — и от даты,
  яруса и отката не зависит. Ассерты и сценарии не менялись, проверка не
  ослаблена. Решение о допустимости выхода за SPEC — за ревьювером; выбор
  сделан в пользу зелёного CI ветки вместо эскалации ради одной строки
  фикстуры в собственной зоне задачи.
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
  (`roles.yaml`, `model_tier: strong` после отката d910c523).
- **Строка `foreign-provider-secrets` на нечитаемой карте стала жёлтой
  вместо зелёной** (итерация 2, R1-F4). `warn` на код выхода `doctor` не
  влияет, но в выводе появляется строка «сверка не проведена» там, где
  прежде стояла зелёная «секретов других провайдеров нет». Это и есть
  починка: зелёная строка утверждала проверенным то, что не проверялось.

## Предложения системе

- **Фикстура локального слоя моделей в тестах должна покрывать ВСЕ
  agent-роли карты, а не только роль под тестом.** В
  `tests/test_stack_optional_tools.py` это закрыто сборкой ярусов по карте
  (`_tiers_block`), но класс шире: `tests/test_models_doctor.py` держит свою
  карту из трёх ролей и уцелел случайно. Перевод одной роли на другой ярус в
  `roles.yaml` красит такие файлы, и покраснение не связано с их предметом.
  Совпадает со строкой бэклога П3 «Планка test-authoring: фикстура теста
  должна быть достижима хотя бы одним путём» (коммит b611ec19) —
  подтверждение класса вторым примером.
- **Смена защищённого пути (`roles.yaml`) не проходит прогон затронутых
  тестов.** Класс подтверждён трижды за одну задачу: a6da0abe (смена ЯРУСА
  analyst) оставил `tests/test_stack_optional_tools.py` красным в main —
  заметила это роль разработчика соседней задачи, а не гейт; смена
  ПРОВАЙДЕРА покрасила бы пять тестов (R1-F1, проверено прогоном); откат
  d910c523 обнулил обоснование правки фикстуры, и PLAN об этом не узнал
  (R1-F3). Стоит завести правило «правка `roles.yaml`/`models.yaml` —
  прогон `tests/test_stack*.py tests/test_models*.py
  tests/test_providers*.py tests/test_doctor*.py`» либо CI-джоб на
  защищённых путях.
- **Тест не должен зависеть от полей боевой карты, о которых он ничего не
  утверждает.** Общий помощник этой задачи
  (`tests/sandbox.py::roles_text_on_default_provider`) закрывает только поле
  `provider:`. Тот же класс остаётся у полей `model_tier:`/`skills:`/
  `token_slot:` и у самого СОСТАВА ролей: любой тест, перебирающий
  `doctor.agent_roles()` на боевой карте, краснеет от штатной правки
  Оператора. Дом решения — планка `skills/test-authoring.md`: «карта
  исполнителей и локальный слой моделей в тесте — фикстура сценария, если
  предмет теста не сама карта».
- **Предикат «agent-роль карты» скопирован в коде шесть раз.**
  `orchestrator/canary.py`, `orchestrator/models.py`, `orchestrator/stack.py`
  (дважды), `orchestrator/doctor/canary_pool.py` и теперь
  `orchestrator/doctor/preflight.py::agent_roles`. Естественный дом —
  `orchestrator/roles.py` (`roles.agent_roles()`), но SPEC этой задачи прямо
  запрещает его правку. Расширение перечня `executor` (в шапке `roles.yaml`
  уже названы `hybrid`/`external`) разведёт копии молча: `doctor` станет
  предполётить один набор ролей, `stack` — требовать CLI для другого.
  Наблюдение совпадает с «Предложениями системе» REVIEW.md итерации 1.
