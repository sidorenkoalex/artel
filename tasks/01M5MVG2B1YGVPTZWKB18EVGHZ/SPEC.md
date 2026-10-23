---
task: 01M5MVG2B1YGVPTZWKB18EVGHZ
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/canary.py, tests/test_canary_parallel_protection.py, tests/test_canary_parallel.py, tests/test_canary_child_row_write.py, docs/codebase-map.md
budget_usd: 30
---

# SPEC: canary --parallel: строка «оборвана сигналом» не теряется у дочернего, тесты гонки говорят причину, GroupSignalTest не виснет

## Контекст
Два теста гонки SIGTERM неустойчивы на CI main: у одного из дочерних
вместо строки «оборвана сигналом SIGTERM» стоит `drive_failed`
(`tests/test_canary_parallel_protection.py::BaselineTest::test_parent_sigterm_leaves_canary_baseline_unchanged`,
утверждение около :500, прогон 39913903312 на c5af4add;
`tests/test_canary_parallel.py::StopTest::test_parent_sigterm_stops_children_and_skips_queue`,
утверждение около :382, прогон 39954804501). `drive_failed` пишет
родитель (`_finish_child` → `_report_child_failure`), когда дочерний
завершился без своей строки. Дочерний пишет строку в ветке
`except CanaryInterrupted` `cmd_canary_run_task`
(`orchestrator/canary.py:3759-3767`) одним вызовом
`store.insert_canary_run(store.db(), …)`; оба дочерних пишут
одновременно, и исключение записи (например, «database is locked»)
завершает процесс кодом 1 без строки — вероятная причина; другая —
SIGKILL по сроку `PARALLEL_STOP_GRACE_SEC`. Различить их нельзя: вывод
дочерних в сообщения утверждений не попадает. Отдельно
`GroupSignalTest` (около :653) висит до таймаута pytest, если внук не
появился: `run_cli` держит дескриптор канала внука на запись до
`thread.join()`, а `read_grandchild_pid` ждёт конца данных.

Мандат Оператора 23.10.2026 (дословно): «мандат на чинку двух тестов
гонки SIGTERM и зависания GroupSignalTest без ослабления утверждений —
даю» — покрывает правки существующих тестовых файлов (сообщения к
утверждениям, помощники `run_cli` и `read_grandchild_pid`). Правка
`cmd_canary_run_task` — решение сессии при Операторе по правам волны G
23.10.2026.

## Требования
1. Диагностика (первым шагом): в
   `BaselineTest::test_parent_sigterm_leaves_canary_baseline_unchanged`
   и `StopTest::test_parent_sigterm_stops_children_and_skips_queue` к
   утверждению о строках прогона (`sorted((r["title"], r["outcome"]) …)`)
   добавляется сообщение — вывод родителя и дочерних (`run.out` / `out`).
   Утверждения и литералы не меняются; это дополнение сообщения, не
   ослабление.
2. Укрепление против гипотезы «сбой записи»: запись строки «оборвана
   сигналом …» дочерним в ветке `except CanaryInterrupted`
   `cmd_canary_run_task` идёт через `store.insert_canary_run`, вызов
   `store.db()` — внутри каждой попытки; при `sqlite3.OperationalError` —
   не более 3 попыток подряд без `sleep` (ожидание — штатное ожидание
   блокировки соединения, 5 с); число попыток — именованная константа
   `CHILD_ROW_WRITE_ATTEMPTS = 3` в `orchestrator/canary.py`. При любом исключении записи, которое не удалось преодолеть
   (включая не `OperationalError` — такое не повторяется), дочерний
   пишет в stderr «строка прогона не записана:» и полный стек
   (`traceback.format_exc()`) и выходит с кодом `128 + сигнал` (сейчас —
   1). Успешная запись — прежний выход `128 + сигнал`.
3. Родитель не меняется: строка «строка прогона не записана: …» попадает
   в его вывод через журнал дочернего, который печатает `_finish_child`;
   строка БД родителя для такого дочернего — прежняя `drive_failed`.
4. В PLAN записываются остаточный риск (SIGHUP во время повторов
   выбрасывает `CanaryInterrupted` из ветки — как и в текущем коде),
   известное ограничение требования 5 (согласующий поток, не дошедший до
   открытия канала к концу работы родителя: неблокирующее открытие на
   запись падает, поток может висеть — от зависания защищает
   `timeout = 120` pytest) и допущение модели границы срока: «не более
   трёх ожиданий блокировки на попытку» со ссылками
   `orchestrator/store.py:409`, `:431`, `:1620–1623`,
   `orchestrator/schema.py:291–400`. Если причина неустойчивости будет
   установлена в ходе работы (например, по выводу CI-прогона ветки) и
   окажется другой — эскалация, а не расширение задачи; если гонка не
   воспроизводится, задача сдаётся с диагностикой (требование 1) и
   укреплением (требование 2) — это исход нормы.
