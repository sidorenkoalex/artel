---
task: 01M70RYVVZ5JPZ9NJ326MZ2KZH
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/doctor/orphans.py, orchestrator/doctor/hung_test_watchdog.py, tests/test_01m70ryvvz5jpz9nj326mz2kzh_*.py
budget_usd: 25
---

# SPEC: Уборка doctor не удаляет базу живого suite-run, если каталог процесса не узнан

## Контекст
`doctor --fix` удаляет временные каталоги-сироты `artel-canary-*` и
`artel-suite-base-*`. Базу `suite-run` без маркера владельца защищает
только `_live_suite_run_in(path)` (`orchestrator/doctor/orphans.py:62-83`,
вызов `:117`): для каждого `run.json` в `config.LOGS/suite-run/` с живым
pid он узнаёт cwd процесса через `_process_cwd`
(`orchestrator/doctor/hung_test_watchdog.py:68-81`, `lsof -a -p <pid> -d cwd -Fn`).
Исполняемый `lsof` выбирается в `orphans.py:74`: `/usr/sbin/lsof`, если файл
есть, иначе `lsof` из `PATH`. Если `lsof` нет, он вернул не 0 или превысил
10 с, `_process_cwd` даёт `None`, `_live_suite_run_in` пропускает живой
прогон (`continue`, `orphans.py:76-77`), и база живого прогона удаляется —
закрыто не по умолчанию. На Linux без `lsof` (образ `python:3.13`) тест
`tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py::CanaryDoctorTest::test_ac10_fix_removes_only_orphan_among_live_owners`
падал 3 из 3 (08.11.2026, строка копилки `4a21a85b9`).

Ту же `_live_suite_run_in` зовёт сторож зависших прогонов:
`hung_test_watchdog.py:175-179` → `doctor._temp_owner_alive` →
`orphans.py:115-117`. По решению Оператора (ANSWER-1, п. 1) новая защита
при неузнанном cwd действует только для уборки каталогов, сторож её не
получает.

## Требования
1. Уборка каталогов (`_orphan_temp_dirs` / `_fix_orphan_temp_dirs`):
   живой прогон (`run.json` в `config.LOGS/suite-run/*/` с живым pid), чей
   рабочий каталог не узнан (`_process_cwd` вернул `None`), защищает любой
   каталог `artel-suite-base-*` (закрыто по умолчанию).
2. В случае требования 1 `doctor` выводит строку-предупреждение, несущую
   pid, путь `run.json`, причину «каталог процесса не узнан» и то, что
   база не удалена.
3. Сторож зависших прогонов (`hung_test_watchdog.py:172-183`, путь через
   `doctor._temp_owner_alive`) защиты требования 1 не получает: при живом
   прогоне `suite-run` с неузнанным cwd он, как сейчас, сообщает зависший
   pytest в базе `artel-suite-base-*` без маркера. Два вызова
   `_live_suite_run_in` разводятся в `orchestrator/doctor/orphans.py`
   (ANSWER-1, п. 1); поведение сторожа при `_process_cwd(pid) is None`
   (`continue`, `:173-174`) не меняется.
4. На Linux (`sys.platform` начинается с `linux`) `_process_cwd` сначала
   читает ссылку `/proc/<pid>/cwd` (`os.readlink`); ссылка недоступна —
   прежний путь через `lsof`. На macOS поведение `_process_cwd` не меняется.
   Сторож с новым `_process_cwd` ведёт себя как раньше там, где `lsof`
   отвечал.
5. Путь системного `lsof` — публичная константа модуля
   `orchestrator.doctor.orphans.SYSTEM_LSOF` со значением `"/usr/sbin/lsof"`
   (ANSWER-1, п. 2). Выбор исполняемого `lsof` (`orphans.py:74`) берёт её:
   файл есть — она, нет — `lsof` из `PATH`. Боевой выбор не меняется.
6. Удаление сирот при мёртвом pid в `run.json` и при узнанном cwd вне
   каталога — без изменений.
7. Тесты задачи — в новом долгоживущем файле
   `tests/test_01m70ryvvz5jpz9nj326mz2kzh_*.py` по образцу песочницы
   `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`: системный
   `lsof` отключается подменой `orphans.SYSTEM_LSOF` несуществующим путём
   песочницы, `lsof` подменяется исполняемым файлом в `PATH` песочницы (с
   журналом вызовов), `/proc` — подменой функции чтения ссылки, живой
   процесс — настоящий дочерний процесс теста. Каждый тест несёт строку
   «Ловит мутацию: …». Настоящие каталоги `config.LOGS` и клоны канарейки
   главной копии тесты не читают и не удаляют.

## Критерии приёмки
Случай образа без `lsof` и без каталога процесса (`python:3.13`), на
котором падал существующий `test_ac10_…`, воспроизводят критерии AC-1,
AC-2 и AC-5: на машине пульта (macOS) его даёт подмена `SYSTEM_LSOF`,
`PATH` и функции чтения ссылки.

AC-1. Живой прогон: `run.json` в песочнице `config.LOGS/suite-run/` несёт
pid настоящего живого дочернего процесса теста, `orphans.SYSTEM_LSOF`
подменён несуществующим путём песочницы, функция чтения ссылки
`/proc/<pid>/cwd` бросает `OSError`. Два случая: (а) исполняемого `lsof` в
`PATH` песочницы нет; (б) `lsof` в `PATH` песочницы завершается с кодом 1.
В обоих `doctor --fix` не удаляет каталог `artel-suite-base-*` и выводит
предупреждение, в котором есть pid прогона, путь его `run.json`, причина
«каталог процесса не узнан» и указание, что база не удалена (ловит
прежний `continue` в `orphans.py:76-77`). Критерий — поведение команды
целиком в форме теста ТЗ (подключение решения AC-2 к `doctor --fix`),
поэтому строки поверхности решения нет.
Размер проверки: большой — ТЗ требует настоящий живой дочерний процесс как владельца прогона и исполнение подменённого `lsof` дочерним процессом; подмена живости не держит связку pid → защита в `doctor --fix`.

