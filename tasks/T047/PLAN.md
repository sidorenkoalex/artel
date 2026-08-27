---
task: T047
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: Ветко-корректные чтения статусов SPEC и REVIEW на переходах FSM

## Подход

Тот же приём, что T031 уже применил к `spec_gate`/брифу/трассируемости
AC/локу/фиксации: единый предикат `gitcmd.on_foreign_branch(branch)` —
True только когда рабочее дерево пульта ДОКАЗУЕМО стоит не на ветке
задачи и сама ветка реально существует в git. False (свой чекаут; ветка
ещё не создана ролью; git не ответил) — прежний путь чтения с диска,
байт в байт как до этой задачи. True — источник истины ВЕТКА задачи
(`git show`/`git ls-tree`), не рабочая копия.

Общий узел для трёх новых мест (SPEC.md в `spec_writing`, REVIEW.md в
`review`, QUESTIONS.md в `spec_writing`) вынесен в приватный хелпер
`fsm._read_branch_text_or_refuse(conn, task_id, branch, rel_name)`:
читает `tasks/<id>/<rel_name>` с ветки, на неудаче сам журналирует и
печатает отказ тем же текстом, что уже был у `in_dev`/PLAN.md (T031) —
`in_dev` тоже переведён на этот хелпер, чтобы не множить копию одной и
той же последовательности «прочитать/отказать» в четвёртый раз (скил
coding-standards, «чини класс, не экземпляр»). Отсутствие файла на
ветке для SPEC.md/REVIEW.md/PLAN.md — не легитимное «ещё не готово», а
именованный отказ («дерево не на ветке задачи ... не прочитан»): тот же
принцип, на котором уже стоит `in_dev`/PLAN.md, применён к двум новым
местам для одинакового поведения класса.

QUESTIONS.md устроен иначе: файл НЕОБЯЗАТЕЛЕН (большинство задач его не
заводят вовсе), поэтому отсутствие на ветке — не отказ, а нормальный
«эскалации нет» ответ. Наличие проверяется отдельно, через
`gitcmd.ls_tree_files(branch, "tasks/<id>/QUESTIONS.md")` (пустой список
— легитимно, файла нет; `None` — git не ответил на сам вопрос
существования — вот это уже отказ), тем же приёмом, что
`_tests_writing_ac_state` (T031) уже использует для необязательного
каталога `acceptance_tests/`. Только если ls-tree нашёл файл — он
читается через `_read_branch_text_or_refuse` и идёт в `guard_refuses`.

`guard_refuses` уже принимает `text` (T031) — на чужом чекауте гвардом
проверяется РОВНО ТОТ ЖЕ текст, что определил статус, не повторное
чтение с диска (которое на main его бы не увидело).

`artifacts.fresh_verdict_iteration` (SPEC, требование 3) сам не читает
файлов — принимает уже разобранный `meta`-словарь; его «ветко-
зависимость» была целиком в том, откуда `review`-ветка `fsm.py` брала
этот `meta` (диск, всегда) — почина на входе (branch-correct `meta`)
закрывает и его тоже, без изменения кода `artifacts.py`.

Не архитектурно значимое решение — ADR не заводится: продолжение того
же механизма, что и T031 (т.д. сам T031 решил так же).

## Аудит по требованию 3

Проверены все чтения статусов/фронтматтеров артефактов задачи на
переходах FSM в `orchestrator/fsm.py` и `orchestrator/artifacts.py`
(`config.TASKS`-based пути):

