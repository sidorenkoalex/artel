---
task: 01M4MQAGRWMWR0GFDM9086P3TD
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm_advance.py, orchestrator/config.py, orchestrator/brief.py, orchestrator/auto.py, orchestrator/catalog.py, orchestrator/fsm.py, orchestrator/advance_gates/, scripts/guard.py, docs/codebase-map.md, tests/, orchestrator/runner.py, orchestrator/role_prompt.py, orchestrator/artel.py, orchestrator/zone_lock.py, orchestrator/merge_after.py, orchestrator/report.py, orchestrator/canary.py
budget_usd: 85
---

# SPEC: Аудит SPEC — шаг spec_auditor между сдачей SPEC и spec_gate (ADR-0022 п.2–3)

## Контекст
ADR-0022 (`docs/adr/0022-handoff-audit.md`, принят 11.10.2026) вводит
независимую проверку SPEC до гейта: сегодня SPEC аналитика проверяет
только сессия Оператора на `spec_gate`, делящая допущения с ТЗ, которое
она же писала. Переход `spec_writing → spec_gate` сегодня один `advance`
(`orchestrator/fsm_advance.py::spec_writing`, ~86–172: батч вопросов →
guard → `budget.apply_spec_budget` → `set_state(..., "spec_gate")`).
Задача вводит между ними агентский шаг роли `spec_auditor` с артефактом
`SPEC-AUDIT.md`, глубиной разбора по сигналам SPEC, возвратом аналитику
по `fail` (по образцу `changes_requested` ревью), вердиктом на гейте и
командой повторного аудита. Решения Оператора по батчу вопросов —
`tasks/01M4MQAGRWMWR0GFDM9086P3TD/ANSWER-1.md` (11.10.2026): новое
состояние в `config.STATE_ROLE`; аудит у задач с `TZ.md`; расширение зон;
модель аудитора по ярусу strong; требование 9 ТЗ — отдельной задачей.

Ниже новое состояние называется `spec_audit` (роль `spec_auditor`),
артефакт — `tasks/<id>/SPEC-AUDIT.md`, флаг `approve` — `--accept-audit-fail`,
команда повторного аудита — `artel.py spec-audit <id>`.

## Требования

1. **Состояние аудита.** В FSM появляется агентское состояние
   `spec_audit`: `config.STATE_ROLE["spec_audit"] == "spec_auditor"`.
   Роль шага резолвится через `STATE_ROLE` — особого случая роли вне
   `STATE_ROLE` (как у `analyst` в `runner.step_role`) не заводится
   (ANSWER-1 п.1).
2. **Вход в аудит.** Задача, у которой есть `tasks/<id>/TZ.md` (флоу
   аналитика), при `advance` из `spec_writing` с `SPEC.md status: ready` и
   чистым guard переходит в `spec_audit`, а не в `spec_gate`; иного пути
   из `spec_writing` в `spec_gate` у такой задачи нет, без исключений по
   размеру задачи и проекту. Задача без `TZ.md` (SPEC пишет Оператор) идёт
   `spec_writing → spec_gate` как сегодня (ANSWER-1 п.2); аудит для неё —
   командой Оператора (требование 12).
3. **Прежние проверки входа не меняются.** Батч вопросов (`QUESTIONS.md` —
   эскалация раньше статуса SPEC), проверка грязного дерева, guard SPEC и
   их порядок на выходе из `spec_writing` остаются прежними по смыслу;
   меняется только целевое состояние перехода для задачи с `TZ.md`.
4. **Бюджет из SPEC.** `budget.apply_spec_budget` применяется на переходе
   `spec_writing → spec_audit`, до первого шага аудитора: шаг аудита идёт
   под потолком SPEC, а не под потолком по умолчанию. Повторное применение
   на `approve` гейта SPEC сохраняется.
5. **Роль `spec_auditor`.** Запись роли в `roles.yaml` (приложением PLAN,
   в том же мерже, что ключ `STATE_ROLE`): `executor: agent`,
   `model_tier: strong`, скилы `conventions-core`, `escalation-rules`,
   `spec-audit`. Модель и провайдер резолвятся как у прочих ролей: без
   записи `spec_auditor` в наборе моделей — по ярусу `strong`, в том числе
   в наборе `codex-all`, где аналитик на другой модели; модель аналитика
   не наследуется. Смена модели аудитора — только записью `spec_auditor`
   в набор моделей (ANSWER-1 п.4).
