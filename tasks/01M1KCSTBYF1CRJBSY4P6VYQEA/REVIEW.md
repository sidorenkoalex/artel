---
task: 01M1KCSTBYF1CRJBSY4P6VYQEA
type: review
author_role: reviewer
status: escalate
iteration: 1
schema_version: 3
---

# REVIEW: auto: детекция буксования цикла и алерты Оператору

## Фаза A: гейт плана

1. Покрытие требований SPEC шагами PLAN — полное: таблица «Покрытие
   требований» закрывает все 5 требований, шаги 2-7 соответствуют
   заявленному подходу (константа, alerts-обёртки, hook в
   `store.set_state`, счётчик `idle_steps`, тесты, регенерация карты).
2. Шаги — проверяемые единицы разумного размера, не микрооперации и не
   «сделать всё».
3. Подход не конфликтует с конвенциями: отложенный импорт `alerts`
   внутри `store._close_attention_alert` — тот же приём, что уже несут
   `record_fixation`/`_append_passport_line` (сохраняет `store.py`
   листом графа импортов, ADR-0003 3ж); `auto_stop` получил
   keyword-only `alert` по тому же прецеденту, что `expected_state` у
   `store.set_state`. Замечаний к подходу нет.

Отдельно — сама секция PLAN «Эскалация»: PLAN несёт `status: ready`
(не `escalate`), но содержит блокирующий вопрос Оператору. Технически
это разошлось с escalation-rules («Эскалируй... Заверши текущий
артефакт со `status: escalate`»), но по существу задача была
продвинута в `review` намеренно — 24 из 25 приёмочных тестов зелёные,
единственный красный привязан к дефекту ЗАЛОЧЕННОГО файла вне зоны
developer, а не к реализации. Отношусь к этому как к добросовестному
пограничному случаю (см. «Предложения системе»), не как к отдельному
нарушению — существо вопроса разбираю в «Эскалации» ниже.

## Фаза B: ревью MR

### Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (стоп-кран по классу, регресс-тесты) | OK | Код не менялся (подтверждено чтением `orchestrator/auto.py`); AC-1/AC-2 зелёные — прогнано лично. |
| 2 (порог холостых шагов) | OK | `config.AUTO_STALL_STEPS_LIMIT=5`, счётчик `idle_steps` в `_cmd_auto` (auto.py:227,325-342) — сброс на переходе, независим от стоп-крана. AC-3..AC-6 зелёные. |
| 3 (алерты на остановках не-гейта) | OK | Все точки `auto_stop(...)` в `auto.py` явно проставляют `alert=`, включая `_advance_verifying_poll` (auto.py:100) и финальный выход (`_final_stop_raises_alert`, auto.py:106-119). AC-7..AC-16 зелёные. |
| 4 (авто-закрытие на любом переходе) | Частично подтверждено | Хук `store._close_attention_alert` (store.py:613-628) сидит строго после успешного CAS, до journal/passport — общая точка для `auto`/`advance`/`approve`/`reject`, подтверждено юнит-тестом `tests/test_stall_alerts.py::SetStateClosesAttentionAlertTest` и приёмочными AC-18, AC-19 (approve/reject ветки). Один под-сценарий AC-19 (`advance`) красный — не дефект реализации, см. «Эскалация». |
| 5 (тесты) | Реализовано с замечанием | Приёмочные тесты покрывают все AC с содержательными докстрингами и заявкой «Ловит мутацию» (кроме двух исключений — R1-F3). Юнит-тесты `tests/test_stall_alerts.py` содержательны, но целиком без заявок «Ловит мутацию» — R1-F2. |

### Замечания

