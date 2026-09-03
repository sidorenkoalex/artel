---
task: 01M1KCSTBYF1CRJBSY4P6VYQEA
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: auto: детекция буксования цикла и алерты Оператору

## Подход

Ветка отставала от `main` на 58 коммитов (после мержа A7) — первым шагом
подтянут `main` (`git merge main`, без конфликтов) и перегенерирована
`docs/codebase-map.md` (conventions-core: подтяжка меняет `orchestrator/`/
`tests/` не через Edit, регенерация — тем же коммитом). Полный набор
`tests/` зелёный после подтяжки (см. «Влияние на систему»).

Три независимых механизма поверх существующего цикла `orchestrator/auto.py::_cmd_auto`:

1. **Стоп-кран по классу (требование 1)** — уже реализован (T038,
   `_advance_refusal` сравнивает `row["action"]`, не полную запись);
   код не трогается, приёмочные тесты AC-1/AC-2 фиксируют это регрессом.

2. **Порог холостых шагов (требование 2)** — новый счётчик `idle_steps`
   внутри `_cmd_auto`: инкремент на каждом шаге, где `state == before`
   (без перехода), сброс на 0 при переходе. Достигает
   `config.AUTO_STALL_STEPS_LIMIT` (новая константа, дефолт 5) — цикл
   останавливается сообщением «цикл не сходится: N шагов без перехода[,
   последний отказ: <класс>]» (хвост — только если `advance`
   журналировал отказ на последнем из N шагов). Проверяется ПОСЛЕ
   стоп-крана требования 1 на том же шаге — крана дефолтный порог (2
   шага) меньше дефолтного порога холостых (5), пересечения на практике
   нет, но код проверяет оба условия на каждом шаге независимо.

3. **Алерты `kind=attention` (требования 3-4)**:
   - `alerts.KINDS` += `"attention"`; новые функции `alerts.
     raise_attention_alert`/`alerts.close_attention_alerts` (тонкие
     обёртки над существующими `raise_alert`/`ack_alert` — дедуп и
     решение не переопределяются, SPEC «Не входит»).
   - **Открытие**: `auto.auto_stop` получает keyword `alert: bool`,
     каждая точка остановки цикла передаёт своё значение явно — `True`
     для всех причин требования 3 (стоп-кран, порог холостых, лимит
     `AUTO_MAX_STEPS`, красный CI в `verifying`, отказ guard'а, отказ
     `run` не по паузе, эскалация любой причины), `False` для паузы.
     Финальный выход цикла (`auto_stop_advice`, отсутствие роли) решает
     отдельная функция `_final_stop_raises_alert(state, steps)`:
     `False` для ручных гейтов (`spec_gate`/`acceptance`/`merge_gate`),
     `False` для терминалов (`done`/`killed`), `False` для
     `spec_writing` с нулём пройденных шагов (роли не было с самого
     начала — TZ.md не заведён); во всех остальных случаях, включая
     `escalated` даже с нулём шагов (задача уже была в эскалации до
     вызова, AC-17) — `True`.
   - **Закрытие**: хук в `store.set_state` (единственная точка ЛЮБОГО
     перехода FSM — мандат ANSWER-1, вопрос 1, вариант B) зовёт
     `alerts.close_attention_alerts(conn, task_id)` после журналирования
     перехода. Покрывает `auto`, ручной `advance`, `approve`, `reject`
     одним хуком без дублирования по каждой команде.

## Шаги

1. Подтяжка `main` + регенерация карты кодовой базы (сделано перед
   написанием этого плана, коммитится вместе с ним).
2. `config.py`: константа `AUTO_STALL_STEPS_LIMIT = 5`.
3. `alerts.py`: `"attention"` в `KINDS`, `raise_attention_alert`,
   `close_attention_alerts`.
4. `store.py::set_state`: хук `_close_attention_alert` (отложенный
   импорт `alerts`, тем же приёмом, что `record_fixation`/
   `_append_passport_line`).
5. `auto.py`: счётчик `idle_steps` + остановка требования 2; `auto_stop`
   получает `alert: bool`, все точки остановки цикла проставляют
   значение явно; `_final_stop_raises_alert` для финального выхода без
   роли.
6. Юнит-тесты новых функций — отдельный файл `tests/test_stall_alerts.py`
   (17 тестов: `alerts.raise_attention_alert`/`close_attention_alerts` в
   изоляции, хук `store.set_state -> _close_attention_alert` через
   `TmpRootTest` + `store.insert_task` — тот же минимальный приём, что
   `tests/test_cas_set_state.py`, без git/FSM; `auto._final_stop_raises_
   alert` как чистая функция) + прогон приёмочных тестов задачи и
   полного набора `tests/`.
