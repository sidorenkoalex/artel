---
task: 01M1HNNHDMP2C1AJTH5QF1BTN2
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 3
---

# REVIEW: Штатная команда правки зафиксированной планки приёмки

## Фаза A: проверка плана

Покрытие требований/AC в PLAN.md полное (таблицы «Покрытие требований» и
AC есть, все пункты закрыты шагом 1, регресс — шагами 2-3). Размер шага 1
(один модуль `orchestrator/amend.py`) — проверяемая единица, не «сделать
всё». Подход не противоречит конвенциям (SQL остаётся в store.py,
`lease.run_locked` — тот же приём, что `answer.cmd_answer`).

Однако ключевая техническая посылка подхода не подтверждается кодом:
PLAN.md («Подход», шаг 3) заявляет, что песочница приёмочных тестов
использует «тот же рецепт, что `LockTest.enter_in_dev` в
`tests/test_acceptance_tests_flow.py`». Это не так — `LockTest` (после
A7) работает с ОДНИМ репозиторием без отдельного worktree, коммитит
`tasks/<id>/` на явно заведённую артефактную ветку пульта и вручную
имитирует создание кодовой ветки задачи (`self.code_branch`) ПЕРЕД тем,
как в неё что-то писать. Песочница этой задачи (`_sandbox.py`,
`AmendSandbox`) вместо этого использует `RealGitSandbox` + `catalog.
cmd_new` и сразу пишет в `workspace.path(TASK) / "tasks" / TASK`, ни разу
не вызывая `workspace.ensure`/не создавая кодовую ветку — то есть
опирается на ДОГЕНЕРАЛИЗОВАННОЕ (до-A7) поведение `cmd_new`, которое
после мержа A7 в эту ветку (коммит `3d79a14`) в системе уже не
действует. Возможное объяснение — PLAN.md/песочница написаны ДО мержа
A7 в эту ветку, и после «подтяжки main» (`3d79a14`, разрешение
конфликтов + `tests/` 1323 OK) collateral-эффект на СОБСТВЕННЫЙ
приёмочный набор этой задачи не был перепроверен. См. замечание R1-F1 —
это не только дефект плана, но и подтверждённый исполнением дефект кода
песочницы (Фаза B).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (коммит, лок, журнал sha+reason) | реализовано | `_cmd_amend_tests` (orchestrator/amend.py:107-152); юнит-тестами покрыты хелперы, но сквозной приёмочный тест AC-1 сейчас не проходит из-за R1-F1 (фикстура, не логика команды) |
| 2 (три именованных отказа + лок-не-стоял) | реализовано | AC-2/AC-3/AC-4/AC-5 в коде есть; сквозная проверка блокирована R1-F1 |
| 3 (журнал — признаваемое основание, без ссылки на ADR) | реализовано | коммит формируется командой, ADR не требуется в сообщении |
| 4 (метка «правка планки», отчётность, порог/алерт) | реализовано | `AMEND_ACTION`, `report._all_steps` без нового кода, `alerts.raise_alert`; юнит-тесты окна/счётчика зелёные (tests/test_amend.py) |
| 5 (не оценивает существо, не запускает агентов) | реализовано | нет обращений к `runner.spawn_agent`/оценке диффа |
| 6 (обязательный прогон, маркер красноты, итог в журнале) | реализовано технически | `acceptance.run` + `guard.scan_redness_markers`, `_run_summary`; сквозная проверка AC-10/AC-11 блокирована R1-F1 |

## Замечания

