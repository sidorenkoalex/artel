---
task: 01M3H3JRBD544GQ10SS3DBGEVP
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: doctor предполётит роль analyst и вход провайдера Codex

## Фаза A: гейт плана

| Проверка | Вердикт | Комментарий |
|---|---|---|
| Таблица покрытия полна | OK | Пять требований и пять AC имеют адрес; шаги 5-6 итерации 3 (подтяжка main, карта) дописаны в таблицу требования 5. |
| Шаги — единицы размера MR | OK | 6 шагов (узел, читатели, новые тесты, развязка с боевой картой, резолюция подтяжки, карта); монолит обоснован в SPEC. |
| Подход не конфликтует с конвенциями/архитектурой | OK | `config.STATE_ROLE` и `orchestrator/config.py` в диффе отсутствуют вовсе (`git diff origin/main...HEAD` — 13 файлов, `config.py` не среди них); защищённые пути (`roles.yaml`, `skills/`, `templates/`, `.github/`, `gates.yaml`) не тронуты; карта кодовой базы регенерирована на слитом дереве (ANSWER-2 п.4). |
| «Влияние на систему» = фактический дифф | OK | Заявлено «пять файлов `orchestrator/doctor/`, семь файлов `tests/`, карта» — дифф ровно такой: `__init__.py`, `isolation.py`, `model_catalog.py`, `model_tariffs.py`, `preflight.py` + `sandbox.py`, `test_doctor.py`, `test_doctor_agent_roles.py`, `test_providers.py`, `test_providers_codex.py`, `test_stack_optional_tools.py`, `test_stack_roles_tier_spread.py` + `docs/codebase-map.md`. Одна неточность без последствий: «единственные добавленные ассерты — два контроля вырожденности», но в ПРЕЖНИХ файлах добавлен один (`tests/test_providers.py:456`), второй стоит в новом файле ветки и заменил там `assertTrue` на `assertGreater`. |
| «Риски» соответствуют состоянию ветки | OK | R1-F3 итерации 1 закрыт: обоснования через откаченный ярус `standard` в ветке больше нет, `_tiers_block` в дереве отсутствует (греп), риск переписан под фактическое состояние «покрытие ярусов несёт главная ветка». |
| Путь отката описан | OK | Revert одного merge-коммита; ни схемы БД, ни формата артефактов, ни состояний FSM правка не касается. |
| Решения Оператора (ANSWER-1, ANSWER-2) учтены | OK | п.1 — `_tiers_block` снят, файл берёт `_tiers_text` главной ветки; п.2 — `roles_text_on_default_provider` применён и к `tests/test_stack_roles_tier_spread.py::_spread_roles_text`; п.3 — PLAN «Риски» переписан; п.4 — карта свежа; п.5 — 15 тестовых методов против 15 в `origin/main`, множества имён совпадают (сверено скриптом). `budget_usd: 25` из ANSWER-1 стоит в SPEC. |

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `preflight.py:531 agent_roles()` читает `roles.load()` с фильтром `executor == "agent"`; живой прогон на пульте: `['analyst','developer','reviewer','test_author']` против `['developer','reviewer','test_author']` у `sorted(set(config.STATE_ROLE.values()))`. `config.STATE_ROLE` не изменён. |
| 2 | OK | Живой прогон: строка `token` печатается по одной на каждую из четырёх ролей, включая analyst; на карте с `provider: codex` появляются `codex-chatgpt-auth` и `codex-role-home`, цепочка роли стоит и в `role-providers`, и в `models-local` (`AnalystPreflightLinesTest`, оба провайдера — зелёные). |
| 3 | OK, теперь и доказано тестами | Живой прогон: `cli-found`/`cli-version`/`role-home-reference` по одной штуке при четырёх ролях. Мутация «дедупликация склейки снята» теперь краснит файл — 4 failed (на итерации 1 весь файл оставался зелёным), см. R1-F2. |
| 4 | OK | Нечитаемая карта: `role-providers` — `warn` с путём файла и «не разобран»; восемь перебирающих роли функций отвечают значением (сабтесты `test_no_line_that_walks_the_roles_crashes`); `models-local` и `foreign-provider-secrets` теперь не утверждают проверенным непроверенное, и обе ветки закрыты ассертами. Все восемь точек вызова перечня разобраны: строгий `agent_roles()` остался только в `check_role_providers:622` и `model_provider_mismatches:311` — оба внутри `except RolesError` (греп `agent_roles` по `orchestrator/`). |
| 5 | OK | Новый файл `tests/test_doctor_agent_roles.py` (12 методов, 3 класса). Неослабление проверено по диффу: в `git diff origin/main...HEAD -- tests/` нет ни одной удалённой или изменённой строки `assert`/`def test_`; единственный добавленный ассерт в прежнем файле — контроль вырожденности. Мина из R1-F1 снята: на карте с `provider: codex` у analyst 16 файлов дают 502 passed. |

