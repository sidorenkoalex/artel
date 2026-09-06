---
task: 01M1VBEDGMEXHVGWAH42FTDZ4X
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: budget под живым шагом и возврат из эскалации без холостого шага роли

## Подход

Три требования SPEC закрываются точечными правками в трёх независимых
узлах, которые уже существуют в коде — ни одного нового состояния FSM,
ни одной новой таблицы/колонки БД (зона задачи не включает `store.py`/
`schema.py`).

**Требование 1 (AC-1..AC-4, AC-10, AC-11) — `budget` под живым lease
своего хоста.** `lease.acquire()` получает keyword-only параметр
`same_host_ok: bool = False` (дефолт сохраняет поведение всех текущих
вызывателей — `approve`/`reject`/`run`/`kill`/`workspace`/`advance`/
`auto` продолжают звать `run_locked` без него, «Не входит» SPEC не
нарушается). При `same_host_ok=True` и живом чужом lease с ТЕМ ЖЕ
hostname отказ не выдаётся, а строка lease НЕ мутируется (это не
захват lease, просто разрешение продолжить работу параллельно) —
`(None, False)`. Чужой live lease с другим hostname по-прежнему
отказывает тем же текстом (проверка hostname идёт раньше проверки
`same_host_ok`). `lease.run_locked()` получает тот же keyword и
пробрасывает его в `acquire()`. `budget.cmd_budget` — единственный
вызыватель, передающий `same_host_ok=True`.

Пометка «во время шага <роль>» (AC-2/AC-10) — НЕ производная от
`same_host_ok`/`fresh` (оба значения также истинны при перехвате
протухшего чужого lease, что не «во время шага»): `cmd_budget` читает
`lease.is_live(conn, task_id)` ДО вызова `run_locked` (живой ли lease —
своей или чужой сессии, неважно чьей) и передаёт этот флаг в
`_cmd_budget`. Флаг истинен — в `detail` журнальной записи «бюджет
изменён» добавляется `, во время шага {role}` (роль — `runner.step_role`
текущего состояния, отложенный импорт по образцу `lease.
warn_foreign_live`, во избежание цикла budget<->runner). Флаг ложен
(обычный вызов без активного lease) — `detail` не меняется ни на
символ: существующие точные сравнения (`tests/test_step_cost.py`,
`tests/test_spec_budget.py`) не задеты (AC-16).

**Требование 2 (AC-5..AC-7, AC-12, AC-13) — рубеж «возврат не
отработан» сверяется с возвратом из review, не с возвратом из
escalated.** Единственная правка — `auto._role_step_since_state_entry`:
при поиске ПОСЛЕДНЕЙ записи `state -> {state}` пропускаются записи с
detail, совпадающим с одним из двух известных текстов возврата из
эскалации (`"эскалация разрешена, продолжаем"` — `fsm.py`,
`"бюджет поднят, продолжаем"` — `budget.py`) — они не являются
основанием переделки и не должны маскировать более раннюю запись,
несущую его. Функция общая для `auto.py` (пред-advance цикла) и
`fsm_advance.py::_review_rework_gate` (ручной `advance` для `in_dev`) —
правка одной функции закрывает оба пути одновременно (SPEC AC-6: «оба
пути равноправными»), это уже проверено конструкцией — второго места
для правки нет.