- **blocker** — `tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/_sandbox.py:230-273` (`AmendSandbox.setUp`/`enter_in_dev`) — приёмочный набор этой же задачи (единственное сквозное доказательство AC-1..AC-12) фактически НЕ ПРОХОДИТ на текущем HEAD ветки. Воспроизведено исполнением:
  `python3 -m unittest discover -s tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests -v` → `Ran 14 tests ... FAILED (failures=1, errors=13)`.
  Причина: после мержа A7 в эту ветку (`3d79a14`) `catalog.cmd_new` больше не заводит worktree/кодовую ветку задачи автоматически (см. докстринг `catalog.cmd_new`, требование A7 №2, и докстринг `LockTest` в `tests/test_acceptance_tests_flow.py`: «cmd_new больше не заводит worktree/кодовую ветку задачи... код задачи заводится явно»). `AmendSandbox.setUp` (строка 230) вызывает `catalog.cmd_new`, затем сразу вычисляет `self.tdir = workspace.path(self.TASK) / "tasks" / self.TASK` (строка 235) и в `enter_in_dev` (строка 270) пишет в этот путь `SPEC.md` — ни разу не вызвав `workspace.ensure(self.TASK, branch)` (или эквивалент — заведение кодовой ветки/worktree, как это вручную делает `LockTest.setUp`). Каталог физически не существует → `FileNotFoundError` на первой же попытке записи. Затронуты все тесты, которые доходят до `enter_in_dev()`: test_ac1, test_ac2, test_ac3, test_ac5, test_ac6, test_ac7, test_ac8, test_ac9, test_ac10 (оба метода), test_ac11, test_ac12 (оба метода) — 13 из 14.
  Предложение: в `AmendSandbox.setUp` перед первой записью в `self.tdir` явно завести кодовую ветку/worktree задачи — либо вызвать `workspace.ensure(self.TASK, t["branch"])` (если `amend.py` действительно ожидает `tasks/<id>/acceptance_tests/` в worktree кодовой ветки — что, судя по production-коду `amend.py:120` (`workspace.ensure(task_id, t["branch"])`), верно и для собственно команды), либо взять рецепт `LockTest.setUp` целиком (явное `git checkout -b <code_branch>` + коммит фиктивного файла + возврат на артефактную/main-ветку) — какой из двух путей ближе к реальному потоку роли-разработчика, решает исполнитель, но фикстура обязана давать зелёный прогон.

- **blocker** — `tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/_sandbox.py:50-57` (`BASELINE_COMMANDS`) — снимок команд диспетчера устарел относительно текущего HEAD: не содержит `"pin-update"`, которая уже присутствует в таблице `orchestrator/artel.py::main` (внесена A7, тоже пришла мержем `3d79a14`). Из-за этого `discover_amend_command_name()` видит ДВЕ новые команды (`{"amend-tests", "pin-update"}`) вместо одной и падает `AssertionError`. Воспроизведено исполнением — единственный тест, доходящий до этой точки без R1-F1 (у него нет `enter_in_dev()`):
  `python3 -m unittest tasks.01M1HNNHDMP2C1AJTH5QF1BTN2.acceptance_tests.test_ac4_lock_not_set_refuses` → `AssertionError: в таблице диспетчера появилось больше одной новой команды: ['amend-tests', 'pin-update']`.
  После исправления R1-F1 эта же ошибка проявится во ВСЕХ 14 тестах (сейчас 13 из них не долетают до неё только потому, что раньше падают в `enter_in_dev`). Предложение: добавить `"pin-update"` (и вообще сверить полный текущий список команд `orchestrator/artel.py::main` на момент HEAD этой ветки) в `BASELINE_COMMANDS`.

Обе находки — один класс («приёмочная песочница задачи не сверена с состоянием ветки после подтяжки A7», коммит `3d79a14`, где `tests/` перепроверены, а `tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/` — нет). Юнит-тесты `tests/test_amend.py` (17/17 OK) и логика самой команды `orchestrator/amend.py` при чтении не вызывают подобных сомнений — обе находки локализованы в тестовой песочнице задачи, не в production-коде.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/_sandbox.py:230-273 | `AmendSandbox` не заводит кодовую ветку/worktree задачи (пост-A7 `cmd_new` этого не делает сама) перед записью в `self.tdir` | 13 из 14 приёмочных тестов задачи падают `FileNotFoundError`, AC-1..AC-3, AC-5..AC-12 фактически не проверены сквозным прогоном | завести worktree/кодовую ветку явно в `setUp`/`enter_in_dev` (напр. `workspace.ensure`) до первой записи в `self.tdir` |
| R1-F2 | open | tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/_sandbox.py:50-57 | `BASELINE_COMMANDS` не включает `"pin-update"`, уже существующую в диспетчере после мержа A7 | `discover_amend_command_name()` падает `AssertionError` («больше одной новой команды») на любом тесте, реально доходящем до вызова команды; подтверждено на test_ac4 | добавить `"pin-update"` (и сверить полный список) в `BASELINE_COMMANDS` |

