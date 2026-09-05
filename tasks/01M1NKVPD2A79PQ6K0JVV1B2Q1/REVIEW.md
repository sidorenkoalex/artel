---
task: 01M1NKVPD2A79PQ6K0JVV1B2Q1
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 3
---

# REVIEW: Механика зон, часть 1: машиночитаемое поле `zones` и общий список зон

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1: `zones:` во frontmatter SPEC; `guard.py::requires_zones`/`spec_zones_errors` version-gated на `schema_version >= 4` (scripts/guard.py:49,770-793); сохранение на approve — `orchestrator/fsm.py:744-748`. Analyst-инструкция (AC-2) — protected-paths.patch применён Оператором в skills/spec-authoring.md. Код этой части diff с ce368cca (итерация 1) не менял. |
| 2 | OK | Без изменений: `COMMON_ZONES` в `orchestrator/config.py:353` — ровно 4 пути, состав подтверждён `tests/test_guard_zones.py::CommonZonesDeclarationTest`. |
| 3 | OK | Замечание R1-F1 закрыто: маркеры `# AC-n` в `test_scope_markers.py` перенумерованы под актуальные AC-1..AC-5 суженной SPEC. `guard.acceptance_traceability_errors(Path("tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1"))` — 0 ошибок (проверено исполнением этой же командой, не пересказом PLAN). |

## Замечания

(пусто — 0 blocker/major/minor)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests/test_scope_markers.py | маркеры AC-n использовали старую сквозную нумерацию (1..16) вместо актуальной нумерации суженной SPEC (1..5) | коммитом 7f4b65d4 файл переписан по мандату ANSWER-2/ADR-0012: AC-6..AC-15 убраны, обоснование бывшего AC-16 перенесено под реальный AC-5, остались только AC-2 и AC-5 (manual); AC-1/AC-3/AC-4 подтверждены прямыми тестами соседних файлов (проверено запуском: 6/6 зелёных) | закрыто — `guard.acceptance_traceability_errors` даёт 0 ошибок при повторном самостоятельном запуске (не только по слову PLAN), маркеры точно совпадают с текстом SPEC «Критерии приёмки» AC-1..AC-5 (сверено построчно) |

## Вердикт

approved — единственное открытое замечание прошлой итерации (R1-F1) закрыто корректно и проверено самостоятельным запуском (не пересказом PLAN): `guard.acceptance_traceability_errors` — 0 ошибок, текст маркеров построчно совпадает с актуальным разделом SPEC «Критерии приёмки» (AC-1..AC-5), AC-1/AC-3/AC-4 подтверждены прямыми тестами. Diff с итерации 1 (`git diff ce368cca..HEAD`) ограничен ровно тремя файлами задачи (PLAN.md, REVIEW.md, test_scope_markers.py) — кода механики и protected-paths.patch эта итерация не касалась, повторной проверки требований 1/2 по существу не требовалось.

## Проверено исполнением

- `git checkout -- tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/` — каталог задачи снова пропал из рабочего дерева на старте ревью (тот же повторяющийся паттерн, что в итерации 1); восстановлен из HEAD, не переписан.
- `git diff ce368cca..HEAD --stat` — ровно 3 файла изменены (PLAN.md, REVIEW.md, acceptance_tests/test_scope_markers.py); код механики (`scripts/guard.py`, `orchestrator/*`, protected-paths.patch) с итерации 1 не трогался — повторное построчное ревью кода не требовалось, только проверка фикса R1-F1.
- `git show 7f4b65d4` — прочитан целиком; подтверждено, что правка ограничена уборкой маркеров AC-6..AC-15 и переносом обоснования AC-16 -> AC-5, без изменения логики/ассертов (файл и так не содержит исполняемых тестов).
- Прочитан текущий `tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests/test_scope_markers.py` целиком и сверен построчно с `SPEC.md` разделом «Критерии приёмки» (AC-1..AC-5) — маркеры AC-2/AC-5 (manual) и текст docstring про AC-1/AC-3/AC-4 (прямые тесты соседних файлов) точно соответствуют актуальной, суженной нумерации.
- `python3 -c "...guard.acceptance_traceability_errors(Path('tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1'))..."` — `[]`, 0 ошибок (самостоятельный прогон, не переписывание вывода из PLAN/предыдущего REVIEW).
- `python3 -m unittest discover -s tests` — 1491 тестов, `Ran 1491 tests ... OK` (0 failures/errors), полный прогон в переднем плане.
- `python3 -m unittest discover -s tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests -v` — 6 тестов, все `ok` (соответствует заявленной планке 6/6).
- `python3 scripts/guard.py --all` — `GUARD: ок (447 файлов)`.
- `git show main:scripts/guard.py | grep SUPPORTED_SCHEMA_VERSION` — на `main` до сих пор `= 3` (задача не мержена); это и есть причина держать `schema_version` этого REVIEW.md на 3 (см. ANSWER-2, п.2) — с версией 4 живой пин `main`-гейта отклонил бы переход как «новее поддерживаемой» без ручного моста Оператора, как уже случилось на итерации 1.

## Предложения системе

- Итерация 1 этой же задачи уже несла `schema_version: 4` в REVIEW.md вопреки мандату ANSWER-2 «держать REVIEW.md на 3 до мержа» — Оператору пришлось вручную «понизить мостом» гейт для того перехода. Причина смещения — шаблон `templates/REVIEW.md` в ветке уже несёт `schema_version: 4` (patch защищённых путей), и роль по умолчанию копирует версию из шаблона, не сверяя её с реальным пином `main`. Стоит явно пометить в `skills/review-checklist.md`/`skills/conventions-core.md`: пока задача, поднимающая `SUPPORTED_SCHEMA_VERSION`, не смержена, артефакты СВОЕЙ ЖЕ ветки обязаны нести версию, которую поддерживает `main` (проверяемо командой из «Проверено исполнением» выше), а не версию своего локального шаблона — иначе класс повторится на каждой итерации ревью до мержа.
