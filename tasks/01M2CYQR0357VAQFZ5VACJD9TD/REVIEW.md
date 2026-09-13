---
task: 01M2CYQR0357VAQFZ5VACJD9TD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Рефакторинг fsm_advance.py — гейты в пакет orchestrator/advance_gates/

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (пакет `orchestrator/advance_gates/` дословным переносом; имя пакета — с поправкой ANSWER-1/2) | OK | AST-сравнение каждого перенесённого top-level определения (функции и константы) между старым `orchestrator/fsm_advance.py` (sha `2b0c6679`) и соответствующим новым файлом даёт побайтовую идентичность для всех 30 функций и 6 констант (`CAPACITY_GATE_REASON`, `_ZONES_MANDATE_MARKER`, `_REWORK_REFUSAL_ACTION`, `_PULL_MAIN_COMMIT_INFIX`, `_REVIEWER_STEP_AUTOCOMMIT_PREFIX`, `_STEP_ARTIFACTS_COMMIT_PREFIX`), включая вложенную `_missing_plank_refuses` внутри `_acceptance_run_refuses`. Файлы `__init__.py`, `_base.py`, `zones.py`, `capacity.py`, `review.py`, `acceptance.py`, `tests_writing.py` на месте. |
| 2 (обработчики/эффекты остаются в fsm_advance.py, алиасы на все перенесённые имена, `answer.py` не правится) | OK | Оставшиеся в `fsm_advance.py` `spec_writing`, `tests_writing`, `review`, `verifying`, `in_dev`, `_review_approved`, `_review_changes_requested`, `_review_escalate`, `_in_dev_plan_escalate`, `_apply_plan_budget` — байт-в-байт идентичны себе прежним (AST-сравнение). `git diff --stat` не содержит `orchestrator/answer.py`; `_split_zone_paths`/`_plan_zones_extension_paths`/`_ZONES_MANDATE_MARKER` доступны как `fsm_advance.<имя>` и являются тем же объектом (`is`), что в `advance_gates.zones` (проверено вручную и приёмочным `test_ac2_all_transferred_names_are_true_aliases_to_gates_objects`). |
| 3 (поведение не меняется; обход `_run_gates` у `_acceptance_run_refuses` сохранён; полный набор `tests/` зелёный) | OK | Байт-в-байт идентичность текстов отказов/журнала/кодов исключает изменение поведения. `_run_gates` отсутствует в `co_names` `_acceptance_run_refuses` — обход сохранён (подтверждено и вручную, и приёмочным тестом). CI коммита 952ad801 зелёный (7 проверок, по данным пакета); локально прогнаны 9 тестовых файлов требования 4 + смежные (94 теста) и `test_invariants.py` (63 теста, включая инвариант «нет чужих импортов») — все зелёные. |
| 4 (только импорты/пути патчей в 9 тестовых файлах) | OK | `git diff --stat` не содержит ни одного файла `tests/` — по факту не потребовалось ни одной правки (PLAN честно фиксирует это в шаге 3); проверено grep'ом: ни один тест не патчит гейт-функции через `mock.patch(fsm_advance._...)` — единственный найденный patch (`test_git_fixation.py:360`, `_capacity_gate_refuses`) патчит имя в `fsm_advance`, а вызывающий код (`in_dev()`) остался в `fsm_advance.py` и берёт имя из того же модуля — патч продолжает работать. |
| 5 (`docs/codebase-map.md` тем же коммитом; диф ёмкости < 256 КиБ) | OK | `python3 scripts/codebase_map.py` локально даёт diff только по строке `built_at_sha` (ожидаемо отстаёт на коммит генерации — не дефект, см. skill). `git diff` кода (без `tasks/<id>/`) между базой и HEAD — 173253 байта, меньше потолка 262144 байт; задача уже прошла гейт ёмкости на `in_dev -> review` (сейчас в `verifying`). |
| 6 (PLAN несёт таблицу переносов, откат, смоук до/после) | OK | Таблица переносов PLAN.md сверена построчно с фактическим AST-диффом — расхождений нет. Способ отката (revert одного коммита 952ad801 — единственного, создающего `advance_gates/` и правящего `fsm_advance.py`+`codebase-map.md`) корректен. Смоук до/после описан конкретными командами. |

