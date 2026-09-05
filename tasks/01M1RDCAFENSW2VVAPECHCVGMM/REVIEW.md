---
task: 01M1RDCAFENSW2VVAPECHCVGMM
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: объявленный стек пульта, часть 1 — манифест, инвариант «только стандартная библиотека», проверка doctor

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (манифест `orchestrator/stack.py`) | OK | `REQUIRED_PYTHON=(3,11)`, `REQUIRED_TOOLS` (git/gh/claude, минимум+команда), `THIRD_PARTY_EXCEPTIONS=()` — все три части требования на месте. |
| 2 (`docs/stack.md`) | OK | Ссылается на `orchestrator/stack.py` как источник, объясняет «только stdlib», числа версий не продублированы. |
| 3 (инвариант stdlib-only в `tests/test_invariants.py`) | OK | `StdlibOnlyImportsInvariantTest` — `ast`-скан, сверка со `sys.stdlib_module_names` и `stack.THIRD_PARTY_EXCEPTIONS`. Тест функционально верен (см. «Проверено исполнением»), но докстринги двух его методов не несут заявку «Ловит мутацию» — см. замечание R1-F1. |
| 4 (`check_stack()`) | OK | 4 проверки (python/git/gh/claude), WARN при заниженной версии, FAIL при отсутствии, без сети — проверено и тестами, и реальным прогоном. |
| 5 (подключение в `doctor.py`) | OK | `checks.extend(stack.check_stack())` — одна строка, сравнение версий не продублировано (подтверждено AC-11-тестом: `REQUIRED_PYTHON` в `doctor.py` не встречается). |
| 6 (вывод `version`) | OK | Добавлены строка версии Python и строки `check_stack()`, три существующие строки не тронуты — `tests/test_version.py` зелёный без правок. |

## Замечания

- major — `tests/test_stack.py:29,33,41,47,56,70,83` и `tests/test_invariants.py:1634,1642` — ни один из 7 новых тестовых методов в `tests/test_stack.py` не несёт докстринга вовсе (только докстринг модуля), и оба новых метода `StdlibOnlyImportsInvariantTest` в `tests/test_invariants.py` (`test_repo_tree_has_no_foreign_imports`, `test_planted_foreign_import_is_caught_on_a_synthetic_tree`) несут только короткую AC-ссылку без явной заявки «Ловит мутацию: …» (конвенция skills/test-authoring.md, требование review-checklist п.3: «заявки нет вовсе → замечание»). Для сравнения — все тесты `tasks/01M1RDCAFENSW2VVAPECHCVGMM/acceptance_tests/*.py` конвенцию соблюдают полностью (каждый метод несёт развёрнутый докстринг с явным «Ловит мутацию: …»), то есть разработчик применил конвенцию выборочно — только к приёмочной планке, не к постоянным юнит-тестам, которые эту планку переживут. Предложение: дописать в каждый из 9 методов докстринг с явной заявкой «Ловит мутацию: …» (сценарий + что именно она ловит), по образцу уже написанных докстрингов в `acceptance_tests/test_ac1_ac2_ac3_manifest.py` и `acceptance_tests/test_ac7_ac8_ac9_ac10_ac17_check_stack.py`, которые для тех же самых сценариев эту заявку уже формулируют — можно взять за основу, не придумывать с нуля.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_stack.py:29,33,41,47,56,70,83; tests/test_invariants.py:1634,1642 | 9 новых тестовых методов без заявки «Ловит мутацию» в докстринге (конвенция test-authoring, скил review-checklist п.3) | будущий читатель/ревьювер не может свериться, какую мутацию тест ловит и ловит ли вообще — конвенция явно требует эту заявку для новых/изменённых тестов | дописать докстринг с заявкой «Ловит мутацию: …» в каждый из 9 методов; готовые формулировки для тех же сценариев уже есть в parallel-версиях acceptance_tests этой же задачи (test_ac1_ac2_ac3_manifest.py, test_ac6_ac16_stdlib_only_scan_is_sound.py, test_ac7_ac8_ac9_ac10_ac17_check_stack.py) |

