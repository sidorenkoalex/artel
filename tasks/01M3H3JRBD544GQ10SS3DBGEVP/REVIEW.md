---
task: 01M3H3JRBD544GQ10SS3DBGEVP
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: doctor предполётит роль analyst и вход провайдера Codex

## Фаза A: гейт плана

| Проверка | Вердикт | Комментарий |
|---|---|---|
| Таблица покрытия полна | OK | Все пять требований и все пять AC имеют адрес; сверил построчно с SPEC. |
| Шаги — единицы размера MR | OK | 4 шага (узел, читатели, тесты, карта); монолит обоснован в SPEC, деление здесь дало бы либо изменение маршрута без охвата, либо тесты без кода. |
| Подход не конфликтует с конвенциями/архитектурой | OK | `config.STATE_ROLE` и его читатели не тронуты; защищённые пути (`roles.yaml`, `skills/`, `.github/`) в диффе отсутствуют; карта кодовой базы регенерирована. |
| «Влияние на систему» = фактический дифф | OK | Заявлено «пять файлов `orchestrator/doctor/`, новый файл тестов, одна фикстура, карта» — дифф ровно такой. |
| «Риски» соответствуют состоянию ветки | **не OK** | Обоснование правки фикстуры (`analyst → model_tier: standard`) устарело: Оператор откатил ярус коммитом d910c523, который лежит в основании диффа. См. R1-F3. |
| Путь откката описан | OK | Revert одного merge-коммита; ни схемы БД, ни формата артефактов, ни FSM правка не касается. |

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `preflight.py:531 agent_roles()` читает `roles.load()` с фильтром `executor == "agent"`; живой прогон: `['analyst','developer','reviewer','test_author']` против прежних `['developer','reviewer','test_author']`. `config.STATE_ROLE` в диффе отсутствует. |
| 2 | OK | Живой прогон на пульте: `token` для analyst появилась, цепочка `analyst → …` стоит и в `role-providers`, и в `models-local`; на карте с `provider: codex` появляются `codex-chatgpt-auth` и `codex-role-home` (прогон `AnalystPreflightLinesTest`). |
| 3 | OK по коду, **не доказано тестами** | Склейка по имени строки не менялась; живой прогон даёт `cli-found`/`cli-version`/`role-home-reference` по одной штуке при четырёх ролях. Но оба теста, которыми PLAN закрывает AC-3, мутацию «дедупликация снята» не ловят — R1-F2. |
| 4 | OK | Нечитаемая карта: `role-providers` = warn с именем файла и «не разобран»; `models-local`, склейка, тариф, сверка провайдеров, чужие секреты — все отвечают значением (прогон вживую, ни одного трейсбека). Чтение перечня внутри `except RolesError` в `check_role_providers:622` и `model_provider_mismatches:311` — верно. |
| 5 | **не OK** | Новый файл добавлен, ни один существующий ассерт не изменён и не удалён (дифф `tests/` — только фикстура `LOCAL`). Но перечень стал шире, и четыре постоянных теста (три из них названы в AC-5) краснеют, как только analyst встаёт на Codex — R1-F1. |

## Замечания