6. **Бриф аудитора.** Миссия шага аудитора непуста
   (`orchestrator/role_prompt.py` собирает её для роли `spec_auditor`). Бриф несёт: `TZ.md`,
   `SPEC.md`, каждый `ANSWER-n.md` задачи, карту кодовой базы, скилы роли;
   рабочий каталог шага — рабочая копия кода задачи. Бриф не несёт
   `QUESTIONS.md`, логов шагов агентов и иных артефактов задачи сверх
   перечисленных (черновики и переписка аналитика). Повторный аудит после
   возврата получает текущий `SPEC.md` целиком.
7. **Глубина по сигналам.** На входе в `spec_audit` пульт вычисляет
   сигналы глубины по SPEC, ТЗ и ANSWER задачи:
   а) раздел SPEC «Меняемое поведение» непуст;
   б) в каком-либо `ANSWER-n.md` задачи есть строка мандата («Ослабление
      тестов разрешено», «Расширение зон разрешено»);
   в) зоны SPEC или пути, названные в его требованиях, касаются `tests/`,
      защищённых путей (`config.is_protected_path`), гейтов
      (`orchestrator/advance_gates/`, `gates.yaml`), лимитов или песочницы
      ролей, либо SPEC требует приложения PLAN; перечень путей-признаков —
      именованной константой `orchestrator/config.py`;
   г) `budget_usd` SPEC ≥ 45 (порог — именованной константой);
   д) `TZ.md` ссылается на ADR (`ADR-NNNN`).
   Есть хоть один сигнал — бриф аудитора требует полного разбора разделов
   а–ж требования 8; нет — краткого (вердикт и отклонения). Перечень
   сработавших сигналов (или «нет») пишется записью журнала задачи на входе
   в `spec_audit` и попадает в бриф аудитора; аудитор переносит его в
   `SPEC-AUDIT.md`.
8. **Артефакт `SPEC-AUDIT.md`.** Шаблон `templates/SPEC-AUDIT.md`
   (приложением PLAN). guard знает тип артефакта `spec_audit`: статусы
   `draft` | `ready`; обязательные разделы — «ТЗ и SPEC» (а: соответствие в
   обе стороны), «Факты против кода» (б), «Проверяемость критериев» (в:
   каждый `AC-n` и ловимая мутация), «Зоны» (г: права записи, песочница,
   защищённые пути), «Матрица неослабления» (д: форма
   `docs/operator-gates.md`), «Пути обхода гейтов» (е), «Вердикт» (ж:
   перечень отклонений со ссылками файл:строка); обязательные поля
   frontmatter — `verdict` со значением из `pass` | `concerns` | `fail` и
   `signals` (сработавшие сигналы требования 7 или `нет`). guard отказывает
   артефакту без любого из разделов, без поля `verdict` или с иным его
   значением.
9. **Выход из аудита.** `advance` из `spec_audit` продвигает задачу только
   по `SPEC-AUDIT.md` со `status: ready`, чистым guard и написанному в
   текущем визите `spec_audit` (аудит прошлого визита задачу не
   продвигает): `pass` и `concerns` → `spec_gate`; `fail` → `spec_writing`
   (возврат аналитику), не более двух возвратов по `fail` на задачу;
   третий `fail` → `spec_gate` с вердиктом аудита. `SPEC-AUDIT.md` не
   ready или guard не чист — задача остаётся в `spec_audit` с отказом
   класса «роль ещё не закончила» / guard соответственно.
10. **Бриф возврата.** Возврат `spec_audit → spec_writing` — триггер раздела
    «Причина возврата» брифа аналитика (`orchestrator/brief.py`,
    `_RETURN_TRIGGER_STATES_BY_TARGET`): бриф продолжения несёт вердикт и
    отклонения `SPEC-AUDIT.md`. Первый, штатный вход аналитика раздела не
    получает (как сегодня).
