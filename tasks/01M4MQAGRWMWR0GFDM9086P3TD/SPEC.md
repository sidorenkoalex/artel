---
task: 01M4MQAGRWMWR0GFDM9086P3TD
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm_advance.py, orchestrator/config.py, orchestrator/brief.py, orchestrator/auto.py, orchestrator/catalog.py, orchestrator/fsm.py, orchestrator/advance_gates/, scripts/guard.py, docs/codebase-map.md, tests/, orchestrator/runner.py, orchestrator/role_prompt.py, orchestrator/artel.py, orchestrator/zone_lock.py, orchestrator/merge_after.py, orchestrator/report.py, orchestrator/canary.py, docs/stack.md
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

Редакция 2 (возврат со `spec_gate` 11.10.2026 по независимому аудиту
SPEC, вердикт `concerns`): добавлены белый список артефакта
(требование 9), проверка обязательного артефакта шага (требование 10),
свежесть и привязка вердикта к проверенному SPEC (требования 12–13),
вердикт записью журнала (требование 14), разбор флага при позиционном
`sha` (требование 16), канарейка при последнем `fail` (требование 19),
семантика счётчика возвратов и эскалация аудитора (требования 11, 15),
раздел «Матрица неослабления».

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
   командой Оператора (требование 17).
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
   (`orchestrator/role_prompt.py` собирает её для роли `spec_auditor`).
   Бриф несёт: `TZ.md`, `SPEC.md`, каждый `ANSWER-n.md` задачи, карту
   кодовой базы, скилы роли, sha версии `SPEC.md`, взятой на аудит
   (требование 13), и перечень сработавших сигналов (требование 7);
   рабочий каталог шага — рабочая копия кода задачи. Бриф не несёт
   `QUESTIONS.md`, логов шагов агентов и иных артефактов задачи сверх
   перечисленных (черновики и переписка аналитика). Повторный аудит после
   возврата получает текущий `SPEC.md` целиком.
7. **Глубина по сигналам.** На входе в `spec_audit` пульт вычисляет
   сигналы глубины по SPEC, ТЗ и ANSWER задачи:
   а) раздел SPEC «Меняемое поведение» непуст;
   б) в каком-либо `ANSWER-n.md` задачи есть строка мандата («Ослабление
      тестов разрешено», «Расширение зон разрешено»);
   в) зоны SPEC или пути, названные в его разделах «Требования» и
      «Критерии приёмки», касаются хотя бы одного признака: тестов
      (`tests/`), гейтов, лимитов, песочницы ролей, защищённых путей
      (`config.is_protected_path`); либо текст SPEC требует приложения
      PLAN (упоминание «приложени… PLAN»). Пути-признаки тестов, гейтов,
      лимитов и песочницы ролей — именованной константой
      `orchestrator/config.py`, сгруппированной по этим четырём
      категориям, ни одна категория не пуста; гейты включают
      `orchestrator/advance_gates/` и `gates.yaml` (как путь-признак:
      сам `gates.yaml` задача не меняет);
   г) `budget_usd` SPEC ≥ 45 (порог — именованной константой);
   д) `TZ.md` ссылается на ADR (`ADR-NNNN`).
   Есть хоть один сигнал — бриф аудитора требует полного разбора разделов
   а–ж требования 8; нет — краткого (вердикт и отклонения). Перечень
   сработавших сигналов (или «нет») пишется записью журнала задачи на входе
   в `spec_audit` и попадает в бриф аудитора; аудитор переносит его в
   поле `signals` `SPEC-AUDIT.md`.
8. **Артефакт `SPEC-AUDIT.md`.** Шаблон `templates/SPEC-AUDIT.md`
   (приложением PLAN). guard знает тип артефакта `spec_audit`: статусы
   `draft` | `ready` | `escalate`; обязательные разделы — «ТЗ и SPEC» (а:
   соответствие в обе стороны), «Факты против кода» (б), «Проверяемость
   критериев» (в: каждый `AC-n` и ловимая мутация), «Зоны» (г: права
   записи, песочница, защищённые пути), «Матрица неослабления» (д: форма
   `docs/operator-gates.md`), «Пути обхода гейтов» (е), «Вердикт» (ж:
   перечень отклонений со ссылками файл:строка); обязательные поля
   frontmatter — `verdict` со значением из `pass` | `concerns` | `fail`,
   `signals` (сработавшие сигналы требования 7 или `нет`) и `spec_sha`
   (sha проверенной версии `SPEC.md`, требование 13). guard отказывает
   артефакту без любого из разделов, без любого из трёх полей, с
   `verdict` вне перечня или с пустым `signals`.