- **major — tests/test_providers.py:429, tests/test_providers.py:395,
  tests/test_doctor.py:219, tests/test_providers_codex.py:648 — перевод
  analyst на Codex, ради которого задача и существует, красит четыре
  постоянных теста.** Расширенный перечень сделал провайдер РЕАЛЬНОЙ роли
  из `roles.yaml` предметом тестов, которые про провайдеры ролей ничего не
  утверждают. Проверил обе стороны: с `provider: codex` у analyst в
  `roles.yaml` и нынешним `agent_roles()` — `4 failed` (перечисленные
  выше); с той же `roles.yaml` и прежним телом `agent_roles()`
  (`sorted(set(config.STATE_ROLE.values()))`) — `15 passed`. То есть
  краснота вносится именно этим диффом. Сценарий поломки конкретный:
  SPEC «Контекст» говорит «роль analyst переведена на провайдер Codex»,
  Оператор возвращает `provider: codex` в `roles.yaml` (защищённый путь,
  правится отдельным MR без прогона тестов — это же наблюдение стоит в
  PLAN «Предложения системе»), и main краснеет — ровно повтор инцидента
  a6da0abe, записанного в копилку двумя коммитами раньше основания этой
  ветки. Механика каждого экземпляра класса:
  `test_provider_preflight_is_collected_without_duplicates` сверяет
  `len(grouped["token"]) == len(doctor.agent_roles())` — роль на Codex
  даёт `codex-chatgpt-auth`, а не `token`;
  `test_role_providers_line_names_every_agent_role` ждёт `→ claude` у
  каждой роли перечня; `test_a_pult_without_a_codex_role_…:664` ждёт
  `"codex" not in {name_for_role(r) for r in doctor.agent_roles()}`;
  `test_healthy_repo_prints_ok_and_does_not_exit` — зелёного прогона
  `doctor` без строк Codex. Пятый, уже пролеченный экземпляр того же
  класса — фикстура `tests/test_stack_optional_tools.py:70`. Предложение:
  развязать эти сценарии с боевой картой (своя карта исполнителей в
  песочнице либо ожидание, параметризованное `providers.name_for_role(role)`),
  ассертов не ослабляя; если это признано выходом за SPEC — эскалировать
  Оператору решением «чинить сейчас или строкой бэклога», но не оставлять
  мину молча.

- **major — tests/test_doctor_agent_roles.py:260 и
  tests/test_doctor_agent_roles.py:290 — заявки «Ловит мутацию» по AC-3 не
  исполняются.** Обе называют мутацию «дедупликация склейки снята, строки
  печатаются по разу на роль», и обе её пропускают. Проверил: убрал
  `if check not in bucket` из `provider_preflight_checks` — весь новый файл
  `10 passed, 14 subtests passed`. Причины разные и обе структурные.
  (1) `:260` — фикстура `ROLES_TEMPLATE:48` описывает ровно две
  agent-роли, analyst и developer, и тест разводит их по РАЗНЫМ
  провайдерам: на каждом провайдере по одной роли, дедуплицировать нечего,
  `len(...) == 1` выполняется и без дедупликации. Страховка
  `assertTrue(claude_roles, …):277` требует ≥1 роли, тогда как сценарию
  нужно ≥2 на одном провайдере. (2) `:290` — `flat_lines():315` отдаёт
  МНОЖЕСТВО `{(имя, текст)}`, а множество размножение строк не видит по
  построению; докстринг же обещает поймать «прежние строки размножились».
  Последствие ровно то, от которого файл и заведён своим модульным
  докстрингом («планка уходит вместе с каталогом задачи, а свойство обязано
  её пережить»): свойство AC-3 переживает планку только в
  `tests/test_providers.py:429` — том самом тесте, который R1-F1 ставит под
  удар. Предложение: в `:260` дать одному провайдеру не меньше двух
  agent-ролей и считать строки там; в `:290` либо сравнивать
  последовательности/`Counter` вместо множеств, либо сузить заявку до того,
  что тест действительно ловит.

- **minor — tests/test_stack_optional_tools.py:64-72 (+ PLAN «Риски») —
  обоснование правки фикстуры устарело до сдачи MR.** Комментарий
  утверждает настоящим временем «С 27.09 (roles.yaml: analyst →
  `model_tier: standard`) слой с одним `strong` перестал покрывать карту», а
  Оператор вернул analyst на `strong` коммитом d910c523 — предком этой
  ветки, втянутым подтяжкой eccb1140. Проверил: убрал строку `standard:
  {claude_model}` — `15 passed, 4 subtests passed`, тест зелёный и без неё.
  Последствие: следующий читатель грепает `roles.yaml`, находит `strong` и
  не может понять, несущая строка или мёртвая; PLAN «Риски» при этом
  объясняет правку альтернативой «эскалация с красным CI», которой на
  сданной ветке уже нет. Предложение: оставить строку, но переписать
  обоснование как безусловную полноту фикстуры (ярус любой agent-роли
  карты) со ссылкой на откат d910c523, и поправить PLAN «Риски»; либо
  снять строку.