11. **Вердикт на гейте.** У задачи с аудитом `show` выводит последний
    вердикт, число возвратов по `fail` и сработавшие сигналы; `status`
    показывает последний вердикт у задачи на `spec_gate`; остановка `auto`
    на `spec_gate` называет последний вердикт. `approve` на `spec_gate` при
    последнем вердикте `fail` без нового аудита отказывает с текстом,
    называющим флаг `--accept-audit-fail`; с флагом — проход и запись
    журнала о принятии `fail` Оператором. Флаг вне `spec_gate` отказывает
    (по образцу `--no-answer`). Задача без аудита (`spec_gate` без
    `SPEC-AUDIT.md`) проходит `approve` как сегодня.
12. **Повторный аудит командой Оператора.** `artel.py spec-audit <id>`
    переводит задачу из `spec_gate` в `spec_audit` с записью журнала;
    дальше — по требованиям 4, 6, 7, 9 (в том числе для задачи без
    `TZ.md`). Вне `spec_gate` команда отказывает, состояние не меняется.
13. **Состояние в перечнях пульта.** `spec_audit` входит в
    `zone_lock.LATER_STATES` (задача на аудите видна в прогнозе очереди
    зон), `merge_after.STATUS_DECLARED_STATES`, перечень состояний
    `orchestrator/report.py` (~41). Иные перечни состояний, требующие его по
    смыслу (`catalog`, `auto`), — тоже.
14. **Канарейка.** Прогон канарейки проходит `spec_audit` тем же кодом
    (`auto`), её автоматический `spec_gate` срабатывает после аудита; если
    `orchestrator/canary.py` перечисляет состояния — правка там.
15. **Свипы инвариантов.** `spec_audit` дописан в `FSM_STATES`
    `tests/test_invariants.py` (~75, приложением PLAN) и
    `tests/test_auto_cycle.py` (~63).
16. **Ослабления нет.** Существующие гейты и проверки `spec_writing →
    spec_gate` (guard, батч вопросов, бюджет из SPEC) не меняются по
    смыслу; смена ожиданий существующих тестов — только перечнем раздела
    «Меняемое поведение».

## Критерии приёмки

AC-1. `config.STATE_ROLE["spec_audit"] == "spec_auditor"`, `runner.step_role`
задачи в `spec_audit` возвращает `spec_auditor`, `roles.yaml` (с приложением
PLAN) несёт роль `spec_auditor` с `executor: agent`, `model_tier: strong` и
скилом `spec-audit`.

AC-2. Песочница: задача с `TZ.md`, `SPEC.md status: ready`, guard чист —
`advance` переводит её в `spec_audit`, не в `spec_gate`; мутация «аудит
пропущен» (переход сразу в `spec_gate`) ловится.

AC-3. Песочница: задача без `TZ.md` с `SPEC.md status: ready` —
`advance` переводит её в `spec_gate`, как сегодня.

AC-4. Песочница: задача с `TZ.md` и `QUESTIONS.md` эскалируется из
`spec_writing` как сегодня (в `spec_audit` не уходит); SPEC без AC-разметки
отказан guard'ом и остаётся в `spec_writing`.

AC-5. На переходе `spec_writing → spec_audit` потолок задачи равен
`budget_usd` SPEC (не значению по умолчанию) до первого шага аудитора;
`approve` на `spec_gate` по-прежнему применяет `budget_usd` SPEC.

AC-6. Под набором моделей `codex-all` без записи `spec_auditor` роль
`spec_auditor` резолвится в модель `claude-opus-5-5` провайдера `claude`,
а не в модель аналитика набора.

AC-7. Бриф/миссия шага `spec_auditor` непусты и содержат `TZ.md`, `SPEC.md`,
каждый `ANSWER-n.md` задачи и карту кодовой базы; при лежащих в задаче
`QUESTIONS.md` и логе шага агента их содержимое в бриф не попадает.

AC-8. SPEC с непустым «Меняемое поведение» — бриф аудитора требует полного
разбора а–ж, журнал на входе в `spec_audit` называет сработавший сигнал;
SPEC без единого сигнала требования 7 — бриф требует краткого разбора,
журнал пишет «нет».