## Вердикт

changes_requested — исправить R1-F1 и R1-F2 (приёмочная песочница
задачи), затем прогнать `tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/`
и приложить результат («Проверено исполнением» следующей итерации).
Production-код `orchestrator/amend.py`/`orchestrator/artel.py` и юнит-тесты
`tests/test_amend.py` при чтении и прогоне нареканий не вызвали — после
починки фикстуры ожидаю быстрое схождение, если сквозной прогон не
вскроет новых дефектов уже в самой команде.

## Проверено исполнением

- `python3 -m unittest tests.test_amend -v` — 17 тестов, все `OK`.
- `python3 -m unittest discover -s tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests -v` — `Ran 14 tests in 4.210s`, `FAILED (failures=1, errors=13)` (см. R1-F1/R1-F2).
- `python3 -m unittest tasks.01M1HNNHDMP2C1AJTH5QF1BTN2.acceptance_tests.test_ac1_successful_amend_commits_locks_journals -v` — изолированный прогон одного файла, тот же `FileNotFoundError` (не артефакт совместного discover-прогона).
- `python3 -m unittest tasks.01M1HNNHDMP2C1AJTH5QF1BTN2.acceptance_tests.test_ac4_lock_not_set_refuses -v` — `AssertionError` про `BASELINE_COMMANDS` (R1-F2), отдельно от R1-F1.
- Чтение сигнатур `store.update_task`/`store.journal`/`store.all_tasks`/`store.task_steps`/`store.resolve_task_id`/`store.get_task`/`store.open_alerts`, `alerts.raise_alert`, `gitcmd.in_repo`/`head_sha`, `workspace.ensure`/`path`, `lease.run_locked`, `acceptance.run`, `guard.scan_redness_markers`, `report._all_steps` — все вызовы в `orchestrator/amend.py` и `tests/test_amend.py` соответствуют реальным сигнатурам.
- Сверка `tests_locked_sha=` конвенции (`store.update_task` без `updated_at`) с существующим вызывающим местом `orchestrator/fsm_advance.py:401` — совпадает, не отклонение.
- `git log -- tests/test_new_argv_parsing.py` / чтение файла — подтверждено, что «Ловит мутацию:»-докстринги в проекте требуются для `acceptance_tests/` (test-authoring), а не для обычных юнит-тестов `tests/*.py`; отсутствие таких докстрингов в `tests/test_amend.py` — не отклонение от конвенции.

## Предложения системе

- `tasks/<id>/acceptance_tests/` песочницы, построенные поверх
  `RealGitSandbox`/`catalog.cmd_new`, стоит явно предупреждать (в
  `templates/`/skills для test_author) о пост-A7 поведении `cmd_new`
  (не заводит кодовую ветку/worktree сама) — иначе класс дефекта
  R1-F1 будет повторяться в каждой задаче, чья песочница написана по
  аналогии со старыми (до-A7) приёмами.
- «Подтяжка main в ветку задачи» (conventions-core уже фиксирует
  регенерацию codebase-map при такой подтяжке) стоит расширить явным
  напоминанием прогнать СОБСТВЕННЫЙ `tasks/<id>/acceptance_tests/`
  задачи, не только `tests/` — оба найденных дефекта (R1-F1, R1-F2)
  возникли именно потому, что после `3d79a14` был перепроверен только
  общий набор.