9. **Артефакт не посторонний.** `SPEC-AUDIT.md` входит в белый список
   `.md` первого уровня каталога задачи (`scripts/guard.py`,
   `TASK_ROOT_ALLOWED_MD`, ~1983): автокоммит шага аудитора и проверки
   посторонних файлов каталога задачи (в том числе на гейте мержа) его не
   отвергают. Прочие имена вне списка по-прежнему посторонние.
10. **Обязательный артефакт шага.** Шаг роли `spec_auditor`, завершившийся
    с кодом 0 без `SPEC-AUDIT.md` в каталоге документов задачи, — не
    успех: тот же класс отказа, что у прочих ролей с обязательным
    артефактом (`orchestrator/runner.py`, `_missing_required_artifact`,
    ~1204–1247). Ветка для `spec_auditor` не меняет поведения этой
    проверки для прочих ролей.
11. **Выход из аудита.** `advance` из `spec_audit` продвигает задачу только
    по свежему (требование 12) и привязанному к проверенному SPEC
    (требование 13) `SPEC-AUDIT.md` со `status: ready` и чистым guard:
    `pass` и `concerns` → `spec_gate`; `fail` → `spec_writing` (возврат
    аналитику), не более двух возвратов по `fail` на задачу; `fail` при
    исчерпанных двух возвратах → `spec_gate` с вердиктом аудита.
    `SPEC-AUDIT.md` не ready или guard не чист — задача остаётся в
    `spec_audit` с отказом класса «роль ещё не закончила» / guard
    соответственно. `status: escalate` с разделом «Эскалация» (Вопросы,
    Контекст, Блокирует — как у прочих ролей, `skills/escalation-rules`)
    переводит задачу в `escalated` с возвратом в `spec_audit` после
    ответа Оператора тем же механизмом `escalated_from`, что у прочих
    агентских состояний; правило guard «раздел Эскалация при status не
    escalate» распространяется на тип `spec_audit`.
    Счётчик возвратов по `fail` — число записей журнала задачи о возврате
    `spec_audit → spec_writing` по `fail` за всю жизнь задачи (колонок и
    миграций БД не добавляется: `orchestrator/store.py` и
    `orchestrator/schema.py` — только чтение); его не сбрасывают ни
    `reject` на `spec_gate`, ни команда повторного аудита (требование 17).
12. **Свежесть вердикта.** `SPEC-AUDIT.md` засчитывается на выходе из
    `spec_audit`, только если его последний коммит на артефактной ветке
    задачи — автокоммит шага роли `spec_auditor`, сделанный после
    последнего входа задачи в `spec_audit`. Иначе (файл прошлого визита,
    файл, записанный аналитиком или любой иной ролью) — задача остаётся в
    `spec_audit` с отказом класса «роль ещё не закончила».
13. **Привязка к проверенному SPEC.** Запись журнала на входе в
    `spec_audit` несёт sha версии `SPEC.md` на артефактной ветке в момент
    входа. `advance` из `spec_audit` отказывает (состояние не меняется,
    текст отказа называет оба sha), если `SPEC.md` на артефактной ветке
    отличается от версии входа (SPEC менялся в шаге аудитора) либо
    `spec_sha` в `SPEC-AUDIT.md` не равен sha версии входа.
14. **Вердикт — запись журнала.** Выход из `spec_audit` (в `spec_gate` или
    `spec_writing`) пишет запись журнала задачи с вердиктом, номером
    возврата по `fail` (если это возврат) и сработавшими сигналами.
    `approve`, `show` и `status` берут последний вердикт из журнала, а не
    из файла `SPEC-AUDIT.md`.
