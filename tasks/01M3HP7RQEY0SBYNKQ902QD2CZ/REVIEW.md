---
task: 01M3HP7RQEY0SBYNKQ902QD2CZ
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Тесты не зависят от полей боевой карты ролей — остаток класса

## Фаза A: гейт плана

1. **Покрытие требований.** Таблица PLAN называет шаг у каждого из шести
   требований SPEC; перечень требования 1 отдан отдельной секцией, второй
   список (требование 4) в ней есть. Пробелов покрытия нет.
2. **Размер шагов.** Монолит из трёх шагов в одном MR — то же решение, что
   принял SPEC («Оценка объёма и деление»), и граница между частями
   действительно прошла бы поперёк `tests/sandbox.py`. Возражений нет.
3. **Конфликт с конвенциями.** Подход (карта литералом вместо производной
   от боевого файла) совпадает с обоснованием требования 3 SPEC; зона —
   только `tests/`, защищённые пути не тронуты; карта кодовой базы
   регенерирована.
4. **Замечание по плану.** Раздел «Влияние на систему» утверждает, что
   ранее случайное покрытие согласованности боевой карты «становится явным
   и адресным». Фактически возвращена только часть его (поля ролей,
   которые в карте есть), а состав ролей и их `executor` не покрыты ни
   одним тестом — R1-F1 ниже. Это же расхождение делает раздел «Влияние на
   систему» не соответствующим диффу.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Перечень из 21 файла, у каждого пункта поля «до/после» и вердикт «предмет карты»; AC-1 планки зелёный |
| 2 | OK | Проверено не диффом, а прогоном: на копии дерева ветки, где в боевом `roles.yaml` у analyst стоят `provider: codex` и `model_tier: standard`, 13 файлов дают 269 passed (на базе — 1 упавший) |
| 3 | OK | Единственный сборщик `tests/sandbox.py:233 role_map_fixture`; `_roles_yaml_text`/`_tiers_text` стали его обёртками, второго источника карты в `tests/` нет (AC-6 зелёный) |
| 4 | OK по букве | `tests/test_yaml_parsing.py` и `LiveRolesMapConsistencyTest` адресуют боевой файл путём репозитория и краснеют от несогласованной правки (проверял ярусом вне перечня — краснеет). Неполнота возвращённого покрытия — не нарушение этого требования, а R1-F1 по принципу целостности |
| 5 | OK | `Ac7MapAcceptedTest` подменяет карту в самом тесте; заявленную PLAN цену класса воспроизвёл на базе: ровно 1 упавший тест, тот же, что назван в PLAN |
| 6 | OK | Тестовые методы только добавлены (новый файл — 6), ни один ассерт в диффе `tests/` не удалён и не изменён; AC-9 планки зелёный |

Планка задачи зелёная целиком: 9 критериев, 11 тестов.

## Замечания

- **major — tests/test_roles_map_fixture.py:253 (+ tests/sandbox.py:194)** —
  возвращённое покрытие боевой карты не проверяет ни СОСТАВ ролей, ни их
  `executor`: `LiveRolesMapConsistencyTest` перебирает только те роли,
  которые в карте УЖЕ есть (`live_agent_roles()` фильтрует по
  `executor == "agent"`), а единственная проверка состава —
  `assertTrue(agents)` на строке 274 («agent-ролей нет вовсе»). До этого MR
  пропажу роли ловил набор; теперь — никто. Проверено двумя парами
  прогонов на копиях дерева:
  - роль `analyst` переименована в боевом `roles.yaml` (`analyst` →
    `analitik`): на дереве ветки 8 файлов, включая
    `tests/test_analyst_role.py`, `tests/test_roles_map_fixture.py` и
    `tests/test_yaml_parsing.py`, дают **165 passed, rc 0**; на базе
    cad57d0d та же правка даёт `FAILED
    tests/test_analyst_role.py::RunAnalystTest::test_run_starts_analyst_when_tz_present`
    («роль 'analyst' не описана»);
  - у `analyst` в боевой карте `executor: none`: на ветке **92 passed,
    rc 0**; на базе — `FAILED
    tests/test_doctor_agent_roles.py::AgentRolesListTest::test_the_list_covers_every_executor_agent_role_of_the_map`
    с текстом «roles.yaml: analyst обязан быть agent-ролью — иначе сверять
    нечего». Этот ассерт (`tests/test_doctor_agent_roles.py:125`,
    файл в диффе не менялся) был поставлен именно про боевую карту и
    теперь молча проверяет фикстуру, где analyst — agent-роль по
    построению.

  Сценарий поломки: Оператор своим MR по защищённому пути переименовывает
  роль, снимает её с агента или удаляет из карты (та же крутилка, ради
  которой задача и делалась) — CI зелёный, главная ветка зелёная, отказ
  приходит Оператору только на первом шаге этой роли («роль не описана» /
  роль без строк предполёта). До MR это краснело названным тестом.
  Предложение: дополнить `LiveRolesMapConsistencyTest` сверкой боевой
  карты с составом, который запускает пульт, в одну сторону (⊆, чтобы
  ДОБАВЛЕННАЯ Оператором роль тест не красила): каждая роль из
  `FIXTURE_ROLES` (либо `set(config.STATE_ROLE.values()) | {"analyst"}` —
  `orchestrator/config.py:665` плюс особый случай `spec_writing` в
  `orchestrator/runner.py:129`) описана в боевом файле и с тем же
  `executor`, каким её знает фикстура. Одним ассертом верхнего уровня, как
  уже сделано для списка `problems`.

