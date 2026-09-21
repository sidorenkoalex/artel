---
task: 01M31JWD10728N5YGWVQGWYACW
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Возврат из эскалации ревьювера — маркер «ответ должен дойти до роли»

## Фаза A — гейт плана

1. **Покрытие SPEC.** Таблицы покрытия PLAN («Покрытие требований»,
   требования 1-5 и AC-1..AC-8) полны: ни одно требование и ни один
   критерий не остались без шага. Сверено построчно со SPEC.
2. **Размер шагов.** Три шага (код, тесты, прогон+карта) — один MR;
   обоснование монолита SPEC («части „только код“/„только тесты“ по
   отдельности не мержатся») проверяемо и верно: часть «только тесты»
   действительно красна (эмпирически — см. «Проверено исполнением»,
   мутация с переносом вызова даёт `1 failed` ровно на переписанном
   тесте).
3. **Конвенции и архитектура.** Подход совпадает с уже существующим
   приёмом двух точек эскалации (`spec_writing`/`tests_writing`) и с
   `pull.PULL_CONFLICT_ROLE_STEP_MARKER`; читатель маркера
   (`auto._ROLE_STEP_REQUIRED_MARKERS`) не трогается — ссылки PLAN на
   `auto.py:321`, `auto.py:384-395` проверены по коду, соответствуют.
   Границы («вызов ВНУТРЬ `_review_escalate`, не в `review()` и не в
   общий узел») выдержаны в диффе. Регенерация карты кодовой базы
   заявлена и выполнена. Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (маркер тем же вызовом, сразу после `state -> escalated`) | OK | `orchestrator/fsm_advance.py:224-228`: `detail` — одна переменная для `set_state` и `_mark_artifact_escalation`, вызов идёт строго после перехода. Текст эскалации не продублирован — расхождение формулировок структурно невозможно. |
| 2 (возврат в `in_dev` становится анкером, developer обязателен) | OK | Читатель не менялся: `auto._role_step_since_state_entry` взводит `role_step_required` на `_ROLE_STEP_REQUIRED_MARKERS` (`orchestrator/auto.py:322-323, 390-397`) и делает анкером запись возврата, иначе пропускаемую как `_ESCALATED_RETURN_DETAILS`. Сквозной эффект подтверждён прогоном планки AC-2/AC-4 (цикл `auto` даёт шаг developer до `in_dev -> verifying`). |
| 3 (точка возврата — `in_dev`, шаг developer) | OK | `escalated_from` в `_review_escalate` не выставляется, `fsm._approve_escalated:850` даёт `back = "in_dev"`. Планка AC-7 зелёная. |
| 4 (возвраты без основания переделки — как раньше) | OK | Вызов стоит внутри `_review_escalate`; `budget.enforce_budget` (`orchestrator/budget.py:203-212`) идёт мимо него и маркера не пишет — новый тест `test_budget_escalation_from_review_journals_no_marker` и планка AC-5 это фиксируют. `_ESCALATED_RETURN_DETAILS` и ветка пропуска не тронуты. |
| 5 (тесты: сценарий 21.09; прежнее поведение бюджета и `spec_writing`/`tests_writing`) | OK с оговоркой | Вторая половина закрыта в `tests/` полностью (новый бюджетный тест + три нетронутых теста точек эскалации). Сквозной сценарий 21.09 в `tests/` отдельным тестом не воспроизводится — он лежит в планке (`acceptance_tests/test_ac4_incident_21_09_replay.py`, зелёный), ровно тем же делением, что уже применил модуль-предшественник (шапка `tests/test_artifact_escalation_marker.py:11-17`: сквозной сценарий 13.09 кроет планка, в `tests/` — обе половины механики в изоляции). Замечанием не считаю: обе половины (запись маркера точкой review; чтение маркера анкером) в `tests/` покрыты, и мутация «маркер не пишется/пишется не там» ловится `tests/` без планки — проверено переносом вызова. |