| Место | Файл:строка (до правки) | Ветко-зависимо? | Действие |
|---|---|---|---|
| `spec_writing → spec_gate`, статус SPEC.md | `fsm.py:323` | Да (SPEC, требование 1) | Починено (шаг 1) |
| `spec_writing`, наличие/содержимое QUESTIONS.md | `fsm.py:314` | Да — тот же класс, диск не видит ветку (SPEC, требование 3, явно названо) | Починено (шаг 1) |
| `review → acceptance/in_dev`, вердикт REVIEW.md | `fsm.py:339` | Да (SPEC, требование 2) | Починено (шаг 1) |
| `artifacts.fresh_verdict_iteration` | `fsm.py:349`, `artifacts.py:23` | Да — зависимость от входа, не от своего кода (SPEC, требование 3, явно названо) | Закрыто фиксом входа (шаг 1), код `artifacts.py` не менялся |
| `in_dev → review`, статус PLAN.md | `fsm.py:449-473` | Уже ветко-корректно (T031) | Без изменений — рефакторено на общий хелпер (шаг 1), поведение то же |
| `_cmd_approve`, `spec_gate`, статус SPEC.md (skip_tests) | `fsm.py:587-610` | Уже ветко-корректно (T031, AC-1) | Без изменений |
| `tests_writing`, SPEC.md + `acceptance_tests/` (трассируемость AC) | `fsm.py:225-268` | Уже ветко-корректно (T031, AC-3) | Без изменений |
| `catalog.cmd_show`, статусы SPEC/PLAN/REVIEW/TEST_REPORT | `catalog.py:126` | Не переход FSM — команда отображения карточки задачи, состояние не двигает | Вне зоны (не переход, SPEC формулирует именно «на переходах FSM») |
| `acceptance.run(acc_tdir)` в `review`-ветке (approved) | `fsm.py:373-376` | Нет — уже читает через `workspace.path()` (worktree на ветке задачи, T045), не `tdir` пульта напрямую | Вне зоны — другой механизм (не входит по SPEC: механика фиксации/приёмки не трогается) |
| `_dirty_refuses` (сверка грязной копии) | `fsm.py:194-222` | Нет — сверяет `fixation.read()` текущего чекаута с зафиксированным sha, не содержимое статуса артефакта | Вне зоны — механика фиксации не трогается (SPEC «Не входит») |

## Шаги

1. `orchestrator/fsm.py`:
   - хелпер `_read_branch_text_or_refuse(conn, task_id, branch, rel_name)`
     — общий для SPEC.md/REVIEW.md/PLAN.md/QUESTIONS.md;
   - ветка `spec_writing`: `on_foreign_branch` → QUESTIONS.md проверяется
     через `ls_tree_files` (необязательный файл), при находке — читается
     и уходит в guard тем же текстом; SPEC.md — обязательный, через
     хелпер; иначе — прежний путь с диска, без изменений;
   - ветка `review`: `on_foreign_branch` → REVIEW.md через хелпер, `meta`
     из его текста, `guard_refuses(..., text=review_text)`; иначе —
     прежний путь с диска;
   - ветка `in_dev`: PLAN.md-чтение переведено на тот же хелпер (было
     инлайн-дублирование того же кода, T031) — поведение не изменилось.
2. Юнит-тесты `tests/test_fsm_branch_correct_status_reads.py`: свежая
   ветка задачи с реальным git (тот же приём, что
   `tests/test_gitcmd_branch_reads.RealGitSandbox`) — SPEC.md/REVIEW.md
   закоммичены только на ветке, рабочее дерево на main, `cmd_advance`
   переводит переход; отдельно — QUESTIONS.md на ветке при чужом
   чекауте триггерит эскалацию; отдельно — деградация без ветки/без git
   не меняется. Приёмочные тесты `tasks/T047/acceptance_tests/` уже
   залочены (T023-механика) — прогоняются как есть, не правятся.
3. Полный прогон `python3 -m unittest discover -s tests`, приёмочные
   тесты задачи, `scripts/guard.py --all`.
4. Диф `docs/invariants.md` (инвариант 28) — приложен ниже для
   Оператора, агент его не коммитит (SPEC «Не входит», тот же приём,
   что tasks/T046).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (AC-1) | 1, 2 |
| 2 (AC-2) | 1, 2 |
| 3 (аудит) | Аудит по требованию 3 |
| 4 (закрытие найденного) | 1 |
| 5 (AC-3) | 1, 2 |
| 6 (AC-6) | 4 |