- **minor — orchestrator/doctor/isolation.py:374-410 — класс «перечень
  пуст» пролечен в одном читателе и не пролечен в соседнем.**
  `check_models_local` получил честную ветку «ярусы не сверены»
  (`model_catalog.py:87-92`), а `check_foreign_provider_secrets` на пустом
  перечне доходит до финального `ok` «секретов других провайдеров в
  собранном окружении шагов ролей нет» — проверил вживую на нечитаемой
  карте. Это положительное утверждение о том, что не проверялось, и оно
  спорит с собственным докстрингом функции (`isolation.py:360-364`: «`skip`
  читался бы как норма, а `fail` называл бы утечкой то, чего не
  проверяли»). Сценарий: Оператор ломает `roles.yaml`, `doctor` печатает
  зелёную строку об отсутствии утечки чужих секретов, ничего не сверив.
  Предложение: ранний выход с тем же приёмом, что у `models-local`
  («сверка не проведена — agent-ролей в карте нет либо она не прочитана»).

- **minor — orchestrator/doctor/model_catalog.py:87-92 — новая ветка не
  покрыта ни одним ассертом.** Грепнул `ярусы не сверены` и
  `agent-ролей в карте` по `tests/` и по приёмочной планке — ни одного
  вхождения; `test_no_line_that_walks_the_roles_crashes` проверяет только
  `assertIsNotNone`. Мутация «убрать `if not listed_roles:` целиком»
  оставляет всё зелёным: остаток кода отдаёт тот же статус `ok` с пустым
  списком цепочек. Сценарий: ветку правят или удаляют при следующем
  рефакторинге, и `models-local` возвращается к строке «локальный слой
  моделей <путь>: » с висящим двоеточием, о которой никто не узнает.
  Предложение: один ассерт на статус и текст этой ветки в
  `UnreadableRolesMapTest`.

- **minor — orchestrator/doctor/preflight.py:664-667 — докстринг называет
  компенсирующую строку красной, а она жёлтая.** Новый абзац
  `provider_preflight_checks` обосновывает пустую склейку тем, что «причину
  называет та же КРАСНАЯ строка выше», но на нечитаемой карте
  `check_role_providers` отдаёт `warn` (проверено вживую и тестом
  `:test_role_providers_keeps_its_named_refusal`), а `warn` не влияет на код
  выхода `doctor` (`cli.py:206-210`). Последствие: довод, которым правка
  оправдана, при чтении выглядит сильнее, чем есть — следующая задача
  сошлётся на него как на «блокирующий сигнал рядом». Предложение: назвать
  статус как есть («жёлтая строка `role-providers`»), утверждение о
  деградации от этого не страдает.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_providers.py:429, tests/test_providers.py:395, tests/test_doctor.py:219, tests/test_providers_codex.py:648 | расширенный перечень сделал провайдер реальной роли предметом четырёх постоянных тестов | `provider: codex` у analyst (цель задачи) красит main: проверено — 4 failed на новом теле `agent_roles()`, 15 passed на прежнем | развязать сценарии с боевой картой (своя карта в песочнице либо ожидание через `providers.name_for_role`) без ослабления ассертов, либо эскалировать решение Оператору → **сделано:** общий помощник `tests/sandbox.py::roles_text_on_default_provider` (реальная карта со снятыми строками `provider:`) применён во всех четырёх местах плюс в пятом, найденном прогоном (`tests/test_stack_optional_tools.py::_ManifestSandbox.use_tier`, строка `model-provider-cli`); ассерты и имена методов не менялись, добавлены два контроля вырожденности. Проверено прогоном на карте с `provider: codex` у analyst: 335 passed вместо прежних 4 failed |
