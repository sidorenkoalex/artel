---
task: 01M4VC31NFCS6JZ0VE8HNJ7FYM
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/models.py, orchestrator/canary.py, orchestrator/store.py, tests/
budget_usd: 45
---

# SPEC: Чистый прогон канарейки учитывает эскалацию аудитора SPEC по той же ловушке

## Контекст
`orchestrator/models.py::unclean_reason` на шаблоне с ожидаемой эскалацией
признаёт прогон чистым только при `escalations <= 1` (решение Оператора
02.10.2026, SPEC 01M3YCHVVEK14SK8GT4R0H7M2C, требование 8) — правило
принято до роли `spec_auditor` (ADR-0022, 11.10.2026). Строка
`canary_runs` (`orchestrator/store.py::insert_canary_run`) хранит только
общее число эскалаций (`len(metrics["escalations"])` из
`orchestrator/canary.py::_escalation_notes`), без роли. В прогоне
20261013T185506Z (набор `c-codex-all`, шаблон `canary-status-sort`) одну
намеренную ловушку шаблона верно увидели и analyst (эскалация из
`spec_writing`), и аудитор SPEC (эскалация из `spec_audit`) — прогон
засчитан не чистым. Это наказывает верную работу аудитора и мешает
допуску любой пары через `admit` (ADR-0019 п.5) на шаблонах с ловушкой
(`canary-status-sort`, `canary-budget-percent-ambiguous`).

## Требования
1. Строка `canary_runs` хранит перечень ролей, эскалировавших в прогоне,
   по порядку эскалаций в журнале задачи клона (одна позиция на каждый
   переход `state -> escalated`; длина перечня равна числу эскалаций
   прогона).
   - Где вычисляется: перечень вычисляет пульт из поля `steps` результата
     процесса клона (журнал задачи клона по порядку, поля `action`/
     `detail`; `orchestrator/canary_drive.py::build_result`), не код
     клона. Набор обязательных полей результата
     (`orchestrator/canary.py::_DRIVE_METRIC_FIELDS`) и проверка его
     разборчивости не меняются: результат клона, ведомого кодом коммита
     до этой задачи, принимается как сейчас, и строка его прогона всё
     равно получает перечень ролей.
   - Интерфейс: публичная функция `orchestrator/canary.py::escalation_roles(steps)`
     принимает список шагов журнала (словари с ключом `action`, порядок —
     порядок журнала) и возвращает список строк — роли эскалаций по
     порядку; пустой список, если эскалаций нет.
   - Состояние-источник эскалации — состояние, в которое задача вошла
     последним переходом `state -> X` журнала, предшествующим этому
     `state -> escalated`. Если такого перехода нет, состояние-источник —
     начальное состояние задачи `spec_writing`: задача заводится сразу в
     нём, и первый вход журналом `state -> spec_writing` не пишется
     (`orchestrator/catalog.py:667`, `:670`; докстринг
     `orchestrator/auto.py:400`). Записи прочих действий журнала (не
     `state -> …`: `created`, `набор моделей задачи`, `agent run started`,
     `agent run finished` и любые другие), стоящие между переходом и
     `state -> escalated` или перед первым переходом, на
     состояние-источник не влияют — в журнале клона между ними всегда есть
     записи шага роли.
   - Эскалация самой роли и эскалация пульта. Ролью состояния-источника
     засчитывается только эскалация самой роли по её артефакту (батч
     `QUESTIONS.md` аналитика; `status: escalate` в `SPEC-AUDIT.md`
     аудитора; так же пометка `AC-n: escalate` автора тестов,
     `status: escalate` в `PLAN.md` и `REVIEW.md`). Признак — запись
     журнала, следующая сразу за этим `state -> escalated`, имеет действие,
     равное `orchestrator/fsm.py::ARTIFACT_ESCALATION_ROLE_STEP_MARKER`:
     пульт пишет её сразу после перехода только при эскалации по
     артефакту роли (`orchestrator/fsm_advance.py::_mark_artifact_escalation`).
     Сравнивается только действие записи, не текст детали. Эскалация без
     такой записи сразу за ней — эскалация пульта из того же состояния
     (исчерпанный бюджет `orchestrator/budget.py:300`, инцидент фиксации
     `orchestrator/fixation.py:248`, инцидент целостности
     `orchestrator/runner.py:447`, лимит ревью и прочие), её роль —
     `unknown`, из какого бы состояния она ни шла, в том числе из
     `spec_writing` и `spec_audit`.
   - Роль по состоянию-источнику (для эскалации самой роли): `spec_writing` — `analyst`, прочие —
     роль этого состояния по `orchestrator/config.py::STATE_ROLE`
     (`spec_audit` — `spec_auditor`, `tests_writing` — `test_author`,
     `in_dev` — `developer`, `review` — `reviewer`). Текст детали перехода
     для определения роли не разбирается. Состояние-источник вне этого
     сопоставления (например `verifying`, `merge_gate`) — роль `unknown`
     (литерал строки ровно `unknown`).
   - Хранение: колонка `escalation_roles` таблицы `canary_runs` — роли
     через запятую без пробелов в порядке эскалаций (`analyst,spec_auditor`);
     пустая строка — эскалаций не было; `NULL` — данных о ролях нет
     (строки до этой задачи). `store.insert_canary_run` принимает
     именованный параметр `escalation_roles` (список строк либо `None`,
     по умолчанию `None` — запись `NULL`).
   - Строки прогонов без результата клона (`_report_drive_failure` —
     исход `drive_failed`; оборванный сигналом прогон в `cmd_canary`)
     пишутся без данных о ролях (`NULL`), как сейчас без метрик.