15. **Бриф возврата.** Возврат `spec_audit → spec_writing` — триггер раздела
    «Причина возврата» брифа аналитика (`orchestrator/brief.py`,
    `_RETURN_TRIGGER_STATES_BY_TARGET`): бриф продолжения несёт вердикт и
    отклонения `SPEC-AUDIT.md`. Первый, штатный вход аналитика раздела не
    получает (как сегодня).
16. **Вердикт на гейте.** У задачи с аудитом `show` выводит последний
    вердикт, число возвратов по `fail` и сработавшие сигналы; `status`
    показывает последний вердикт у задачи на `spec_gate`; остановка `auto`
    на `spec_gate` называет последний вердикт. `approve` на `spec_gate` при
    последнем вердикте `fail` (после него не было нового входа в
    `spec_audit`) отказывает с текстом, называющим флаг
    `--accept-audit-fail`; с флагом — проход и запись журнала о принятии
    `fail` Оператором. Флаг принимается в обеих формах команды:
    `approve <id> --accept-audit-fail` и `approve <id> <sha>
    --accept-audit-fail` — разбор позиционного `sha`
    (`orchestrator/artel.py::_approve_sha_arg`, ~1658–1668) флаг за `sha`
    не берёт. Флаг вне `spec_gate` отказывает (по образцу `--no-answer`).
    Задача без записи вердикта в журнале проходит `approve` на `spec_gate`
    как сегодня.
17. **Повторный аудит командой Оператора.** `artel.py spec-audit <id>`
    переводит задачу из `spec_gate` в `spec_audit` с записью журнала;
    дальше — по требованиям 4, 6, 7, 11–14 (в том числе для задачи без
    `TZ.md`). Вне `spec_gate` команда отказывает, состояние не меняется.
18. **Состояние в перечнях пульта.** `spec_audit` входит в
    `zone_lock.LATER_STATES` (задача на аудите видна в прогнозе очереди
    зон и в пометке «зона занята» строки `status`),
    `merge_after.STATUS_DECLARED_STATES`, перечень состояний
    `orchestrator/report.py` (~41). Раздел `docs/stack.md` о зонах и
    подтяжке main (~1009, ~1035), перечисляющий состояния
    `LATER_STATES`, называет и `spec_audit`. Иные перечни состояний,
    требующие его по смыслу (`catalog`, `auto`), — тоже.
19. **Канарейка.** Прогон канарейки проходит `spec_audit` тем же кодом
    (`auto`), её автоматический `spec_gate` срабатывает после аудита; если
    `orchestrator/canary.py` перечисляет состояния — правка там. Автогейт
    SPEC канарейки (`canary._pass_spec_gate`, ~1342) обходит
    `cmd_approve`: при последнем вердикте `fail` он проходит гейт и пишет
    запись журнала о принятии `fail` автоматически (эквивалент `approve
    --accept-audit-fail`), отдельную от записи о проходе гейта.
20. **Свипы инвариантов.** `spec_audit` дописан в `FSM_STATES`
    `tests/test_invariants.py` (~75, приложением PLAN) и
    `tests/test_auto_cycle.py` (~63).
