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
`review`, только на журнал/детали отказов. Свежая планка
`tasks/<id>/acceptance_tests/` (обнаружено ТОЛЬКО после завершения
подтяжки, прогоном планки) буквально проверяла имя состояния
`verifying`/`review`, зафиксированное ДО переезда ADR-0015, и потому не
совпадала с фактическим (корректным) поведением — Оператор применил
патч эскалации через `amend-tests` (ANSWER-2.md), лок планки сдвинут
b1c9d335 -> a77a7e0f, все 16 из 16 сценариев планки зелёные.

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

## Итерация 2 — правка по REVIEW.md (changes_requested)

REVIEW.md итерации 1 нашло major R1-F1 и minor R1-F2. Часть R1-F2,
лежащая в моей зоне (код), исправлена в этом шаге; остаток обоих
замечаний лежит в `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/`
— зафиксированной планке (лок `a77a7e0f`, T023): правка планки — не
дело разработчика, только эскалация (см. «Эскалация» ниже).

- R1-F2 (minor), часть «код»: `orchestrator/fsm_advance.py:220` —
  докстринг `_review_escalation_sha_gate` называл целью перехода
  `verifying`, хотя после ADR-0015 approved review ведёт в
  `acceptance` (`_review_approved`, `fsm_advance.py:280`). Поправлено:
  «не должна пропускать переход в `acceptance`» вместо «в `verifying`».
  Остальные ~10 упоминаний того же устаревшего слова лежат в
  докстринге и именах тестов планки `test_ac8_ac9_ac14_ac15_review_
  verdict_sha.py` (собственно R1-F1 и вторая половина R1-F2) — см.
  эскалацию.
- R1-F1 (major): assertion `test_ac9_manual_advance_does_not_reach_
  verifying_on_changed_sha` (`assertNotEqual(state(), "verifying")`)
  тривиально проходит после переезда ADR-0015 (approved review больше
  не ведёт в `verifying` вовсе, независимо от того, сработал ли
  гейт), не ловя снятие гейта `_review_escalation_sha_gate` — ровно
  то, что показала мутационная проверка ревью. Правка требует
  переписать assertion в файле планки — не в моей зоне, эскалирую
  (см. «Эскалация»).

## Предложения системе

- Класс «планка `tasks/<id>/acceptance_tests/` фиксирует буквальное имя
  состояния FSM, а состояние переставляют местами последующим ADR,
  смерженным в main, пока задача стояла эскалированной» — кандидат в
  copilka/backlog.md, тот же тип проблемы, что П2 06.09 (отставание
  ветки от main до первого шага developer), но на уровне ЛОКАЛЬНОЙ
  планки конкретной задачи, не только кода. Разрешено ANSWER-2.md
  (Оператор применил патч через `amend-tests`, вариант (a) эскалации).
- Тот же класс всплыл повторно (R1-F1 этой задачи, REVIEW.md итерации
  1) — на этот раз не в имени состояния, а в СИЛЕ негативной проверки
  («не оказался в X» тривиально проходит, когда X вообще перестал быть
  достижимым путём независимо от гейта): ревью уже отметило это как
  отдельный урок в своей секции «Предложения системе». Второй случай
  подряд на одной и той же планке — сигнал, что чек-лист test_author
  после ADR, переставляющего состояния, стоит закрепить отдельным
  пунктом скила, а не полагаться на то, что ревью поймает эмпирически
  мутационной проверкой каждый раз заново.

## Эскалация

**Вопросы**

