---
task: 01M2XJKKPHM5XDAE42838AMBQH
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: scripts/guard.py, orchestrator/advance_gates/tests_writing.py, tests/
budget_usd: 40
---

# SPEC: Guard планки: артефакты задачи читаются только из артефактной ветки, отказ на выходе tests_writing

## Контекст

Приёмочная планка задачи пишется в worktree, где `tasks/<id>/` лежит на
диске целиком, а прогоняется пультом в среде, где из этого каталога
материализован ТОЛЬКО `acceptance_tests/`
(`orchestrator/pull.py::_materialize_and_run_plank`,
`orchestrator/acceptance.py::materialize_from_branch`). Тест, читающий
`PLAN.md`/`SPEC.md`/`REVIEW.md` с диска, поэтому зелен у автора и красен
на гейте. Класс сработал дважды за сутки: 12.09 задача 01M2B6K3EM,
тест AC-8 (`Path(__file__)…/PLAN.md`), и 13.09 задача 01M2CN465W,
`test_ac4` — оба закрыты вручную через `amend-tests`. Правило «читать
артефакты из артефактной ветки» сегодня не записано нигде, кроме памяти
и уже исправленных планок; сухой сбор на выходе `tests_writing`
(`orchestrator/advance_gates/tests_writing.py::_tests_writing_dry_collect_gate`)
проверяет импорт и синтаксис, но не источник артефактов, а пометка
«Красен до реализации» маскирует дефект среды до первого прогона пультом.

## Требования

1. `scripts/guard.py`: статическая проверка планки — отдельная функция,
   принимающая `*.py` каталога `acceptance_tests/`. Ошибка, если имя
   артефакта задачи (`PLAN.md`, `SPEC.md`, `REVIEW.md`, `TZ.md`,
   `QUESTIONS.md`, `TEST_REPORT.md`, `ANSWER-`) встречается в строковом
   литерале, участвующем в выражении доступа к файловой системе:
   `Path(…)` и операции `/` с ним, `open(`, `.read_text(`,
   `os.path.join`, `os.path.exists`.
2. Чтение того же артефакта через `gitcmd.show(…)`, через
   `artifact_branch`, а также через `subprocess` с `git show`/
   `git cat-file` ошибкой не считается. Имя артефакта в докстринге или
   комментарии ошибкой не считается.
3. Текст ошибки называет файл, номер строки и рецепт: «читай из
   артефактной ветки: gitcmd.show(artifact_branch.branch_name(TASK_ID),
   "tasks/<id>/PLAN.md")».
4. Проверка вызывается гейтом (требование 5) и НЕ включается в
   `check()`/`main()` `scripts/guard.py` — режим CI «Валидация
   артефактов» по всему `tasks/` её не исполняет: исторические планки не
   переписываются.
5. Гейт на выходе `tests_writing`
   (`orchestrator/advance_gates/tests_writing.py`, рядом с сухим сбором):
   отказ проверки требования 1 отклоняет переход именованным действием
   «переход отклонён: планка читает артефакты с диска» с текстом ошибок
   — тот же класс отказа, что остальные отказы этого состояния, то есть
   шаг `test_author` повторяется с историей отказов в брифе
   (`brief.advance_refusal_history`), а стоп-кран T038 не срабатывает
   раньше шага роли.
6. Приложением к PLAN.md — unified diff к `skills/test-authoring.md`
   (защищённый путь, применяет Оператор) с абзацем: «Источник артефактов
   задачи в планке: только артефактная ветка через
   gitcmd.show(artifact_branch.branch_name(TASK_ID), …); диск рабочей
   копии — не источник, пульт материализует только acceptance_tests/».
7. Тесты в `tests/` на поведение требований 1–5; существующие
   `tests/test_guard_*.py`, `tests/test_acceptance_collect.py`,
   `tests/test_fsm_advance_tests_writing_dry_collect.py` остаются
   зелёными.

## Критерии приёмки

AC-1. Планка с чтением артефакта с диска (`Path(__file__)…/"PLAN.md"`,
а равно `open(`, `.read_text(`, `os.path.join`, `os.path.exists` со
строковым литералом имени артефакта) даёт ошибку новой функции
`scripts/guard.py`; текст ошибки называет имя файла планки, номер строки
и рецепт «читай из артефактной ветки:
gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/PLAN.md")».

AC-2. Планка, читающая артефакт через `gitcmd.show(…)` либо через
`artifact_branch`, ошибок новой функции не даёт.

AC-3. Планка, читающая артефакт через `subprocess` с `git show` или
`git cat-file`, ошибок новой функции не даёт.

AC-4. Упоминание имени артефакта (`PLAN.md`, `SPEC.md`, `REVIEW.md`,
`TZ.md`, `QUESTIONS.md`, `TEST_REPORT.md`, `ANSWER-`) в докстринге или
комментарии планки ошибкой не считается.

AC-5. Каждое из имён `PLAN.md`, `SPEC.md`, `REVIEW.md`, `TZ.md`,
`QUESTIONS.md`, `TEST_REPORT.md`, `ANSWER-` в выражении доступа к
файловой системе даёт ошибку; область проверки — все `*.py` каталога
`acceptance_tests/`, не только `test_*.py`.

AC-6. `advance` на выходе `tests_writing` при непустом результате
проверки отклоняет переход: в журнале — действие «переход отклонён:
планка читает артефакты с диска», в detail — текст ошибок; задача
остаётся в состоянии `tests_writing`.