2. Критерий чистоты `unclean_reason` для строки с данными о ролях на
   шаблоне с ожидаемой эскалацией (`expected_escalation_met(row)`
   истинно) допускает не больше одной эскалации `analyst` и не больше
   одной `spec_auditor`; хотя бы одна эскалация обязана быть (как
   сейчас). Эскалация любой другой роли или роли `unknown`, вторая
   эскалация той же роли — прогон не чистый; причина содержит подстроку
   `эскалаций роли <роль>: <число>` (например `эскалаций роли developer: 1`,
   `эскалаций роли analyst: 2`). Если нарушителей несколько, причина
   называет хотя бы первого по порядку перечня.
3. На шаблоне без ожидаемой эскалации (`expected_escalation_met(row)`
   ложно) правило не меняется: любая эскалация, включая эскалацию
   `spec_auditor`, делает прогон не чистым.
4. Строки `canary_runs` без данных о ролях (записанные до этой задачи)
   разбираются по нынешнему правилу: выполненная ожидаемая эскалация
   покрывает ровно одну эскалацию по общему числу `escalations`. Задним
   числом прогоны не перекрашиваются. «Без данных о ролях» — значение
   `escalation_roles` равно `NULL` (`None`) либо в строке нет ключа
   `escalation_roles` вовсе (словарь-строка без этого ключа, как у
   помощника `canary_row` в `tests/test_model_sets.py`): отсутствие ключа
   равнозначно `NULL` и читается по нынешнему правилу, без исключения.
5. Сводка `admit` (`models.pair_admission`) в строке не чистого прогона
   называет причину по новому правилу (требование 2). Прочие числа
   допуска ADR-0019 п.5 (три чистых, два шаблона, чистый на среднем
   классе) и прочие условия чистоты (вердикт, итерации ревью, отказ
   автогейта) не меняются.
6. Тесты в `tests/` покрывают: прогон с ловушкой — `analyst` +
   `spec_auditor` по одной — чистый; `analyst` + `developer` — не чистый;
   две эскалации `analyst` — не чистый; одна эскалация `spec_auditor` без
   ловушки — не чистый; строка без данных о ролях с двумя эскалациями при
   выполненной ожидаемой — не чистая, как раньше; роль определяется по
   последнему переходу до `escalated` при записях шага роли между ними;
   эскалация пульта (бюджет исчерпан) из `spec_writing` и из `spec_audit`
   — роль `unknown`, прогон не чистый.

## Критерии приёмки

Ниже «маркер роли» — запись журнала с действием
`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER`, стоящая сразу за
`state -> escalated` (требование 1).