## Замечания

Blocker/major/minor по диффу этой итерации не найдено. Три наблюдения, не
являющиеся замечаниями к MR (предсуществующее, чужой коммит, механика
пакета), вынесены в «Предложения системе» — с адресами и доказательством,
почему это не дефект ветки.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_providers.py:408,452, tests/test_doctor.py:211-217, tests/test_providers_codex.py:673-676, tests/test_stack_optional_tools.py:113, tests/test_stack_roles_tier_spread.py:64-66 | расширенный перечень сделал провайдер реальной роли предметом постоянных тестов | `provider: codex` у analyst красил main (итерация 1: 4 failed) | **принято.** Помощник `tests/sandbox.py:189 roles_text_on_default_provider` применён в шести точках; класс закрыт целиком. Проверил сам: дописал `provider: codex` роли analyst в `roles.yaml` и прогнал 16 файлов (`test_doctor_agent_roles`, `test_doctor`, `test_providers`, `test_providers_codex`, `test_models_doctor`, `test_runner_model_preflight`, `test_stack_optional_tools`, `test_stack_roles_tier_spread`, `test_runner_role_model`, `test_stack`, `test_stack_ci`, `test_models`, `test_model_tariffs`, `test_provider_scoped_step_env`, `test_invariants`, `test_auto_cycle`) — 502 passed, 374 subtests вместо прежних 4 failed. Ассерты не ослаблены (дифф `tests/` без удалённых ассертов), добавлен один контроль вырожденности. Отдельно проверил седьмую точку того же КЛАССА вне причинности диффа — `tests/test_analyst_role.py:418`: краснеет и с прежним телом `agent_roles()`, то есть диффом не вносится (см. «Предложения системе») |
| R1-F2 | accepted | tests/test_doctor_agent_roles.py:293, tests/test_doctor_agent_roles.py:333-346 | заявки «Ловит мутацию» по AC-3 не исполнялись: одна роль на провайдера и сравнение множеств | снятая дедупликация проходила весь файл зелёным | **принято.** В `ROLES_TEMPLATE` третья agent-роль (reviewer), вырожденность сторожит `assertGreater(len(claude_roles), 1)`; `flat_lines()` → `line_counts()` (`Counter` пар). Мутацию исполнил сам: заменил `bucket = grouped.setdefault(...); if check not in bucket: bucket.append(check)` на безусловный `append` — **4 failed** (`test_promoting_a_role_in_the_map_only_adds_lines_naming_it` плюс три сабтеста `cli-found`/`cli-version`/`role-home-reference`), файл восстановлен. Заявка теперь исполняется |
| R1-F3 | accepted | tests/test_stack_optional_tools.py:64-72 (снято), PLAN.md «Риски» | обоснование правки фикстуры ссылалось на откаченный ярус `standard` | запись вводила в заблуждение, PLAN объяснял правку несуществующей альтернативой | **принято.** По ANSWER-2 п.1 собственный `_tiers_block` и его комментарий сняты (`grep -rn "_tiers_block" tests/ orchestrator/` — ни одного вхождения), файл берёт `_tiers_text` главной ветки, покрывающий ВСЕ ярусы `models.TIERS`; сценарий с одним ярусом (`test_unreadable_roles_map_…`) оставлен сознательно и это названо комментарием на строке 187. PLAN «Риски» переписан под фактическое состояние. Число методов файла не уменьшилось: 15 = 15, множества имён совпадают |
| R1-F4 | accepted | orchestrator/doctor/isolation.py:389-395 | зелёная строка «секретов других провайдеров нет» на пустом перечне | `doctor` утверждал проверенным то, чего не проверял | **принято.** Ранний выход по `by_provider` отдаёт `warn` «сверка не проведена…» и адресует `role-providers`; условие по `by_provider`, а не по перечню, покрывает и роль с незнакомым провайдером. Мутацию исполнил сам: снял блок — `test_foreign_secrets_line_does_not_claim_a_clean_environment` краснеет |
| R1-F5 | accepted | orchestrator/doctor/model_catalog.py:87-92 | ветка «перечень пуст» не покрыта ассертом | удаление ветки не краснило ничего | **принято.** `test_models_local_says_the_tiers_were_not_checked` сверяет статус, путь слоя, «ярусы не сверены» и адрес причины. Мутацию исполнил сам (снял блок вместе с блоком R1-F4) — **2 failed**, оба новых теста |
| R1-F6 | accepted | orchestrator/doctor/preflight.py:664-669 | докстринг звал компенсирующую строку красной | довод читался сильнее фактического сигнала | **принято.** Абзац говорит «жёлтая (`warn`, на код выхода `doctor` не влияет)»; сверил по коду: `orchestrator/doctor/cli.py:206` считает только `status == "fail"`, `warn` в код выхода не входит — формулировка теперь точна |