21. **Ослабления нет.** Существующие гейты и проверки `spec_writing →
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

AC-6. Фикстура: локальный слой моделей, где ярус `strong` резолвится в
`claude-opus-5-5` провайдера `claude`; набор моделей `codex-all`, где
аналитик на модели провайдера `codex` и записи `spec_auditor` нет. Роль
`spec_auditor` под этим набором резолвится в `claude-opus-5-5` провайдера
`claude`, а не в модель аналитика набора; с записью `spec_auditor` в
наборе — в модель этой записи.

AC-7. Бриф/миссия шага `spec_auditor` непусты и содержат `TZ.md`, `SPEC.md`,
каждый `ANSWER-n.md` задачи, карту кодовой базы и sha версии `SPEC.md`
входа; при лежащих в задаче `QUESTIONS.md` и логе шага агента их
содержимое в бриф не попадает.

AC-8. SPEC с непустым «Меняемое поведение» — бриф аудитора требует полного
разбора а–ж, журнал на входе в `spec_audit` называет сработавший сигнал;
SPEC без единого сигнала требования 7 — бриф требует краткого разбора,
журнал пишет «нет».

AC-9. Каждый из признаков по отдельности (на SPEC, иначе не дающем ни
одного сигнала) переключает бриф на полный разбор и называется в журнале:
мандат в ANSWER (б); по одному пути-признаку из каждой из четырёх
категорий константы требования 7в — тесты, гейты, лимиты, песочница
ролей; защищённый путь в зонах; упоминание приложения PLAN в тексте SPEC
(в); `budget_usd` 45 (при 44 — сигнала нет) (г); `ADR-0022` в ТЗ (д).

AC-10. guard: `SPEC-AUDIT.md` со всеми разделами, `verdict: pass`,
непустым `signals` и `spec_sha` валиден; без любого одного обязательного
раздела — отказ; без поля `verdict`, `signals` или `spec_sha` — отказ;
`verdict` вне `pass`/`concerns`/`fail` — отказ; пустой `signals` — отказ;
шаблон `templates/SPEC-AUDIT.md` (приложение) проходит guard после
заполнения.

AC-11. `guard.is_extraneous_task_root_file("SPEC-AUDIT.md")` — `False`;
песочница: шаг аудитора, оставивший `SPEC-AUDIT.md`, не отвергнут как
оставивший посторонний файл и его автокоммит переносит файл в
артефактную ветку; имя вне белого списка (например `SPEC-AUDIT2.md`)
по-прежнему постороннее.

AC-12. Шаг роли `spec_auditor` с кодом выхода 0 без `SPEC-AUDIT.md` —
не успех (тот же класс отказа, что у `reviewer` без `REVIEW.md`); с
`SPEC-AUDIT.md` в каталоге документов — успех.

AC-13. `advance` из `spec_audit` со свежим `SPEC-AUDIT.md` `verdict: pass`
→ `spec_gate`; `verdict: concerns` → `spec_gate`; `SPEC-AUDIT.md` не
ready — задача остаётся в `spec_audit`; каждый выход пишет запись журнала
с вердиктом.

AC-14. `verdict: fail` дважды → два возврата в `spec_writing`; третий
`fail` → `spec_gate`; бриф аналитика после каждого возврата несёт раздел
«Причина возврата» с отклонениями из `SPEC-AUDIT.md`; первый вход
аналитика этого раздела не несёт.

AC-15. Свежесть: после возврата по `fail` и повторной сдачи SPEC
`SPEC-AUDIT.md` прошлого визита (`verdict: pass`) задачу из `spec_audit`
не продвигает; `SPEC-AUDIT.md` с `verdict: pass`, записанный аналитиком
в шаге `spec_writing`, задачу из `spec_audit` не продвигает.

AC-16. Привязка: `SPEC.md`, изменённый на артефактной ветке в шаге
аудитора, — `advance` из `spec_audit` отказывает, состояние не меняется,
текст отказа называет оба sha; `spec_sha` в `SPEC-AUDIT.md`, не равный
sha версии входа, — отказ так же; совпадающие — проход.

AC-17. Счётчик: после двух возвратов по `fail` `reject` на `spec_gate`
(возврат аналитику) и новый `fail` аудита ведут задачу в `spec_gate`, не в
`spec_writing`; после двух возвратов `artel.py spec-audit <id>` и новый
`fail` — так же в `spec_gate`.

AC-18. `SPEC-AUDIT.md` со `status: escalate` и разделом «Эскалация» —
`advance` переводит задачу в `escalated` с `escalated_from = spec_audit`;
после ответа Оператора задача возвращается в `spec_audit`. `SPEC-AUDIT.md`
с непустыми «Вопросы» при `status: ready` — отказ guard.

AC-19. `show` задачи с аудитом выводит последний вердикт, число возвратов
и сигналы; `status` у задачи на `spec_gate` показывает вердикт; остановка
`auto` на `spec_gate` называет вердикт; вердикт берётся из журнала:
`SPEC-AUDIT.md` на диске с другим `verdict` вывод не меняет.

AC-20. `approve` на `spec_gate` при последнем вердикте `fail` в журнале
без флага — отказ с именем флага `--accept-audit-fail`, состояние не
меняется; `approve <id> --accept-audit-fail` и `approve <id> <sha>
--accept-audit-fail` — проход и запись журнала о принятии `fail`, `sha` во
второй форме разобран как `sha`; флаг в ином состоянии — отказ; `approve`
задачи без записи вердикта в журнале на `spec_gate` проходит без флага.

AC-21. `artel.py spec-audit <id>` на `spec_gate` переводит задачу в
`spec_audit` с записью журнала (в том числе задачу без `TZ.md`); вне
`spec_gate` — отказ, состояние не меняется.

AC-22. Задача в `spec_audit` с зоной, пересекающей зону другой задачи,
видна в прогнозе очереди зон (`zone_lock`) и получает пометку «зона
занята» в `status`; `spec_audit` входит в
`merge_after.STATUS_DECLARED_STATES` и перечень состояний `report`.

AC-23. Канарейка: прогон с задачей с `TZ.md` проходит `spec_audit` и
автоматический гейт SPEC после него; при последнем вердикте `fail`
автогейт SPEC канарейки проходит гейт и пишет запись журнала о
принятии `fail` автоматически.

## Меняемое поведение

Сверка по `tests/` (база de280309): из задач с `TZ.md`, проходящих
настоящий переход из `spec_writing`, `spec_gate` сразу ждёт один метод —
`auto` теперь запускает аналитика и аудитора (фейк второго вызова пишет
`SPEC-AUDIT.md` с `verdict: pass`), состояние и текст остановки прежние.

- `tests/test_analyst_role.py::AutoAnalystTest::test_auto_runs_analyst_and_stops_at_spec_gate`: `cmd_run.call_count == 1` → `cmd_run.call_count == 2` (требование 2)

Свипы по `zone_lock.LATER_STATES` — ожидания методов не меняются, меняется
только состав перебираемых состояний (требование 18):
`tests/test_catalog_zone_overlap.py` (~439,
`test_pre_dev_states_get_the_zone_taken_suffix` — ждёт ту же добавку
«зона занята» и для `spec_audit`) и `tests/test_stack_zones_pull_section.py`
(~63 — ждёт имя каждого состояния в разделе `docs/stack.md`, отсюда
правка документа в зоне). Дополнение кортежей `FSM_STATES`
(`tests/test_invariants.py` ~75, `tests/test_auto_cycle.py` ~63) —
расширение свипов, не смена ожидания метода (требование 20).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Белый список `.md` каталога задачи расширен на `SPEC-AUDIT.md` (`scripts/guard.py` ~1983) | Посторонний `.md` первого уровня отвергается (`guard.is_extraneous_task_root_file`, ~1987; проверка на гейте мержа и в автокоммите шага) | Остаётся для всех имён, кроме `SPEC-AUDIT.md` | Существующие тесты белого списка + AC-11 (имя вне списка постороннее) | Расширение — новый легальный артефакт, не ослабление |
| Маршрут `spec_writing → spec_gate` для задачи с `TZ.md` идёт через `spec_audit` (`fsm_advance.py::spec_writing` ~171) | Guard SPEC, батч вопросов, бюджет из SPEC до гейта | Остаётся, порядок прежний | AC-4, AC-5 | Добавлен шаг проверки, прежние проверки не тронуты |
| Ожидание `test_auto_runs_analyst_and_stops_at_spec_gate`: 1 → 2 вызова `cmd_run` | `auto` доводит задачу аналитика до `spec_gate` и там останавливается | Остаётся (состояние и текст остановки прежние) | Тот же метод с новым числом; AC-2 | Смена ожидания из-за нового шага, не ослабление |
| `approve` на `spec_gate` получает отказ при последнем `fail` и флаг `--accept-audit-fail` | Разбор позиционного `sha` (`artel.py::_approve_sha_arg` ~1658) | Остаётся: флаг за `sha` не берётся | AC-20 (обе формы) | Ужесточение гейта |
| Автогейт SPEC канарейки при последнем `fail` (`canary._pass_spec_gate` ~1342) | Канарейка проходит гейт SPEC автоматически | Остаётся; принятие `fail` видно записью журнала | AC-23 | Канарейка не мержится; запись журнала — наблюдаемость |
| `LATER_STATES`, `STATUS_DECLARED_STATES`, `FSM_STATES` дополнены `spec_audit` | Прогноз очереди зон, пометка «зона занята», `merge_after` в `status`, свипы инвариантов | Остаётся и распространяется на новое состояние | `tests/test_catalog_zone_overlap.py` ~439, `tests/test_stack_zones_pull_section.py` ~63, AC-22 | Расширение свипов |

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны ≥ 5 (18 элементов зоны); критериев
приёмки ≥ 10 (23); `budget_usd` ≥ 60 (85); зона задевает механизм записей
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
красит `tests/test_roles_map_fixture.py`; состояние без белого списка
артефакта и проверки свежести дало бы шаг, чей вердикт либо отвергнут,
либо подделываем. Рамка — $85 (ТЗ, ANSWER-1 п.5).

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
  командой Оператора (требование 17); уточнение ADR-0022 пп.3, 6 вносит
  Оператор документом.
- `gates.yaml` — только чтение: путь-признак сигнала 7в, сам файл задача
  не меняет.
- `orchestrator/checkpoint.py` — только чтение: исключение `RETRO.md`
  поверх белого списка guard (~55–63) не трогается, `SPEC-AUDIT.md`
  добавляется в сам список guard (требование 9).
- Колонки и миграции БД под счётчик возвратов и вердикт — нет (журнал).
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
  дополнением `FSM_STATES` (требование 20).

## Материалы

- ТЗ: `tasks/01M4MQAGRWMWR0GFDM9086P3TD/TZ.md`; ответ Оператора:
  `tasks/01M4MQAGRWMWR0GFDM9086P3TD/ANSWER-1.md`.
- `docs/adr/0022-handoff-audit.md` — п.2 (разделы а–ж), п.3 (сигналы), п.6
  (модель); `docs/operator-gates.md` — «Матрица неослабления» (~53).
- Приложениями PLAN (защищённые пути): `roles.yaml` (роль
  `spec_auditor`), `templates/SPEC-AUDIT.md`, `skills/spec-audit.md`,
  `tests/test_invariants.py` (`FSM_STATES`, ~75).
- `docs/stack.md` в зонах — прямое следствие ANSWER-1 п.1 (правка
  `zone_lock.LATER_STATES`, ~118) и существующего свипа
  `tests/test_stack_zones_pull_section.py` (~63), требующего имени каждого
  состояния `LATER_STATES` в разделе документа (~1009, ~1035).
- Опоры в коде: `orchestrator/fsm_advance.py::spec_writing` (~86–172);
  `orchestrator/config.py` `STATE_ROLE` (~792), `AUTO_STOP` (~820),
  `PROTECTED_PATHS`/`is_protected_path` (~744–757);
  `orchestrator/runner.py::step_role` (~95), `_missing_required_artifact`
  (~1204–1247); `scripts/guard.py` `TASK_ROOT_ALLOWED_MD` (~1983),
  `escalation_status_errors` (~3160); `orchestrator/brief.py`
  `_RETURN_TRIGGER_STATES_BY_TARGET` (~62); `orchestrator/fsm.py`
  `NO_ANSWER_FLAG` (~84), `_cmd_approve` (~1340), возврат по
  `escalated_from` (~1331); `orchestrator/artel.py::_approve_no_answer_arg`
  (~1647), `_approve_sha_arg` (~1658); `orchestrator/zone_lock.py`
  `LATER_STATES` (~118); `orchestrator/merge_after.py`
  `STATUS_DECLARED_STATES` (~58); `orchestrator/report.py` (~41);
  `orchestrator/canary.py` (`_pass_spec_gate` ~1342, цикл ~1709);
  `orchestrator/artifacts.py::fresh_verdict_iteration` (прецедент
  свежести вердикта); `orchestrator/advance_gates/review.py`
  (`_review_rework_gate` — прецедент возврата);
  `orchestrator/advance_gates/mandate.py` (строки мандата);
  `tests/test_roles_map_fixture.py` (~50, `PULT_AGENT_ROLES`).