AC-7. Этот отказ — того же класса, что остальные отказы `tests_writing`:
он попадает в историю отказов брифа роли (`brief.advance_refusal_history`)
и шаг `test_author` повторяется, стоп-кран T038 не срабатывает раньше
шага роли.

AC-8. `python3 scripts/guard.py --all` (режим CI «Валидация артефактов»
по `tasks/`) на дереве, где есть исторические планки, читающие артефакты
с диска, остаётся зелёным: новая функция не вызывается ни из `check()`,
ни из `main()`.

AC-9. PLAN.md несёт приложением unified diff к `skills/test-authoring.md`
с абзацем требования 6, и в PLAN.md подтверждено, что `git apply --check`
на этом дифе прошёл на чистом дереве.

AC-10. Прогон `python3 -m pytest tests/` зелёный; в частности
`tests/test_guard_*.py`, `tests/test_acceptance_collect.py`,
`tests/test_fsm_advance_tests_writing_dry_collect.py`.

## Оценка объёма и деление

Прогноз диффа: 16 КиБ.

Сработавшие сигналы:
- **число затрагиваемых модулей/файлов** — по тексту SPEC регулярка
  `guard._zone_paths` насчитывает ≥ 5 путей `orchestrator/*.py` /
  `scripts/*.py`. Фактических зон правки три
  (`scripts/guard.py`, `orchestrator/advance_gates/tests_writing.py`,
  `tests/`); остальные пути (`orchestrator/pull.py`,
  `orchestrator/acceptance.py`, `orchestrator/amend.py`,
  `orchestrator/gitcmd.py`, `orchestrator/artifact_branch.py`,
  `orchestrator/fsm_advance.py`) упомянуты только как «только чтение» и
  адреса причины — их задача не трогает.
- **число критериев приёмки** — 10, ровно на пороге
  `config.SPLIT_SIGNAL_AC_COUNT`.
- **затронут инвариантный механизм** — `scripts/guard.py` упомянут в
  `docs/invariants.md:90` (инвариант «новые правила guard и гейтов
  действуют на живые задачи, история не переписывается»). Этот инвариант
  задача не ослабляет, а исполняет буквально: требование 4 прямо
  запрещает включать проверку в CI-режим по всему `tasks/`.

**Обоснование монолита.** Разрезать нечего: проверка guard без гейта —
мёртвый код, который никто не зовёт (требование 4 запрещает единственный
другой вызов — `check()`/`main()`), а гейт без проверки не существует.
Обе половины — одна смена механики в двух файлах общим объёмом ~110
строк; промежуточное состояние «функция есть, гейт не зовёт» не даёт
системе ничего и оставляет тот же дефект открытым. Правило для роли
(требование 6) — не отдельная задача, а приложение-диф в том же PLAN.md,
применяет его Оператор.

## Не входит

- **Проверка guard в `amend-tests`.** Сверка по коду (требование 3 ТЗ):
  `orchestrator/amend.py::cmd_amend_tests` зовёт из guard только
  `guard.acceptance_traceability_errors` (`orchestrator/amend.py:315`) и
  `guard.scan_redness_markers` (`orchestrator/amend.py:329`) — общего
  прогона проверок планки там нет, поэтому новая функция в `amend-tests`
  сама НЕ включится. Добавлять её следует в `cmd_amend_tests` рядом с
  блоком трассируемости (`orchestrator/amend.py:311–320`), до прогона
  планки `acceptance.run(tdir)` (`orchestrator/amend.py:322`), отказом в
  стиле `_refuse_traceability`. `orchestrator/amend.py` — вне зон этой
  задачи, правка отдельным ТЗ.
- Guard SPEC на критерий «о содержании документа без пометки manual»
  (кандидат (б) строки копилки 12.09) — отдельное ТЗ, эвристика по
  тексту.
- Материализация полного `tasks/<id>/` в worktree при прогоне:
  `orchestrator/pull.py` и `orchestrator/acceptance.py` не меняются —
  планка должна жить в среде гейта, а не гейт подстраиваться под планку.
- Переписывание исторических планок и любой backfill по `tasks/`.
- Включение новой проверки в `check()`/`main()` `scripts/guard.py` (CI
  «Валидация артефактов»).
- Новых состояний FSM и новых шагов между существующими состояниями
  задача не вводит — гейт встраивается в уже существующий переход
  `tests_writing -> in_dev`; правки `tests/test_invariants.py` не
  предполагается.
- Правка `skills/test-authoring.md` в ветке задачи: только unified diff
  приложением к PLAN.md, применяет Оператор (защищённый путь).

## Материалы

- ТЗ: `tasks/01M2XJKKPHM5XDAE42838AMBQH/TZ.md`.
- Копилка `docs/backlog.md`: П2 12.09, П1 13.09.
- Образец правильного чтения:
  `tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/test_ac4_invariants_diff_attachment.py`
  — `gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/PLAN.md")`.
- Соседний гейт того же состояния (образец формы отказа):
  `orchestrator/advance_gates/tests_writing.py:158`
  `_tests_writing_dry_collect_gate` → `GateRefusal("переход отклонён:
  планка не собирается", …)`; вызов —
  `orchestrator/fsm_advance.py:337`.
- Образцы отдельной функции guard над `acceptance_tests/`:
  `scripts/guard.py:390` `scan_redness_markers`, `scripts/guard.py:867`
  `scan_indented_ac_markers`.