## Замечания

(нет)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- AST-сравнение (`ast.parse`, побайтовое сравнение исходных срезов) каждого top-level имени старого `orchestrator/fsm_advance.py` (sha `2b0c667998a4a3c424b63cf2ae748af4d037d6fd`) против соответствующего имени в новых `orchestrator/advance_gates/_base.py`, `acceptance.py`, `capacity.py`, `review.py`, `tests_writing.py`, `zones.py` — 0 расхождений среди 30 функций и 6 констант; отдельно сверены 11 оставшихся в `fsm_advance.py` функций (обработчики состояний + эффекты вердиктов) — тоже 0 расхождений.
- `python3 -c "import orchestrator.fsm_advance, orchestrator.advance_gates"` плюс проверка `is`-идентичности реэкспортов (`fsm_advance._capacity_gate_refuses is advance_gates.capacity._capacity_gate_refuses` и аналогично для `_zones_gate_refuses`, `_review_rework_gate_refuses`) — импорт чистый, идентичность подтверждена; `orchestrator.gates.__file__` по-прежнему указывает на `gates.py` (коллизии имени с новым пакетом нет).
- `python3 -m py_compile` всех 8 затронутых файлов пакета `orchestrator/` — без ошибок.
- `python3 -m unittest tests.test_fsm_advance_gate_framework tests.test_capacity_gate tests.test_zones_gate tests.test_mutation_claim_gate tests.test_fsm_review_rework_gate tests.test_fsm_review_rework_sha_gate tests.test_protected_paths_gate tests.test_review_registry_gate tests.test_fsm_advance_tests_writing_dry_collect tests.test_fsm_advance_gate_smoke -v` — 94 теста, все зелёные (включая три smoke-теста «byte for byte» против до-рефакторного фикстура).
- `python3 -m unittest tests.test_invariants -v` — 63 теста, все зелёные (в т.ч. инвариант «нет сторонних импортов» на реальном дереве `orchestrator/`).
- `python3 -m pytest tasks/01M2CYQR0357VAQFZ5VACJD9TD/acceptance_tests -q` — 7 passed (AC-1/AC-2/AC-3 планки этой задачи; AC-4/5/6 — manual, AC-3 остаток — skip, обоснования в докстринге планки проверены и приняты).
- `python3 scripts/codebase_map.py` — regen локально даёт diff только в строке `built_at_sha` (содержимое совпадает с закоммиченной картой; расхождение — ожидаемый лаг генерации, не дефект).
- `git diff --stat 2b0c667998a4a3c424b63cf2ae748af4d037d6fd...952ad801` — подтверждено: изменения строго в `docs/codebase-map.md`, `orchestrator/fsm_advance.py`, `orchestrator/advance_gates/*`; `orchestrator/gates.py`, `orchestrator/fsm_autogate.py`, `tests/*`, `orchestrator/answer.py` не тронуты; защищённые пути (`gates.yaml`, `roles.yaml`, `.github/`, `templates/`, `skills/`) не задеты.
- `git diff 2b0c667998a4a3c424b63cf2ae748af4d037d6fd...952ad801 -- . ':!tasks/01M2CYQR0357VAQFZ5VACJD9TD/' | wc -c` — 173253 байта, ниже потолка гейта ёмкости 262144 байта.
- `grep -rn "patch.*fsm_advance\._"` по `tests/` — единственное совпадение (`test_git_fixation.py:360`, `_capacity_gate_refuses`) патчит имя, вызываемое из `fsm_advance.py` (не из подмодуля), патч жизнеспособен после переноса.
- CI коммита 952ad801 — зелёный (7 проверок, по данным пакета).

## Предложения системе

- Генератор ревью-пакета сообщил `tasks/01M2CYQR0357VAQFZ5VACJD9TD/SPEC.md` и `PLAN.md` отсутствующими («в ветке» — fatal: path does not exist; «в дереве» — файл не найден), хотя оба файла физически присутствуют в рабочем каталоге шага (материализованы из головы артефактной ветки). Расхождение подтверждено независимо в этой же итерации — стоит проверить, по какому пути/ссылке генератор искал эти файлы для этой задачи, иначе ревьювер рискует эскалировать по несуществующему основанию.
