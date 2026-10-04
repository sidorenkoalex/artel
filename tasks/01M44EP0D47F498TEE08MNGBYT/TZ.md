---
task: 01M44EP0D47F498TEE08MNGBYT
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Порядок мержей по зависимостям задач: поле merge_after

# ТЗ: порядок мержей по зависимостям задач, а не по приходу на гейт мержа

Источник: бэклог, строка «Порядок мержей по зависимостям, не по приходу»
(приоритет 1, $35; поглощает строку копилки 06.09 «порядок из ТЗ/SPEC
пульт не исполняет»); прецедент 13.09 (инвариант из приложения
01M2CN465W закоммичен в main раньше мержа фикса — набор красен до мержа,
другие мержи волны заблокированы). Решение Оператора 05.10 «заводи
вторую волну».

Факты (пин 1d2229b7, сверка кода 05.10):
- Поля зависимостей у задачи нет нигде: frontmatter SPEC
  (`templates/SPEC.md`) несёт `zones`, `budget_usd`, `skip_tests`;
  таблица `tasks` (`orchestrator/schema.py` ~114-116, миграции
  `add_column` ~251-266) — `zones`, `zones_extension`,
  `zone_queue_position`, колонки порядка мержа нет.
- Формат SPEC проверяет `scripts/guard.py` (без доступа к БД):
  `SUPPORTED_SCHEMA_VERSION = 5` (~69, история версий ~40-68),
  `spec_zones_errors` (~2496) и `spec_budget_field_errors` (~2550)
  вызываются из общей проверки (~3033-3034). Поле `Порядок:` уже
  разбирается в подразделах «## Деление» (`parse_division_subsections`
  ~2601-2645), но остаётся только текстом `TZ.md` подзадачи
  (`orchestrator/fsm.py::_spawn_division_subtasks` ~775-795 его не
  читает).
- Переход `spec_writing -> spec_gate` — `orchestrator/fsm_advance.py::
  spec_writing` (~83-172): guard SPEC и `budget.apply_spec_budget`
  (~163-167) до смены состояния. Значения SPEC в БД пишет `approve` на
  гейте SPEC — `orchestrator/fsm.py::_approve_spec_gate` (~831-925):
  сверка путей с зонами и отказ «approve отклонён» мягким `return`
  (~865-870), запись `zones=meta.get("zones")` (~875), перечитывание
  бюджета (~887).
- Однократная переоценка из PLAN — `fsm_advance._apply_plan_budget`
  (~482-536), вызов на переходе `in_dev -> verifying` (~625); образец
  записи значения из PLAN с журналом «применён/не применён».
- Строки мандатов Оператора в ANSWER-n.md: маркеры
  `orchestrator/advance_gates/mandate.py` (~28-42, `MANDATE_MARKERS` —
  ровно два вида), разбор `elements` (~65), проверка элементов при
  записи ответа `refusals` (~172), потребитель — `orchestrator/
  answer.py` (~66-147).
- Гейт мержа: `fsm.py::_approve_merge_gate` (~1019-1032) зовёт
  `orchestrator/fsm_merge_gate.py::_cmd_approve_merge_gate_cycle`
  (~1202-1288): `merge_lock.acquire` и при занятом окне
  `merge_queue.wait_for_window` (~1263-1265) — ДО тела гейта
  `_cmd_approve_merge_gate` (~1110-1199). Очередь `orchestrator/
  merge_queue.py` — FIFO по времени входа (`_head_task_id` ~43-47),
  о смысловом порядке задач не знает; отказы тела — журнал «merge
  FAILED»/«merge отклонён» и `sys.exit` с подсказкой `approve <id>`.
- `status` — `orchestrator/catalog.py::cmd_status` (~825-856): добавки
  в конец строки `_zone_wait_suffix` (~709-737, вычисляется заново из
  БД через `zone_lock.blocking_conflict`, вид «[ждёт зоны <путь>: занята
  <id> (<состояние>)…]») и `merge_queue.wait_suffix` (~84-96, «[ждёт
  merge-окна: …]»).
- Терминальные состояния — `orchestrator/cleanup.py::TERMINAL_STATES`
  = ("done", "killed") (~337). Префикс id разрешает
  `orchestrator/store.py::resolve_task_id` (~806-832).