7. Регенерация `docs/codebase-map.md` (conventions-core: новый файл
   `tests/test_stall_alerts.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (стоп-кран по классу — не меняется, фиксируется тестами) | 6 |
| 2 (порог холостых шагов) | 2, 5, 6 |
| 3 (алерты на остановках не-гейта) | 3, 4, 5, 6 |
| 4 (авто-закрытие на любом переходе) | 3, 4, 6 |
| 5 (тесты) | 6 |

## Влияние на систему

- `store.set_state` — единственная точка перехода FSM; новый хук
  добавляет один запрос (`open_alerts` фильтром по `kind=attention`,
  обычно 0 строк) на КАЖДЫЙ переход, включая уже нагруженные пути
  (advance/approve/reject/kill). Стоимость — один `SELECT` по
  индексируемому `ack_ts IS NULL`, тот же порядок, что уже несут
  `record_fixation`/`_append_passport_line` рядом. Отложенный импорт
  `alerts` внутри функции (не на уровне модуля) сохраняет `store.py`
  листом графа импортов (ADR-0003 3ж) — `alerts.py` уже импортирует
  `store` на уровне модуля, прямой импорт в обратную сторону дал бы
  цикл.
- `auto.auto_stop` меняет сигнатуру (новый keyword `alert`) — все
  вызовы внутри `orchestrator/auto.py` обновлены этим же PLAN; внешних
  вызывающих `auto_stop` за пределами модуля нет (не публичный API
  пакета, не входит в `docs/codebase-map.md` «Публичные функции» —
  фактически используется только внутри `auto.py`, что подтверждено
  чтением карты).
- Стоп-кран T038 (требование 1) и существующий текст/порядок его
  остановки не меняются — только оборачиваются в `alert=True`. Лимит
  `AUTO_MAX_STEPS`, `docs/invariants.md 18` (ручные гейты auto не
  проходит) не трогаются.
- Дедуп `alerts.raise_alert` не меняется — новый `kind` использует его
  как есть (SPEC «Не входит»). Откат: убрать `"attention"` из `KINDS`,
  вызовы `raise_attention_alert`/`close_attention_alerts` и хук в
  `set_state` — остальной код (стоп-кран, порог холостых) не зависит от
  алертов и продолжит работать без них.
- Полный набор `tests/` (`python3 -m unittest discover -s tests`) после
  подтяжки `main` зелёный (`exit 0`, без FAILED/ERROR) — сверено ДО
  начала правок этой задачи, чтобы отличить регресс подтяжки от
  регресса реализации.

## Риски

- Порог холостых шагов (дефолт 5) может останавливать циклы, которые
  раньше докручивались до `AUTO_MAX_STEPS=30` без разбора — это и есть
  цель требования 2 (видимость раньше), не риск для существующих
  тестов: `tests/test_auto_cycle.py::AutoStepLimitTest` и
  `AutoNeverPassesAGateTest` используют сценарии с ready PLAN.md/REVIEW.md
  или переходами, не длинные холостые серии — не задеты (проверено
  прогоном).

## Предложения системе

(пусто)

## Эскалация

Реализация (требования 1–4, шаги 2–5) готова, зелена на `tests/`
(`python3 -m unittest discover -s tests` — `OK`) и на 24 из 25
приёмочных тестов задачи. Один приёмочный тест красный по причине,
которую я не имею права чинить (файл залочен, T023 требование 5):
`spec: 01M1KCSTBYF1CRJBSY4P6VYQEA` /
`tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/
test_ac18_ac19_attention_alert_closes_on_next_transition.py::
Ac19AlertClosesOnAManualOperatorTransitionOutsideAutoTest::
test_ac19_manual_advance_outside_auto_closes_the_alert`.

### Вопросы

1. (блокирует) Один залоченный приёмочный тест красен по причине вне
   моей зоны (диагноз ниже) — что делать?
   - **A** — вернуть задачу в `tests_writing` (T023 требование 5:
     «правка залоченного теста = правка SPEC = только Оператор»),
     `test_author` добавляет в `_sandbox.py` этой задачи патчи
     `gitcmd.show`/`gitcmd.ls_tree_files` →
     `tests.sandbox.disk_backed_show`/`disk_backed_ls_tree_files` —
     установленный приём, уже несомый `tests/test_auto_cycle.py::
     AutoCycleTest` (строки 186–194 того файла) для той же причины
     (A7: `artifact_source.resolve` теперь всегда `foreign=True`).
   - **B** — принять как задокументированное ограничение теста
     (аналог REVIEW.md T101, R1-F1: реестр замечаний, `accepted`) —
     сценарий требования 4 «закрытие алерта переходом ВНЕ `auto`»
     остаётся доказанным транзитивно двумя соседними тестами этого же
     файла, которые зелены (`test_ac19_manual_approve_outside_auto_
     closes_the_alert`, `test_ac19_manual_reject_outside_auto_closes_
     the_alert`) плюс прямым юнит-тестом
     `tests/test_stall_alerts.py::SetStateClosesAttentionAlertTest::
     test_a_transition_closes_the_open_attention_alert` — хук сидит в
     `orchestrator/store.py::set_state` (строка 583), общей для ВСЕХ
     вызывающих команд точке, а не в конкретном обработчике `advance`/
     `approve`/`reject`; разница между тремя командами для самого хука
     отсутствует.
   - **Дефолт при молчании**: B — красный тест остаётся красным
     (задокументированным), ветка не мержится без решения Оператора
     по гейту `review → verifying` (см. «Блокирует» ниже) в любом
     случае — молчание не проталкивает задачу дальше само по себе.

### Контекст

`tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/_sandbox.py`
патчит только `gitcmd.git` (генерическая заглушка `fake_git`: любой
вызов → `rc=0`, пустой `stdout`, кроме `rev-parse --verify --quiet
refs/heads/*` → отказ) и `runner.cmd_run` — НЕ патчит `gitcmd.show`/
`gitcmd.ls_tree_files`.

Тест `test_ac19_manual_advance_outside_auto_closes_the_alert`
вызывает НАСТОЯЩИЙ `fsm.cmd_advance(self.TASK)` (не через `auto`, не
через фейк) после `write_plan()` (`status: ready` на диске,
`self.tdir`) и `set_state("in_dev")`. Обработчик `in_dev`
(`orchestrator/fsm_advance.py:467-546`) читает `PLAN.md` через
`artifact_source.resolve()` → всегда `foreign=True` (A7, «снятие
особого случая догфуда» — `orchestrator/artifact_source.py:20-22`) →
`fsm._read_branch_text_or_refuse` → `gitcmd.show(branch, "tasks/<id>/
PLAN.md")` → патченный `fake_git("show", "<branch>:tasks/<id>/
PLAN.md")` → `CompletedProcess(rc=0, stdout="", stderr="")` →
`gitcmd.show` возвращает `("", "")` (`text=""`, НЕ `None` — файл
«прочитан», просто пустой). `plan_meta = yamlmini.frontmatter("")` →
`{}` → `status` не `ready`/`approved` → переход не происходит,
печатается «PLAN.md не ready — разработчик ещё работает» (сверено
прогоном: ровно это и печатается, `self.state()` остаётся `in_dev`).

Диск (`self.tdir / "PLAN.md"`, куда пишет `write_plan()`) в этом
сценарии не участвует вовсе — `gitcmd.show` в продакшн-коде
принципиально не откатывается на диск (SPEC T031, AC-1/AC-2,
докстринг `gitcmd.show`: «ветка — источник истины БЕЗ отката на
дерево»), это существующий, не мой, инвариант, ослаблять который я не
вправе (principle целостности) и не должен (не входит в SPEC этой
задачи).

Установленный приём для этого класса песочниц —
`tests/sandbox.py::disk_backed_show`/`disk_backed_ls_tree_files`,
уже применяемый `tests/test_auto_cycle.py::AutoCycleTest` (строки
186-194, комментарий там прямо называет причину: «`foreign=True` —
FSM читает SPEC/PLAN/REVIEW через `gitcmd.show`/`gitcmd.
ls_tree_files`, заглушенный выше `fake_git` вернул бы [пусто]»).
Соседний тест этого же файла, `Ac18...` (строки 56-76), обошёл ту же
проблему иначе — переопределил сам `fsm.cmd_advance` на прямой вызов
`store.set_state`, явно объяснив это в докстринге как «не
завязываться на конкретный гейт-путь». Для `test_ac19_manual_advance`
это же решение не годится буквально (тест обязан звать НАСТОЯЩИЙ
`fsm.cmd_advance`, не подмену, — так велит докстринг класса, строки
16-23), а вариант с `disk_backed_show` требует правки `_sandbox.py`.

Ссылка в докстрине теста (строки 27-32) на
`tasks/T034/acceptance_tests/test_auto_guard_refusal.py::
Ac4NonGuardStateKeepsRunningTest::
test_ac4_valid_ready_plan_still_advances_the_task` как на образец
«того же минимального набора патчей» — стала неактуальной: тот тест
из T034 предшествует A7 (`artifact_source.resolve` тогда возвращал
`foreign` по факту чекаута, не безусловно) и сегодня сам красен по
не связанной причине (`self.TASK = "T001"` — отменённый T094 формат
id; прогнал отдельно: `SystemExit: Задача T001 не найдена`) — не
регресс этой задачи, само T034 не входит в `tests/` (историческая
песочница вне гоняемого набора), но как образец для копирования он
недостоверен.

Я НЕ правил `_sandbox.py` и файлы `test_*.py` каталога
`acceptance_tests/` — это правка залоченного артефакта (T023
требование 5), вне полномочий роли `developer`; не пытался обойти
инвариант «ветка — источник истины» в продакшн-коде (`gitcmd.show`,
`fsm._read_branch_text_or_refuse`) — единственный альтернативный путь
сделать тест зелёным без правки теста, и он запрещён принципом
целостности плюс вне зоны этой задачи (SPEC «Не входит» не упоминает
`gitcmd.py`/`artifact_source.py`).

### Блокирует

Гейт `review → verifying` этой же задачи: на нём оркестратор
прогоняет `tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/`
целиком (T023 требование 6) — с текущим состоянием файла прогон будет
красным на этом одном тесте, переход откажет. Ревьюверу и Оператору
стоит решить вопрос выше ДО итерации ревью, а не после красного
прогона на гейте.