## Влияние на систему

Затронут один модуль вне «нового кода» в узком смысле —
`orchestrator/fsm.py`, уже несущий плотное покрытие (590+ тестов после
T031). Изменение — строго внутри ДВУХ существующих веток `if/else`
(`spec_writing`, `review`) плюс рефакторинг третьей (`in_dev`) на общий
хелпер без изменения её `else`-пути; каждый `else`-путь (свой чекаут,
ветка не создана, git не ответил) остаётся дословно тем же кодом, что
до этой задачи — прежний стенд заглушек `gitcmd.git` в существующих
тестах (`fake_git`, `test_advance_guard.py` и другие) не задет.

Инвариант 28 (docs/invariants.md, «чтение артефактов задачи не зависит
от чекаута пульта») расширяется, не ослабляется: он и раньше требовал
ветко-корректности для перечисленных мест, эта задача добавляет к списку
мест ещё три (SPEC.md/`spec_writing`, REVIEW.md/`review`,
QUESTIONS.md/`spec_writing`) тем же правилом. Инвариант 13 (переход
`review → acceptance` без свежего вердикта) не ослаблен: `fresh_verdict_iteration`
как функция не менялась, только источник `meta`, который в неё
передают, — сама проверка свежести осталась той же. Инвариант 25 (FSM
решает только по зафиксированным хэшам) не задет: `fixation`/`_dirty_refuses`
не тронуты.

Откат: `git revert` — новый код только ДОБАВЛЯЕТ ветвление и хелпер;
`else`-путь каждого места дословно совпадает с кодом до T047.

## Риски

Одинаковый принцип «отсутствие файла на ветке = отказ» для SPEC.md и
REVIEW.md (не «ещё не готово», как раньше вело себя чтение с диска)
может дать при первом реальном срабатывании на чужом чекауте
диагностику «дерево не на ветке задачи» вместо привычного «SPEC.md ещё
не ready»/«REVIEW.md status=None — жду вердикта» в узком транзитном
окне (ветка только что заведена ролью, первый коммит артефакта ещё не
сделан). Тот же трейд-офф уже принят и работает в проде для `in_dev`/
PLAN.md (T031) — решение сознательно повторяет его для одинакового
поведения класса, а не изобретает новое.

## Предложения системе
<нет>

---

# Дифф для Оператора

Ниже — унифицированный дифф защищённого `docs/invariants.md` (инвариант
28, SPEC требование 6, AC-6). Исполнитель его не коммитит в ветку задачи
— диф прикладывается и применяется Оператором отдельным MR, тем же
приёмом, что tasks/T046/PLAN.md.

## docs/invariants.md

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -52,7 +52,7 @@
 | 25 | FSM принимает решения только по артефактам, чьи хэши зафиксированы его журналом: расхождение живого sha (или грязная копия) с зафиксированным на последнем переходе — инцидент целостности, агент не запускается, `approve` без подтверждённого sha не проходит гейт | `test_git_fixation.FsmDecidesOnlyOnFixedHashesTest`; `test_git_fixation.IntegrityIncidentBlocksRunTest`; `test_git_fixation.ApproveByShaTest` | ADR-0003 п.15, п.17; tasks/T021/SPEC.md, требования 4–6 |
 | 26 | Выход из `tests_writing`: критерий приёмки (AC-n) без теста и без пометки manual/skip/escalate — невалидный выход, переход отказывает с именем критерия | `test_acceptance_tests_flow.TraceabilityTest` | tasks/T023/SPEC.md, требование 4 |
 | 27 | Каталог `acceptance_tests/` залочен фиксацией T021 после выхода из `tests_writing`: расхождение с зафиксированным на выходе sha — отказ перехода `in_dev → review`, код чинится под тест, не наоборот | `test_acceptance_tests_flow.LockTest` | tasks/T023/SPEC.md, требование 5 |