| R1-F2 | fixed | tests/test_doctor_agent_roles.py:260, tests/test_doctor_agent_roles.py:290 | заявки «Ловит мутацию» по AC-3 не исполняются: по одной роли на провайдера в фикстуре и сравнение множеств | снятие дедупликации склейки проходит весь новый файл зелёным (проверено); AC-3 переживает приёмочную планку только за счёт tests/test_providers.py:429 | дать одному провайдеру ≥2 agent-роли и считать строки там; сравнение множеств заменить на последовательности/`Counter` либо сузить заявку → **сделано:** в `ROLES_TEMPLATE` добавлена третья agent-роль (reviewer) — на Claude теперь две роли, а вырожденность сторожит `assertGreater(len(claude_roles), 1)`; `flat_lines()` заменён на `line_counts()` (`Counter` пар «имя строки, текст»), сравнение мультимножеств. Заявка проверена мутацией: снятие `if check not in bucket` даёт 4 failed в файле (было 10 passed) |
| R1-F3 | fixed | tests/test_stack_optional_tools.py:64-72, PLAN.md «Риски» | обоснование правки фикстуры ссылается на ярус `standard` у analyst, откаченный Оператором в d910c523 — предке этой ветки | тест зелёный и без строки (проверено); запись вводит в заблуждение, PLAN объясняет правку несуществующей альтернативой | переписать обоснование как безусловную полноту фикстуры со ссылкой на d910c523 и поправить PLAN, либо снять строку → **сделано:** литеральная строка `standard:` снята, секция `tiers:` собирается ПО КАРТЕ (`_tiers_block`) — ярус роли под тестом в модель сценария, ярус каждой остальной agent-роли в модель Claude каталога; обоснование в комментарии стало безусловным, откат d910c523 назван; PLAN «Риски» переписан |
| R1-F4 | fixed | orchestrator/doctor/isolation.py:374-410 | на пустом перечне строка чужих секретов зеленеет утверждением «секретов нет», ничего не сверив | нечитаемая `roles.yaml` даёт зелёную строку об отсутствии утечки вопреки собственному докстрингу функции (isolation.py:360-364) | ранний выход с текстом «сверка не проведена», тем же приёмом, что `models-local` → **сделано:** ранний выход `if not by_provider` отдаёт `warn` «сверка не проведена — ни одной agent-роли с зарегистрированным провайдером: карта пуста, не прочитана либо называет незнакомые имена (см. строку role-providers)»; условие взято по `by_provider`, поэтому покрывает и роль с незнакомым провайдером. Ветка закрыта ассертом `test_foreign_secrets_line_does_not_claim_a_clean_environment` — её снятие краснит тест (проверено) |
| R1-F5 | fixed | orchestrator/doctor/model_catalog.py:87-92 | новая ветка «перечень пуст» не покрыта ассертом ни в tests/, ни в приёмочной планке | удаление ветки не краснит ничего; `models-local` вернётся к строке с висящим двоеточием незамеченно | ассерт на статус и текст ветки в `UnreadableRolesMapTest` → **сделано:** `test_models_local_says_the_tiers_were_not_checked` сверяет статус `ok`, путь слоя, «ярусы не сверены» и адрес причины (`role-providers`); снятие ветки краснит тест (проверено мутацией) |
| R1-F6 | fixed | orchestrator/doctor/preflight.py:664-667 | докстринг зовёт компенсирующую строку `role-providers` красной, а на нечитаемой карте она `warn` и на код выхода не влияет | довод, оправдывающий правку, читается сильнее фактического сигнала; следующая задача сошлётся на него как на блокирующий | назвать статус как есть → **сделано:** абзац говорит «жёлтая (`warn`, на код выхода `doctor` не влияет), но именованная, с путём файла и словом о разборе» |

## Вердикт

`changes_requested` — два major. Требования 1, 2, 4 реализованы и
подтверждены исполнением, деградация разведена на два перечня верно,
`config.STATE_ROLE` и защищённые пути не тронуты, ни один существующий
ассерт не ослаблен. Исправить:

1. **R1-F1** — снять мину под переводом analyst на Codex (четыре
   перечисленных теста), либо эскалировать решение Оператору. Класс
   чинить целиком: пятый экземпляр — фикстура
   `tests/test_stack_optional_tools.py:70`, уже пролеченная.
2. **R1-F2** — довести до дела обе заявки «Ловит мутацию» по AC-3.
3. R1-F3…R1-F6 — minor, чинятся дешево и в одном коммите с major.

## Проверено исполнением

Все прогоны — в переднем плане, `timeout` до 10 минут, полный набор
`tests/` не гонялся (решение Оператора 05.09; CI коммита eccb1140 зелёный).

- Приёмочная планка задачи: `python3 -m pytest
  tasks/01M3H3JRBD544GQ10SS3DBGEVP/acceptance_tests/ -q` — **13 passed,
  10 subtests**. Пометок `# AC-n: manual|skip` в планке нет (греп).
- Тесты задачи и пять файлов AC-5: `python3 -m pytest
  tests/test_doctor_agent_roles.py tests/test_doctor.py
  tests/test_models_doctor.py tests/test_providers.py
  tests/test_providers_codex.py tests/test_runner_model_preflight.py
  tests/test_stack_optional_tools.py -q` — **268 passed, 107 subtests**.
- Соседние модули: `python3 -m pytest tests/test_invariants.py
  tests/test_stack.py tests/test_stack_optional_tools.py
  tests/test_stack_ci.py tests/test_models.py tests/test_model_tariffs.py
  tests/test_canary_sets.py tests/test_doctor_canary_sets.py
  tests/test_doctor_canary_pool.py tests/test_provider_scoped_step_env.py
  -q` — **251 passed, 237 subtests**; `tests/test_runner_role_model.py
  tests/test_auto_cycle.py tests/test_yaml_parsing.py
  tests/test_doctor_wave_breaker.py
  tests/test_doctor_fix_ignored_artifacts.py -q` — **105 passed, 66
  subtests**.
- Живой вывод строк `doctor` на этой ветке (скрипт через `python3 -c`):
  `agent_roles()` = `['analyst','developer','reviewer','test_author']`
  против `['developer','reviewer','test_author']` у `STATE_ROLE`; склейка
  предполёта — `cli-found`/`cli-version`/`role-home-reference` по ОДНОЙ
  строке при четырёх ролях, `token` по одной на роль, включая analyst;
  строк Codex нет. Это доказательство требований 2-3 на боевой карте.
- Требование 4 вживую: `config.ROLES` уведён на файл
  `roles:\n  - developer\n` — `role-providers` = `warn` с именем файла и
  «не разобран»; `models-local` отвечает значением; склейка предполёта
  `{}`; `model_provider_mismatches` `[]`; `model-provider-cli` `ok`;
  `foreign-secrets` `ok`; `tariff-freshness` `skip`. Ни одного трейсбека.
- **R1-F1, проверка обеими сторонами.** Временно дописал `provider: codex`
  роли analyst в `roles.yaml`: `python3 -m pytest tests/test_providers.py
  tests/test_doctor.py tests/test_models_doctor.py
  tests/test_providers_codex.py tests/test_doctor_agent_roles.py -q` —
  **4 failed, 234 passed** (`test_provider_preflight_is_collected_without_duplicates`,
  `test_role_providers_line_names_every_agent_role`,
  `test_healthy_repo_prints_ok_and_does_not_exit`,
  `test_a_pult_without_a_codex_role_gets_neither_the_line_nor_the_call`).
  С той же `roles.yaml` и прежним телом `agent_roles()`
  (`sorted(set(config.STATE_ROLE.values()))`): `python3 -m pytest
  tests/test_providers.py::DoctorProviderLinesTest
  tests/test_doctor.py::DoctorCommandTest
  tests/test_providers_codex.py::PreflightTest -q` — **15 passed, 22
  subtests**. Оба файла восстановлены `git checkout --`, дерево чистое
  (`git status --short` — только неотслеживаемый `tasks/<id>/`).
