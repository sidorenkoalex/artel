---
task: 01M5TBCY7WTN121S136XP2C6SR
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Эпики Э2а — конверт бюджета эпика и зависимость запуска start_after

## Фаза A — план
- Таблица покрытия полна: требования 1–20 сопоставлены шагам 1–7.
- Шаги размером с MR (схема/модель, merge_after, команды, runner, auto, watch, тесты).
- Сверка интерфейсов Э1 (раздел SPEC «Порядок разработки») зафиксирована в «Подходе»: расхождений нет, эскалация не нужна — это соответствует коду Э1 в main (f909b7dd9).
- «Влияние на систему» совпадает с diff: 12 модулей зоны SPEC плюс один новый тест; `fsm.py`, `spend.py`, `config.py`, защищённые пути не тронуты; существующие тесты не правились (в diff `tests/` только новый `tests/test_start_after_units.py`). Откат описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Сумма считается в одном месте — `budget.epic_spent`. Её через атрибут модуля зовут `board._epic_item`, `runner._first_step_refusal`, `check_epic_alert`, `watch._EpicWarnings`, `catalog._warn_exhausted_envelope`, `epics.cmd_envelope`. Других сумм по эпику нет: grep `sum(.*spent` нашёл только сумму по проекту в `report.py:789`. |
| 2 | OK | `EPIC_ALERT_RATIO = 0.8`, сравнение `>=` (`epic_envelope_warning`); `config.py` не тронут. |
| 3 | OK | `epics.cmd_envelope`: число разбирает `spend.cli_number` (nan/inf отсекаются), `<= 0` — отказ; запись журнала эпика «конверт эпика изменён». |
| 4 | OK | Предупреждение в `status` — заголовок группы; в `watch` — `_EpicWarnings`: события KNOWN/PARTIAL/ESTIMATED, «до» берётся из памяти сессии, у первого события «до» нет, строка — один раз на эпик. История до старта сессии событием не считается: `watch.py:844-847` берёт её как базу. В БД не пишет. |
| 5 | OK | `check_epic_alert` вызывается в общем хвосте `_account_step` после обеих ветвей учёта и в `pause._account_partial_cost`. Повторный алерт отсекается по последней записи журнала эпика (изменение конверта или алерт) под `BEGIN IMMEDIATE`, так что `alert-ack` второго алерта не открывает. Наблюдение (не замечание): `epic envelope <id> N` с тем же значением тоже пишет запись «$10 → $10» и заново взводит алерт. |
| 6 | OK | `merge_after.role_step_started` — по записи «agent run started»; записи отказов не учитываются (AC-10). |
| 7 | OK | `_first_step_refusal` стоит в `_refuse_before_start` после паузы и стоп-крана, до проекта и pre-flight; пишет запись журнала с именованным действием и выходит через `("exit", …)`. |
| 8 | OK | Проверка срабатывает только до первого шага, потолок не трогается (AC-12). |
| 9 | OK | `catalog._warn_exhausted_envelope` — задача заводится, печатается предупреждение. |
| 10 | OK | При `envelope is None` нет ни отказа, ни предупреждения, ни алерта; алерта 100 % нет. |
| 11 | OK | Колонка в DDL плюс `add_column` в миграции; каналы `new --start-after` и `epic start-after`. |
| 12 | OK | `_undivided` идёт по цепочке делений до задачи без деления; защита от цикла — `seen`. Подстановка делается до `check`. |
| 13 | OK | `check(..., column="start_after")` — те же правила элемента, в причинах указан свой канал. |
| 14 | OK | `_dependency_graph`: объединение рёбер обеих колонок; у проверяемой задачи — новое значение своего канала плюс текущее значение другого. Все каналы `merge_after` идут через `check` (AC-19). |
| 15 | OK | Отказ с перечнем ожидаемых задач; только до первого шага (AC-28). |
| 16 | OK | `killed` или пропавшая задача попадает в `dead`; подсказка «сними её: epic start-after … (или «нет»)». |
| 17 | OK | `replace_divided` обходит и колонку `start_after` тем же правилом, с записью журнала; `fsm.py` не тронут. |
| 18 | OK | `auto._run_first_step_refusal`: отказ узнаётся по действию журнала этого вызова, `Stop(..., False)` без алерта, подсказки «epic envelope <эпик> N» и «ждёт start_after: <ids>». |
| 19 | OK | `status` и `epic show`: «потрачено / конверт» и строка ВНИМАНИЕ; в `board.waiting_on` — `dependency` через `start_after_blocks`. |
| 20 | OK | Без эпика с конвертом и без `start_after` функция выходит до записей (AC-26). |

## Замечания
Нет blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5tbcy7wtn121s136xp2c6sr_*.py tests/test_start_after_units.py` — 40 passed.
- `artel.py plank-run 01M5TBCY7WTN121S136XP2C6SR` — отказ «планки нет: в источнике нет файлов test_*.py». Критерии задачи держат долгоживущие файлы `tests/test_01m5tbcy7wtn121s136xp2c6sr_*.py` (прогон выше).
- Соседние модули: `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_{board_model,division_epic,epic_commands,migration,views}.py`, `tests/test_epics_board_units.py`, `tests/test_merge_after_module.py`, `tests/test_pause_now.py`, `tests/test_watch.py` — 142 passed.
- Временная мутация: в `merge_after.start_after_blocks` убрано условие `not role_step_started(...)`. `tests/test_start_after_units.py::test_start_after_blocks_only_before_first_step` покраснел (1 failed, 3 passed). Код восстановлен `git checkout`, git status чистый.
- Точечное чтение `watch.py:838-850`: база `known_step_id` на старте сессии, история событием не считается (требование 4). `store.begin_immediate` (`store.py:615`) — проверка, что транзакция в `check_epic_alert` открывается корректно.

## Предложения системе
- Механика пакета ревьювера: для задачи без зафиксированной планки (`plank-run` отказывает «планки нет») пакет об этом не говорит. Стоит писать в пакете явно, что критерии держат только долгоживущие файлы задачи.
