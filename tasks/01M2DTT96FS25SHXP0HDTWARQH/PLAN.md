---
task: 01M2DTT96FS25SHXP0HDTWARQH
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Модель роли из roles.yaml — флаг --model в команде запуска и модель в журнале шага

## Подход

Реализация целиком в зоне (`orchestrator/runner.py`, `orchestrator/
roles.py`, `tests/`) и проходит весь залоченный приёмочный набор
(`tasks/01M2DTT96FS25SHXP0HDTWARQH/acceptance_tests/`, 12/12 зелёных).

1. `orchestrator/roles.py::model(role) -> str | None` — тем же приёмом,
   что `skills()`: `RolesError` на нечитаемом значении поля `model`
   (не строка, пустая строка), но, в отличие от `skills()`, отсутствие
   поля — не отказ, а `None` (AC-1/AC-2).

2. `orchestrator/runner.py`:
   - `_refuse_before_start` (не входит в залоченный AC-7 набор девяти
     имён `tasks/01M2CN3ZCSZ54TFJGTDCXTDHXD/acceptance_tests/
     test_ac7_locked_public_surface.py` — там зафиксировано только
     существование и сигнатуры девяти конкретных функций) резолвит
     `roles.model(role)` ОДИН раз на шаг (до цикла попыток): нечитаемое
     значение — `sys.exit` тем же приёмом, что и skills выше; поле не
     задано — РОВНО одна запись журнала «модель роли не задана — дефолт
     CLI» (требование 4, AC-4) действием `"model WARNING"`, шаг не
     останавливается.
   - `run_agent_once` — сигнатура ЗАЛОЧЕНА AC-7 (`tasks/
     01M2CN3ZCSZ54TFJGTDCXTDHXD`, 101 патч по имени модуля в 38 файлах
     тестов) и не вправе принять новый параметр. Модель резолвится ЕЩЁ
     РАЗ внутри тела функции (`_resolved_role_model`, защитный повтор —
     `RolesError` там уже недостижим, шаг остановился бы раньше) и
     передаётся в ПРИВАТНЫЕ фазы `_prepare_step`/`_spawn_and_wait`/
     `_account_step` (не в AC-7 наборе — их сигнатуры свободны), а не
     резолвится заново предупреждением: warning уже журналирован ровно
     один раз, до попыток.
   - `_spawn_and_wait` — argv `role_cmd()` (сигнатура тоже залочена
     AC-7: `[]`, без параметров) дополняется `["--model", model_id]`
     СНАРУЖИ, доводком к списку, а не внутри неё — конец списка не
     переставляет существующие пять флагов (AC-3).
   - `_prepare_step` — запись «agent run started» несёт `model=
     <идентификатор|дефолт CLI>` (AC-5).
   - `_account_step` — `orchestrator/spend.py` (журналирует «agent cost
     KNOWN»/«agent cost PARTIAL»/«agent cost UNKNOWN»/«agent cost LOST»/
     «agent cost ESTIMATED») ВНЕ зоны этой задачи (SPEC zones), править
     нельзя. `model=` в «agent cost KNOWN»/«agent cost PARTIAL» без
     правки `spend.py` — параметр `numbered`, который `spend.py`
     дословно вставляет в начало своей записи, дополняется `model=`
     ТОЛЬКО когда условие для журналирования именно этой ветки
     (совпадает с условием внутри `spend.py`, прочитано отсюда вызовом
     её же публичной `partial_cost_usd`, не копией арифметики курса) уже
     верно ЗДЕСЬ, до вызова — иначе «agent cost UNKNOWN»/«agent cost
     LOST»/«agent cost ESTIMATED» получили бы `model=` по ошибке
     (требование 6 называет только KNOWN и PARTIAL). Существующий
     `tests/test_step_cost.py::test_missing_cost_is_warned_but_step_
     survives` (точная сверка текста «agent cost UNKNOWN») остаётся
     зелёным без правки ассерта — довод, что выбор ветки здесь совпадает
     с `spend.py`, а не любое место, где вставлен `numbered`.

3. `roles.yaml` — защищённый путь (правит только Оператор), приложен
   unified diff `tasks/01M2DTT96FS25SHXP0HDTWARQH/roles-yaml.patch`:
   `model: claude-opus-5` для `developer`/`reviewer`, `model:
   claude-sonnet-5` для `analyst`/`test_author` (AC-9). `git apply
   --check tasks/01M2DTT96FS25SHXP0HDTWARQH/roles-yaml.patch` на чистом
   дереве — пройден этим шагом; дополнительно патч применён во временную
   рабочую копию и `roles.model()` на четырёх ролях дал ожидаемые
   значения, копия отброшена (`git checkout -- roles.yaml`), сам файл
   этой веткой не тронут.

4. `orchestrator/canary.py` не правится (требование 6, AC-7): канарейка
   зовёт тот же `runner.cmd_run`/`role_cmd`, уже покрытый
   `test_ac4_no_model_flag_when_the_field_is_absent`/`test_ac4_missing_
   model_warns_exactly_once_without_failing_the_step` — роль без поля
   `model` не останавливает и не проваливает шаг.

5. Юнит-тесты в `tests/` (не только приёмочная планка — AC-8): новый
   класс `RolesModelTest` в `tests/test_yaml_parsing.py` рядом с
   существующим `RolesTest` для `skills()`, и новый файл `tests/
   test_runner_role_model.py` (по образцу `tests/test_step_cost.py::
   CmdRunCostTest`) — постоянная копия покрытия приёмочной планки,
   переживающая её будущую чистку.