## Вердикт

`approved`. Все шесть записей реестра закрыты в `accepted` — каждая
проверена исполнением, а не чтением: два major итерации 1 сняты
доказуемо (мутация дедупликации теперь краснит 4 теста; карта с
`provider: codex` у analyst даёт 502 passed вместо 4 failed), три minor
закрыты ассертами и подтверждены снятием кода, один — сверкой статуса по
`cli.py:206`. Требования 1-5 реализованы; `config.STATE_ROLE`,
`orchestrator/config.py`, `roles.py`, `roles.yaml` и прочие защищённые
пути не тронуты; ни один существующий тест, гейт, лимит или guard не
ослаблен и не удалён; решения Оператора ANSWER-1 и ANSWER-2 (все пять
пунктов) выполнены.

Внимание Оператору перед правкой `roles.yaml` (не замечание к MR, дефект
предсуществующий и не в зоне причинности диффа):
`tests/test_analyst_role.py:418
RunAnalystTest::test_run_starts_analyst_when_tz_present` краснеет от
`provider: codex` у analyst — и краснел бы до этой ветки. Его фикстура
локального слоя (`models.ensure_local_template()` в `tests/sandbox.py:230`)
называет ярусам модели Claude, поэтому шаг отклоняется штатным отказом
`runner.py:241` «модель роли не поддерживается CLI: claude-opus-5 требует
codex ≥ 1.0.0». То есть перевод analyst на Codex требует ещё и яруса,
разрешающегося в модель Codex, — либо строки бэклога на эту фикстуру.

## Проверено исполнением

Все прогоны — в переднем плане, `-p timeout -o timeout=200|300`, таймаут
команды до 10 минут; полный набор `tests/` не гонялся (решение Оператора
05.09, CI коммита 315dec3d зелёный — 14 проверок). Дерево после всех
проверок чистое: `git status --short` — только неотслеживаемый
`tasks/01M3H3JRBD544GQ10SS3DBGEVP/`.

- **Приёмочная планка задачи:** `python3 -m pytest
  tasks/01M3H3JRBD544GQ10SS3DBGEVP/acceptance_tests/ -q` — **13 passed,
  10 subtests**. Пометок `# AC-n: manual|skip` в планке нет
  (`grep -rnE "AC-[0-9]+: *(manual|skip)"` — ни одного вхождения),
  автогейт acceptance задачи не выключен.