**Требование 3 (AC-8, AC-9, AC-14, AC-15) — budget-эскалация из review
с approved-вердиктом требует нового прогона reviewer только при
сменившемся sha.** `budget.enforce_budget`, ветка эскалации: если
эскалация происходит ИЗ состояния `review`, sha головы кодовой ветки
(`gitcmd.branch_head_sha(t["branch"])`) журналируется отдельной записью
(`budget.REVIEW_ESCALATION_CODE_SHA_ACTION`) — пусто, если git не
ответил (тогда просто не журналируется, вырожденный случай). В
`fsm_advance.review()`, для `status == "approved"`, новый гейт
(`_review_escalation_sha_gate`, через каркас `_run_gates`) ищет
последнюю такую запись, но учитывает её, только если она НОВЕЕ
последнего `"agent run finished"` роли `reviewer` (иначе она осталась
от предыдущего цикла ревью и относится не к текущему вердикту — тот же
приём отсечки, что и в требовании 2). Найдена и относится к текущему
вердикту, и текущий `gitcmd.branch_head_sha` git ответил и не совпадает
с зафиксированным — переход отклонён, нужен новый прогон reviewer.
Совпадает, либо записи нет, либо текущий git не ответил — гейт
пропускает (fail-open, тот же принцип, что и у соседних гейтов
`_review_rework_gate`/`_capacity_gate`).

Внутри лёгкой песочницы `fake_git` (`tests/test_auto_cycle.py`,
приёмочные тесты этой задачи) `gitcmd.branch_head_sha` либо не
патчена (возвращает `""` по построению `fake_git`), либо патчена
приёмочным тестом на управляемое значение — обе ветки корректно
дают fail-open/сравнение на существующих тестах (AC-16).

**Возврат по причине конфликта подтяжки main (см. ANSWER-1).** Ветка
задачи стартовала от c4f89371 — ДО того, как в main смержился ADR-0015
«CI до ревью» (01M1TQ0TRC), поменявший местами `review` и `verifying`
в порядке состояний: было `in_dev -> review -> verifying -> acceptance`,
стало `in_dev -> verifying -> review -> acceptance` (сверка головы на
origin и прогон acceptance_tests переехали с входа `review()` на вход
`in_dev()`, `review()` approved теперь ведёт прямиком в `acceptance`,
не в `verifying`). `git merge origin/main` — конфликт в
`orchestrator/fsm_advance.py::review()` (мой гейт
`_review_escalation_sha_gate` вставлен в блок, который ADR-0015 убрал
целиком) и `docs/codebase-map.md`; разрешено по точному месту, данному
ANSWER-1: гейт вставлен один, без `_origin_push_gate`/`is_canary` (та
проверка уже переехала в `in_dev()`, строка ~1180), карта взята с
main и перегенерирована. Юнит-тесты (`tests/test_budget*.py`,
`tests/test_auto*.py`, `tests/test_fsm_review_rework*.py`,
`tests/test_fsm_advance*.py`, `tests/test_advance_guard.py`,
`tests/test_review_freshness.py`, `tests/test_review_registry_gate.py`,
`tests/test_zones_gate.py`, `tests/test_capacity_gate.py`,
`tests/test_branch_freshness_gate.py`, `tests/test_verifying_ceiling.py`,
`tests/test_cmd_approve_dispatch.py` — 171 тестов) зелёные без правки
утверждений: они не завязаны на конкретное имя состояния после
`review`, только на журнал/детали отказов. См. раздел «Эскалация» ниже
— свежая планка `tasks/<id>/acceptance_tests/` (обнаружено ТОЛЬКО
после завершения подтяжки, прогоном планки) буквально проверяет имя
состояния `verifying`/`review`, зафиксированное ДО переезда ADR-0015,
и теперь не совпадает с фактическим (корректным) поведением.

## Шаги

1. `orchestrator/lease.py`: `same_host_ok` в `acquire()`/`run_locked()`;
   `is_live()` — читает лайвость lease без мутации.
2. `orchestrator/budget.py`: `cmd_budget` передаёт `same_host_ok=True` и
   `mid_step` (из `lease.is_live`) в `_cmd_budget`; пометка «во время
   шага <роль>» в detail; `enforce_budget` журналирует sha кода при
   эскалации из `review` (`REVIEW_ESCALATION_CODE_SHA_ACTION`).
3. `orchestrator/auto.py`: `_role_step_since_state_entry` пропускает
   записи возврата из эскалации при поиске анкера.