## Шаги

1. `orchestrator/roles.py::model()` — требования 1-2, AC-1/AC-2.
   **Готово.**
2. `orchestrator/runner.py` — резолв модели в `_refuse_before_start`
   (отказ/предупреждение), флаг `--model` в `_spawn_and_wait`, `model=`
   в «agent run started» (`_prepare_step`) и в «agent cost KNOWN»/
   «agent cost PARTIAL» (`_account_step`, без правки `spend.py`) —
   требования 3-6, AC-3/AC-4/AC-5/AC-6. **Готово.**
3. Unified diff `roles.yaml` приложением к PLAN.md, `git apply --check`
   пройден — требование 1, AC-9. **Готово.**
4. Юнит-тесты `tests/test_yaml_parsing.py::RolesModelTest`, `tests/
   test_runner_role_model.py` — AC-8. **Готово.**
5. Регенерация `docs/codebase-map.md` (`python3 scripts/codebase_map.py`,
   conventions-core — правка `.py` в `orchestrator/`/`tests/`) —
   **Готово.**
6. Прогон приёмочной планки задачи (12/12) и затронутых модулей
   `tests/` (см. «Влияние на систему») — требование 3 (принцип
   целостности). **Готово.**

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 3 |
| 2 | 1 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 (не правка canary.py) |

## Влияние на систему

`orchestrator/spend.py` — вне зоны SPEC (`orchestrator/runner.py,
orchestrator/roles.py, tests/`), не тронут. AC-6 закрыт БЕЗ правки
`spend.py`: `_account_step` решает, дополнять ли параметр `numbered`
меткой `model=`, ЗАРАНЕЕ повторяя условие, при котором сама `spend.py`
выберет ветку KNOWN/PARTIAL (вызовом её публичной `partial_cost_usd`,
не копией расчёта курса) — риск расхождения условий описан в «Риски»
ниже.

`role_cmd()`/`run_agent_once()` — сигнатуры залочены посторонним (для
этой задачи) приёмочным тестом `tasks/01M2CN3ZCSZ54TFJGTDCXTDHXD/
acceptance_tests/test_ac7_locked_public_surface.py` (101 патч по имени
модуля в 38 файлах тестов, привязанных именно к этим сигнатурам): этот
файл НЕ собирается общим прогоном CI (`pytest tests -n auto` смотрит
только `tests/`, не `tasks/**/acceptance_tests/`) и не входит в
приёмочный гейт ЭТОЙ задачи (`acceptance.run` материализует и гоняет
только `tasks/01M2DTT96FS25SHXP0HDTWARQH/acceptance_tests/`), но
сигнатуры не тронуты явно, из уважения к зафиксированному в нём
инварианту — флаг `--model` добавлен ДОВОДКОМ к результату `role_cmd()`
снаружи, модель резолвится заново внутри тела `run_agent_once` без
нового параметра.

Существующие тесты `orchestrator/runner.py` (AC-8, «101 патч по именам
модуля») не меняют ассертов — патчатся только девять залоченных имён,
их сигнатуры не тронуты. Приватные фазы `_prepare_step`/`_spawn_and_
wait`/`_account_step`/`_refuse_before_start` получили новый параметр
каждая — эти имена НЕ патчатся ни одним существующим тестом `tests/`
(проверено grep, см. «Риски» — единственные упоминания вне этой задачи
живут в дормant-акцептансе `01M2CN3ZCSZ54TFJGTDCXTDHXD`, который
проверяет только `hasattr`, не сигнатуру).

`status`/`report` не изменены (требование 6, AC-7) — вне зон SPEC, дифф
их не касается (проверено `git status`/диффом разработчика).

Откат: тривиален — ревертом `orchestrator/roles.py`/`orchestrator/
runner.py`/`tests/test_yaml_parsing.py`/`tests/test_runner_role_model.
py` (и регенерацией карты). `roles.yaml` этой веткой не менялся вовсе
(диф — только приложение), откатывать нечего.

## Риски

- `_account_step` дублирует ВЕТВЛЕНИЕ (не арифметику) `spend.charge_
  step`/`charge_missing_result` для решения «эта попытка заведёт именно
  KNOWN/PARTIAL» — если условие внутри `spend.py` изменится будущей
  задачей без синхронной правки этого дубля, `model=` может перестать
  появляться в KNOWN/PARTIAL либо ошибочно появиться в UNKNOWN/LOST/
  ESTIMATED. Дубль сведён к минимуму (сама денежная арифметика вызывает
  `spend.partial_cost_usd` напрямую, не копируется), но не устранён
  полностью — правка `spend.py` для приёма выделенного параметра `model`
  была бы чище, но требует расширения зоны за пределы SPEC.
- Патч `roles.yaml` — только предложение Оператору; до его применения
  все роли остаются на дефолте CLI (нынешнее поведение), предупреждение
  «модель роли не задана» появится в журнале каждого шага agent-ролей.

## Предложения системе

- SPEC поставил `orchestrator/spend.py` вне зоны задачи, требующей
  правки его журнальных записей («agent cost KNOWN»/«agent cost
  PARTIAL» несут `model=`) — решение нашлось (вставка через уже
  существующий параметр `numbered`), но потребовало дублировать
  ВЕТВЛЕНИЕ чужого модуля извне зоны. Класс «SPEC зона не включает
  файл, чьё наблюдаемое поведение требование всё равно называет явно»
  стоит проверять на этапе SPEC: либо файл в zones, либо анализ зоны
  заранее подтверждает, что решение без его правки существует.