- **Затронутые модули, чистое дерево:** `tests/test_doctor_agent_roles.py
  tests/test_doctor.py tests/test_providers.py
  tests/test_providers_codex.py tests/test_models_doctor.py
  tests/test_runner_model_preflight.py tests/test_stack_optional_tools.py
  tests/test_stack_roles_tier_spread.py tests/test_runner_role_model.py` —
  **281 passed, 113 subtests**.
- **Соседи и инварианты, чистое дерево:** `tests/test_invariants.py
  tests/test_stack.py tests/test_stack_ci.py tests/test_models.py
  tests/test_model_tariffs.py tests/test_provider_scoped_step_env.py
  tests/test_codebase_map.py tests/test_canary_sets.py
  tests/test_doctor_canary_pool.py tests/test_yaml_parsing.py
  tests/test_agent_prompt.py tests/test_analyst_role.py` — **330 passed,
  277 subtests**.
- **R1-F1, карта с `provider: codex` у analyst** (временная правка
  `roles.yaml`, снятая `git checkout --`; после возврата
  `grep -c "provider:" roles.yaml` = 0): 16 файлов (перечень в реестре) —
  **502 passed, 374 subtests**, ни одного провала. Прежнее состояние того
  же прогона на итерации 1 — 4 failed.
- **R1-F2, мутация дедупликации** (снял `if check not in bucket` из
  `provider_preflight_checks`, вернул `git checkout --`):
  `tests/test_doctor_agent_roles.py` — **4 failed, 11 passed**
  (`test_promoting_a_role_in_the_map_only_adds_lines_naming_it` и три
  сабтеста `test_role_independent_lines_stay_one_per_provider`). До
  правки эта мутация давала 10 passed — заявка исполняется.
- **R1-F4 и R1-F5, мутации обеих ветвей пустого перечня** (снял блок
  `if not by_provider` из `isolation.py` и блок `if not listed_roles` из
  `model_catalog.py`, вернул `git checkout --`):
  `tests/test_doctor_agent_roles.py` — **2 failed**
  (`test_foreign_secrets_line_does_not_claim_a_clean_environment`,
  `test_models_local_says_the_tiers_were_not_checked`).
- **Живой вывод `doctor` на этой ветке** (`python3 -c` по установленному
  пакету): `doctor.agent_roles()` =
  `['analyst','developer','reviewer','test_author']` против
  `['developer','reviewer','test_author']` у `STATE_ROLE`; склейка —
  `{'cli-found': 1, 'cli-version': 1, 'role-home-reference': 1,
  'token': 4}`, то есть не зависящие от роли строки по одной на
  провайдера, строка секрета — по одной на роль, включая analyst. Это
  доказательство требований 1-3 на боевой карте.
- **R1-F6, сверка по коду:** `orchestrator/doctor/cli.py:206` —
  `failed = [c for c in checks if c.status == "fail"]`; `warn` в код
  выхода не входит, докстринг `preflight.py:666-668` теперь называет
  статус как есть.
- **ANSWER-2 п.1 и п.5:** `grep -rn "_tiers_block" tests/ orchestrator/` —
  ни одного вхождения (дубль снят); скрипт сравнения множеств имён
  `def test_*` между `git show origin/main:tests/test_stack_optional_tools.py`
  и файлом ветки — **15 против 15, потеряно []**, **дописано []**.
- **ANSWER-2 п.4 (карта кодовой базы):** `python3 scripts/codebase_map.py`
  + `git diff -- docs/codebase-map.md` — расхождений нет вовсе (даже в
  строке `built_at_sha`); файл восстановлен.
- **Неослабление `tests/`:** `git diff origin/main...HEAD -- tests/`,
  фильтр по удалённым строкам с `assert`/`self.fail`/`subTest`/`def test_`
  — пустой вывод; добавленных ассертов в прежних файлах ровно один
  (`tests/test_providers.py:456`, контроль вырожденности).
