---
task: 01M1SHJTT0V516BWHYXWS50F3G
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: автогейт приёмки — критерий «существующие tests/ зелёные» исполняется по CI

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (маркер `ci` в guard) | OK | `AC_MARKER`/`scan_ac_content` распознают `ci` наравне с manual/skip/escalate (scripts/guard.py:167). |
| 2 (автогейт исполняет `ci` по CI головы кодовой ветки) | OK | `_autogate_conditions` — отдельная ветвь `ci_ns`, `ci.verifying_status(t["branch"])`, fail-closed на не-green (orchestrator/fsm_autogate.py:83-93). |
| 3 (`ci` только для формулировки про существующие tests/) | OK | `ci_marker_wording_ok` + ключевые слова совпадают с SPEC дословно (scripts/guard.py:176-186). |
| 4 (сводка ручного гейта показывает `ci` вместе с результатом CI) | реализовано не так | Код `acceptance.summary` корректен изолированно, но на РЕАЛЬНОЙ планке этой же задачи выдаёт фиктивный критерий `AC-9` с исковерканным текстом причины — см. R1-F2. AC-6 фактически не выполняется для этой задачи. |
| 5 (`skills/test-authoring.md`) | OK | Приложение к PLAN — `git apply --check` на чистом дереве пройден мной независимо (см. «Проверено исполнением»). |
| 6 (существующие тесты guard/автогейта зелёные) | OK, но без новых тестов | 234 теста присутствующих модулей (`test_fsm_autogate`, `test_acceptance`, `test_ci_status`, `test_acceptance_tests_flow`, `test_guard_*`) зелёные — ни один существующий ассерт не тронут. Но ни один тест НЕ добавлен для новой пометки `ci` — см. R1-F1. |

## Замечания

- blocker — tests/ (весь диф) — PLAN.md шаги 1–3 явно обещают юнит-тесты на `scan_ac_content`/`acceptance_traceability_errors` (шаг 1), на `_autogate_conditions`/`_maybe_autogate_acceptance` (шаг 2) и на `summary` (шаг 3) для пометки `ci`; SPEC зона явно включает `tests/`. Фактический diff (`git diff --stat main...HEAD`) не трогает `tests/` вовсе — ни одного нового или изменённого файла. Постоянный регресс-набор, который реально гоняет CI (`.github/workflows/ci.yml`, джоб `python`: `unittest discover -s tests`), не знает о пометке `ci` совсем: будущая правка `AC_MARKER`, `ci_marker_wording_ok` или ветки `_autogate_conditions`/`summary` может сломать fail-closed поведение требований 2/3/5 SPEC — ни один существующий прогон `tests/` этого не заметит. Только временные `tasks/.../acceptance_tests/` этой задачи покрывают сценарий, а они не часть постоянного набора и не гоняются CI после мержа. Предложение: перенести/продублировать хотя бы по одному юнит-тесту на каждый пункт (распознавание `ci`, отказ по формулировке, зелёный/красный/отсутствующий CI в автогейте, отображение в `summary`) в `tests/test_guard_schema.py` / `tests/test_fsm_autogate.py` / `tests/test_acceptance.py`, как и обещал PLAN.

