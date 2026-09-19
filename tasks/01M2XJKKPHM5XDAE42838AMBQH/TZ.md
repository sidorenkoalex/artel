---
task: 01M2XJKKPHM5XDAE42838AMBQH
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Guard планки: артефакты задачи читаются только из артефактной ветки, отказ на выходе tests_writing

Источник: копилка docs/backlog.md, строки П2 12.09 «Планка читает
артефакты задачи с диска, а пульт при прогоне материализует только
acceptance_tests/» и П1 13.09 «Повтор класса 12.09 (AC-8 01M2B6K3EM):
планка задачи 01M2CN465W (test_ac4) читает tasks/<id>/PLAN.md с диска».
Решение Оператора 19.09: заводить сейчас, до волны 5.

Инциденты:
- 12.09, 01M2B6K3EM, тест AC-8: `Path(__file__)…/PLAN.md` прошёл у
  test_author в worktree (артефакты лежат на диске во время шага) и
  покраснел на прогоне пультом после подтяжки main — эскалация
  «приёмочные тесты красные после подтяжки», правка Оператора через
  amend-tests на чтение через `gitcmd.show`.
- 13.09, 01M2CN465W, test_ac4: тот же класс, тот же обход (amend-tests +
  answer). Второй случай за сутки — антипаттерн повторился.
- Правило «читать артефакты из ветки» живёт только в памяти ассистента
  и в исправленных планках (образец: tasks/01M2CN465WEDCF6D77V37FJ82E/
  acceptance_tests/test_ac4_invariants_diff_attachment.py —
  `gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/PLAN.md")`).

Причина (по коду):
- `orchestrator/pull.py::_materialize_and_run_plank` и
  `orchestrator/acceptance.py::materialize_from_branch` кладут в worktree
  ТОЛЬКО `tasks/<id>/acceptance_tests/`; PLAN.md/SPEC.md/REVIEW.md/TZ.md/
  ANSWER-n.md на диске прогона нет — среда автора не равна среде гейта.
- Сухой сбор на выходе tests_writing
  (`orchestrator/advance_gates/tests_writing.py::
  _tests_writing_dry_collect_gate`) проверяет только импорт и синтаксис
  планки; статических проверок содержимого планки в `scripts/guard.py`
  несколько (`scan_indented_ac_markers`, `scan_redness_markers`,
  `test_functions_without_mutation_claim`), но проверки источника
  артефактов среди них нет.
- Пометка «Красен до реализации» маскирует дефект среды до первого
  прогона пультом.

Требуется:
1. `scripts/guard.py`: статическая проверка планки (`*.py` в
   `acceptance_tests/`) — чтение артефактов задачи с диска. Ошибка, если
   имя артефакта (`PLAN.md`, `SPEC.md`, `REVIEW.md`, `TZ.md`,
   `QUESTIONS.md`, `TEST_REPORT.md`, `ANSWER-`) встречается в строковом
   литерале, участвующем в выражении доступа к файловой системе (`Path(…)`
   и операции `/` с ним, `open(`, `.read_text(`, `os.path.join`,
   `os.path.exists`). Чтение через `gitcmd.show(…)`, `artifact_branch`,
   `subprocess` с `git show`/`git cat-file` ошибкой не считается. Текст
   ошибки называет файл, строку и рецепт: «читай из артефактной ветки:
   gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/PLAN.md")».
   Проверка — отдельная функция guard, вызываемая гейтом; в `check()`/
   `main()` guard (CI «Валидация артефактов» по всему `tasks/`) НЕ
   включается: исторические планки не переписываются.
2. Гейт на выходе `tests_writing` (`orchestrator/advance_gates/
   tests_writing.py`, рядом с сухим сбором): отказ проверки 1 отклоняет
   переход именованным действием «переход отклонён: планка читает
   артефакты с диска» с текстом ошибок — тот же класс отказа, что и
   остальные отказы этого состояния (шаг test_author повторяется с
   историей отказов в брифе, стоп-кран T038 не срабатывает раньше шага
   роли).
3. Тот же отказ на входе штатной правки планки: аналитик сверяет по коду,
   прогоняет ли `amend-tests` (`orchestrator/amend.py`) проверки guard
   планки; если да — проверка 1 включается тем же путём без правки
   amend.py, если нет — фиксирует в SPEC как «Не входит» с указанием,
   где именно её добавить (amend.py вне зон этой задачи).
4. Правило для роли: приложением к PLAN.md unified diff к
   `skills/test-authoring.md` (защищённый путь, применяет Оператор) —
   абзац «Источник артефактов задачи в планке: только артефактная ветка
   через gitcmd.show(artifact_branch.branch_name(TASK_ID), …); диск
   рабочей копии — не источник, пульт материализует только
   acceptance_tests/».
5. Тесты (tests/): планка с `Path(__file__)…/"PLAN.md"` — ошибка с именем
   файла и строкой; планка с `gitcmd.show(...)` и с `subprocess git show`
   — ошибок нет; упоминание имени артефакта в докстринге или комментарии
   — не ошибка; гейт tests_writing отказывает именованным действием и
   роль получает историю отказа; `scripts/guard.py` в режиме CI по
   `tasks/` с историческими планками, читающими с диска, остаётся
   зелёным. Существующие `tests/test_guard_*.py`,
   `tests/test_acceptance_collect.py`,
   `tests/test_fsm_advance_tests_writing_dry_collect.py` остаются
   зелёными.

Зоны: scripts/guard.py, orchestrator/advance_gates/tests_writing.py,
tests/.

Только чтение (не менять): orchestrator/pull.py, orchestrator/acceptance.py
(материализация не меняется — планка должна жить в среде гейта, а не
гейт подстраиваться под планку), orchestrator/amend.py (см. требование 3),
orchestrator/gitcmd.py, orchestrator/artifact_branch.py (образец чтения).

Приложением: skills/test-authoring.md (unified diff в PLAN.md, защищённый
путь).

Не входит: guard SPEC на критерий «о содержании документа без пометки
manual» (кандидат (б) строки копилки 12.09 — отдельное ТЗ, эвристика по
тексту); материализация полного `tasks/<id>/` в worktree при прогоне;
переписывание исторических планок.

Рамка: $40.