- **Атрибуция чужой правки:** в инкрементальном diff пакета фигурирует
  смена ассерта `{"HOME", "CODEX_HOME"}` → `{"HOME", "CODEX_HOME",
  "ZDOTDIR"}` (`tests/test_providers_codex.py`). `git log -S` показывает
  автора — f65e3213 задачи 01M3H3K73XBMJMD0EPXZX6HYY9, уже слитой в main;
  диффом собственных коммитов ветки (`git diff 3de0686b..HEAD`) этот файл
  меняется на 14 строк, не на 22. Ветка чужой ассерт не трогала.
- **Предсуществующая точка класса R1-F1:** под той же временной правкой
  `roles.yaml` прогнал `tests/test_agent_prompt.py
  tests/test_yaml_parsing.py tests/test_canary_sets.py
  tests/test_doctor_canary_sets.py tests/test_doctor_canary_pool.py
  tests/test_analyst_role.py tests/test_stack_parity_table.py
  tests/test_brief.py tests/test_venv.py` — **1 failed, 172 passed**
  (`tests/test_analyst_role.py::RunAnalystTest::test_run_starts_analyst_when_tz_present`).
  Проверил причинность: с тем же `roles.yaml` и ПРЕЖНИМ телом
  `agent_roles()` (`sorted(set(doctor.config.STATE_ROLE.values()))`) тест
  падает так же — **1 failed, 25 passed**. Значит диффом он не вносится;
  на чистом дереве зелёный (см. прогон соседей выше).

## Предложения системе

- **Инкрементальный diff ревью-пакета приписывает ветке правки, приехавшие
  подтяжкой main.** `orchestrator/review.py:530` строит диапазон «от sha
  предыдущего вердикта до HEAD» и фильтрует его по ПУТЯМ собственных
  коммитов, поэтому в пакете этой задачи изменённый ассерт чужой задачи
  (`tests/test_providers_codex.py`, ZDOTDIR, коммит f65e3213) читается как
  ослабление теста ревьюируемой ветки — то есть прямо как класс, который
  скил велит заворачивать блокером. Стоит либо строить diff по коммитам
  ветки (`git diff` от точки слияния), либо помечать в пакете строки,
  пришедшие подтяжкой. Ревьювер спасается только сверкой `git log -S`,
  которую ничто не подсказывает.
- **Класс «тест зависит от полей боевой карты» шире помощника этой
  задачи.** `roles_text_on_default_provider` закрывает поле `provider:` в
  шести точках, но `tests/test_analyst_role.py:418` краснеет от
  `provider: codex` у analyst через другой механизм: фикстура локального
  слоя песочницы (`tests/sandbox.py:230`, `models.ensure_local_template()`)
  называет всем ярусам модели Claude, а провайдер роли приходит из боевого
  `roles.yaml` — и `runner.py:241` отклоняет шаг «модель роли не
  поддерживается CLI». Третье подтверждение класса (ярус — a6da0abe,
  провайдер — R1-F1, модель яруса — здесь); дом решения — планка
  `skills/test-authoring.md` («карта исполнителей и локальный слой моделей
  в тесте — фикстура сценария») плюс правило прогона
  `tests/test_stack*.py tests/test_models*.py tests/test_providers*.py
  tests/test_doctor*.py tests/test_analyst_role.py` при правке
  `roles.yaml`/`models.yaml`, о котором просит и PLAN этой задачи.
- **Гейт реестра не различает severity, и minor-наблюдение стоит целой
  итерации.** `orchestrator/fsm_advance.py::review()` не пропускает
  `approved`, пока в реестре есть запись не в `accepted`, а статус
  `minor` в реестре не отличим от `major`. Поэтому у ревьювера ровно два
  выхода: завести minor и отправить задачу на ещё один прогон
  разработчика, либо не заводить его вовсе (как сделано здесь — minor
  уехали в эту секцию и в текст вердикта). Дом — либо severity-колонка
  реестра, которую гейт учитывает, либо явное разрешение статуса
  `wontfix`/`backlog` для minor в `skills/review-checklist.md`.