- **minor — tests/test_doctor.py:216, tests/test_providers.py:408,
  tests/test_providers.py:452, tests/test_providers_codex.py:674** — четыре
  подмены «карты сценария» стали пустыми: они кладут `SANDBOX_ROLES_TEXT`,
  то есть ровно тот текст, который `TmpRootTest.setUp` уже поставил в
  `config.ROLES` через `use_role_map()`. Проверено: на копии дерева со
  снятыми всеми четырьмя подменами `tests/test_doctor.py`,
  `tests/test_providers.py`, `tests/test_providers_codex.py` дают
  **214 passed**. Последствие — не красное, а читательское: докстринги
  («Карта исполнителей сценария — фикстура песочницы», «Контроль
  вырожденности») обещают, что сценарий чем-то управляет, а следующий
  автор будет править эти строки, думая, что они на что-то влияют.
  Предложение: снять их и оставить ссылку на общую фикстуру в докстринге
  либо объяснить в комментарии, зачем дубль сохранён.

- **minor — tests/sandbox.py:917 (`use_role_map`)** — карта сценария
  ставится патчем (`mock.patch.object` + `addCleanup`, восстанавливается),
  а СОДЕРЖИМОЕ локального слоя перезаписывается без восстановления
  (строка 929). Для классов с полным `PATCHED_ATTRS` это безобидно:
  `config.MODELS_LOCAL` у них свой, в tmp-корне. Но
  `tests/test_doctor.py:2445` (`_RoleHomeReferenceTmpRootTest`,
  `PATCHED_ATTRS = ("ROLE_HOME", "ROLE_CONFIG_DIR")`) MODELS_LOCAL не
  патчит — у него `config.MODELS_LOCAL` это ПРОЦЕССНЫЙ файл
  (`tests/sandbox.py:302`), и первый же будущий вызов
  `use_role_map(tiers=...)`/`allow_experimental=...` в таком классе
  переконфигурирует слой всем последующим тестам процесса, без отката.
  Сегодня текст совпадает с шаблоном, поэтому ловушка не выстрелила.
  Предложение: восстанавливать прежний текст слоя `addCleanup`'ом (или
  ставить слой через `self.patch(config, "MODELS_LOCAL", ...)` в свой
  каталог) — тогда «карта сценария не утекает в соседние тесты» из
  докстринга будет верно и про слой.

- **minor — tests/sandbox.py:182, tests/sandbox.py:269** —
  `FIXTURE_TIER_MODEL` завёл второй источник «модель яруса по умолчанию»
  рядом с шаблоном слоя: без параметров фикстура отдаёт
  `models.local_template_text()` (шаблон), а с `tiers=`/
  `allow_experimental=` — словарь на литерале `claude-opus-5`. Докстринг
  на строке 251 сам объясняет, почему второй крутилки быть не должно
  («разошлась бы с шаблоном на первой же правке») — и тут же её заводит.
  Сценарий: модель шаблона сменили, а прежнюю сняли из каталога
  `models.yaml` — все сценарии, зовущие фикстуру с `tiers=`
  (`_tiers_text`, `_ManifestSandbox`, `tests/test_stack_roles_tier_spread.py`),
  получают ярусы на модели, которой в каталоге нет, и краснеют строкой
  `model-<роль>` мимо своего предмета. Предложение: выводить значение из
  того же шаблона (`models.local_template_layer().tiers[FIXTURE_TIER]`) —
  именно так делает планка этой задачи,
  `acceptance_tests/_util.py::template_tier_model`, и по той же причине.

