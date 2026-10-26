---
task: 01M5W27CY7K7NR9347NKD8F0NX
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: GitLab А0 — неподдержанный хостинг или гейт людей проекта: именованный отказ до первой задачи

## Фаза A — план
Таблица покрытия PLAN полна (требования 1–7 → шаги 1–3). Шаги размера MR.
Подход (одна функция в `targets.py`, вызовы внутри тел `_cmd_*` под
lease-обвязкой) не конфликтует с архитектурой: линтер
`tests/test_lease_run_task_command.py` зелёный. «Влияние на систему»
соответствует diff: 6 файлов `orchestrator/` из зон SPEC + карта, `tests/`
не тронут, защищённые пути не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py:29-30` константы; `unsupported_reason` (`targets.py:270`) — тексты причин совпадают с SPEC дословно; списки только в константах. Нечитаемый слой/необъявленный проект → `None` — их отказ даёт `_checked_target`/`target`, разумно. |
| 2 | OK | `targets.target`/`check` не изменены; существующие тесты с записями `gitlab`/`target-human` (`test_doctor.py`, `test_multitarget.py` и др.) не правлены и зелёные. |
| 3 | OK | `catalog.py:759-761` — сразу за `_checked_target`, до `_new_refs`, `store.db()`, `ensure_clone`, `new_task_id`; `sys.exit` → ненулевой код. AC-2 зелёный (нет клона, git, строк). |
| 4 | OK | `runner._cmd_run` первым действием; `auto._cmd_auto` до `_auto_cycle`. Обёртка `lease.run_task_command`/`run_locked` git не зовёт (`lease.py:383-396`); AC-3/AC-4 зелёные. |
| 5 | OK | `fsm._cmd_approve` первым действием, до `store.get_task`/таблицы состояний — в любом состоянии. AC-5/AC-6 зелёные. |
| 6 | OK | `doctor/cli.py:36` `project_support_check`, вызов первой строкой цикла записей `all_checks` (вкл. артель). |
| 7 | OK | Для поддержанного проекта функция возвращает `None` и вызывающие идут прежним путём; AC-8 (позитивный `new`) зелёный, существующие тесты не изменены. |

## Замечания
Блокирующих и major нет. Наблюдения уровня ниже minor (на вердикт не
влияют, в реестр не заведены):

- `orchestrator/runner.py:180` — докстринг `refuse_unsupported_project`
  говорит «до lease», а вызов после итерации 2 стоит под lease (внутри
  `_cmd_*`). Неточность текста, поведение верное.
- `orchestrator/auto.py:673-681` — отказ `auto` (`SystemExit`) ловится
  внешним `except BaseException` `cmd_auto`, и в журнал дополнительно
  попадает запись `CYCLE_ABORTED_ACTION` «SystemExit: … отклонён …». Это
  общий путь любого `sys.exit` в цикле `auto` (не новое поведение), и
  запись с причиной `unsupported_reason` всё равно есть первой.
- `runner.py:183` — повторный `store.resolve_task_id` при уже полном id
  от обвязки; безвреден.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний уровня minor и выше не заведено.

## Вердикт
approved.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py tests/test_lease_run_task_command.py tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py tests/test_doctor.py tests/test_multitarget.py` — 190 passed, 54 subtests passed (15.5 с).
- `artel.py plank-run 01M5W27CY7K7NR9347NKD8F0NX` — 1 passed, код выхода pytest 0.
- `grep` вызывателей `_cmd_run`/`_cmd_auto`/`_cmd_approve`/`unsupported_reason` по `orchestrator/`: тела вызываются только через обвязку (`runner.py:170`, `auto.py:671`, `fsm.py:979`), других обходов отказа нет.
- Чтение `lease.run_task_command` (`lease.py:383`) и `auto.cmd_auto` (`auto.py:660-681`) — проверка, что до тела нет git, и как обрабатывается `SystemExit` в `auto`.
- Временная мутация (снять вызов в `_cmd_auto`, прогнать AC-4) не выполнена: составная команда отклонена правами Bash шага. Заявки «Ловит мутацию» долгоживущего файла сверены глазами — все наблюдаемы (вызов шпиона `cmd_advance`/`spawn_agent`/git, текст причины в выводе, запись журнала).

## Предложения системе
- Bash шага ревьювера отклоняет составные команды (`sed -i … && pytest …; git checkout`), из-за чего приём «временная мутация» из review-checklist в шаге не исполним одним вызовом; стоит либо разрешить его, либо описать в скиле пошаговый вариант.