AC-1. `canary.escalation_roles` на журнале как у реального клона, с
записями шагов роли между переходами — `created`,
`набор моделей задачи`, `agent run started`, `agent run finished`,
`state -> escalated` (без предшествующего `state -> spec_writing`),
маркер роли, `state -> spec_writing`, `agent run started`,
`agent run finished`, `state -> spec_audit`, `agent run started`,
`agent run finished`, `state -> escalated`, маркер роли — возвращает
`["analyst", "spec_auditor"]` (вторая эскалация — `spec_auditor`, хотя
непосредственно перед ней стоит не переход, а `agent run finished`).
Строка `canary_runs`, записанная прогоном `_run_one_task`, в котором
подменён только процесс клона (`_drive_in_clone` либо разбор его файла
`_read_drive_result` отдаёт результат с таким `steps`), несёт в колонке
`escalation_roles` значение `analyst,spec_auditor` и `escalations = 2`.
Где внутри пульта вычисляется перечень (до или внутри
`_record_canary_run`), критерий не проверяет: подмена глубже результата
процесса клона в его тесте не делается.

AC-2. Роль эскалации самой роли берётся из последнего перехода
`state -> X` до `escalated`, не из текста детали и не из непосредственно
предыдущей записи: в каждом случае ниже между `state -> X` и
`state -> escalated` стоят записи `agent run started` и
`agent run finished`, а сразу за `state -> escalated` — маркер роли.
`state -> escalated` после `state -> spec_audit` с деталью
«analyst: батч вопросов по ТЗ» даёт `spec_auditor`; после
`state -> in_dev` — `developer`; после `state -> tests_writing` —
`test_author`; после `state -> review` — `reviewer`; после
`state -> spec_writing` — `analyst`.

AC-3. `state -> escalated` с маркером роли, перед которым в журнале нет
ни одного перехода `state -> X`, но есть записи `created`,
`набор моделей задачи`, `agent run started`, `agent run finished`, даёт
`analyst` (источник — начальное `spec_writing`), а не `unknown`.
`state -> escalated` с маркером роли после `state -> verifying`
(состояния вне сопоставления ролей), между которыми стоит запись
`agent run finished`, даёт `unknown`. Журнал без `state -> escalated`
даёт пустой список.

AC-4. Результат клона без нового поля в `metrics` (набор полей как у
кода до задачи: ровно `_DRIVE_METRIC_FIELDS` на main) принимается
разбором результата без отказа, и строка его прогона получает
`escalation_roles`, вычисленные из `steps`.

AC-5. Строка с `escalation_roles = 'analyst,spec_auditor'`,
`escalations = 2`, вердиктом `green`, нулём итераций ревью, без отказа
автогейта (`autogate_refusal` пуст) и с выполненной ожидаемой эскалацией
(`expected_escalation = 'yes'`, `actual_escalation = 1`,
`marker_mismatch = 0`) — чистая: `unclean_reason` возвращает `None`,
`clean_run` — истину. То же для `escalation_roles = 'analyst'` и
`'spec_auditor'` (`escalations = 1`).

AC-6. На строке AC-5 с иным `escalation_roles` (и `escalations`, равным
длине перечня) прогон не чистый, и причина `unclean_reason` содержит
указанную подстроку: `analyst,developer` — `эскалаций роли developer: 1`;
`analyst,analyst` — `эскалаций роли analyst: 2`;
`analyst,spec_auditor,spec_auditor` — `эскалаций роли spec_auditor: 2`;
`unknown` — `эскалаций роли unknown: 1`; `analyst,test_author` —
`эскалаций роли test_author: 1`; `analyst,reviewer` —
`эскалаций роли reviewer: 1`.

AC-7. Строка с `escalation_roles = 'analyst,spec_auditor'` при
выполненной ожидаемой эскалации остаётся не чистой по прочим условиям с
их нынешними причинами: вердикт не `green` (причина начинается с
`вердикт`); `review_iterations = 1` (`итераций ревью 1`); отказ автогейта,
вина которого по `autogate_refusal_blame` — `BLAME_ROLE` (причина
`отказ автогейта, вина: роль`). Отказ автогейта с виной `BLAME_PULT` её,
как и сейчас, не пачкает.

