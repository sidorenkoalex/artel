---
task: T081
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Сканер AC-маркеров: маркеры только из test_*.py

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `scan_acceptance_tests` (scripts/guard.py:221) фильтрует `tests_dir.rglob("test_*.py")` вместо `"*.py"` — тем же приёмом, что `scan_redness_markers` (guard.py:299, T064). Проверено чтением обеих функций рядом. |
| 2 | OK | `tasks/T075/acceptance_tests/_sandbox.py:93-102` — `AC_TEST_ESCALATE` собран без конкатенации `"esca"+"late"`, маркер лежит естественной строкой `# AC-2: escalate — критерий сформулирован противоречиво, тест не пишется`. Сверил байт-в-байт: старая версия (тройная строка + `"# AC-2: esca" + "late — ...\n"`) и новая (весь текст внутри одной тройной строки) дают идентичное содержимое `AC_TEST_ESCALATE`. |
| 3 | OK | `tests/test_guard_schema.py:426-476`, класс `AcMarkerScannersOnlyReadTestFilesTest` — по два теста на каждый сканер: маркер/тест-метод в `_sandbox.py` не считается, тот же маркер в `test_*.py` считается. Ассерты точечные (`assertEqual(tested, {1})`, `assertEqual(markers, {2: (...)})`), не просто truthy — мутационно чувствительны. |

## Замечания

Пусто.

## Вердикт
approved

## Проверено исполнением
- `python3 -m unittest discover -s tests` — 1032 теста, все зелёные (полный набор репозитория, требование AC-3 «зелёный полный набор»).
- `python3 scripts/guard.py --all` — `GUARD: ок (269 файлов)`.
- `python3 -m unittest tasks.T081.acceptance_tests.test_ac1_non_test_files_excluded tasks.T081.acceptance_tests.test_ac2_test_files_still_included tasks.T081.acceptance_tests.test_ac3_sandbox_marker_reverted -v` — 8/8 тестов зелёные (AC-1..AC-3 задачи T081).
- `python3 scripts/codebase_map.py --check` — карта свежая (exit 0, без вывода), соответствует правке `scripts/guard.py` (built_at_sha поднят до `a6ff501`).
- Чтение `scripts/guard.py:203-227` (scan_acceptance_tests) и `:289-304` (scan_redness_markers) рядом — подтверждает, что приём фильтрации идентичен (SPEC требование 1 явно требует «тем же приёмом»).
- `git diff main...HEAD --stat -- 'tasks/*' ':!tasks/T081' ':!tasks/T075/acceptance_tests/_sandbox.py'` — пусто: подтверждает пункт «Не входит» SPEC (изменений в других задачах/файлах `tasks/`, кроме `_sandbox.py`, нет).
- `git log`/`git merge-base main HEAD` — ветка задачи слита с актуальным main (03c7f64), расхождений вне заявленного объёма нет.

## Предложения системе
Пусто (наблюдение про `count_test_methods` уже честно занесено в PLAN.md разработчиком — дублировать не буду).