4. `orchestrator/fsm_advance.py`: `_review_escalation_sha_gate` +
   `_code_sha_at_review_escalation`, вызов гейта в `review()` для
   `status == "approved"` (после подтяжки main/ADR-0015 — сразу после
   `_freshness_refuses`, до `iteration = artifacts.
   fresh_verdict_iteration(...)`; `_origin_push_gate` этой веткой не
   вызывается — переехал в `in_dev()` ДО начала работы над этой
   задачей, см. «Подход»).
5. Юнит-тесты: `tests/test_budget_live_lease_and_escalation.py` (шаги
   1-2), `tests/test_auto_escalated_return_rework_gate.py` (шаг 3),
   `tests/test_fsm_review_rework_sha_gate.py` (шаг 4) — имена под маски
   AC-16 (`test_budget*`, `test_auto*`, `test_fsm_review_rework*`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (AC-1..AC-4, AC-10, AC-11) | 1, 2 |
| 2 (AC-5..AC-7, AC-12, AC-13) | 3 |
| 3 (AC-8, AC-9, AC-14, AC-15) | 2, 4 |
| AC-16 (регресс) | 5 |

## Влияние на систему

- `lease.acquire`/`run_locked` меняют сигнатуру добавлением
  keyword-only параметра с дефолтом, сохраняющим прежнее поведение —
  все 8 существующих вызывателей (`approve`/`reject`/`run`/`kill`/
  `workspace`/`advance`/`auto`/`amend-tests`/`answer`) не тронуты ни
  строкой (SPEC «Не входит», абзац 3). Единственный новый путь отказа
  НЕ добавляется — `same_host_ok=True` только РАСШИРЯЕТ множество
  принимаемых случаев для `budget`, ничего не отбирает.
- `auto._role_step_since_state_entry` — общий узел `auto.py`/
  `fsm_advance.py` (уже был им до этой задачи, SPEC «Оценка объёма»):
  правка одной функции меняет поведение обоих потребителей
  одновременно и осознанно (это и есть требование 2) — не побочный
  эффект.
- Гейт `_review_escalation_sha_gate` — НОВАЯ точка отказа перехода
  `review -> acceptance` (имя цели уточнено после подтяжки main —
  ADR-0015 переставил `review` и `verifying` местами, см. выше; на
  момент написания SPEC этого раздела цель называлась `verifying`),
  но срабатывает только при выполнении ВСЕХ
  условий: эскалация из `review` была именно по бюджету
  (`enforce_budget`, не по вердикту `escalate`/лимиту ревью — те не
  проходят через `enforce_budget`), эта запись новее последнего прогона
  reviewer, и git ответил обоими sha разными значениями. Ни один
  существующий тест (AC-16: `tests/test_budget*.py`,
  `tests/test_fsm_review_rework*.py`, `tests/test_auto*.py`) не создаёт
  такой комбинации — не патчит `gitcmd.branch_head_sha` вовсе, поэтому
  функция возвращает `""` (через `fake_git`) на обоих измерениях, гейт
  пропускает по правилу fail-open.
- Откат: все три правки независимо реверсируемы (разные функции,
  разные файлы) без остатка миграций БД — новых колонок/таблиц нет.
- Ни один существующий тест/гейт/лимит не ослаблен: отказ `budget` по
  чужому lease ДРУГОГО хоста сохраняется дословно (AC-4/AC-11); рубеж
  «возврат не отработан» для случая «шага не было вовсе» не меняется
  (AC-7/AC-13 — зелёные с рождения); гейт `review -> verifying` — новый,
  но строго ДОПОЛНИТЕЛЬНЫЙ отказ (более узкий набор пропускаемых
  переходов, не более широкий).

## Риски

- Пометка «во время шага <role>» в detail «бюджет изменён» — новый
  текст в уже читаемом другими инструментами (например, `catalog.
  cmd_log`) поле; не структурная колонка, риск минимален (assertIn, не
  equals, используется и в существующих тестах).
- `_code_sha_at_review_escalation` полагается на порядок записей
  журнала (`store.task_steps`, по возрастанию `id`) — при отсутствии
  реальных временных меток (лёгкие песочницы) порядок вставки и есть
  единственный надёжный сигнал; тот же приём уже используют
  `_role_step_since_state_entry`/`_reviewer_verdict_baseline`.

## Предложения системе

- Класс «планка `tasks/<id>/acceptance_tests/` фиксирует буквальное имя
  состояния FSM, а состояние переставляют местами последующим ADR,
  смерженным в main, пока задача стояла эскалированной» — см.
  «Эскалация» ниже; кандидат в copilka/backlog.md, тот же тип проблемы,
  что П2 06.09 (отставание ветки от main до первого шага developer), но
  на уровне ЛОКАЛЬНОЙ планки конкретной задачи, не только кода.

## Эскалация

### Вопросы

1. (блокирует) Три сценария локальной планки `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/`
   буквально проверяют имя состояния FSM (`"verifying"`/`"review"`),
   зафиксированное ДО того, как ADR-0015 (01M1TQ0TRC, уже смержен в
   main) поменял `review` и `verifying` местами в порядке состояний
   (см. «Подход»/«Влияние на систему» выше). После честной подтяжки
   main (см. ANSWER-1) факт таков:
   - AC-8 (`test_ac8_ac9_ac14_ac15_review_verdict_sha.py:86`) и AC-14
     (там же, `:136`) ожидают `self.state() == "verifying"` сразу после
     возврата в `review` с approved-вердиктом и неизменным sha; по
     факту (корректно, по ADR-0015) задача идёт в `"acceptance"` —
     `review -> verifying` в новом порядке вообще не существует как
     переход (verifying стоит ДО review, не после).
   - AC-12 (`test_ac12_ac13_escalated_return_regression.py:64`) ожидает
     `self.state() == "review"` после `auto()` от уже готового
     `PLAN.md`, без мока `ci.verifying_status` — по факту (тоже
     корректно) `auto` останавливается на новом промежуточном
     `"verifying"` (CI не отвечает зелёным по дефолту песочницы),
     не дойдя до `review` за один вызов.
   Все 171 юнит-тест (`tests/test_budget*.py`, `tests/test_auto*.py`,
   `tests/test_fsm_review_rework*.py`, `tests/test_fsm_advance*.py` и
   ещё 8 планок, см. «Подход») и оставшиеся 13 из 16 сценариев планки —
   зелёные; сама механика требований 1-3 SPEC работает по всем AC,
   расхождение только в трёх буквальных именах состояния плюс
   отсутствующем моке CI. Я не могу это починить сам: `tasks/<id>/
   acceptance_tests/` залочены для разработчика (conventions-core) —
   правка требует эскалации, не самостоятельного решения; вернуть
   ADR-0015 к старому порядку состояний, чтобы планка совпала буквально,
   я тоже не вправе (принцип целостности — решение Оператора через ADR,
   и это отменило бы уже смерженный и не относящийся к этой задаче
   ADR).
   Проверенный (прогнан на временных копиях в `_scratch_verify/`, потом
   удалённых, планка не тронута) минимальный патч — правит только три
   точки, не переписывает сценарии:

   ```diff
   --- a/tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/test_ac8_ac9_ac14_ac15_review_verdict_sha.py
   +++ b/tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/test_ac8_ac9_ac14_ac15_review_verdict_sha.py
   @@ -83,7 +83,7 @@ class UnchangedShaSkipsANewReviewerRunTest(_ReviewSandbox):

            self.capture(fsm.cmd_advance, self.TASK)

   -        self.assertEqual(self.state(), "verifying")
   +        self.assertEqual(self.state(), "acceptance")


    class ChangedShaBlocksTheTransitionTest(_ReviewSandbox):
   @@ -133,7 +133,7 @@ class UnchangedShaAutoCycleSkipsTheReviewerTest(_ReviewSandbox):
            self.agent.script = [lambda: None]
            self.auto()

   -        self.assertEqual(self.state(), "verifying")
   +        self.assertEqual(self.state(), "acceptance")
            reviewer_steps = [a for a in agent_run_finished_actors(conn, self.TASK)
                             if a == "reviewer"]
            self.assertEqual(len(reviewer_steps), 1)
   --- a/tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/test_ac12_ac13_escalated_return_regression.py
   +++ b/tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/test_ac12_ac13_escalated_return_regression.py
   @@ -19,7 +19,7 @@ sys.path.insert(0, str(Path(__file__).resolve().parent))

    from _sandbox import (AutoCycleTest, agent_run_finished_actors,  # noqa: E402
                          journal_agent_run_finished)
   -from orchestrator import auto, budget, fsm, store  # noqa: E402
   +from orchestrator import auto, budget, ci, fsm, store  # noqa: E402


    class ReturnAfterAnAlreadyFinishedDeveloperStepAdvancesTest(AutoCycleTest):
   @@ -41,6 +41,9 @@ class ReturnAfterAnAlreadyFinishedDeveloperStepAdvancesTest(AutoCycleTest):
            застрянет в `in_dev`, повторно позвав developer, и не дойдёт до
            `review` в границах одного вызова `auto`.
            """
   +        self.patch_object(ci, "verifying_status",
   +                          lambda branch: (ci.VERIFYING_GREEN,
   +                                          "CI коммита aaaaaaaa зелёный (2 проверок)"))
            conn = store.db()
            self.write_plan("ready")
            self.set_state("review")
   ```

   Варианты:
   a) Оператор применяет патч выше (`amend-tests` либо правкой в
      артефактной ветке) — я продолжаю с шага 4 (прогон планки,
      guard, коммит, PLAN.md status: ready) следующим шагом.
   b) Оператор считает планку/SPEC устаревшими иначе (другая замена
      имени состояния, другой мок) — жду точных строк для применения.
   c) Оператор решает, что механика ДОЛЖНА буквально попадать в
      `verifying`/`review` (то есть требование 3/2 этой задачи имели в
      виду что-то отличное от «сразу после review» в терминах СТАРОГО
      порядка ADR-0015, а не переименование) — прошу уточнить, что
      именно тогда должно измениться в реализации требований 2/3 (см.
      «Подход»), раз текущая реализация уже проходит все AC SPEC
      функционально, кроме буквального имени состояния.
   Дефолт при молчании: (a) — применить патч выше как есть.