- Защищённые пути — `orchestrator/config.py::PROTECTED_PATHS` (~694-700):
  шаблоны, скилы, `tests/test_invariants.py` и др.;
  `scripts/guard.py` и `orchestrator/` в перечень не входят.

Требуется:
1. SPEC несёт необязательное frontmatter-поле `merge_after` — список id
   задач через запятую либо пусто (нет поля — нет зависимостей). guard
   проверяет только форму (элементы — id задач, без повторов, не id
   самой задачи); SPEC решает, нужна ли для этого новая
   `schema_version`, и сохраняет валидность всех существующих SPEC.
2. Гейт SPEC (`approve` на `spec_gate`; SPEC решает, проверять ли ещё
   на `spec_writing -> spec_gate`) отказывает именованно, если задача
   из `merge_after` не существует, неоднозначна по префиксу, в
   состоянии `killed`, принадлежит другому target, или зависимости
   образуют цикл. Иначе значение пишется в БД тем же моментом, что
   `zones`, полными id; отказ — задача остаётся на `spec_gate`.
3. Переписать поле вправе только три канала, каждый с обоснованием и
   записью журнала «было → стало»: PLAN (frontmatter `merge_after` при
   переходе `in_dev -> verifying`, по образцу `_apply_plan_budget`;
   обоснование — в разделе «Влияние на систему»), эскалация роли
   (вопрос в QUESTIONS/эскалации предлагает новое значение) и `answer`
   Оператора (строка мандата нового вида в ANSWER-n.md, проверяемая
   при записи ответа тем же узлом `mandate.refusals`). Новое значение
   проходит те же проверки, что в п. 2.
4. `approve` на `merge_gate` ДО взятия мьютекса merge-окна и входа в
   `merge_queue` отказывает, пока хоть одна задача из `merge_after` не
   `done`: журнал задачи и печать называют каждую ожидаемую задачу с её
   состоянием и подсказку повтора; окно и очередь не занимаются, задача
   остаётся на `merge_gate`. Задача из списка в `killed` — отдельный
   именованный отказ с указанием канала снятия зависимости (п. 3), а не
   вечное ожидание. Без зависимостей поведение гейта и очереди прежнее
   (`merge_queue` остаётся только взаимным исключением окна).
5. `status` показывает ожидание добавкой в конец строки тем же
   способом, что `_zone_wait_suffix`: вычисляется из БД на каждый вызов,
   вид «[ждёт мержа: <id> (<состояние>), …]», только пока есть
   незавершённые зависимости. SPEC решает, в каких состояниях задачи
   добавка печатается (как минимум `acceptance` и `merge_gate`) и
   выводит ли `show <id>` поле целиком.
6. `docs/codebase-map.md` описывает поле, место проверки и место отказа.
7. Тесты в `tests/` с заявками «Ловит мутацию» на пп. 1–5, в том числе:
   несуществующая, убитая, собственная и циклическая зависимость —
   отказ гейта SPEC; `merge_gate` при зависимости не в `done` —
   отказ без захвата мьютекса и без записи в `merge_queue`; при всех
   зависимостях в `done` и без поля — merge идёт прежним путём; PLAN и
   мандат ANSWER меняют значение с записью журнала, неверное значение
   отвергается; добавка `status`. Существующие тесты не ослабляются.

Зоны: orchestrator/, scripts/guard.py, tests/, docs/codebase-map.md.

Приложением: templates/SPEC.md — закомментированное поле
`merge_after` с пояснением по образцу `zones`/`budget_usd`;
templates/PLAN.md — закомментированное поле `merge_after` с правилом
обоснования (если SPEC выберет канал PLAN через frontmatter);
skills/spec-authoring.md — правило аналитику: заполнять `merge_after` из
ТЗ («Порядок: после …») и не изобретать зависимостей без основания;
skills/escalation-rules.md — как роль предлагает смену `merge_after`
(если SPEC сочтёт нужным).

Только чтение (не менять): docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, CLAUDE.md, models.yaml, roles.yaml,
.github/workflows/ci.yml, conftest.py, tests/test_invariants.py,
docs/invariants.md.

Не входит: зависимость старта developer (предусловие `run` по
`merge_after`, как у лока зон); автоматический разбор строки «Порядок:»
ТЗ командой `new` и подразделов «## Деление»; ожидание зависимости
циклом внутри `approve` (вместо отказа); перестановка FIFO
`merge_queue`; проверка циклов в `doctor`.

Рамка: $40.