- major — `tests/test_stall_alerts.py:27,37,47,58,71,78,88,98,116,124,130,144,149,154,158,161,166` — ни один из 17 тестов файла не несёт докстринг с заявкой «Ловит мутацию: …» (skill test-authoring, требование 3 review-checklist): часть тестов вовсе без докстринга (например, `test_attention_is_a_registered_alert_kind`, `test_raises_an_open_alert_of_kind_attention_naming_the_task`, весь класс `CloseAttentionAlertsTest` кроме одного метода), часть несёт короткое пояснение без явной формулировки ловимой мутации (`test_repeated_call_with_the_same_message_does_not_duplicate`, `test_leaves_other_kinds_of_this_task_open`, `test_spec_writing_with_zero_steps_raises_no_alert`, `test_escalated_with_zero_steps_raises_an_alert`). Сами тесты содержательны (проверено прогоном — все 17 зелёные, логика ассертов соответствует сценариям), но без заявки ревьювер не может сверить тест с конкретной мутацией, которую он обязан ловить, а не гадать по наитию (явное требование скила). Предложение: дописать в докстринг каждого теста «Ловит мутацию: …» — какую мутацию кода (`alerts.py`/`store.py`/`auto.py`) тест обязан поймать.
- minor — `tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/test_ac18_ac19_attention_alert_closes_on_next_transition.py:151,163` — `test_ac19_manual_approve_outside_auto_closes_the_alert` и `test_ac19_manual_reject_outside_auto_closes_the_alert` несут докстринг co сценарием, но без явной заявки «Ловит мутацию: …» (сосед `test_ac18_...`/`test_ac19_manual_advance_...` в этом же файле такую заявку несёт). Этот файл залочен (T023 требование 5) — правка вне полномочий и developer, и reviewer; фиксирую для того, кто будет исправлять `_sandbox.py` по итогам эскалации ниже (естественно лечится тем же заходом test_author, что и R1-F1).

### Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | `tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/_sandbox.py` (не патчит `gitcmd.show`/`gitcmd.ls_tree_files`); `.../test_ac18_ac19_attention_alert_closes_on_next_transition.py:132` (`test_ac19_manual_advance_outside_auto_closes_the_alert`) | Залоченный приёмочный тест красен: `artifact_source.resolve` после A7 всегда `foreign=True`, `fsm._read_branch_text_or_refuse` читает PLAN.md через `gitcmd.show`, а песочница подменяет только `gitcmd.git`/`runner.cmd_run` — `gitcmd.show` получает пустой ответ, PLAN.md парсится как `{}`, `advance` честно отказывает «не ready». Диагноз подтверждён лично (запуск теста, чтение `artifact_source.py`/`gitcmd.py::show`/`fsm_advance.py::in_dev`) — совпадает с диагнозом PLAN.md разработчика. Это дефект тестовой инфраструктуры (планки), не реализации требования 4. | Гейт `review → verifying` (T023 требование 6 прогоняет `acceptance_tests/` целиком) откажет на этом одном тесте — ветка не сможет продвинуться дальше без вмешательства. Ни developer, ни reviewer не вправе править залоченный `_sandbox.py`/`test_*.py` (T023 требование 5). | Требуется решение Оператора — см. «Вердикт»/«Эскалация» ниже: вариант A (вернуть в `tests_writing`, test_author патчит `_sandbox.py` `disk_backed_show`/`disk_backed_ls_tree_files`, заодно закрывает R1-F3 тем же заходом) или вариант B (принять как задокументированное ограничение — свойство требования 4 для ветки `advance` остаётся доказанным транзитивно двумя соседними зелёными сценариями + юнит-тестом). |
| R1-F2 | open | `tests/test_stall_alerts.py:27,37,47,58,71,78,88,98,116,124,130,144,149,154,158,161,166` | Ни один из 17 тестов файла не несёт заявку «Ловит мутацию: …» в докстринге (детали в «Замечания»). | Ревьювер следующей итерации не может механически сверить тест с заявленной мутацией — риск, что тест де-факто не ловит то, что должен, остаётся непроверяемым по формальному критерию скила. | Developer дописывает докстринги в следующей итерации (файл не залочен, в зоне developer). |
| R1-F3 | open | `tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/test_ac18_ac19_attention_alert_closes_on_next_transition.py:151,163` | Два теста AC-19 (approve/reject) несут докстринг-сценарий без явной заявки «Ловит мутацию: …». | Тот же класс дефекта планки, что и R1-F1, но не блокирует гейт (тесты зелёные) — второстепенно. | Правится тем же заходом test_author, что и R1-F1 (файл залочен, вне зоны developer/reviewer). |

### Вердикт

escalate.

**Вопрос Оператору** (тот же по существу, что и в PLAN.md «Эскалация»
— endorse диагноза разработчика, добавляю R1-F3 к объёму варианта A):
залоченный приёмочный тест `test_ac19_manual_advance_outside_auto_
closes_the_alert` красен из-за отсутствующего в `_sandbox.py` патча
`gitcmd.show`/`gitcmd.ls_tree_files`, а не из-за дефекта реализации
требования 4 — я лично воспроизвёл падение, прочитал прод-код
(`artifact_source.resolve`, `gitcmd.show`, `fsm_advance.py::in_dev`) и
подтверждаю диагноз PLAN.md буквально. Правка залоченного файла — вне
полномочий и developer, и reviewer (T023 требование 5).