- **minor — tests/sandbox.py:88-91** — комментарий к `ALL_CONFIG_ATTRS`
  по-прежнему называет `ROLES` примером пути, который песочницы
  сознательно НЕ подменяют («от сценария к сценарию не меняется — тот же
  довод, что у `ROLES`/`TEMPLATES`), тогда как этот же модуль теперь
  уводит `config.ROLES` на весь процесс (строка 300) и подменяет его
  посценарно (`use_role_map`). Последствие: следующий автор песочницы
  прочитает, что `config.ROLES` — настоящий файл репозитория, и напишет
  сценарий, который на это опирается. Предложение: поправить довод в
  комментарии (или назвать там, почему `ROLES` подменяется не через
  `PATCHED_ATTRS`, а модульно плюс `use_role_map`).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_roles_map_fixture.py:253 (+ tests/sandbox.py:194) | возвращённое покрытие боевой карты не проверяет состав ролей и их `executor`; ассерт про боевую карту в tests/test_doctor_agent_roles.py:125 теперь проверяет фикстуру | переименование/удаление роли или `executor: none` в боевом `roles.yaml` проходит зелёным CI (проверено: 165 passed и 92 passed на ветке против названного FAILED на базе), отказ приходит Оператору на первом шаге роли | дополнить `LiveRolesMapConsistencyTest` односторонней сверкой: каждая роль, которую запускает пульт (`FIXTURE_ROLES` либо `config.STATE_ROLE` + analyst), описана в боевой карте с тем же `executor`; одним ассертом верхнего уровня |
| R1-F2 | fixed | tests/test_doctor.py:216; tests/test_providers.py:408; tests/test_providers.py:452; tests/test_providers_codex.py:674 | четыре подмены карты сценария кладут текст, уже стоящий в `config.ROLES` после `use_role_map()` — пустые операции (проверено снятием: 214 passed) | докстринги обещают управление картой, которого нет; следующий автор правит мёртвые строки | снять подмены (докстринг сослать на общую фикстуру) либо объяснить комментарием, зачем дубль сохранён |
| R1-F3 | fixed | tests/sandbox.py:917 | `use_role_map` восстанавливает `config.ROLES` патчем, но содержимое локального слоя перезаписывает без откатa | в классе, не патчящем `MODELS_LOCAL` (tests/test_doctor.py:2445), первый вызов с `tiers=` переконфигурирует процессный слой всем следующим тестам | восстанавливать прежний текст слоя `addCleanup`'ом либо патчить `config.MODELS_LOCAL` в свой каталог |
| R1-F4 | fixed | tests/sandbox.py:182; tests/sandbox.py:269 | `FIXTURE_TIER_MODEL` — второй источник «модели яруса» рядом с шаблоном слоя, против довода собственного докстринга (строка 251) | модель шаблона сменили и старую сняли из каталога — все сценарии с `tiers=` краснеют строкой `model-<роль>` мимо предмета | выводить значение из шаблона (`models.local_template_layer().tiers[FIXTURE_TIER]`), как делает `acceptance_tests/_util.py::template_tier_model` |
| R1-F5 | fixed | tests/sandbox.py:88-91 | комментарий `ALL_CONFIG_ATTRS` называет `ROLES` примером неподменяемого пути, хотя модуль уводит его на весь процесс и посценарно | автор следующей песочницы будет считать `config.ROLES` настоящим файлом репозитория | поправить довод в комментарии, назвав, где и почему `ROLES` подменяется |

## Разметка разработчика, итерация 1 -> 2

- **R1-F1 — fixed.** `LiveRolesMapConsistencyTest` получил второй метод
  `test_the_live_map_describes_every_role_the_pult_and_the_fixture_know`
  (`tests/test_roles_map_fixture.py`): `expected_executors()` собирает
  {роль -> ожидаемый `executor`} из двух источников — сначала
  `PULT_AGENT_ROLES` (`config.STATE_ROLE.values()` плюс `analyst`, особый
  случай `spec_writing` в `runner.step_role`) с требованием `agent`,
  затем `setdefault` остальными ролями `FIXTURE_ROLES` с их `executor`.
  Порядок именно такой, чтобы правка `FIXTURE_ROLES` на `executor: none`
  не обнулила заодно и проверку боевого файла. Сверка односторонняя (⊆):
  добавленная Оператором роль теста не красит. Один ассерт верхнего
  уровня по списку `problems`, как и у соседнего метода. Проверено
  поведением — правкой боевого `roles.yaml` на месте с восстановлением:
  `analyst` -> `analitik` (rc 1, FAILED названный), `analyst` с
  `executor: none` (rc 1), `verifier` с `executor: agent` (rc 1, красят
  оба метода класса); `git status -- roles.yaml` после прогона чистый.
