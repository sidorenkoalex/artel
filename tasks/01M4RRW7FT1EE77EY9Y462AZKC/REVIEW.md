---
task: 01M4RRW7FT1EE77EY9Y462AZKC
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Проект задачи — флаг `new --target`, однозначный выбор проекта и клон в `target-init`

## Фаза A — план
- Таблица покрытия PLAN полна (требования 1–8 → шаги 1–5 и долгоживущий
  файл задачи); шаги размером с MR, не микрооперации.
- Подход в рамке решений Оператора В-1 (а) и В-2: `_new_target_arg` по
  образцу `_new_set_arg`, форма `_parse_new_args` не тронута, правило
  «укажи проект» вынесено в `catalog.new_cli_target` и в `cmd_new` не
  попало.
- «Влияние на систему» соответствует diff: тронуты `artel.py`,
  `catalog.py`, `projects.py`, подготовка тестов по разделу SPEC
  «Меняемое поведение», карта. Откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `artel.py::_new_target_arg` снимает пару до `_parse_new_args`; флаг без значения или со значением-флагом → `sys.exit`; без проекта `cmd_new` вызывается без keyword `target=` (`project = {}`); `_NEW_USAGE` и общая справка называют `[--target <имя>]`. |
| 2 | OK | `catalog._checked_target` — первая строка `cmd_new`, до набора моделей, ТЗ, `ensure_clone`, id, ссылки и строки БД; в отказе перечислены объявленные проекты; для `target=None` при нечитаемом файле печатается предупреждение и задача уходит в артель. |
| 3 | OK | `new_cli_target`: при `len(declared) > 1` без флага — отказ с «--target» и перечнем; при нечитаемом файле — `None`. В `cmd_new` правила нет (AC-4 зелёный). |
| 4 | OK | `_project_line_reasons` (`^Проект:` с `re.M`) вызывается под `if not canary` рядом с «Порядок:», до `workspace.ensure_clone` (catalog.py ~615); одна строка сверяется, при двух и более — отказ. |
| 5 | OK | Вывод `new` печатал target и раньше; деталь записи `created` теперь `"<название> (проект <имя>)"`. Других потребителей детали `created` нет (grep: `watch.py:187` читает только `session_id`). |
| 6 | OK | `projects.cmd_target_init`: сверка `targets.target` как была, до `init_project`; после каталогов вызывается `workspace.ensure_clone`, неудача → `sys.exit` с причиной, каталоги остаются. Подготовка в `test_doctor`/`test_git_fixation` переставлена, утверждения не тронуты; комментарии `test_git_fixation.py:~246` и `test_multitarget.py:273` поправлены. |
| 7 | OK | Все мутации требования держит долгоживущий файл `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`; дублей разработчик не добавил. В `NewSetFlagTest.setUp` подставлен `declared_artel_profile()`, утверждения методов не тронуты. |
| 8 | OK | После повторной генерации `scripts/codebase_map.py` карта расходится только в строке `built_at_sha`. |

Утверждения существующих тестов сверены с base по diff: в
`tests/test_doctor.py`, `tests/test_git_fixation.py`, `tests/test_multitarget.py`,
`tests/test_task_model_set_units.py` изменились только порядок подготовки,
комментарии, `setUp` и докстринг. Ни одно `assert` не удалено и не
изменено, данные под утверждениями не сужены. Это совпадает с разделом
SPEC «Меняемое поведение».

## Замечания
Нет замечаний уровня blocker или major.

Наблюдение без статуса замечания: при явном `--target artel` и нечитаемом
`targets.yaml` `_checked_target` отказывает, а `new` без флага в той же
ситуации проходит с предупреждением. SPEC делает исключение только для
`target=None`, так что поведение соответствует букве требования 2.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py tests/test_task_model_set_units.py tests/test_new_argv_parsing.py tests/test_multitarget.py tests/test_git_fixation.py tests/test_doctor.py`: 224 passed, 44 subtests passed (50.9 с).
- Временная мутация заявки изменённого метода
  `ExternalTargetAdvanceIgnoresDirtyCheckTest::test_uncommitted_plan_still_advances_for_external_target`:
  в `orchestrator/fsm.py:364` `if not current or clean:` заменено на
  `if not current:`. Прогон `pytest tests/test_git_fixation.py -k test_uncommitted_plan_still_advances_for_external_target`
  дал 1 failed, то есть заявка исполнима. Код возвращён `git checkout -- orchestrator/fsm.py`, `git status` чист.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`:
  расходится только `built_at_sha`, то есть карта свежа. Файл возвращён.
- `artel.py plank-run 01M4RRW7FT1EE77EY9Y462AZKC`: отказ «планки нет» (в
  `refs/artifacts/…` нет `test_*.py`). Это совпадает с PLAN: зафиксирован только
  долгоживущий файл, и он прогнан выше.
- CI коммита e89f217b по пакету зелёный (16 проверок); полный набор в
  шаге не гонялся (решение Оператора 05.09).

## Предложения системе
- Пакет ревью (`skills/review-checklist.md`, приём «временная мутация»):
  в шаге ревью `sed -i` по коду требует подтверждения, а Edit не может
  точечно вернуть строку, если её текст неуникален. Стоит прямо
  рекомендовать возврат через `git checkout -- <файл>`.