| Критерий приёмки | Вердикт | Комментарий |
|---|---|---|
| AC-1 | OK | Планка `test_ac1_review_escalation_marker.py` зелёная; юнит-дубль в `tests/` — `test_review_escalation_journals_the_marker` (actor `fsm`, `detail` равен detail эскалации, порядок «маркер сразу за переходом»). |
| AC-2 | OK | `test_ac2_auto_runs_developer_after_the_return.py` зелёный. |
| AC-3 | OK | `test_ac3_developer_brief_carries_the_answer.py` зелёный; `brief.py` не правился — ANSWER в брифе developer уже был. |
| AC-4 | OK | `test_ac4_incident_21_09_replay.py` зелёный. Краснота до правки подтверждена мутацией (вызов маркера убран из `_review_escalate` и перенесён в `review()` — AC-1 и AC-8 планки краснеют). |
| AC-5 | OK | `test_ac5_budget_escalation_from_review.py` зелёный + новый юнит-тест в `tests/`. |
| AC-6 | OK | Три прежних теста точек эскалации (`tests_writing`, оба пути `spec_writing`) не правились ни строкой и зелёные. |
| AC-7 | OK | `test_ac7_return_point_is_in_dev.py` зелёный; `escalated_from` в диффе не встречается. |
| AC-8 | OK | Четыре модуля прогнаны — 112 тестов зелёных; `test_ac8_existing_suites_escalation.py` (сверка «проверки не исчезли» + прогон) зелёный. Единственный изменённый тест переписан по прямому решению Оператора (ANSWER-1, вопрос 1), ослабления нет: его вторая половина («маркер не в общем узле») сохранена отдельным новым тестом. |

**Системная целостность.** Ни один тест/гейт/лимит/инвариант не ослаблен:
правка ДОБАВЛЯЕТ анкер там, где его не было. Правка единственного
существующего теста авторизована ANSWER-1 (границы решений Оператора
учтены: имя метода — ровно то, которое требует планка AC-8; половина
проверки сохранена). Защищённые пути (`tests/test_invariants.py`,
`templates/`, `skills/`, `gates.yaml`, `.github/`) не тронуты. Зоны SPEC
(`orchestrator/fsm_advance.py`, `tests/`) выдержаны, третий файл диффа —
обязательная регенерация `docs/codebase-map.md`. «Влияние на систему»
PLAN совпадает с фактическим диффом: три файла, ничего сверх. Откат —
revert одного merge-коммита, внешних состояний не заведено. Артефакты
`tasks/` в кодовую ветку не закоммичены (`git status` — каталог задачи
untracked).

**Корректность, сценарии поломки — искал, не нашёл.** Проверил четыре
кандидата: (1) лишняя строка журнала между `state -> escalated` и
маркером (`sha зафиксирован` хука `record_fixation`) — читателю
безразлична, `startswith("state -> ")` её не задевает; (2) текст
`"эскалация от ревьювера"` нигде в `orchestrator/`/`tests/` не
разбирается, кроме самой этой строки (`grep`) — консументов detail,
которых сдвинула бы новая запись, нет; (3) `_code_sha_at_review_escalation`
и `_review_rework_gate` фильтруют по `action`/`actor`, а не по соседству
записей — маркер их не задевает (модули прогнаны); (4) тупик «developer
без коммита» — `_review_rework_gate` применяется только к REVIEW.md со
статусом `changes_requested`, а при `escalate` не срабатывает, поэтому
дешёвый подтверждающий шаг developer не запирает задачу в `in_dev`.

## Замечания

- minor — `tests/test_artifact_escalation_marker.py:381-386` — заявка
  «Ловит мутацию» теста `test_budget_escalation_from_review_journals_no_marker`
  перечисляет две реализации мутации, а ловит одну. Первая (маркер в
  `store.set_state` на любой переход в `escalated`) ловится честно:
  `budget.enforce_budget` идёт через `store.set_state`
  (`orchestrator/budget.py:210`), маркер появился бы и `assertNotIn`
  упал бы. Вторая («либо в `fsm_advance.review` до разбора вердикта»)
  этим тестом не ловится вовсе: тест зовёт `budget.enforce_budget`
  напрямую, мимо `fsm_advance.review`. Проверено исполнением: перенос
  вызова в начало `review()` оставляет бюджетный тест зелёным и валит
  соседний `test_review_escalation_journals_the_marker` (и AC-1/AC-8
  планки) — то есть мутация ловится модулем, но не тем тестом, который
  её заявляет. Последствие — цена доверия к докстрингу: читатель,
  правящий `review()`, сочтёт бюджетный тест своей страховкой, которой
  тот не является. Предложение: убрать из скобок вторую реализацию
  (оставить «маркер вынесен в `store.set_state` на любой переход в
  `escalated`») либо назвать в ней тест, который её действительно
  ловит.