- **R1-F2 — fixed.** Сняты все четыре пустые подмены: `setUp`
  `DoctorCommandTest` (`tests/test_doctor.py`) целиком, два вызова
  `use_roles_yaml(SANDBOX_ROLES_TEXT)` (`tests/test_providers.py`) и
  запись с `self.patch(config, "ROLES", ...)` в
  `tests/test_providers_codex.py`. Докстринги теперь называют источник
  карты (общая фикстура песочницы) и причину, по которой своей подмены
  нет. Неиспользуемые импорты `SANDBOX_ROLES_TEXT` убраны из трёх файлов.
  Ассерты не тронуты: те же файлы — 240 passed.
- **R1-F3 — fixed.** `use_role_map` (`tests/sandbox.py`) запоминает
  прежний текст `config.MODELS_LOCAL` (либо его отсутствие) и
  восстанавливает его `addCleanup(_restore_file, ...)`. Ловушку сторожит
  новый `SandboxLayerRestoreTest`: он гоняет `_LayerUnpatchedSandbox`
  (весь `ALL_CONFIG_ATTRS`, КРОМЕ `MODELS_LOCAL`), тот внутри зовёт
  `use_role_map(tiers=...)`, и тест сверяет текст процессного слоя до и
  после плюс контроль вырожденности «сценарий слой действительно
  двигал». Проверено снятием `addCleanup`: FAILED именно этот тест.
- **R1-F4 — fixed.** `FIXTURE_TIER_MODEL` считается
  `_fixture_tier_model()` из `models.local_template_layer().tiers[
  FIXTURE_TIER]` — тем же способом и по тому же доводу, что
  `acceptance_tests/_util.py::template_tier_model`; шаблон без этого
  яруса отказывает читаемым `RuntimeError` при импорте, а не молчит.
  Литерала имени модели в `tests/sandbox.py` не осталось.
- **R1-F5 — fixed.** Комментарий `ALL_CONFIG_ATTRS` больше не приводит
  `ROLES` доводом «от сценария к сценарию не меняется»; вместо этого он
  называет обратное — карта меняется, модуль уводит `config.ROLES` на
  фикстуру на весь процесс, сценарию её выдаёт `use_role_map`, — и
  объясняет, почему `ROLES` не в `PATCHED_ATTRS` (путь живёт в общем
  каталоге фикстуры процесса, а не в tmp-корне теста).

Побочное следствие R1-F2: `tests/test_doctor.py` перестал называть
`config.ROLES` и потому выбыл из МАШИННОГО перечня читателей боевой карты
(20 файлов вместо 21). Пункт о нём в PLAN.md оставлен как история
зависимости — перечень от этого шире машинного, а не уже, и AC-1 сверяет
только отсутствующие пункты.

## Вердикт

changes_requested. Механика задачи сделана и класс действительно закрыт —
это проверено прогоном на подменённой боевой карте, а не глазами. Чинить
до аппрува:

1. R1-F1 — вернуть в `LiveRolesMapConsistencyTest` проверку состава ролей
   и `executor` боевой карты; заодно привести раздел PLAN «Влияние на
   систему» в соответствие с тем, что покрытие возвращено полностью.
2. R1-F2 — R1-F5 — мелочь по коду и комментариям; отказ с обоснованием по
   любому из них приму, если обоснование выдерживает критику.

## Проверено исполнением

Полный набор `tests/` в шаге не гонял (решение Оператора 05.09): CI
коммита e55b1ce5 зелёный, 7 проверок. В шаге:

- `pytest tests/test_roles_map_fixture.py tests/test_runner_role_model.py
  tests/test_stack_optional_tools.py tests/test_stack_roles_tier_spread.py`
  — 32 passed, 12 subtests, 0.6 с.
- `pytest tests/test_doctor.py tests/test_providers.py
  tests/test_providers_codex.py tests/test_analyst_role.py
  tests/test_invariants.py tests/test_sandbox.py` — 319 passed,
  306 subtests, 146 с (инварианты 33/35/37 зелёные).
