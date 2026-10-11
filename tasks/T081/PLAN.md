---
task: T081
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Сканер AC-маркеров: маркеры только из test_*.py

## Подход
Применить к `scan_acceptance_tests` (scripts/guard.py) тот же приём
фильтрации по имени файла, что уже применён в `scan_redness_markers`
(T064, scripts/guard.py:284-299): вместо `tests_dir.rglob("*.py")` —
`tests_dir.rglob("test_*.py")`. Это единственная содержательная правка:
`scan_ac_content` (ядро разбора маркеров из уже прочитанных текстов)
не меняется — он источник-агностичен и уже переиспользуется
`orchestrator/fsm.py::_tests_writing_ac_state` для ветки задачи (эта
ось — «не входит» по SPEC, не трогаю).

Второй кусок — чисто механический откат временного обхода T075
(коммит 7cb7e25): `AC_TEST_ESCALATE` в
`tasks/T075/acceptance_tests/_sandbox.py` возвращается к обычной
однострочной записи `# AC-2: escalate — …` вместо конкатенации
`"AC-2: esca" + "late"`. После починки сканера конкатенация там больше
не нужна — `_sandbox.py` не начинается с `test_`, и починенный
`scan_acceptance_tests` его не читает.

Третий кусок — юнит-тесты по требованию 3 SPEC (не путать с уже
залоченными `tasks/T081/acceptance_tests/`, которые эту задачу не
описывают, а проверяют её результат по AC-1..AC-3): добавляю тесты в
`tests/test_guard_schema.py` (тот же файл, где уже живут тесты
`redness_marker_errors_from_files`/`scan_redness_markers`,
schema-тесты — соседняя секция про AC-разметку) — по одному классу на
каждый сканер, каждый проверяет и «маркер в `_sandbox.py` не
считается», и «тот же маркер в `test_*.py` считается».

## Шаги

1. `scripts/guard.py::scan_acceptance_tests` — фильтр по `test_*.py`
   вместо `*.py` (правка одной строки, `rglob`).
2. `tasks/T075/acceptance_tests/_sandbox.py` — откат конкатенации
   `AC_TEST_ESCALATE` к естественной строке, обновление комментария
   рядом (он объяснял ИМЕННО причину конкатенации — с починкой
   сканера объяснение больше не соответствует коду).
3. `tests/test_guard_schema.py` — юнит-тесты
   `scan_acceptance_tests`/`scan_redness_markers` на фильтр имени
   файла (SPEC, требование 3).
4. Прогон `python3 scripts/guard.py --all` и `python3 -m unittest
   discover -s tests` — оба сканера и оба набора тестов
   (`tasks/T081/acceptance_tests/`, `tests/`) зелёные.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |

## Влияние на систему
Правка сужает `scan_acceptance_tests` до подмножества файлов, которое
`scan_redness_markers` уже читает (`test_*.py`) — оба сканера ходят по
`acceptance_tests/` одной и той же задачи, так что расхождения между
ними после этой правки больше нет, а не появляется новое.

Единственный вызывающий код внутри `scripts/guard.py` —
`acceptance_traceability_errors`, единственный внешний —
`orchestrator/fsm.py::_tests_writing_ac_state` (путь "рабочая копия",
`gitcmd.on_foreign_branch` — False) и все тесты, что дергают
`guard.scan_acceptance_tests` напрямую или через `fsm.cmd_advance` в
песочницах (`tests/test_acceptance_tests_flow.py`,
`tests/test_analyst_role.py`, `tests/sandbox.py`,
`tasks/T075/acceptance_tests/_sandbox.py`). Ни один из них не заводит
вспомогательных файлов вида `_helper.py`/`_sandbox.py` с реальными
AC-маркерами внутри `acceptance_tests/` какой-либо ЖИВОЙ задачи —
единственный такой файл в репозитории и есть `tasks/T075/
acceptance_tests/_sandbox.py`, который эта же задача чинит (AC-3).
Ветка задачи T075 не активна (задача done), так что сужение фильтра
не меняет поведение уже прошедших гейт задач — гейт прогоняется
только на переходе `tests_writing -> review`, а не задним числом.

Гейты/тесты/лимиты не ослабляются: наоборот, сканер перестаёт видеть
маркеры там, где их не должно быть по конвенции (маркеры — только в
`test_*.py`, тот же принцип, что T064 уже закрепил для маркера
красноты). `acceptance_traceability_errors` и `count_test_methods`
не трогаются: `count_test_methods` уже требованием SPEC не
затрагивается (T081 говорит только про `scan_acceptance_tests`), и
менять её не буду — она вне зоны задачи (осознанно не расширяю объём:
если Оператору важно тот же фильтр для счётчика тестов на гейте
сводки, это отдельная задача).

Откат: правка `scan_acceptance_tests` — одна строка, откатывается
git revert без побочных эффектов на другие модули.

## Риски
`count_test_methods` (scripts/guard.py:224) остаётся читать все
`*.py` каталога — тот же класс дефекта (учёт тестового метода из
вспомогательного файла) там теоретически возможен, но SPEC его не
называет ни в требованиях, ни в критериях приёмки (AC-1..AC-3 говорят
только про `scan_acceptance_tests`), явно ограничивая объём. Заношу
как наблюдение в «Предложения системе», не расширяю зону задачи
самовольно.

## Предложения системе
- `count_test_methods` (scripts/guard.py:224) читает все `*.py`
  каталога `acceptance_tests/` без фильтра по `test_*.py` — тот же
  класс дефекта, что T081 чинит в `scan_acceptance_tests`, просто
  число в сводке гейта, а не сама AC-трассируемость. Кандидат в
  будущую строку роадмапа (тот же принцип, что уже применён в T064 и
  этой задаче).