1. (блокирует) Планка `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_
   tests/test_ac8_ac9_ac14_ac15_review_verdict_sha.py` зафиксирована
   (лок `a77a7e0f`, T023) — правка не в зоне разработчика. Применить
   через `amend-tests` (ADR-0012) патч ниже, закрывающий R1-F1 (major)
   и остаток R1-F2 (minor) сразу, тем же приёмом, что и в ANSWER-2?
   - Вариант (а) — применить патч дословно, как в ANSWER-2. **Дефолт**
     при молчании: не применять, задача останется в `escalated`.
   - Вариант (б) — применить с правками (указать, с какими).
   - Вариант (в) — отклонить: R1-F1 не требует правки планки (тогда
     нужно назвать альтернативный путь закрытия, не трогающий
     зафиксированный файл).

   Патч (заменить целиком тело двух классов и поправить упомянутые
   докстринги — единственное СМЫСЛОВОЕ изменение — assertion в
   `test_ac9_...`, остальное — только слово `verifying` → `acceptance`
   в комментариях, поведение тестов не меняет):

   ```
   Строка 23 (докстринг модуля):
   - `verifying` даже при сменившемся sha (проверено прогоном на
   + `acceptance` даже при сменившемся sha (проверено прогоном на

   Строки 66-68 (докстринг класса UnchangedShaSkipsANewReviewerRunTest):
   - переходит в `verifying` без нового прогона ревьювера."""
   + переходит в `acceptance` без нового прогона ревьювера."""

   Строки 70-73 (докстринг test_ac8_...):
   -         вердикта — ручной `advance` после `budget` обязан довести задачу
   -         до `verifying`.
   +         вердикта — ручной `advance` после `budget` обязан довести задачу
   +         до `acceptance`.

   Строки 89-112 (класс ChangedShaBlocksTheTransitionTest целиком):
   - class ChangedShaBlocksTheTransitionTest(_ReviewSandbox):
   -     """AC-9: код сменился ПОСЛЕ вердикта — возврат в `review` не переходит
   -     в `verifying` без нового вердикта ревьювера."""
   -
   -     def test_ac9_manual_advance_does_not_reach_verifying_on_changed_sha(self):
   -         """sha кодовой ветки на момент возврата ОТЛИЧАЕТСЯ от sha на
   -         момент вердикта — ручной `advance` обязан отказать переходу в
   -         `verifying`, несмотря на статус `approved` в REVIEW.md.
   -
   -         Ловит мутацию: требование 3 не реализовано вовсе (сегодняшнее
   -         поведение) — advance доведёт задачу до `verifying` по старому
   -         вердикту, написанному для уже неактуального кода.
   -         """
   -         sha_box = self.escalate_with_approved_verdict("a" * 40)
   -         sha_box["sha"] = "b" * 40  # посторонний коммит, пока задача стояла escalated
   -
   -         self.capture(budget.cmd_budget, self.TASK, "50")
   -         self.assertEqual(self.state(), "review")
   -
   -         self.capture(fsm.cmd_advance, self.TASK)
   -
   -         self.assertNotEqual(
   -             self.state(), "verifying",
   -             "переход в verifying случился несмотря на сменившийся sha кода")
   + class ChangedShaBlocksTheTransitionTest(_ReviewSandbox):
   +     """AC-9: код сменился ПОСЛЕ вердикта — возврат в `review` не переходит
   +     в `acceptance` без нового вердикта ревьювера и остаётся в `review`."""
   +
   +     def test_ac9_manual_advance_does_not_reach_verifying_on_changed_sha(self):
   +         """sha кодовой ветки на момент возврата ОТЛИЧАЕТСЯ от sha на
   +         момент вердикта — ручной `advance` обязан отказать переходу в
   +         `acceptance`, несмотря на статус `approved` в REVIEW.md, и
   +         оставить задачу в `review`.
   +
   +         Ловит мутацию: требование 3 не реализовано вовсе (сегодняшнее
   +         поведение) — advance доведёт задачу до `acceptance` по старому
   +         вердикту, написанному для уже неактуального кода; в отличие от
   +         `assertNotEqual(state(), "verifying")` эта проверка не проходит
   +         тривиально после ADR-0015 (approved review больше не ведёт в
   +         `verifying` вовсе, независимо от гейта).
   +         """
   +         sha_box = self.escalate_with_approved_verdict("a" * 40)
   +         sha_box["sha"] = "b" * 40  # посторонний коммит, пока задача стояла escalated
   +
   +         self.capture(budget.cmd_budget, self.TASK, "50")
   +         self.assertEqual(self.state(), "review")
   +
   +         self.capture(fsm.cmd_advance, self.TASK)
   +
   +         self.assertEqual(
   +             self.state(), "review",
   +             "переход в acceptance случился несмотря на сменившийся sha "
   +             "кода — гейт обязан был отказать и оставить задачу в review")

   Строки 119-121 (докстринг test_ac14_...):
   -         `verifying`, не потратив ни одного нового шага ревьювера.
   +         `acceptance`, не потратив ни одного нового шага ревьювера.

   Строка 153 (докстринг test_ac15_...):
   -         задачу прямиком до `verifying` (проверено прогоном на
   +         задачу прямиком до `acceptance` (проверено прогоном на
   ```

   Имя метода `test_ac9_manual_advance_does_not_reach_verifying_on_
   changed_sha` не переименовано (не влияет на поведение, лишний риск
   расхождения с traceability guard) — по желанию Оператора можно
   переименовать отдельно.

**Контекст**

- Итерация 1 REVIEW.md (changes_requested) нашла R1-F1 (major) и
  R1-F2 (minor) — оба про планку `test_ac8_ac9_ac14_ac15_review_
  verdict_sha.py`. R1-F2 в части кода (`fsm_advance.py:220`) исправлен
  в этом шаге. Юнит-тесты `test_budget_live_lease_and_escalation`,
  `test_auto_escalated_return_rework_gate`, `test_fsm_review_rework_
  sha_gate` прогнаны после правки — зелёные (docstring-only правка не
  меняет поведение).
- Планка задачи зафиксирована (`tests_locked_sha` = `a77a7e0f`,
  ADR-0012, T023) — правка файлов под `acceptance_tests/` не входит в
  права роли developer («их правка — эскалация, не правка», см. бриф
  роли); прецедент — ANSWER-2.md этой же задачи, тем же механизмом
  (`amend-tests`).

**Блокирует**

Без амендмента AC-9 остаётся тестом, не ловящим мутацию (major
замечание REVIEW.md) — задача не может дойти до `status: accepted`
записи R1-F1 в реестре замечаний REVIEW.md, а без этого approved-
вердикт следующей итерации не пройдёт `_registry_gate`
(`orchestrator/fsm_advance.py::_registry_gate`).