- Планка задачи целиком, тремя прогонами: AC-1/AC-2/AC-6/AC-8/AC-9 —
  7 passed, 29 subtests, 6 с; AC-5+AC-7 — 2 passed, 22 с; AC-3+AC-4 —
  2 passed, 181 с.
- **Класс закрыт (требование 2, AC-5).** Копия дерева ветки в `/tmp`, в
  боевом `roles.yaml` у роли analyst `provider: codex` и
  `model_tier: standard`; 13 файлов (`test_analyst_role`,
  `test_stack_optional_tools`, `test_stack_roles_tier_spread`,
  `test_roles_map_fixture`, `test_yaml_parsing`, `test_runner_role_model`,
  `test_runner_model_preflight`, `test_doctor_agent_roles`,
  `test_agent_prompt`, `test_stack`, `test_providers_codex`,
  `test_models_doctor`, `test_canary_sets`) — 269 passed, rc 0.
- **Цена класса до правки (AC-8) воспроизведена.** Та же карта на дереве
  базы cad57d0d (`git archive` в `/tmp`), те же файлы — `1 failed,
  262 passed`, упавший ровно тот, что назван в PLAN:
  `FAILED tests/test_analyst_role.py::RunAnalystTest::test_run_starts_analyst_when_tz_present`,
  отказ «модель роли не поддерживается CLI: claude-opus-5 требует codex».
- **Основание R1-F1.** Копия дерева ветки, роль `analyst` в боевой карте
  переименована в `analitik`: 165 passed, rc 0. То же на базе:
  `FAILED tests/test_analyst_role.py::RunAnalystTest::
  test_run_starts_analyst_when_tz_present` («роль 'analyst' не описана»).
  Копия ветки с `executor: none` у analyst: 92 passed, rc 0; на базе —
  `FAILED tests/test_doctor_agent_roles.py::AgentRolesListTest::
  test_the_list_covers_every_executor_agent_role_of_the_map`.
- **Основание R1-F2.** Копия дерева ветки со снятыми четырьмя подменами
  карты сценария (`tests/test_doctor.py:216`, `tests/test_providers.py:408`
  и `:452`, `tests/test_providers_codex.py:674`):
  `pytest tests/test_doctor.py tests/test_providers.py
  tests/test_providers_codex.py` — 214 passed, rc 0.
- **Неослабление и согласованность требования 4.** Дифф `tests/` прочитан
  построчно: удалённого или изменённого `assert`/сценария нет, удалены
  только помощники (`_roles_text_with_tiers`,
  `roles_text_on_default_provider`) и тело `_roles_yaml_text`; ссылок на
  снятые имена в `tests/`, `orchestrator/`, `scripts/` не осталось
  (grep). Краснота боевого теста карты проверена планкой (AC-2 гоняет
  карту с ярусом вне перечня, несуществующим скилом и
  незарегистрированным провайдером) — зелёная.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` —
  расхождение только в строке `built_at_sha`, то есть карта свежая;
  рабочее дерево восстановлено (`git checkout --`), `git status` чистый.
- Приёмочные тесты задачи не правились разработчиком:
  `git log --name-status artifact/... -- tasks/<id>/acceptance_tests/` —
  один коммит шага test_author, все файлы `A`.

## Предложения системе

- Сторож роли в `conftest.py` отказывает не только полному прогону, но и
  ЛЮБОМУ прогону через `pytest -n auto`: воркеры xdist не несут
  позиционных путей, и каждый из них выходит отказом «аргументов-путей нет
  вовсе» (проверено в шаге: 40 отказов, rc 5). Тем же `-n auto` набор
  гоняет CI за минуты, а роль вынуждена обходить 186 файлов
  последовательно — 666 с в замере этой задачи. Либо пропускать процессы
  воркеров (у xdist есть переменная окружения `PYTEST_XDIST_WORKER`), либо
  назвать это ограничение в тексте отказа, чтобы роль не тратила попытку.
- `tests/sandbox.py` копит «фикстуры процесса» (модульная подмена
  `shutil.which`, `config.MODELS_LOCAL`, теперь `config.ROLES`), и у них
  нет ни одного общего сторожа: `ALL_CONFIG_ATTRS` описывает только
  посценарные патчи, а процессные живут комментариями (и один из них уже
  разошёлся с кодом — R1-F5). Одна проверка «что песочница уводит на весь
  процесс» в `tests/test_sandbox.py` дешевле, чем следующий такой
  разошедшийся комментарий.