AC-8. Строка без ожидаемой эскалации (`expected_escalation_met` ложно)
с `escalation_roles = 'spec_auditor'` (`escalations = 1`) — не чистая; с
`escalation_roles = 'analyst'` — не чистая.

AC-9. Строка без данных о ролях (`escalation_roles` — `NULL`, как
записанная до задачи) с выполненной ожидаемой эскалацией и
`escalations = 2` — не чистая с нынешней причиной («эскалаций 2,
ожидаемая эскалация покрывает только одну»); с `escalations = 1` —
чистая. То же для строки-словаря без ключа `escalation_roles` (иначе
та же): `escalations = 2` — не чистая с той же нынешней причиной,
`escalations = 1` — чистая, исключения при чтении нет. БД, заведшая `canary_runs` до задачи, после миграции сохраняет у
прежних строк `escalation_roles = NULL`, и их вердикт чистоты не
меняется.

AC-10. Сводка `pair_admission` для пары с прогоном
`escalation_roles = 'analyst,developer'` (иначе как в AC-5) в строке
этого прогона печатает «не чистый —» с подстрокой
`эскалаций роли developer: 1`; прогон AC-5 печатается «чистый» и
засчитывается в число чистых прогонов допуска. Пороги
`ADMIT_MIN_CLEAN_RUNS`, `ADMIT_MIN_TEMPLATES` и условие чистого прогона
на шаблоне среднего класса не меняются.

AC-11. Эскалация пульта из `spec_writing` и из `spec_audit` ролью
`analyst`/`spec_auditor` не засчитывается. На журналах ниже за
`state -> escalated` с деталью «бюджет исчерпан: $1.00 из $1.00» сразу
следует не маркер роли, а `state -> spec_writing` либо
`agent run started`:
- (а) из `spec_audit`: `created`, `agent run started`,
  `agent run finished`, `state -> escalated` + маркер роли (ловушка
  analyst), `state -> spec_writing`, `agent run started`,
  `agent run finished`, `state -> spec_audit`, `agent run started`,
  `agent run finished`, `state -> escalated` (бюджет, без маркера),
  `state -> spec_audit` — `escalation_roles` возвращает
  `["analyst", "unknown"]`;
- (б) из `spec_writing`: `created`, `agent run started`,
  `agent run finished`, `state -> escalated` (бюджет, без маркера),
  `state -> spec_writing`, `agent run started`, `agent run finished`,
  `state -> spec_audit`, `agent run started`, `agent run finished`,
  `state -> escalated` + маркер роли (ловушка аудитора) —
  `["unknown", "spec_auditor"]`.
Строка AC-5 с `escalation_roles`, равным перечню (а) либо (б) через
запятую, и `escalations = 2` — не чистая, причина `unclean_reason`
содержит `эскалаций роли unknown: 1`.

## Оценка объёма и деление
Сработавшие сигналы: `budget_usd` ≥ $30 и число критериев приёмки ≥ 10
(ставка $45 — класс «до 15 критериев и до 7 файлов зоны»: 11 критериев, зоны `orchestrator/models.py`,
`orchestrator/canary.py`, `orchestrator/store.py`, `tests/`; в рамке ТЗ $50).

Обоснование монолита: запись перечня ролей (`canary.py` — сбор из
журнала, `store.py` — колонка и миграция `canary_runs`) и его чтение
критерием (`models.py::unclean_reason`) — одна смена механики. Часть
«только запись» не меняет ни одного наблюдаемого исхода (критерий данные
не читает) и не проверяема приёмкой ТЗ; часть «только критерий» без
записи никогда не видит строк с ролями — новое правило мёртвое. Вся
правка — несколько функций в трёх модулях; деление удвоило бы цикл
шагов без выигрыша.

## Не входит
- Особое условие допуска для самой пары `spec_auditor` («аудитор обязан
  поймать ловушку», аналог `ADMIT_TZ_AMBIGUITY_ROLE`) — после
  канарейки-ловушки с дефектным SPEC по ADR-0022 п.4–5.
- Правка текста ADR-0019 п.5: формулировка «эскалации (кроме
  ожидаемой)» новому правилу не противоречит.