Замечание НЕ заведено в реестр сознательно: по `skills/review-checklist.md`
вердикт при 0 blocker/major — `approved`, а гейт реестра
(`orchestrator/advance_gates/tests_writing.py::_registry_gate`) отклоняет
`approved` при любой записи со статусом, отличным от `accepted` — запись
уровня minor стоила бы полного круга developer+reviewer ради одной
строки докстринга. Расхождение двух правил вынесено в «Предложения
системе».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: blocker/major замечаний по итогам ревью нет, единственное
minor-замечание оставлено незарегистрированным по причине, названной
выше (иначе гейт реестра отклонил бы `approved`).

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M31JWD10728N5YGWVQGWYACW/acceptance_tests -q`
  — 10 passed, 3 subtests passed (AC-1..AC-8).
- `python3 -m pytest tests/test_artifact_escalation_marker.py
  tests/test_auto_escalated_return_rework_gate.py
  tests/test_fsm_review_rework_gate.py tests/test_fsm_review_rework_sha_gate.py
  tests/test_auto_cycle.py tests/test_review_freshness.py -q` — 112 passed,
  28 subtests passed (четыре модуля AC-8 + соседи затронутого кода).
- `python3 -m pytest tests/test_invariants.py
  tests/test_budget_live_lease_and_escalation.py -q` — 78 passed,
  215 subtests passed за 115 с; ожидаемой красноты защищённого
  `test_invariants.py` (SPEC «Материалы») нет.
- **Мутация 1** (перенос, а не дублирование вызова): вызов
  `_mark_artifact_escalation` убран из `_review_escalate` и поставлен в
  начало `fsm_advance.review` → `tests/test_artifact_escalation_marker.py`
  даёт `1 failed` (`test_review_escalation_journals_the_marker`,
  `assertLess` в `row_after_escalation`), планка — `2 failed`
  (AC-1, AC-8). `test_budget_escalation_from_review_journals_no_marker`
  при этом ОСТАЛСЯ зелёным — основание minor-замечания выше. Дерево
  восстановлено `git checkout orchestrator/fsm_advance.py`,
  `git status --porcelain` чист (кроме untracked `tasks/<id>/`).
- **Мутация 2** (добавление вызова в начало `review()` без удаления
  исходного) — модуль целиком зелёный (12 passed): проверял, не маскирует
  ли дублирующая запись порядок «маркер сразу за переходом»; нет,
  инвариант «следующая значимая запись после `state -> escalated` — маркер»
  сохраняется, ложного красного тест не даёт.
- `python3 scripts/codebase_map.py` — после регенерации `git diff -U0
  docs/codebase-map.md` отличается ровно одной строкой `built_at_sha`
  (`afd4ec66` → `b100e681`), содержимое карты актуально (сверка по
  содержимому без `built_at_sha`, как в CI-джобе `codebase-map`). Дерево
  восстановлено `git checkout docs/codebase-map.md`.
- `python3 scripts/guard.py --all` — `GUARD: ок (974 файлов)`; ни одной
  претензии к файлам этой задачи (`grep 01M31JWD` по выводу — пусто).
- Прочитаны сверх пакета (для проверки конкретных замечаний):
  `orchestrator/auto.py:300-400` (читатель маркера — требование 2),
  `orchestrator/fsm.py::_approve_escalated:822-856` (точка возврата,
  AC-7), `orchestrator/advance_gates/review.py:13-63, 270-368` (гейты
  рядом — не задеты ли новой записью), `orchestrator/budget.py:203-212`
  (валидность первой половины заявки мутации),
  `tests/test_auto_cycle.py::AutoCycleTest` (сигнатура `set_state(**fields)`,
  которой пользуется новый тест), планка AC-4 и AC-8 целиком.
- `git diff --stat` ветки — три файла, ничего сверх заявленного в PLAN;
  `git status --porcelain` — артефакты `tasks/<id>/` в кодовую ветку не
  закоммичены.
- Полный набор `tests/` в шаге не гонял (решение Оператора 05.09) — его
  зелёный статус на коммите `b100e681` подтверждён CI (7 проверок,
  статус из пакета ревью).

## Предложения системе

- `skills/review-checklist.md` («Вердикт»: 0 blocker/major → approved) и
  гейт реестра (`orchestrator/advance_gates/tests_writing.py::_registry_gate`:
  любая запись не в `accepted` валит approved) расходятся ровно на классе
  minor: зарегистрированное minor-замечание автоматически превращает
  вердикт в `changes_requested` и стоит круга developer+reviewer, а
  незарегистрированное нарушает правило «каждое замечание — своя строка
  реестра». Нужен либо статус реестра для незакрывающих замечаний
  (например `noted`, не блокирующий гейт), либо явное правило в скиле,
  что minor при approved в реестр не заводится.
- Планки задач после мержа лежат в `tasks/<id>/acceptance_tests/` в main,
  но CI (`.github/workflows/*.yml:218`) гоняет только `tests/` — сквозные
  сценарии, оставленные в планке (как AC-4 здесь и AC инцидента 13.09 в
  задаче-предшественнике), после закрытия задачи не прогоняются никогда.
  Стоит либо признать это явно в `skills/test-authoring.md` (планка —
  одноразовый гейт, постоянное покрытие обязано жить в `tests/`), либо
  добавить CI-джоб по планкам мерженных задач.