- **A** — вернуть задачу в `tests_writing`: test_author патчит
  `_sandbox.py` (`disk_backed_show`/`disk_backed_ls_tree_files`, приём
  уже несёт `tests/test_auto_cycle.py::AutoCycleTest`), заодно
  дописывает заявки «Ловит мутацию» в `test_ac19_manual_approve_...`/
  `test_ac19_manual_reject_...` (R1-F3). Чистое закрытие обоих дефектов
  планки одним заходом.
- **B** — принять как задокументированное ограничение (реестр,
  R1-F1 → `accepted` с обоснованием: свойство требования 4 для ветки
  `advance` доказано транзитивно `test_ac19_manual_approve_...`/
  `test_ac19_manual_reject_...` + `tests/test_stall_alerts.py::
  SetStateClosesAttentionAlertTest`, хук — в общей точке `store.
  set_state`, разницы между командами для самого хука нет) — но это
  НЕ снимает то, что гейт `review → verifying` физически прогоняет
  этот тест и откажет на его красноте (T023 требование 6): вариант B
  без дополнительного действия Оператора (снятие теста с прогона или
  иное урегулирование гейта) не даёт ветке пройти дальше сам по себе.
- **Дефолт при молчании**: как и в PLAN.md — молчание не проталкивает
  задачу дальше; ветка остаётся в `review`.

R1-F2 (докстринги `tests/test_stall_alerts.py`) не блокирует это
решение — доработка в зоне developer, войдёт следующей итерацией
независимо от выбора A/B.

## Проверено исполнением

- `git checkout -- tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/` — рабочее дерево
  этого ревью первоначально показывало залоченные артефакты задачи
  удалёнными (uncommitted deletion, не коммит); восстановлены из HEAD
  ветки, не переписаны.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` —
  1324 теста, `OK` (полный набор `tests/` зелёный, требование 5/AC-20
  подтверждено лично).
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s
  tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests -p "test_*.py" -v`
  — 25 тестов, 24 `ok`, 1 `FAIL`
  (`test_ac19_manual_advance_outside_auto_closes_the_alert`, тот же
  тест и та же причина, что названы в PLAN.md «Эскалация»).
- Прочитан целиком `orchestrator/auto.py` — подтверждено, что КАЖДАЯ
  точка `auto_stop(...)` явно проставляет `alert=` (включая
  `_advance_verifying_poll` и финальный выход через `_final_stop_
  raises_alert`), пропущенных вызовов нет.
- Прочитан целиком `orchestrator/alerts.py` и участок `orchestrator/
  store.py:550-628` (`set_state`, `_close_attention_alert`,
  `open_alerts`, `ack_alert`) — хук закрытия вызывается ТОЛЬКО после
  успешного CAS (после проверки `rowcount`), до journal/passport;
  подтверждено юнит-тестом `test_a_losing_cas_call_does_not_close_the_
  alert`.
- Прочитаны `orchestrator/artifact_source.py`, `orchestrator/
  gitcmd.py::show`, `orchestrator/fsm_advance.py::in_dev` — подтверждён
  диагноз PLAN.md по красному AC-19 (реальный код, не подмена диска).
- `grep -rn "alerts.KINDS" orchestrator/*.py tests/*.py` — других мест,
  завязанных на состав `alerts.KINDS`, нет; добавление `"attention"`
  не задевает `report.py`/`catalog.py`/`doctor.py` (все зовут
  `open_alerts` с явным `kind` или отображают список общо).
- `python3 scripts/codebase_map.py` (во временную перегенерацию,
  дерево возвращено `git checkout --`) — расхождение с закоммиченной
  картой только в строке `built_at_sha` (законное отставание, не
  дефект по правилу скила); по содержимому карта актуальна.

## Предложения системе

- Класс «PLAN.md несёт `status: ready` и продвигает задачу в `review`
  при незакрытом блокирующем вопросе Оператору вместо `status:
  escalate`» (эта задача, PLAN.md «Эскалация») — escalation-rules
  предписывает `status: escalate` для любого блокера вне права роли,
  но бинарный словарь `ready/escalate` плохо описывает «всё готово,
  кроме одного тестового дефекта вне зоны developer»: `escalate`
  увёл бы 24 честно зелёных AC в `escalated` без пользы для reviewer,
  `ready` — единственный способ довезти работу до ревью, но прячет
  блокер внутри текста, полагаясь на то, что ревьювер его найдёт сам.
  Возможно, стоит явное третье состояние/пометка PLAN («ready с
  оговоркой») — не предмет этой задачи, оставляю наблюдением.