- **R1-F2, мутационная проверка.** Убрал `if check not in bucket` из
  `provider_preflight_checks`: `tests/test_doctor_agent_roles.py` —
  **10 passed, 14 subtests** (мутация не поймана); приёмочная планка при
  той же мутации — **4 failed** (`test_ac3_…` и
  `tests/test_providers.py::…without_duplicates` через
  `test_ac5_named_suites_stay_green`), то есть свойство держит планка и
  один пре-существующий постоянный тест, а не новые.
- **R1-F3, проверка.** Убрал строку `standard: {claude_model}` из
  фикстуры `LOCAL`: `tests/test_stack_optional_tools.py` — **15 passed,
  4 subtests**. Плюс `git show d910c523 -- roles.yaml` и `git merge-base
  e69fe26f d910c523` (= 0f0e5523): правка делалась поверх карты с
  `standard`, а подтяжка eccb1140 втянула откат Оператора.
- **R1-F5, проверка.** `grep -rn "ярусы не сверены|agent-ролей в карте|
  listed_roles" tests tasks/<id>` — ни одного вхождения в тестах.
- Карта кодовой базы: `python3 scripts/codebase_map.py` + `git diff --
  docs/codebase-map.md` — расхождение только в строке `built_at_sha`
  (замечанием не является, T053/T072); файл восстановлен.
- Дифф `tests/` на неослабление: единственная правка существующего файла —
  фикстура `LOCAL` и комментарий над ней; ни одного изменённого или
  удалённого `assert`/сценария. Приёмочные тесты задачи в диффе
  отсутствуют (каталог `tasks/<id>/` не отслеживается кодовой ветвью).

## Предложения системе

- **Предикат «agent-роль карты» скопирован в коде шесть раз.**
  `orchestrator/canary.py:360`, `orchestrator/models.py:754`,
  `orchestrator/stack.py:191`, `orchestrator/stack.py:529`,
  `orchestrator/doctor/canary_pool.py:128` и теперь
  `orchestrator/doctor/preflight.py:558` (плюс копии в `tests/sandbox.py:173`
  и `tests/test_doctor_agent_roles.py:89`). Естественный дом — сам
  `orchestrator/roles.py` (`roles.agent_roles()`), но SPEC этой задачи
  прямо запрещает его правку, так что класс остаётся. Расширение перечня
  `executor` (в шапке `roles.yaml` уже перечислены `hybrid`/`external`)
  разведёт копии молча: `doctor` будет предполётить один набор ролей,
  `stack` — требовать CLI для другого.
- **Тест, читающий боевой `roles.yaml`, — скрытая зависимость от
  защищённого пути.** Второе подтверждение класса за одну задачу:
  `tests/test_stack_optional_tools.py` покраснел от смены ЯРУСА
  (a6da0abe), четыре теста из R1-F1 покраснеют от смены ПРОВАЙДЕРА. Правка
  `roles.yaml`/`models.yaml` идёт отдельным MR Оператора и прогона
  затронутых тестов не имеет — CI-джоб на защищённых путях (или правило
  «правка `roles.yaml` → прогон `tests/test_stack*.py tests/test_models*.py
  tests/test_providers*.py tests/test_doctor*.py`») закрыл бы оба
  экземпляра. Совпадает со строкой PLAN «Предложения системе» этой же
  задачи и со строкой бэклога П3.
- **Скил ревью не требует проверять «Риски»/«Влияние на систему» PLAN на
  свежесть после подтяжки main.** R1-F3 — именно этот класс: подтяжка
  (`eccb1140`) обнулила обоснование риска, а PLAN остался прежним, и
  формально гейт плана он проходит. Стоит дописать в `review-checklist`
  Фазу A строкой: раздел PLAN, ссылающийся на состояние main, перечитывать
  против ГОЛОВЫ ветки, а не против даты написания.
