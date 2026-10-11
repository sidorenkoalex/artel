---
task: T081
type: spec
author_role: analyst
status: ready
schema_version: 2
budget_usd: 15
---

# SPEC: Сканер AC-маркеров: маркеры только из test_*.py

## Контекст
`scan_acceptance_tests` в `scripts/guard.py` собирает AC-маркеры (тесты
`test_ac<n>_...` и пометки `# AC-n: manual|skip|escalate`) со всех `*.py`
файлов каталога `acceptance_tests/`, включая вспомогательные файлы вроде
`_sandbox.py`. Маркер `# AC-2: escalate` внутри строки-фикстуры такого
файла дал ложную эскалацию T075 и фантомный manual-гейт T078. Тот же
класс дефекта уже был исправлен в `scan_redness_markers` (T064): маркеры
красноты собираются только из файлов `test_*.py`. `scan_acceptance_tests`
остался несогласованным с этим приёмом.

## Требования

1. `scan_acceptance_tests` в `scripts/guard.py` собирает AC-маркеры
   только из файлов `acceptance_tests/test_*.py` — тем же приёмом
   (фильтр по имени файла), что уже применён в `scan_redness_markers`
   (T064).
2. Временный обход T075 в `tasks/T075/acceptance_tests/_sandbox.py`
   (конкатенация литерала `"AC-2: esca" + "late"`, коммит 7cb7e25)
   развёрнут обратно к естественной записи маркера одной строкой —
   `# AC-2: escalate — ...`.
3. Добавлены тесты на оба сканера (`scan_acceptance_tests` и
   `scan_redness_markers`): маркер в файле, чьё имя не начинается с
   `test_` (например `_sandbox.py`), не считается; тот же маркер в файле
   `test_*.py` считается.

## Критерии приёмки

AC-1. `guard.scan_acceptance_tests` не включает в результат (ни в
тестированные AC, ни в пометки `manual`/`skip`/`escalate`) маркеры и
тестовые методы из файлов каталога `acceptance_tests/`, чьё имя не
начинается с `test_`.

AC-2. `guard.scan_acceptance_tests` по-прежнему включает в результат
маркеры и тестовые методы из файлов `acceptance_tests/test_*.py` —
поведение для этих файлов не изменилось.

AC-3. `tasks/T075/acceptance_tests/_sandbox.py` содержит маркер
`# AC-2: escalate — критерий сформулирован противоречиво, тест не
пишется` естественной строкой (без конкатенации литерала), и полный
набор тестов репозитория остаётся зелёным.

## Не входит

- Ветко-корректное чтение `acceptance_tests/` с git-ветки задачи
  (`orchestrator/fsm.py::_tests_writing_ac_state`, путь для
  `gitcmd.on_foreign_branch`) — ТЗ ограничивает объём `scripts/guard.py`
  и его тестами.
- Изменение семантики самих маркеров (`AC-n`, `manual`/`skip`/`escalate`,
  «Красен до реализации»/«Зелёный с рождения») и форматов артефактов.
- Изменения в других задачах/файлах `tasks/`, кроме
  `tasks/T075/acceptance_tests/_sandbox.py` (пункт AC-3).

## Материалы

- `docs/roadmap` (P3, «Сканер AC-маркеров читает данные как разметку»).
- T064 (`scan_redness_markers`) — образец приёма фильтрации по `test_*.py`.
- T075, коммит 7cb7e25 — временный обход, который эта задача снимает.
