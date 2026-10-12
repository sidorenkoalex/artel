---
task: 01M4RRW7FT1EE77EY9Y462AZKC
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Проект задачи — флаг `new --target`, однозначный выбор проекта и клон в `target-init`

## Подход
Три точки правки кода, всё в рамке решений Оператора на гейте SPEC (В-1, В-2).

- `orchestrator/artel.py`: помощник `_new_target_arg` снимает пару
  `--target <имя>` из argv по образцу `_new_set_arg` до `_parse_new_args`
  (форма его возврата не меняется); флаг без значения или со значением-флагом
  — именованный отказ. `_cmd_new` спрашивает `catalog.new_cli_target(flag)`
  и зовёт `catalog.cmd_new` с keyword `target=` только когда проект назван —
  без флага при одной записи вызов прежний, без `target=`. `_NEW_USAGE` и
  строка `new` общей справки называют `[--target <имя>]`.
- `orchestrator/catalog.py`:
  - `new_cli_target` — правило требования 3 только для командной строки:
    флаг есть — он; нет флага и записей `targets.yaml` больше одной — отказ
    «укажи проект: --target <одно из …>»; одна запись или нечитаемый файл —
    `None` (артель).
  - `_checked_target` — первым рубежом `cmd_new`, до набора моделей, ТЗ,
    `ensure_clone`, id, ссылки и строки БД: явный проект при нечитаемом
    файле или необъявленный проект — отказ с перечнем объявленных;
    `target=None` при нечитаемом `targets.yaml` — предупреждение
    «сверка проекта с targets.yaml пропущена», задача в артель (В-1 (а)).
  - `_project_line_reasons` — разбор строк `^Проект:` ТЗ тем же рубежом, что
    «Порядок:» (до `ensure_clone`), канарейка не разбирает; одна строка
    обязана совпасть с проектом, две и более — отказ.
  - Запись журнала `created` несёт проект: детали `<название> (проект <имя>)`
    (колонка `steps.target` уже есть; вывод `new` проект печатал и прежде —
    «(target <имя>, …)»).
- `orchestrator/projects.py::cmd_target_init`: сверка имени — как была,
  первой (каталоги после неё); после каталогов — `workspace.ensure_clone`
  (идемпотентен: существующий клон не трогает), неудача — `sys.exit` с
  причиной, каталоги остаются.

Тесты: долгоживущий файл задачи `tests/test_01m4rrw7ft1ee77ey9y462azkc_project_target.py`
покрывает все мутации требования 7 (флаг не передан, неизвестный проект,
две записи без флага, строка «Проект:» после клона/не сверена, клон в
`target-init`, правило 3 в `cmd_new`, каталоги до сверки, нечитаемый
`targets.yaml`) — своих дублирующих тестов не добавляю. Перестановки
подготовки по разделу «Меняемое поведение» SPEC — без смены утверждений.

## Шаги
1. `artel.py`: `_new_target_arg`, `_cmd_new`, `_NEW_USAGE`, общая справка.
2. `catalog.py`: `new_cli_target`, `_checked_target`, `_project_line_reasons`,
   рубеж в `cmd_new`, проект в записи `created`.
3. `projects.py`: клон в `cmd_target_init`.
4. Тесты подготовки: `make_project_repo("sled")` до `cmd_target_init("sled")`
   в `tests/test_git_fixation.py` (`ExternalTargetAdvanceIgnoresDirtyCheckTest`,
   `ExternalIntegrityIncidentBlocksRunTest`,
   `ExternalApproveDoesNotCommitOthersWorkInProgressTest`) и
   `tests/test_doctor.py::RecoveryCheckTest`; комментарии
   `tests/test_git_fixation.py` (~246) и `tests/test_multitarget.py` (~273);
   `NewSetFlagTest.setUp` подменяет `config.TARGETS` временной декларацией
   одной артели (`tests.sandbox.declared_artel_profile`), утверждения
   методов не тронуты.
5. `python3 scripts/codebase_map.py` — карта регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 1, 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 3, 4 |
| 7 | долгоживущий файл задачи; 4 |
| 8 | 5 |

## Влияние на систему
- `catalog.cmd_new` теперь читает `targets.yaml` в начале для любого
  проекта, включая артель: при читаемом файле без записи артели задача
  артели отказывает (это и есть требование 2); нечитаемый файл для
  `target=None` — предупреждение, поведение прежнее. Канарейка
  (`canary_drive`) и `spawn_subtask` правило «укажи проект» не видят — оно
  только в `new_cli_target`.
- `target-init` теперь ходит в сеть (`git clone`), если клона нет;
  существующий клон не трогается. Тесты, звавшие `target-init` без клона,
  переставлены (клон до вызова) — проверки не менялись.
- Гейты, лимиты, инварианты не трогаются. Откат — revert merge-коммита.
- Проверено: долгоживущий файл задачи и затронутые модули (`test_multitarget`,
  `test_git_fixation`, `test_doctor`, `test_task_model_set_units`,
  `test_new_argv_parsing`) — зелёные; `suite-run` №1 полного набора —
  зелёный (прошло 5151, упало 0). `plank-run` — планки `acceptance_tests/`
  у задачи нет (зафиксирован только долгоживущий файл).

## Риски
- Тесты вне перечня SPEC, где `targets.yaml` песочницы не несёт артели, а
  `cmd_new` зовётся без `target`, отказали бы новой сверкой — проверяется
  полным прогоном `suite-run`.

## Предложения системе