AC-2. Решение защиты базы `suite-run` над песочницей `config.LOGS` с одним
`run.json` и каталогом `artel-suite-base-*`, `cleanup` — уборка (`True`)
или сторож (`False`):
- pid в `run.json` мёртв — `False` при `cleanup=True` и при `cleanup=False`;
- pid жив, cwd не узнан (`_process_cwd` вернул `None`) — `True` при
  `cleanup=True`, `False` при `cleanup=False`;
- pid жив, cwd узнан внутри каталога — `True` при обоих значениях;
- pid жив, cwd узнан вне каталога — `False` при обоих значениях.
Живой pid — процесс самого теста, cwd — подмена `_process_cwd`.
Поверхность решения: orchestrator.doctor.orphans.live_suite_run_in(path, cleanup) -> bool
Размер проверки: малый

AC-3. Живой прогон с узнанным cwd внутри одной базы `artel-suite-base-*`
(cwd настоящего живого дочернего процесса) — `doctor --fix` удаляет другую
базу-сироту и сохраняет базу с cwd внутри (ловит «защищать всё при любом
живом прогоне»). Критерий — поведение команды целиком в форме теста ТЗ,
поэтому строки поверхности решения нет.
Размер проверки: большой — cwd должен принадлежать настоящему живому дочернему процессу внутри базы, его отдаёт настоящий `lsof` или `/proc`.

AC-4. При `sys.platform`, подменённом на `linux`, и подменённой функции
чтения ссылки, отдающей путь для `/proc/<pid>/cwd`, cwd процесса берётся
из ссылки без вызова `lsof`: журнал вызовов подменённого `lsof` в `PATH`
песочницы пуст, а возвращённый cwd равен пути ссылки. При недоступной
ссылке (функция чтения бросает `OSError`) вызывается `lsof` и cwd берётся
из его вывода. При `sys.platform`, равном `darwin`, ссылка не читается и
вызывается `lsof`.
Поверхность решения: orchestrator.doctor.hung_test_watchdog.process_cwd(pid, executable) -> str | None
Размер проверки: малый

AC-5. Сторож при живом прогоне `suite-run` с неузнанным cwd: в песочнице
`config.LOGS` есть `run.json` с живым pid, чей cwd не узнан
(`_process_cwd` для него — `None`), а процесс `pytest` старше
`config.HUNG_TEST_RUN_AGE_SEC` работает в каталоге `artel-suite-base-*` без
маркера владельца и без маркера канарейки. Сторож (`_find_hung_test_runs`
и `check_hung_test_runs`) сообщает этот pytest находкой, как до задачи
(ловит «сторож получил защиту уборки при неузнанном cwd»). Критерий —
подключение сторожа к решению AC-2 со значением `cleanup=False`, своей
поверхности решения нет; процессы и cwd — подмены по образцу
`tests/test_canary_doctor_owner.py:12-23`.
Размер проверки: малый

## Не входит
- Установка `lsof` в образы.
- Правка теста канарейки `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`
  и любых других существующих тестов; красный существующий тест —
  эскалация с именем теста.
- Зелёность существующего `test_ac10_fix_removes_only_orphan_among_live_owners`
  на машине без правки (AC-6 ТЗ) — её держит пульт (полный зелёный набор
  `tests/` и неизменность существующих тестов; ANSWER-1, п. 3). Случай образа
  без `lsof` и без каталога процесса воспроизводят AC-1, AC-2 и AC-5 этого SPEC.
- Защита при неузнанном cwd для сторожа зависших прогонов (ANSWER-1, п. 1).
- Другие места, где неизвестное состояние процесса считается «мёртв»
  (роль перечисляет найденные в «Предложения системе» PLAN/REVIEW).
- Правка `orchestrator/doctor/__init__.py`, `orchestrator/liveness.py`
  (только чтение): `__init__.py` реэкспортирует `_process_cwd`,
  `_temp_owner_alive`, `_orphan_temp_dirs`, `_fix_orphan_temp_dirs` по этим
  именам (`__init__.py:155-158, 175-177`), поэтому закрытые имена
  сохраняются рядом с публичными `process_cwd` (AC-4) и
  `live_suite_run_in` (AC-2).
- `orchestrator/prune.py::_run_pid_alive` (ссылается на тот же разбор
  `run.json`) — вне зон.

## Материалы
- ТЗ: `tasks/01M70RYVVZ5JPZ9NJ326MZ2KZH/TZ.md`; ответ Оператора —
  `tasks/01M70RYVVZ5JPZ9NJ326MZ2KZH/ANSWER-1.md`; аудит —
  `SPEC-AUDIT.md` (отклонения В1–В4, А1).
- Код: `orchestrator/doctor/orphans.py:62-83, 92-118, 121-155`;
  `orchestrator/doctor/hung_test_watchdog.py:68-81, 157-189`;
  `orchestrator/doctor/__init__.py:155-158, 175-177` (реэкспорт).
- Образцы: песочница `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py:22-61, 223-240`;
  малые проверки `tests/test_canary_doctor_owner.py:12-43`.
- Копилка: строки `4a21a85b9` (верная причина), `f26634bc6` (неверная).