## Вердикт

changes_requested — единственное замечание (R1-F1) не мешает функциональной корректности (весь код и вся приёмочная планка зелёные), но конвенция test-authoring для постоянных юнит-тестов нарушена систематически по всему новому файлу и по новому классу инварианта. Исправление механическое: дописать докстринги, взяв формулировки из уже существующих acceptance_tests той же задачи для тех же сценариев.

## Проверено исполнением

- Прогнан весь набор приёмочных тестов задачи (16 методов, AC-1..AC-3, AC-4..AC-17 кроме AC-18) — извлечены из `artifact/01m1rdcafensw2vvapechcvgmm:tasks/01M1RDCAFENSW2VVAPECHCVGMM/acceptance_tests/*` (в рабочем дереве этой роли их нет — сама планка проверяет ГОЛОВУ артефактной ветки на момент t0 задачи, а не то, что уже смержено; здесь применён тот же приём с `REPO_ROOT`, что и в оригиналах, чтобы прогнать их против кода этой ветки): все 16 — `ok` (`python3 -m unittest test_ac1_ac2_ac3_manifest test_ac4_docs_stack_md test_ac5_invariant_marker_present test_ac6_ac16_stdlib_only_scan_is_sound test_ac7_ac8_ac9_ac10_ac17_check_stack test_ac11_doctor_hookup test_ac12_ac13_version_output_new_lines test_ac15_manifest_regression_test_exists -v`).
- AC-14 (сравнение существующих строк вывода `version` + подпроцесс `tests.test_version`) — прогнан отдельно тем же приёмом, `ok`.
- `python3 -m unittest tests.test_version tests.test_stack -v` — 11 тестов, все `ok`.
- `python3 -m unittest tests.test_invariants -v` — 45 тестов (весь файл, включая новый класс `StdlibOnlyImportsInvariantTest`), все `ok`.
- `python3 -m unittest tests.test_doctor -v` — 95 тестов (весь файл, задет `all_checks`), все `ok` — регрессии от подключения `check_stack()` нет, в т.ч. `test_healthy_repo_prints_ok_and_does_not_exit` и `test_broken_repo_named_failures_and_nonzero_exit`.
- `python3 -c "from orchestrator import stack; [print(c) for c in stack.check_stack()]"` — реальный прогон на машине роли: `python 3.13.12 ok`, `git 2.50.1 ok`, `gh 2.98.0 ok`, `claude 2.1.236 ok` — выбранные минимумы (git 2.30.0, gh 2.0.0, claude 1.0.0) не шумят на здоровой машине, как и заявлено в PLAN «Риски».
- `python3 scripts/codebase_map.py` — прогнан и сверен: diff с текущим `docs/codebase-map.md` пуст, кроме строки `built_at_sha` (не признак дефекта, см. скил) — карта актуальна; файл возвращён в исходное состояние (`git checkout -- docs/codebase-map.md`) после сверки.
- Полный набор `tests/` в шаге не гонял (решение Оператора 05.09) — за него отвечает CI-джоб на каждый пуш ветки; здесь прогнаны все затронутые модули (`test_stack`, `test_invariants`, `test_doctor`, `test_version`) плюс полная приёмочная планка задачи.

## Предложения системе

- Разрыв между дисциплиной acceptance_tests/ (образцовые докстринги «Ловит мутацию») и постоянными `tests/*.py` того же MR (докстринги отсутствуют вовсе) — уже задокументированный класс наблюдения ([[feedback_test_authoring_mutation_claim_gap]] в памяти ревьювера), повторился и в этой задаче почти буквально: удобный источник формулировок (parallel acceptance-тест на тот же AC) не был использован при переносе теста в постоянный файл.
