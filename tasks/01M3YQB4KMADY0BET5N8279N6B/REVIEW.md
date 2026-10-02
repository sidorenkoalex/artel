---
task: 01M3YQB4KMADY0BET5N8279N6B
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Отбор циклов на старом коде не зависит от погрешности времени процесса в ОС

## Фаза A — план
- Таблица покрытия PLAN закрывает требования 1–6, у каждого есть шаг и тест.
- Шаги размером с MR: код, регрессионный файл, правка AC-5 по мандату.
- Подход совпадает с вариантом (б) SPEC. Схема БД, `pin.py`, `doctor/__init__.py`,
  `lease.py`, `store.py` не тронуты. Изменённые файлы: `stale_cycles.py`,
  `tests/test_stale_cycles_start_precision.py` (в зонах), долгоживущий файл
  01M3Y75GCR (расширение зон по ANSWER-1/ANSWER-2). Раздел «Расширение зон»
  в PLAN — дословно по ANSWER-1. «Влияние на систему» соответствует diff.
  Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `stale_cycles.py::_proc_start_interval`: `starttime` после последней `)` (поле 20 после неё = 22-е), момент загрузки `time.time() - clock_gettime(CLOCK_BOOTTIME)` без целосекундного `btime`, интервал `[s−0,05; s+тик+0,05]` (≤0,06 с при USER_HZ=100). `start_interval`: `/proc` → `ps` `[ответ, ответ+2 с)` → `None`. Сбои чтения/разбора перехватываются. |
| 2 | OK | `stale_cycles`: `lo >= pin` → «новый», не назван; `hi >= pin` → `borderline`; иначе «старый»; `None` → «не удалось определить». Одна функция на `pin.cmd_pin_update` и `check_stale_cycles`. Условие `hi >= pin` совпадает с формулировкой AC-2 («ответ + 2 с не раньше сдвига»). |
| 3 | OK | `stale_cycle_lines` только дописывает пометку к времени старта, остальные поля строки не меняются. Проверено AC-2 долгоживущего файла (`cycle_line`). |
| 4 | OK | На Linux через `/proc` огрубления нет. На `ps` поздний цикл с ответом на 2 с раньше попадает в `borderline`. |
| 5 | OK | `GAP_SEC` и утверждения AC-3 01M3Y75GCR не тронуты. CI d48c85f5 зелёный (14 проверок), там же на Linux исполнились AC-1 через `/proc` и AC-3 01M3Y75GCR. |
| 6 | OK | `tests/test_stale_cycles_start_precision.py::LstartTwoSecondsEarlyTest` — сценарий огрублённого на 2 с `lstart`, в докстринге есть «Ловит мутацию». |

## Замечания
Замечаний уровня blocker, major и minor нет.

Проверка целостности тестов. В `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`
относительно 40c4006c удалены только две строки: строка докстринга и строка
`with` (`git diff 40c4006c -- … | grep '^-'`). Обе заменены в рамках мандата
ANSWER-1, строки `assert` не удалены, `GAP_SEC` и другие методы не тронуты.
Тестовый помощник `proc_table_hidden` продублирован, ANSWER-1 это разрешает.
`tests/test_stale_cycles_start_precision.py` не повторяет долгоживущий файл
задачи: в нём уровень отбора без git, арифметика `/proc` и границы `>=`;
сценарий AC-3 там прямо требует требование 6 SPEC.

Косметика, на вердикт не влияет: комментарий `_PROC_SLACK`
(`orchestrator/doctor/stale_cycles.py`, около стр. 37) ссылается на
`_proc_start_time`, а функция называется `_proc_start_interval`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p timeout -o timeout=120 tests/test_stale_cycles_start_precision.py tests/test_pin_update_stale_cycles.py tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py tests/test_doctor.py tests/test_pin.py tasks/01M3YQB4KMADY0BET5N8279N6B/acceptance_tests` (macOS, передний план): 168 passed, 2 skipped. Пропущены AC-1 через `/proc`, на macOS таблицы `/proc` нет.
- Временная мутация `"borderline": False` в `stale_cycles`: `tests/test_stale_cycles_start_precision.py` дал 2 failed (`LstartTwoSecondsEarlyTest`, `IntervalBoundaryTest`), как заявлено в «Ловит мутацию». Код возвращён через `git checkout`, после этого 4 passed. Прогон шёл с `-B`, чтобы не оставить устаревший `.pyc`.
- `python3 scripts/codebase_map.py` и затем `git diff -- docs/codebase-map.md`: изменилась только строка `built_at_sha`, карта свежая. Регенерация откачена.
- `git diff 40c4006c -- tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py | grep '^-'`: удалены только строка докстринга и строка `with`.
- Статус CI коммита d48c85f5 из пакета: зелёный, Linux-путь `/proc` исполнен на раннере.

## Предложения системе
- Мутацию через `sed -i` ревьюверу в шаге не дают: составная bash-команда ждёт подтверждения. Временную мутацию пришлось делать через Edit с откатом `git checkout`. Стоит описать этот приём в `skills/review-checklist.md` («Сторож — проверен временной мутацией»), заодно с советом PLAN про `-B`/`__pycache__`.