### Контекст

- Merge с `origin/main` завершён и закоммичен (`git merge origin/main`,
  коммит «подтяжка origin/main…» этой сессии): конфликты
  `orchestrator/fsm_advance.py` (гейт `_review_escalation_sha_gate`
  вставлен по месту, данному ANSWER-1) и `docs/codebase-map.md` (взята
  версия main, перегенерирована `scripts/codebase_map.py`) разрешены.
- 171 юнит-тест зелёные (см. список файлов в «Подход»), `scripts/
  guard.py` на SPEC.md/PLAN.md/ANSWER-1.md — без замечаний.
- Планка `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/` — 13 из
  16 тестов зелёные; 3 падают строго по причине переименования/
  перестановки состояний ADR-0015 (см. «Вопросы» п.1), не по ошибке
  реализации требований 1-3 — красная строка изолирована к трём
  `assertEqual`/одному отсутствующему моку, дифф выше.
- Диф проверен: применён к временным копиям файлов планки в
  `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/_scratch_verify/` (не в самой
  планке), прогнан `python3 -m unittest` — все 6 тестов файлов
  AC8/AC12 зелёные с патчем; каталог `_scratch_verify/` удалён после
  проверки, планка на диске не тронута ни байтом.

### Блокирует

Не могу поставить `status: ready` и закоммитить весь шаг как готовый:
планка красна тремя тестами, а её правка вне полномочий роли developer
(conventions-core: «их правка — эскалация, не правка»). Код и юнит-тесты
уже в ветке (коммит подтяжки этой сессии) — при ответе (a) следующий
шаг завершает PLAN без новой работы над самой логикой требований 1-3.
