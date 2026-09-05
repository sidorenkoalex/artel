---
task: 01M1R8B3ZKXQT0Z0G6QQQDV906
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: auto пробует переход по готовым артефактам до шага роли; PLAN status escalate уводит в escalated

## Замечание к самому ревью-пакету (не к коду)

Инкрементальный diff пакета (от sha предыдущего вердикта c9b3ded0 до
HEAD) состоит ЦЕЛИКОМ из «подтяжки main» (коммит `3d4fdca3`) — задачи
`01M1PNBSHR2PMFECMP7C204MF1` (группа процессов/сторож зависших
прогонов), уже смерженной в main и не имеющей отношения к SPEC этой
задачи. Ни `orchestrator/auto.py`, ни `orchestrator/fsm_advance.py`
(единственная зона этой задачи) в этом диапазоне не менялись — сами
правки R1-F1/R1-F2/R1-F3 лежат РАНЬШЕ, в коммите `c9b3ded0`, который и
есть sha предыдущего вердикта. Также в пакете SPEC.md/PLAN.md были
показаны как «не найдены» — путь поиска указывал на
`/Users/al.sidorenko/projects/artel/tasks/...`, а не на фактический
worktree этой сессии; на диске оба файла присутствуют и полны.

Ревью ниже проведено по факту: код и тесты — из `orchestrator/auto.py`,
`orchestrator/fsm_advance.py`, `tests/test_auto_cycle.py` и
`tasks/01M1R8B3ZKXQT0Z0G6QQQDV906/acceptance_tests/` на HEAD ветки
(идентичны состоянию после `c9b3ded0` — в этих файлах подтяжка ничего
не поменяла, проверено `git diff c9b3ded0..HEAD -- orchestrator/auto.py
orchestrator/fsm_advance.py` — пусто); собственные коммиты задачи —
`7cd4abfa` (реализация) и `c9b3ded0` (правки R1-F1/F2/F3) — рассмотрены
по отдельности как обычные (не merge) коммиты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (advance до run для каждой агентной роли) | OK | `orchestrator/auto.py:291-320`; AC-1 зелёный. |
| 2 (переход по предварительному advance → шаг роли не нужен, журнал) | OK | `orchestrator/auto.py:309-320`; AC-2, AC-5 зелёные. |
| 3 (отказ «артефакт не готов» → роль запускается) | OK | `orchestrator/auto.py:405-411`; AC-3 зелёный. |
| 4 (журналируемый отказ другого класса/guard → роль не запускается, старые стоп-краны) | OK | `orchestrator/auto.py:297-306, 364-403`; AC-4, AC-7 зелёные. |
| 5 (журнал пропуска шага одной строкой) | OK | `orchestrator/auto.py:314-316`; текст и формат совпадают с AC-2. |
| 6 (PLAN.md status: escalate → escalated) | OK | `orchestrator/fsm_advance.py:677-697`; AC-6 зелёный (оба сценария). |
| 7 (пороги AUTO_MAX_STEPS/AUTO_STALL_STEPS_LIMIT/стоп-кран не меняются) | OK | Закрыто R1-F1: `steps` теперь инкрементируется точечно (строки 301, 372, 388, 402, 408) — только там, где реально звался `runner.cmd_run` либо цикл останавливается/пропускает шаг журналируемым отказом; голый переход (строка 309-320) `steps` не трогает. Регресс-тест `AutoStepLimitTest::test_transitions_by_advance_alone_do_not_consume_the_step_limit` — зелёный. |

## Замечания

(пусто)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/auto.py:267-408 | Реордеринг advance/run удваивал расход `AUTO_MAX_STEPS` на единицу реальной агентной работы | Цикл `auto` при боевом лимите упирался бы в «лимит шагов исчерпан» примерно вдвое чаще | Подтверждено: `steps += 1` убран из безусловной точки входа и расставлен точечно (строки 301, 372, 388, 402, 408) — только на путях с реальным `cmd_run` либо остановкой/пропуском по отказу требования 4. Прогнан `tests.test_auto_cycle` целиком — 40 тестов, зелёные, включая новый `AutoStepLimitTest::test_transitions_by_advance_alone_do_not_consume_the_step_limit` (лимит 1, два подряд свободных перехода `in_dev -> review -> verifying`). |
| R1-F2 | accepted | orchestrator/auto.py:1-5 (докстринг) → docs/codebase-map.md:148 | Первая строка докстринга обрывалась посреди предложения | Сгенерированная карта показывала незаконченное «Назначение» | Подтверждено: первая строка докстринга — законченное предложение («Цикл `auto`: advance до шага роли, затем — если роль ещё не закончила — run.»). Перегенерировал карту (`python3 scripts/codebase_map.py`) — diff с закоммиченной только в строке `built_at_sha` (карта успела ещё раз перегенерироваться при последующей подтяжке main, содержимое статьи `orchestrator/auto.py` не изменилось и совпадает с закоммиченным); откатил тестовую перегенерацию. |
| R1-F3 | accepted | orchestrator/fsm_advance.py:668-670, 767-768 (нумерация на момент замечания; сейчас 667-670) | Двойное чтение PLAN.md с диска + мёртвый тернарник | Лишний I/O, усложнённое чтение функции | Подтверждено: `else`-ветка теперь тоже строит `plan_meta` через `yamlmini.frontmatter(plan_text) or {}` (строка 670), без повторного чтения диска; мёртвый тернарник `full_plan_text` убран, `_zones_gate_refuses` зовётся прямо с `plan_text` (строка 767). |