5. `GroupSignalTest`: в общем помощнике `run_cli`
   (`tests/test_canary_parallel_protection.py:281`) дескриптор канала
   внука на запись закрывается сразу после открытия (до `join`);
   `read_grandchild_pid` (там же, :260) при пустых данных бросает
   `AssertionError("внук не появился")`. Утверждения теста не меняются.
6. Новый файл `tests/test_canary_child_row_write.py`, у каждого теста —
   строка «Ловит мутацию:». Генераторы нагрузки и серии повторных
   прогонов в нём запрещены.
7. Прочие тесты обоих существующих файлов не правятся; ни одно
   утверждение не удаляется и не ослабляется.

## Критерии приёмки
AC-1. В `BaselineTest::test_parent_sigterm_leaves_canary_baseline_unchanged`
и `StopTest::test_parent_sigterm_stops_children_and_skips_queue`
утверждение о строках прогона несёт сообщением вывод родителя и
дочерних (`run.out` / `out`); само утверждение и его литералы
(`("alfa", "оборвана сигналом SIGTERM")`, `("beta", "оборвана сигналом SIGTERM")`)
совпадают с main.

AC-2. Внутри процесса: `cmd_canary_run_task` с подменами `_set_plan`,
`_mark_owned_by_parent` (истина), `_run_one_task` (бросает
`CanaryInterrupted(SIGTERM)`) и `store.insert_canary_run` (`side_effect`:
первый вызов — `sqlite3.OperationalError("database is locked")`, затем
настоящая запись) — строка «оборвана сигналом SIGTERM» записана в БД,
код выхода `128 + SIGTERM`. На текущем коде красный (тест внутри
процесса: всплывает `sqlite3.OperationalError`, строки нет).

AC-3. То же, но сбой `OperationalError` на всех попытках — код
`128 + SIGTERM`, в перехваченном stderr «строка прогона не записана» и
стек, попыток записи ровно 3; при не `OperationalError` (например,
`sqlite3.IntegrityError`) — ровно одна попытка, код `128 + SIGTERM` и то
же сообщение со стеком. На текущем коде красный.

AC-4. `_finish_child` с поддельным дочерним (код 143, журнал со строкой
«строка прогона не записана: …») — эта строка есть в выводе родителя,
строка БД родителя для шаблона — `drive_failed`. На текущем коде
зелёный.

AC-5. Граница срока: `CHILD_ROW_WRITE_ATTEMPTS × 3 × 5 +
GROUP_TERMINATE_GRACE_SEC < PARALLEL_STOP_GRACE_SEC`, где
`CHILD_ROW_WRITE_ATTEMPTS` — константа числа попыток из требования 2 в
`orchestrator/canary.py` (модель: не более трёх ожиданий блокировки по
5 с на попытку — миграция в `store.db()`, обновление в
`_ensure_canary_tables`, вставка; допущение записано в PLAN,
требование 4). На текущем коде красный (константы нет).

AC-6. Сценарий `GroupSignalTest` без внука (подмена `_GRANDCHILD` на
сценарий, который сразу выходит) — вокруг запуска поднимается
`AssertionError` с «внук не появился»; тест не задаёт срока по часам
(от зависания — `timeout = 120` pytest). На текущем коде красный по
таймауту pytest.

AC-7. В `tests/test_canary_parallel_protection.py` и
`tests/test_canary_parallel.py` изменены только сообщения утверждений
двух тестов гонки (AC-1) и помощники `run_cli` и `read_grandchild_pid`;
ни одно утверждение этих файлов не удалено, не заменено и не ослаблено,
прочие тестовые методы не изменены.

AC-8. `store.db()` внутри каждой попытки: в тесте сбоя
`OperationalError` на всех попытках (AC-3) `store.db` подменён шпионом,
вызовов ровно столько, сколько попыток (3). Второй сценарий — шпион
`store.db` с `side_effect`: первый вызов бросает
`sqlite3.OperationalError("database is locked")`, затем настоящее
соединение — строка «оборвана сигналом SIGTERM» записана в БД, код
выхода `128 + SIGTERM`. Мутации «`store.db()` вне цикла» и
«`store.db()` в цикле, но вне `try`» краснеют. На текущем коде красный.

