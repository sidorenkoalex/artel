---
task: 01M5W27CY7K7NR9347NKD8F0NX
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab А0 — неподдержанный хостинг или гейт людей проекта: именованный отказ до первой задачи

## Подход
Одна функция поддержки `targets.unsupported_reason(name)` и две константы
исполняемых значений (`SUPPORTED_FORGES`, `SUPPORTED_MERGE_GATES`) в
`orchestrator/targets.py`; загрузка и проверка записи (`target`, `check`)
не меняются — запись по-прежнему принимает `FORGES`/`MERGE_GATES`.
Нечитаемый слой или необъявленный проект функция возвращает как `None`:
их отказ уже называет своя проверка (`targets.target`, `_checked_target`),
а артель без `targets.yaml` в песочницах не должна начать отказывать.

Точки отказа — вызов этой функции:
- `catalog.cmd_new` — сразу за `_checked_target`, до `_new_refs`,
  `workspace.ensure_clone` и `idgen.new_task_id`; отказ `sys.exit` с
  причиной, журнала задачи нет (задачи нет).
- `runner.refuse_unsupported_project(conn, task_id, command)` — общий
  отказ задач: запись журнала `отказ: проект не поддержан` (detail —
  команда, проект, причина) и `sys.exit` с причиной. Зовут его первым
  действием ВНУТРИ тел под lease-обвязкой (возврат из verifying, CI
  40330101818: вызов в публичных `cmd_run`/`cmd_auto`/`cmd_approve` до
  обвязки нарушал линтер «обвязка команды — только
  `lease.run_task_command`» и читал БД при подменённой обвязке):
  `runner._cmd_run` (до бюджета, подтяжки, агента и git),
  `auto._cmd_auto` (до `_auto_cycle` — значит до `_pre_advance_step`,
  `fsm.cmd_advance`, опроса CI) и `fsm._cmd_approve` (до таблицы
  состояний, в любом состоянии; ленивый импорт `runner`, как прочие
  ленивые импорты `fsm.py`). Тела этих команд вызываются только через
  обвязку, других вызывателей нет.
- `doctor/cli.project_support_check(name)` — строка
  `project-support-<проект>` первой в цикле записей `all_checks`: `fail`
  с причиной или `ok`.

Сравнений `forge`/`merge_gate` с литералами вне `targets.py` не
добавляется (сторож AC-9).

## Шаги
1. `targets.py`: константы и `unsupported_reason`.
2. Точки отказа: `catalog.cmd_new`, `runner.refuse_unsupported_project` +
   вызовы в `runner._cmd_run`, `auto._cmd_auto`, `fsm._cmd_approve`.
3. `doctor/cli.py`: `project_support_check` в `all_checks`.
4. Регенерация `docs/codebase-map.md`; прогон долгоживущего файла задачи,
   планки и тестов затронутых модулей.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (загрузка не тронута; `doctor`/уборка — без отказа) |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 3 |
| 7 | 2, 3 (для поддержанного проекта функция возвращает None — путь прежний) |

Проверка: `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` —
16 passed; `plank-run` — 1 passed (существующие тесты не изменены);
затронутые модули — `tests/test_doctor.py`, `test_coldstart.py`,
`test_multitarget.py`, `test_01m5scgsqn0at0b07h7m9803ra_local_layer.py`,
`test_github_adapter.py`, `test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`
(250 passed) и 17 файлов `test_approve_*`/`test_auto_*`/`test_catalog_*`/
`test_fsm_*`/`test_runner_*`/`test_new_argv_parsing.py` (193 passed).
Собственных тестов не добавлено: все свойства SPEC покрыты долгоживущим
файлом задачи.

Итерация 2 (возврат из verifying): после переноса проверки внутрь тел —
долгоживущий файл задачи + `test_lease_run_task_command.py`,
`test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`,
`test_01m3xtf5506gf43hd51ece230t_role_refusal.py` — 36 passed (прежние 6
падений CI закрыты); 18 файлов `test_approve_*`/`test_auto_*`/
`test_catalog_*`/`test_fsm_*`/`test_runner_*` + `test_doctor.py`,
`test_multitarget.py` — 342 passed; `plank-run` — 1 passed.

## Влияние на систему
- Гейты, лимиты, инварианты не ослабляются: добавлены только отказы.
  Проверка записи `targets.check` прежняя — `doctor`, уборка, чтение
  записей `gitlab`/`target-human` работают как раньше; существующие
  тесты, заводящие такие записи данными, зелёные без правки.
- `doctor` для записи `gitlab`/`target-human` получает строку `fail` —
  это и есть требование 6; код выхода `doctor` при такой записи станет
  ненулевым (как у любой `fail`).
- `runner._cmd_run` теперь читает `targets.yaml` один раз на вызов (в
  `auto` — и на каждом шаге цикла): нечитаемый слой не отказывает (None).
- Откат — revert коммита задачи; схемы БД и форматов не меняется.

## Риски
- Детачнутый `run`/`auto` (без `--attach`) отказывает в дочернем
  процессе `--attach`, а не в родителе: отказ и запись журнала будут, но
  родитель успеет завести наблюдение. SPEC требует отказ в `cmd_run`/
  `cmd_auto` — так и сделано.

## Предложения системе
- Правило «обвязка публичной команды задачи — только
  `lease.run_task_command`, новая проверка — внутрь тела `_cmd_*`» знает
  линтер `tests/test_lease_run_task_command.py`, но не `coding-standards`
  и не карточки знаний: класс поймал только CI (возврат из verifying).
- Bash шага роли отклоняет `ls`/`cd X && …`/пайпы с `grep -v` как
  «требует подтверждения» — разведка ролей идёт только одиночными
  командами; стоит отметить это в миссии шага, чтобы роли не тратили ходы.