-| 28 | Чтение артефактов задачи оркестратором (маршрутизация `spec_gate`, бриф роли developer, трассируемость AC, лок `acceptance_tests/`, sha догфуд-фиксации) не зависит от того, какая ветка сейчас выписана в рабочем дереве пульта: источник истины — ВЕТКА задачи (`git show`/`git ls-tree`), чужой чекаут её не подменяет; ветка ещё не создана ролью — прежнее поведение (рабочая копия), не именованный отказ | `test_gitcmd_branch_reads.OnForeignBranchTest`; end-to-end по каждому месту чтения — `tasks/T031/acceptance_tests/test_branch_correct_reads.py` (`SpecGateBranchRoutingTest`, `BriefBuildBranchTest`, `TraceabilityBranchTest`, `LockBranchTest`, `FixationBranchTest`, `NoUnhandledExceptionOnMissingBranchTest`) | tasks/T031/SPEC.md, требования 1–2; tasks/T030 (класс-дефект «артефакто-чтения ветко-зависимы», журнал ~17:35 25.08.2026) |
+| 28 | Чтение артефактов задачи оркестратором (маршрутизация `spec_gate`, бриф роли developer, трассируемость AC, лок `acceptance_tests/`, sha догфуд-фиксации, статус SPEC.md и батч QUESTIONS.md на переходе `spec_writing → spec_gate`, вердикт REVIEW.md — status и iteration — на переходе `review → acceptance/in_dev`) не зависит от того, какая ветка сейчас выписана в рабочем дереве пульта: источник истины — ВЕТКА задачи (`git show`/`git ls-tree`), чужой чекаут её не подменяет; ветка ещё не создана ролью — прежнее поведение (рабочая копия), не именованный отказ | `test_gitcmd_branch_reads.OnForeignBranchTest`; end-to-end по каждому месту чтения — `tasks/T031/acceptance_tests/test_branch_correct_reads.py` (`SpecGateBranchRoutingTest`, `BriefBuildBranchTest`, `TraceabilityBranchTest`, `LockBranchTest`, `FixationBranchTest`, `NoUnhandledExceptionOnMissingBranchTest`); `tasks/T047/acceptance_tests/test_branch_correct_status_reads.py` (`SpecWritingBranchRoutingTest`, `ReviewBranchRoutingTest`, `NoTaskBranchDegradationTest`, `NoGitDegradationTest`) | tasks/T031/SPEC.md, требования 1–2; tasks/T030 (класс-дефект «артефакто-чтения ветко-зависимы», журнал ~17:35 25.08.2026); tasks/T047/SPEC.md, требования 1–4 (инциденты T046 27.08.2026, T045 27.08.2026) |
 | 29 | Стоимость шага не остаётся неучтённой молча: если финальное событие потока (`type: result`) не пришло из-за таймаута шага или обрыва stdout-пайпа, в журнал попадает либо частичная сумма из промежуточных usage-событий с пометкой «частичная», либо событие «стоимость шага неизвестна» с открытым алертом `alerts` (`kind=incident`, `source=spend.unknown_cost`); `spent_usd` при этом не дописывается фиктивной суммой | `tasks/T040/acceptance_tests/test_step_cost_on_missing_final_event.py::MissingFinalEventCostTest`; `test_step_cost.ChargeMissingResultTest`; `test_step_cost.CmdRunPartialCostTest` | tasks/T040/SPEC.md, требования 1–3 |
 | 30 | Таймаут шага с незакоммиченным WIP в рабочем дереве ветки задачи коммитится оркестратором чекпоинтом (`<id>: WIP-чекпоинт после таймаута шага <role>`, журнал actor=`orchestrator`) без участия Оператора; провал шага по коду возврата (не таймаут) и таймаут при уже чистом дереве чекпоинт не коммитят | `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py::CheckpointAfterTimeoutTest`; `test_timeout_checkpoint.CommitTimeoutCheckpointTest` | tasks/T041/SPEC.md, требования 1–4; прецеденты tasks/T022, tasks/T037 (ручной чекпоинт Оператора) |
```
