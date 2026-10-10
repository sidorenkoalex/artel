---
task: 01M4JD3SRN66SD6BM63XAGHB11
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Приложения PLAN — рубеж in_dev → verifying и CI ветки по одному правилу

## Подход

Одно правило «уже в базе» и одна запись журнала — в
`orchestrator/advance_gates/plan_appendix.py`, его зовут все три узла пульта;
рубеж `in_dev -> verifying` гоняет планку на дереве `appendix_tree.suite_tree`.

- **Правило** — `plan_appendix.in_base(tree, appendix)`: `git apply --reverse
  --check` проходит. **Узел с записью** — `plan_appendix.skip_in_base(conn,
  task_id, number, appendix, tree, where, outcome)`: правило плюс запись
  журнала нынешней формы гейта применимости (действие
  `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION: <пути>`, подробности «приложение N
  (<пути>) уже наложено в <where> … — <outcome>»).
- **Гейт применимости** (`_plan_appendix_gate`) зовёт `skip_in_base` вместо
  прежнего `_appendix_already_in_base` (текст записи тот же). Отказ
  неприменимого теперь называет номер: «приложение N PLAN (<пути>) не
  применяется к базе сравнения …» — та же форма, что у `appendix_tree`
  (требование 2: рубеж отказывает этим гейтом раньше, чем прогоном планки).
- **Гейт мержа** — `_appendix_already_in_main` стал тонкой обёрткой над
  `skip_in_base` с `where="подтянутом main"`: действие теперь общее, слово
  «main» осталось в подробностях (держит
  `test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied::AlreadyAppliedAppendixTest`).
- **Дерево полного прогона** — `_prepared` разделён на `_checked_out`
  (временное дерево) и `_overlaid` (наложение с признанием); `_prepared`
  сохранил сигнатуру и ответ `(признак, отказ)` для
  `tests/test_appendix_tree.py` и признаёт по `in_base` без записи;
  `suite_tree` зовёт обе части напрямую с `skip_in_base` (запись в журнал
  задачи). Признак прогона «уже в дереве: приложения N» сохранён.
  `SuiteTree` получил поле `fixable` (по умолчанию `False`): отказ по
  содержимому PLAN (не разобран / не накладывается) против сбоя git.
  Параметр `not_run` — хвост отказа («полный набор не запускался» по
  умолчанию; рубеж называет свой прогон).
- **Рубеж `in_dev -> verifying`** (`_acceptance_run_body`): после проверок
  рабочей копии — `suite_tree(conn, task_id, run_cwd, not_run=PLANK_NOT_RUN)`
  на HEAD рабочей копии с её незакоммиченными правками (как `suite-run`):
  рубеж судит то же дерево, что прежде, плюс приложения. Планка выкладывается
  и долгоживущие файлы гоняются в `tree.root`; PLAN без приложений и проект
  не артели — `tree.root` = рабочая копия, поведение прежнее. Отказ дерева —
  запись действием `PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION`, если
  `fixable` (класс «чинит роль»), иначе `PLAN_APPENDIX_GATE_FAILURE_ACTION`;
  планка не запускается. Зелёная карточка помечена `tree.mark`.
- **CI-скрипт** — своя копия правила `in_base(appendix)` поверх
  `apply_appendix(appendix, "--reverse", "--check")`; уже наложенное —
  строка «[id] приложение N (<пути>) уже в базе: …», код 0; ни прямо, ни
  обратно — код 1, как прежде. Пакет `orchestrator` не импортируется.

Бюджет SPEC ($40) не пересматриваю.

## Шаги

1. `plan_appendix.py`: `in_base`, `skip_in_base`, номер в отказе гейта.
2. `fsm_merge_gate.py`: `_appendix_already_in_main` → `skip_in_base`.
3. `appendix_tree.py`: `_checked_out`/`_overlaid`, `skip_in_base` в
   `suite_tree`, `SuiteTree.fixable`, `not_run`.
4. `advance_gates/acceptance.py`: прогон планки рубежа на `suite_tree`.
5. `scripts/plan_appendix_ci.py`: правило «уже в базе» и строка вывода.
6. Юнит-тесты `tests/test_appendix_tree.py::SuiteTreeRefusalClassTest`
   (класс отказа `fixable` и хвост `not_run` — свойства вне долгоживущих
   файлов); общая обвязка вынесена в базовый `GitTreeCase`, методы
   `PreparedTreeTest` не тронуты. Карта — `scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 3, 4 |
| 2 | 1, 3, 4 |
| 3 | 1, 2, 3, 5 |
| 4 | 1, 2, 3, 5 |
| 5 | 1, 5 |
| 6 | 1, 3, 5 |
| 7 | 6 (ожидания существующих тестов не менялись) |

Проверка: долгоживущие файлы задачи
(`tests/test_01m4jd3srn66sd6bm63xaghb11_*.py`, 11 тестов — AC-1…AC-9) зелёные;
существующие `tests/test_appendix_tree.py`, `test_plan_appendix.py`,
`test_plan_appendix_ci.py`, `test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`,
`test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`,
`test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`,
`test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`,
`test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`,
`test_long_lived_transitions.py`, `test_external_code_copy_refusal.py`,
`test_refusal_classes.py` — зелёные локально. Новые тесты проверены
временной мутацией (`fixable` всегда ложен / всегда истинен) — красные.

## Влияние на систему

- Ослабления нет: неприменимое в обе стороны приложение — по-прежнему отказ
  во всех четырёх узлах (AC-7); признание требует `--reverse --check`.
- Рубеж `in_dev -> verifying` теперь может отказать по дереву приложений —
  новый отказ, не ослабление; для задач без приложений поведение прежнее
  (`suite_tree` отдаёт рабочую копию).
- Гейт мержа пишет пропуск действием «приложение PLAN уже в базе: …» вместо
  «приложение PLAN уже в main: …» — по требованию 4; читателей прежнего
  действия в коде нет (grep).
- Отказ гейта применимости сменил текст: «приложение N PLAN (<пути>) не
  применяется…» вместо «приложение PLAN <пути> не применяется…». Действие
  журнала то же; тестов на прежний текст нет (grep).
- Откат — revert одного merge-коммита.

## Риски

- Рубеж в дереве с приложениями гоняет pytest во временном worktree клона —
  тот же приём, что у автогейта; время рубежа растёт на `git worktree add`
  только у задач с приложениями.
- Гейт применимости и дерево рубежа оба пишут «уже в базе» на одном
  переходе (база сравнения и дерево ветки) — две записи для одного
  приложения; AC-4 требует наличия записи, лишняя не вредит.

## Предложения системе

- `suite-run` отказывает «на машине уже идёт прогон … задачи другой» без
  очереди ожидания: шаг разработчика вынужден повторять вручную — не
  хватает режима «встать в очередь замка» у `artel.py suite-run`.