## Вердикт

approved — все 7 требований и все 8 AC реализованы верно, реестр
замечаний итерации 1 закрыт целиком (R1-F1/F2/F3 → accepted), новых
находок при независимой проверке кода, тестов и трассировки нет.

## Проверено исполнением

- `git diff c9b3ded0..HEAD -- orchestrator/auto.py orchestrator/fsm_advance.py` — пусто: единственная зона задачи не менялась после фикс-коммита итерации 1, инкрементальный diff пакета целиком относится к посторонней подтяжке main.
- `python3 -m unittest tests.test_auto_cycle tests.test_invariants tests.test_advance_guard tests.test_id_format_guard tests.test_fsm_draft_mr_reentry tests.test_review_registry_gate tests.test_split_assessment_merge_gate tests.test_acceptance_tests_flow tests.test_git_fixation tests.test_fsm_autogate tests.test_answer_gate tests.test_multitarget_invariants tests.test_answer tests.test_analyst_role tests.test_stall_alerts tests.test_capacity_gate tests.test_branch_freshness_gate tests.test_review_freshness` — 324 теста, все зелёные (тот же набор, что перечислен в PLAN «Влияние на систему», плюс новые тесты, добавленные последующей подтяжкой main в некоторые из этих же модулей).
- `python3 -m unittest tests.test_auto_cycle` отдельно — 40 тестов, зелёные (совпадает с числом, заявленным в PLAN.md).
- `python3 -m unittest discover -s tasks/01M1R8B3ZKXQT0Z0G6QQQDV906/acceptance_tests` — 15 тестов (AC-1..AC-7), все зелёные; AC-8 — легитимный `skip` (регрессия того же поведения уже покрыта CI-джобом `tests/test_auto_cycle.py` на каждый коммит, тот же класс «ci-covered», что уже применён в T045).
- `python3 scripts/codebase_map.py` на HEAD ветки — diff с закоммиченной картой только в строке `built_at_sha`, содержимое статьи `orchestrator/auto.py` подтверждает законченное предложение в «Назначение» (R1-F2). Откатил тестовую перегенерацию (`git checkout -- docs/codebase-map.md`), рабочее дерево чистое (кроме нематериализуемого в код `tasks/01M1R8B3ZKXQT0Z0G6QQQDV906/`).
- Вручную прочитал `orchestrator/auto.py::_cmd_auto` (строки 222-467) и `orchestrator/fsm_advance.py::in_dev`/`review` (строки 118-288, 650-773) целиком, сверил все точки инкремента `steps` и ветку `status == "escalate"` с требованиями 1-7 и с параллельной веткой `review()`; расхождений не нашёл.
- `git log -S zone_lock -- orchestrator/auto.py` и `git log -S is_canary -- orchestrator/auto.py` — обе строки внесены чужими задачами (`01M1P9QAG65GVF69YJEV0V18D9`, `01M1NEEWH5K1XPFRDGRMPYSBXJ`) через подтяжку main, не этой задачей; зона этой задачи (`orchestrator/auto.py`, `orchestrator/fsm_advance.py`, заявлена в SPEC frontmatter) не нарушена собственными коммитами `7cd4abfa`/`c9b3ded0`.

## Предложения системе

- Генератор ревью-пакета показал SPEC.md/PLAN.md как «не найдены» (искал по абсолютному пути `/Users/al.sidorenko/projects/artel/tasks/...` вместо фактического пути worktree сессии) и построил инкрементальный diff, целиком состоящий из посторонней подтяжки main (собственные коммиты задачи лежат раньше sha предыдущего вердикта). Ни то, ни другое не дефект кода, но оба вместе делают пакет практически бесполезным для этой конкретной итерации без ручной перепроверки по git-истории — тот же класс, что уже описан в review-checklist («Инкрементальный diff пакета — пустой не значит «без изменений»»), но здесь стоило бы также чинить путь генератора к worktree.