AC-9. Без `sleep`: в тестах AC-2 и AC-3 `time.sleep` модуля
`orchestrator.canary` подменён шпионом — за время повторов ни одного
вызова. Мутация «`time.sleep` между попытками» краснеет.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `tests/test_canary_parallel_protection.py::BaselineTest::test_parent_sigterm_leaves_canary_baseline_unchanged` — сообщение к утверждению строк прогона | оба дочерних пишут «оборвана сигналом SIGTERM» при SIGTERM родителю, бейзлайн прежний — tests/test_canary_parallel_protection.py:500-505 | остаётся (утверждение и литералы прежние, добавлено только сообщение) | тот же метод, тот же `assertEqual` | ок |
| `tests/test_canary_parallel.py::StopTest::test_parent_sigterm_stops_children_and_skips_queue` — сообщение к утверждению строк прогона | остановка дочерних с их строками «оборвана сигналом SIGTERM», `gamma` не запущен — tests/test_canary_parallel.py:382-384 | остаётся (утверждение и литералы прежние, добавлено только сообщение) | тот же метод, тот же `assertEqual` | ок |
| `tests/test_canary_parallel_protection.py::_ProtectionSandbox::run_cli` — ранее закрытие дескриптора канала внука на запись | согласование сценариев параллельного прогона через каналы для всех тестов файла — tests/test_canary_parallel_protection.py:281 | остаётся (меняется только момент закрытия дескриптора канала внука; согласование каналов шаблонов прежнее) | все тесты файла, использующие `run_cli`; зависание без внука — AC-6 | ок |
| `tests/test_canary_parallel_protection.py::_ProtectionSandbox::read_grandchild_pid` — `AssertionError("внук не появился")` при пустых данных | pid внука для `GroupSignalTest` — tests/test_canary_parallel_protection.py:260-268; при отсутствии внука сейчас — зависание или `ValueError` | остаётся и усиливается (вместо зависания/`ValueError` — явный провал с причиной) | `GroupSignalTest::test_parent_sigterm_reaches_grandchild_in_child_group` (около :653) и AC-6 | ок |
| `orchestrator/canary.py::cmd_canary_run_task` — повторы записи строки «оборвана сигналом» в ветке `except CanaryInterrupted` | лимит `PARALLEL_STOP_GRACE_SEC = 60` с (orchestrator/canary.py:3423): дочерний успевает записать строку до SIGKILL родителя | остаётся (лимит не меняется; повторы укладываются в него: 3 × 3 × 5 + 3 = 48 < 60) | граница срока — AC-5; отсутствие `sleep` — AC-9; `store.db()` в каждой попытке — AC-8 | ок |

## Оценка объёма и деление
Сигналов нет: файлов зоны вне общих зон (`config.COMMON_ZONES`: `tests/`,
`docs/codebase-map.md`) — один (`orchestrator/canary.py`), критериев — 9,
`budget_usd` ниже `SPLIT_SIGNAL_BUDGET_USD`.

## Не входит
- Тест на вторую линию проверки различных имён шаблонов в
  `_cmd_canary_parallel` (новое покрытие вне мандата — отдельная строка
  бэклога).
- Изменение поведения `--parallel` вне записи строки прогона дочерним в
  ветке `except CanaryInterrupted` `cmd_canary_run_task` (родитель,
  `_finish_child`, `_report_child_failure`, срок `PARALLEL_STOP_GRACE_SEC`
  не меняются).
- Генераторы нагрузки и серии повторных прогонов в тестах и проверках;
  мутация «дочерний не пишет строку «оборвана сигналом»» проверяется
  однократным прогоном тестов гонки в приёмке, не в долгоживущем файле.
- Правка `orchestrator/store.py`, `orchestrator/schema.py`, `tests/sandbox.py`,
  `tests/test_invariants.py` (только чтение; новая запись `_EXCEPTIONS`
  в `tests/test_invariants.py` — эскалация).
- Расширение задачи, если установленная в ходе работы причина
  неустойчивости окажется другой, — эскалация (требование 4).
- `tests/test_canary_parallel_protection.py::SigintTest::test_parent_sigint_stops_children_with_exit_130`
  — вне мандата Оператора (мандат — на два названных теста гонки и
  `GroupSignalTest`); в этой задаче не правится, вынесен строкой
  бэклога (решение Оператора на гейте SPEC 23.10.2026).
- Перегенерация `docs/codebase-map.md` после правки `canary.py` — по
  правилу соглашений, не отдельный критерий; полный зелёный `tests/` и
  CI ветки — их держит пульт.

## Материалы
- ТЗ: `tasks/01M5MVG2B1YGVPTZWKB18EVGHZ/TZ.md`; сверено с `origin/main`
  0c58e924.
- `orchestrator/canary.py:3423` (`PARALLEL_STOP_GRACE_SEC = 60`),
  `orchestrator/liveness.py:50` (`GROUP_TERMINATE_GRACE_SEC = 3.0`),
  `orchestrator/canary.py:3505` (`_finish_child`), `:3461`
  (`_report_child_failure`), `:3702` (`cmd_canary_run_task`).
- CI main: прогоны 39913903312, 39954804501.