- blocker — orchestrator/acceptance.py:summary (демонстрируется на `tasks/01M1SHJTT0V516BWHYXWS50F3G/acceptance_tests/` самой этой задачи) — `AC_MARKER`/`scan_ac_content` ищут пометку `#\s*AC-(\d+):\s*(...)` НЕ заякоренной на начало строки (`AC_MARKER.findall(content)` без `re.M`/`^`), поэтому она ловит совпадения внутри докстрок/прозы, где пример синтаксиса приведён буквально без индирекции символа `#`:
  - `acceptance_tests/test_ac1_ac2_guard_ci_marker.py:23` и `:66` — буквальный текст `# AC-9: ci — …` внутри докстроки/комментария (сама задача, которую эти строки описывают, отмечает, что для ЭТОГО же риска нужна индирекция `_HASH`, но забыла применить её здесь).
  - `acceptance_tests/test_ac3_ci_marker_not_manual_or_skip.py:28`, `test_ac4_ci_marker_green_ci_satisfies_autogate.py:28`, `test_ac5_ci_marker_missing_or_red_ci_blocks_autogate.py:27,50`, `test_ac6_manual_gate_summary_shows_ci_result.py:45` — буквальный текст `` `# AC-2: ci` `` внутри докстрок.

  Воспроизведено запуском реального кода на реальной планке задачи:
  `guard.scan_acceptance_tests(Path("tasks/01M1SHJTT0V516BWHYXWS50F3G"))` возвращает
  `markers == {9: ('ci', '<причина>` (без'), 2: ('ci', ''), 7: (...), 8: (...)}`
  — то есть `AC-9`, которого вообще нет в SPEC этой задачи, читается как настоящая пометка `ci`, с полностью исковерканной причиной. Прогон
  `acceptance.summary(Path("tasks/01M1SHJTT0V516BWHYXWS50F3G"), branch="task/01m1shjtt0v516bwhyxws50f3g-avtogeyt-priyomki-kriteriy-sus")`
  печатает Оператору на ручном гейте:
  ```
  ci-критерии (доказательство — CI кодовой ветки):
    AC-2 — статус check-runs коммита ... неизвестен ...
    AC-9: <причина>` (без — статус check-runs коммита ... неизвестен ...
  ```
  — фиктивный критерий `AC-9` с нечитаемым текстом причины прямо в карточке ручного гейта. Это ИМЕННО код AC-6 (`orchestrator/acceptance.py::summary`), который эта задача добавляет, — то есть SPEC-требование 4/AC-6 на практике не выполняется для собственной приёмочной планки задачи, а не только в гипотетическом сценарии.

  Последствие: любой Оператор на ручном гейте этой задачи увидит запутывающую, ложную информацию о несуществующем критерии AC-9; тот же риск актуален для КАЖДОЙ будущей задачи, чей test-author опишет пример синтаксиса `ci`/`manual`/`skip` в докстроке без индирекции — предпосылка (нессылочный текстовый скан без привязки к началу строки) существовала и до этой задачи, но именно эта задача — первое подтверждённое срабатывание.

  `acceptance_tests/` заблокирован (лок хэша каталога после `tests_writing`, зона задачи не включает эти файлы) — разработчик не может просто поправить докстроки сам. Предлагаю на выбор: (а) ужесточить `AC_MARKER`, чтобы матчить только `#`, стоящий в начале строки (после произвольных пробелов) — это в зоне `scripts/guard.py` и не требует правки locked-файлов, но нужно перепроверить, не сломает ли это легитимные использования пометки не в начале строки (я такого сегодня в кодовой базе не нашёл, но нужна отдельная проверка); либо (б) эскалация на разблокировку `acceptance_tests/` для правки докстрок test-author'ом.

- minor — `acceptance_tests/test_ac7_ac8_manual_markers.py:18` — критерий AC-8 («Существующие тесты автогейта приёмки и guard остаются зелёными без ослабления ассертов и условий») сформулирован ровно как класс критериев, для которого эта же задача вводит пометку `ci` (содержит «существующ», «зелён»), но помечен `manual`, не `ci`. Не блокирует (manual — валидный выбор), но ирония показательна: сама задача не воспользовалась собственной новой возможностью для своего же критерия про регресс тестов — как минимум наблюдение для ретро, не обязательное исправление.

- minor — `scripts/guard.py:508-534` (`traceability_errors_from_content`) — ветка `kind in ("skip", "escalate") and not reason` требует причину для `skip`/`escalate`, но НЕ для `ci` (и не для `manual` — тот же пробел уже существовал до этой задачи). SPEC требование 1 и приложение к `skills/test-authoring.md` («Причина обязательна» для `ci`) подразумевают обязательность причины, но guard её не проверяет для `ci` так же, как для `skip`/`escalate`. Не расширяю до blocker, так как это тот же пробел, что уже был у `manual` (не новый регресс этой задачи), но раз уж вводится новая пометка — стоило бы закрыть его для `ci` заодно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_guard_schema.py (`CiMarkerTraceabilityTest`, `AcMarkerLineAnchorTest`), tests/test_fsm_autogate.py (`CiMarkerConditionTest`), tests/test_acceptance.py (`SummaryCiCriteriaTest`) | PLAN обещал юнит-тесты на новую пометку `ci` в tests/test_guard_schema.py, tests/test_fsm_autogate.py, tests/test_acceptance.py — ни один не добавлен | постоянный регресс-набор CI не защищает fail-closed поведение требований 2/3/5 SPEC от будущей поломки | добавлено 4 новых класса, 12 тестовых методов в постоянный набор: `CiMarkerTraceabilityTest` (распознавание `ci` `scan_ac_content`, приём формулировки про существующие tests/, отказ по чужой формулировке с подсказкой manual, отказ без причины — R1-F4), `AcMarkerLineAnchorTest` (регресс R1-F2 — пометка в прозе не в начале строки не матчится), `CiMarkerConditionTest` (автогейт: зелёный CI проходит, красный/отсутствующий CI отказывает с причиной, `ci` не путается с manual/skip, опрашивается именно `t["branch"]`), `SummaryCiCriteriaTest` (счётчик ci в шапке, `branch=None` называет критерий без опроса CI, `branch` задан — показывает результат `verifying_status`). Прогон: `python3 -m unittest tests.test_guard_schema tests.test_fsm_autogate tests.test_acceptance` — 72 теста, все зелёные |
| R1-F2 | fixed | scripts/guard.py:168-179 (`AC_MARKER`) | буквальный текст `# AC-9: ci —` / `` `# AC-2: ci` `` в докстроках без индирекции `#` матчится `AC_MARKER` (не заякорен на начало строки) как настоящая пометка | `acceptance.summary` на РЕАЛЬНОЙ планке задачи показывает фиктивный критерий AC-9 с исковерканной причиной — AC-6 не выполняется на практике | `AC_MARKER` заякорена на начало строки (`^`, `re.M`, без ведущих пробелов — тот же приём, что уже несут `AC_ITEM`/`AC_ITEM_FULL`); grep по всему репозиторию подтвердил, что ни одна легитимная пометка `manual`/`skip`/`escalate`/`ci` в существующих `acceptance_tests/*.py` не стоит с отступом или не в начале строки — сужение не отсекает ни одного реального случая. Повторный прогон `guard.scan_acceptance_tests`/`acceptance.summary` на планке ЭТОЙ задачи (те же вызовы, что привели к находке в ревью) больше не находит фиктивный AC-9; регресс закреплён `AcMarkerLineAnchorTest` в tests/test_guard_schema.py |
| R1-F3 | rejected | acceptance_tests/test_ac7_ac8_manual_markers.py:18 | AC-8 сформулирован про класс «существующие tests/ зелёные», но помечен manual, не ci | не блокирует, наблюдение для ретро | `acceptance_tests/` этой задачи залочен (tasks/T023: хэш каталога зафиксирован после `tests_writing`) — разработчик не вправе править файлы test-author'а без отдельного мандата на разблокировку (тот же класс, что закрыл R1-F2 без правки locked-файлов). `manual` — валидная пометка по SPEC, дефекта в коде нет; сам ревьювер отметил пункт как необязательный наблюдением для ретро, не требованием — оставляю как есть |
| R1-F4 | fixed | scripts/guard.py:538 (`traceability_errors_from_content`) | пометка `ci` не требует причины в guard (в отличие от skip/escalate), хотя SPEC/скил подразумевают обязательность | «# AC-n: ci» без причины пройдёт guard молча, хотя документация обещает обязательность | ветка `kind in ("skip", "escalate") and not reason` расширена до `("skip", "escalate", "ci")` — `# AC-n: ci` без причины теперь отказывает тем же сообщением, что skip/escalate. `manual` осознанно не тронут — тот же пробел уже существовал до этой задачи (не регресс этой правки), реестр отмечает его отдельно как наблюдение, не как объём этой задачи; закрытие — решение Оператора, не разработчика (принцип целостности: не расширять правку сверх названного замечания без мандата) |

## Вердикт

changes_requested — два blocker'а (R1-F1, R1-F2) должны быть закрыты до мержа: отсутствие регресс-тестов на постоянный набор и продемонстрированная поломка отображения AC-6 на собственной планке задачи. R1-F3/R1-F4 — на усмотрение разработчика, не блокируют.

## Проверено исполнением

- `git show --stat 1d8a1b6b` и `git diff --stat main...task/01m1shjtt0v516bwhyxws50f3g-avtogeyt-priyomki-kriteriy-sus` — подтверждено: diff не касается `tests/` (R1-F1).
- `python3 -m unittest tests.test_fsm_autogate tests.test_acceptance tests.test_ci_status tests.test_acceptance_tests_flow tests.test_guard_schema tests.test_guard_zones tests.test_guard_split_signals tests.test_guard_extraneous_acceptance_files` — 234 теста, все зелёные (AC-8/требование 6, без ослабления существующих ассертов).
- `python3 scripts/guard.py tasks/01M1SHJTT0V516BWHYXWS50F3G/SPEC.md` — «GUARD: ок» (структурная проверка SPEC/AC-разметки в порядке; `acceptance_traceability_errors` этим путём не вызывается).
- Прямой вызов `guard.acceptance_traceability_errors(Path("tasks/01M1SHJTT0V516BWHYXWS50F3G"))` — вернул ошибку `AC-9: пометка на критерий, которого нет в SPEC`; `guard.scan_acceptance_tests(...)` — вернул `markers` с фиктивным `9: ('ci', ...)`. Первичное обнаружение R1-F2.
- Прямой вызов `orchestrator.acceptance.summary(Path("tasks/01M1SHJTT0V516BWHYXWS50F3G"), branch="task/01m1shjtt0v516bwhyxws50f3g-avtogeyt-priyomki-kriteriy-sus")` — воспроизвёл фиктивный `AC-9` с исковерканной причиной прямо в карточке ручного гейта. Подтверждение R1-F2 на уровне AC-6.
- Проверка приложения к PLAN: скопировал unified-дифф `skills/test-authoring.md` из PLAN.md во временный файл рабочего каталога и прогнал `git apply --check` на чистом дереве — применяется без конфликтов (подтверждает заявку PLAN, требование 5/AC-7).
- Прочитаны все acceptance_tests/*.py задачи (AC-1..AC-8) и код `orchestrator/fsm_autogate.py`, `orchestrator/acceptance.py`, `scripts/guard.py`, `orchestrator/fsm_advance.py` целиком по diff и напрямую из рабочего дерева.

## Предложения системе

- Скан AC-пометок (`scripts/guard.py::AC_MARKER`, использован без привязки к началу строки уже до этой задачи) уязвим к ложным срабатываниям на буквальные примеры синтаксиса в докстроках тестов — этот класс риска был явно осознан в `_sandbox.py` (приём `_HASH`-индирекции), но не применён последовательно во ВСЕХ файлах этой же задачи (R1-F2). Стоит закрепить в skills/test-authoring.md явное правило «не пиши `# AC-n: kind` буквально в докстроке/прозе — только как настоящую пометку либо с индирекцией символа `#`», раз уже второй раз (после `_sandbox.py`) это стало источником путаницы.