AC-9. Каждый из сигналов б–д требования 7 по отдельности (мандат в ANSWER;
зона `tests/` или защищённый путь; `budget_usd` 45 при 44 без сигнала;
`ADR-0022` в ТЗ) переключает бриф на полный разбор и называется в журнале.

AC-10. guard: `SPEC-AUDIT.md` со всеми разделами и `verdict: pass` валиден;
без любого одного обязательного раздела — отказ; без поля `verdict` или с
`verdict` вне `pass`/`concerns`/`fail` — отказ; шаблон
`templates/SPEC-AUDIT.md` (приложение) проходит guard после заполнения.

AC-11. `advance` из `spec_audit` с `SPEC-AUDIT.md` `verdict: pass` → `spec_gate`;
`verdict: concerns` → `spec_gate`; `SPEC-AUDIT.md` не ready — задача
остаётся в `spec_audit`.

AC-12. `verdict: fail` дважды → два возврата в `spec_writing`; третий `fail`
→ `spec_gate`; бриф аналитика после каждого возврата несёт раздел «Причина
возврата» с отклонениями из `SPEC-AUDIT.md`; первый вход аналитика этого
раздела не несёт.

AC-13. После возврата по `fail` и повторной сдачи SPEC `SPEC-AUDIT.md`
прошлого визита (`verdict: pass`) задачу из `spec_audit` не продвигает.

AC-14. `show` задачи с аудитом выводит последний вердикт, число возвратов и
сигналы; `status` у задачи на `spec_gate` показывает вердикт; остановка
`auto` на `spec_gate` называет вердикт.

AC-15. `approve` на `spec_gate` при последнем вердикте `fail` без флага —
отказ с именем флага `--accept-audit-fail`, состояние не меняется; с флагом
— проход и запись журнала; флаг в ином состоянии — отказ; `approve` задачи
без `SPEC-AUDIT.md` на `spec_gate` проходит без флага.

AC-16. `artel.py spec-audit <id>` на `spec_gate` переводит задачу в
`spec_audit` с записью журнала (в том числе задачу без `TZ.md`); вне
`spec_gate` — отказ, состояние не меняется.

AC-17. Задача в `spec_audit` с зоной, пересекающей зону другой задачи,
видна в прогнозе очереди зон (`zone_lock`); `spec_audit` входит в
`merge_after.STATUS_DECLARED_STATES` и перечень состояний `report`.

AC-18. Канарейка: прогон с задачей с `TZ.md` проходит `spec_audit` и
автоматический гейт SPEC после него.

## Меняемое поведение

Сверка по `tests/` (база de280309): из задач с `TZ.md`, проходящих
настоящий переход из `spec_writing`, `spec_gate` сразу ждёт один метод —
`auto` теперь запускает аналитика и аудитора (фейк второго вызова пишет
`SPEC-AUDIT.md` с `verdict: pass`), состояние и текст остановки прежние.

- `tests/test_analyst_role.py::AutoAnalystTest::test_auto_runs_analyst_and_stops_at_spec_gate`: `cmd_run.call_count == 1` → `cmd_run.call_count == 2` (требование 2)

Дополнение кортежей `FSM_STATES` (`tests/test_invariants.py` ~75,
`tests/test_auto_cycle.py` ~63) — расширение свипов, не смена ожидания
метода (требование 15).

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны ≥ 5 (16 элементов зоны); критериев
приёмки ≥ 10 (18); `budget_usd` ≥ 60 (85); зона задевает механизм записей
`docs/invariants.md` (машина состояний, `tests/test_invariants.py`).

Деление решено Оператором (ANSWER-1 п.5, вариант B): требование 9 ТЗ
(матрица последствий в `templates/QUESTIONS.md` и `skills/spec-authoring.md`)
вынесено отдельной задачей сразу после этой — см. «Не входит». Оставшаяся
механика — материал для обоснования монолита: новое состояние в
`STATE_ROLE`, роль в `roles.yaml`, вход/выход аудита, возврат по `fail`,
вердикт и флаг `approve` на гейте — одна атомарная смена маршрута
`spec_writing → spec_gate`. Часть без выхода по `fail` или без вердикта на
гейте оставила бы задачи застрявшими в `spec_audit` либо пропускала бы
`fail` на гейт молча; ключ `STATE_ROLE` без записи роли в `roles.yaml`
красит `tests/test_roles_map_fixture.py`. Рамка — $85 (ТЗ, ANSWER-1 п.5).

