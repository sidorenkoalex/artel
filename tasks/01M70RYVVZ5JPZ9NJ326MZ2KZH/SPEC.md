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
Если `lsof` нет, он вернул не 0 или превысил 10 с, `_process_cwd` даёт
`None`, `_live_suite_run_in` пропускает живой прогон (`continue`,
`orphans.py:76-77`) и база живого прогона удаляется — закрыто не по
умолчанию. На Linux без `lsof` (образ `python:3.13`) тест
`tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py::CanaryDoctorTest::test_ac10_fix_removes_only_orphan_among_live_owners`
падал 3 из 3 (08.11.2026, строка копилки `4a21a85b9`).

## Требования
1. Живой прогон (`run.json` в `config.LOGS/suite-run/*/` с живым pid),
   чей рабочий каталог не узнан (`_process_cwd` вернул `None`), защищает
   базу: проверка защиты базы `suite-run` (`_live_suite_run_in`) в этом
   случае отвечает «защищено» для любого каталога `artel-suite-base-*`
   (закрыто по умолчанию).
2. В случае требования 1 `doctor` выводит строку-предупреждение, несущую
   pid, путь `run.json`, причину «каталог процесса не узнан» и то, что
   база не удалена.
3. На Linux (`sys.platform` начинается с `linux`) `_process_cwd` сначала
   читает ссылку `/proc/<pid>/cwd` (`os.readlink`); ссылка недоступна —
   прежний путь через `lsof`. На macOS поведение `_process_cwd` не меняется.
4. Сторож зависших прогонов (`hung_test_watchdog.py:172`) с новым
   `_process_cwd` ведёт себя как раньше там, где `lsof` отвечал; поведение
   сторожа при `None` (`continue`) не меняется.
5. Удаление сирот при мёртвом pid в `run.json` и при узнанном cwd вне
   каталога — без изменений.
6. Тесты задачи — в новом долгоживущем файле
   `tests/test_01m70ryvvz5jpz9nj326mz2kzh_*.py` по образцу песочницы
   `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`: `lsof`
   подменяется исполняемым файлом в `PATH` песочницы (с журналом вызовов),
   `/proc` — подменой функции чтения ссылки, живой процесс — настоящий
   дочерний процесс теста. Каждый тест несёт строку «Ловит мутацию: …».
   Настоящие каталоги `config.LOGS` и клоны канарейки главной копии тесты
   не читают и не удаляют.

## Критерии приёмки
Критерии AC-1…AC-4 — форма теста, заданная ТЗ (прогон `doctor --fix` в
песочнице над настоящим живым дочерним процессом), поэтому строки
поверхности решения у них нет: проверяется поведение команды целиком.

AC-1. Живой прогон в `run.json`, `lsof` в `PATH` песочницы отсутствует и
`/proc/<pid>/cwd` недоступен — `doctor --fix` не удаляет каталог
`artel-suite-base-*` и выводит предупреждение, содержащее pid прогона и
причину «каталог процесса не узнан» (ловит прежний `continue`).
Размер проверки: большой — ТЗ требует настоящий живой дочерний процесс как владельца прогона; подмена liveness не держит связку pid → защита.

AC-2. Живой прогон в `run.json`, подменённый `lsof` завершается с кодом 1 —
то же, что AC-1: база `artel-suite-base-*` не удалена, предупреждение с
pid и причиной выведено.
Размер проверки: большой — тот же настоящий живой дочерний процесс, что в AC-1, и исполнение подменённого `lsof` дочерним процессом.

AC-3. В `run.json` мёртвый pid — `doctor --fix` удаляет базу-сироту
`artel-suite-base-*`, как раньше.
Размер проверки: большой — тест сравнивает с живым случаем в той же песочнице `doctor --fix` и исполняемым `lsof`; мёртвый pid получается от завершённого дочернего процесса.

AC-4. Живой прогон с узнанным cwd внутри одной базы `artel-suite-base-*` —
`doctor --fix` удаляет другую базу-сироту и сохраняет базу с cwd внутри
(ловит «защищать всё при любом живом прогоне»).
Размер проверки: большой — cwd должен принадлежать настоящему живому дочернему процессу внутри базы.

AC-5. При `sys.platform`, подменённом на `linux`, и подменённой функции
чтения ссылки, отдающей путь для `/proc/<pid>/cwd`, cwd процесса берётся
из ссылки без вызова `lsof`: журнал вызовов подменённого `lsof` в `PATH`
песочницы пуст, а возвращённый cwd равен пути ссылки. При недоступной
ссылке (функция чтения бросает `OSError`) вызывается `lsof` и cwd берётся
из его вывода.
Поверхность решения: orchestrator.doctor.hung_test_watchdog.process_cwd(pid, executable) -> str | None
Размер проверки: малый

## Не входит
- Установка `lsof` в образы.
- Правка теста канарейки `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`
  и любых других существующих тестов; красный существующий тест —
  эскалация с именем теста.
- Зелёность существующего `test_ac10_fix_removes_only_orphan_among_live_owners`
  на машине без правки (AC-6 ТЗ) — её держит пульт (полный зелёный набор
  `tests/` и неизменность существующих тестов).
- Другие места, где неизвестное состояние процесса считается «мёртв»
  (роль перечисляет найденные в «Предложения системе» PLAN/REVIEW).
- Правка `orchestrator/doctor/__init__.py`, `orchestrator/liveness.py`
  (только чтение): `__init__.py` импортирует `_process_cwd` по этому имени,
  поэтому имя `_process_cwd` в `hung_test_watchdog.py` сохраняется рядом
  с публичным `process_cwd` AC-5.
- `orchestrator/prune.py::_run_pid_alive` (ссылается на тот же разбор
  `run.json`) — вне зон.

## Материалы
- ТЗ: `tasks/01M70RYVVZ5JPZ9NJ326MZ2KZH/TZ.md`.
- Код: `orchestrator/doctor/orphans.py:62-83, 115-118, 134-147`;
  `orchestrator/doctor/hung_test_watchdog.py:68-81, 172-174`;
  `orchestrator/doctor/__init__.py:177` (реэкспорт `_process_cwd`).
- Образец песочницы: `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py:223-240`.
- Копилка: строки `4a21a85b9` (верная причина), `f26634bc6` (неверная).