- Правка шаблонов пула канарейки и синтетического ANSWER канарейки.
- Правка кода клона (`orchestrator/canary_drive.py`, `canary._task_metrics`)
  и набора обязательных полей результата `_DRIVE_METRIC_FIELDS`: перечень
  ролей пульт вычисляет из `steps` результата (требование 1).
- Правка мест эскалации и записи маркера роли
  (`orchestrator/fsm_advance.py`, `orchestrator/fsm.py`,
  `orchestrator/budget.py`, `orchestrator/fixation.py`,
  `orchestrator/runner.py`): признак эскалации самой роли читается из
  журнала как есть (требование 1).
- Дыра main «одна эскалация пульта в прогоне шаблона с ловушкой
  засчитывается ожидаемой» (`actual_escalation` — любая эскалация,
  SPEC-AUDIT Е-1): `expected_escalation_met` не меняется. По новому правилу
  такая эскалация даёт роль `unknown` и прогон не чистый только у строк с
  данными о ролях.
- Перекраска прежних строк `canary_runs` задним числом и восстановление
  ролей для них из журналов клонов (требование 4).
- Смена чисел допуска ADR-0019 п.5 и прочих условий чистоты (вердикт,
  итерации ревью, повтор developer, отказ автогейта).
- Долгоживущий тест `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`
  (строки без данных о ролях, `escalations > 1` — не чистые) сохраняет
  своё ожидание без изменений: это и есть требование 4, отдельный тест
  на старое правило сверх него не заказывается.
- Правка помощника `canary_row` в `tests/test_model_sets.py` (ключ
  `escalation_roles` в нём не появляется): строка без ключа читается по
  нынешнему правилу (требование 4), и проверки этого файла остаются на
  старой ветке критерия.

## Материалы
- ТЗ: `tasks/01M4VC31NFCS6JZ0VE8HNJ7FYM/TZ.md`; копилка 13.10, коммит
  60271ad3 (П2).
- `orchestrator/models.py:1128` (`expected_escalation_met`), `:1136`
  (`unclean_reason`), `:1174` (`pair_admission`).
- `orchestrator/canary.py:1848` (`_escalation_notes`), `:1867`
  (`_task_metrics`), вызовы `store.insert_canary_run` — `:2416`, `:2645`,
  `:2762`.
- `orchestrator/store.py:1442` — DDL и миграции `canary_runs`
  (`add_column`).
- `orchestrator/config.py:805` — `STATE_ROLE` (без `spec_writing`).
- `orchestrator/canary_drive.py:67-87` (`build_result`: `steps` — журнал
  клона); `orchestrator/canary.py:291` (`_DRIVE_METRIC_FIELDS`), `:2330-2343`
  (разбор результата), `:2232` (`steps = result["steps"]` в
  `_run_task_in_ephemeral_clone`, def `:2146`; `steps` возвращаются в
  `_run_one_task`, def `:2504`, распаковка `:2565-2568`; в
  `_record_canary_run`, `:2361`, вызов `:2578`, сейчас идут только `metrics`).
- `orchestrator/catalog.py:667`, `:670` — задача заводится в
  `spec_writing` без записи `state -> spec_writing`; то же — докстринг
  `orchestrator/auto.py:400` (только чтение).
- `orchestrator/models.py:996-998` — `BLAME_ROLE`/`BLAME_PULT`/`BLAME_UNKNOWN`.
- Маркер эскалации по артефакту роли: `orchestrator/fsm.py:71`
  (`ARTIFACT_ESCALATION_ROLE_STEP_MARKER`), `orchestrator/fsm_advance.py:67`
  (`_mark_artifact_escalation`, шесть точек вызова — `:180`, `:207`
  spec_writing; `:292` spec_audit; `:382` review; `:556` tests_writing;
  `:650` in_dev); пишется сразу после `set_state(..., "escalated")`.
- Эскалации пульта без маркера: `orchestrator/budget.py:300`,
  `orchestrator/fixation.py:248`, `orchestrator/runner.py:447`, `:800`,
  `orchestrator/fsm_advance.py:347` (лимит ревью); канарейка переживает
  бюджетную — `orchestrator/canary.py:1734-1747`.
- Аудит SPEC Е-1, В-1 — `tasks/01M4VC31NFCS6JZ0VE8HNJ7FYM/SPEC-AUDIT.md`.