## Не входит

- Требование 9 ТЗ — матрица последствий по вариантам в QUESTIONS аналитика
  (`templates/QUESTIONS.md`, `skills/spec-authoring.md`): отдельная задача
  сразу после этой (ANSWER-1 п.5).
- Проверка матрицы в `answer` (строка бэклога 11.10, отдельная задача;
  `orchestrator/answer.py` — только чтение).
- Канарейка-ловушка с дефектным SPEC (ADR-0022 п.4 плана, после этой
  задачи).
- Выбор другой модели для аудитора и наследование модели аналитика
  (ANSWER-1 п.4); правка `models.yaml`, `model_sets.yaml`.
- Аудит ТЗ и PLAN.
- Аудит SPEC задачи без `TZ.md` автоматически (ANSWER-1 п.2) — только
  командой Оператора (требование 12); уточнение ADR-0022 пп.3, 6 вносит
  Оператор документом.
- Полный зелёный набор `tests/`, зелёный CI ветки, неизменность защищённых
  путей и непревышение бюджета — их держит пульт.
- Только чтение: `orchestrator/answer.py`, `orchestrator/providers/`,
  `orchestrator/canary_drive.py`, `orchestrator/store.py`,
  `orchestrator/schema.py`, `orchestrator/budget.py`,
  `orchestrator/acceptance.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/fsm_postmerge.py`, `orchestrator/retro.py`,
  `orchestrator/snapshot.py`, `orchestrator/suite_run.py`,
  `orchestrator/suite_lock.py`, `.github/workflows/ci.yml`,
  `docs/invariants.md`, `docs/adr/`, `docs/roadmap.md`, `docs/backlog.md`,
  `docs/operator-session.md`, `docs/operator-gates.md`, `CLAUDE.md`,
  `models.yaml`, `model_sets.yaml`, `targets.yaml`, `.artel/`.
  `tests/test_invariants.py` — только приложением PLAN и только
  дополнением `FSM_STATES` (требование 15).

## Материалы

- ТЗ: `tasks/01M4MQAGRWMWR0GFDM9086P3TD/TZ.md`; ответ Оператора:
  `tasks/01M4MQAGRWMWR0GFDM9086P3TD/ANSWER-1.md`.
- `docs/adr/0022-handoff-audit.md` — п.2 (разделы а–ж), п.3 (сигналы), п.6
  (модель); `docs/operator-gates.md` — «Матрица неослабления» (~53).
- Приложениями PLAN (защищённые пути): `roles.yaml` (роль
  `spec_auditor`), `templates/SPEC-AUDIT.md`, `skills/spec-audit.md`,
  `tests/test_invariants.py` (`FSM_STATES`, ~75).
- Опоры в коде: `orchestrator/fsm_advance.py::spec_writing` (~86–172);
  `orchestrator/config.py` `STATE_ROLE` (~792), `AUTO_STOP` (~820),
  `PROTECTED_PATHS`/`is_protected_path` (~744–757);
  `orchestrator/runner.py::step_role` (~95);
  `orchestrator/brief.py` `_RETURN_TRIGGER_STATES_BY_TARGET` (~62);
  `orchestrator/fsm.py` `NO_ANSWER_FLAG` (~84), `_cmd_approve` (~1340);
  `orchestrator/artel.py::_approve_no_answer_arg` (~1647);
  `orchestrator/zone_lock.py` `LATER_STATES` (~118);
  `orchestrator/merge_after.py` `STATUS_DECLARED_STATES` (~58);
  `orchestrator/report.py` (~41); `orchestrator/canary.py` (~1709,
  `_pass_spec_gate`); `orchestrator/advance_gates/review.py`
  (`_review_rework_gate` — прецедент счётчика возвратов);
  `orchestrator/advance_gates/mandate.py` (строки мандата);
  `tests/test_roles_map_fixture.py` (~50, `PULT_AGENT_ROLES`).
