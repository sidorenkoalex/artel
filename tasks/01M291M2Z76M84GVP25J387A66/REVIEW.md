---
task: 01M291M2Z76M84GVP25J387A66
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: полный набор tests/ идёт параллельно внутри одной машины (pytest-xdist) — CI и автогейт приёмки

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1, AC-2, AC-4) | OK | `run_full_suite` несёт `_pytest_command("tests") + ["-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"]` (orchestrator/acceptance.py:213-215); `config.FULL_SUITE_WORKERS = "auto"` (orchestrator/config.py:131); `-n`/`-p xdist` добавлены ТОЛЬКО в конкатенации `run_full_suite`, `_pytest_command` не тронут — `run()` (планка) остаётся без них, подтверждено реальным вызовом `acceptance.run(...)` в тесте `test_ac4_run_command_carries_no_parallel_flags`. |
| 2 (AC-5) | OK | Срез хвоста `[-2000:]` не менялся; проверено и мокнутым тестом (`test_ac5_noisy_worker_output_does_not_push_out_the_passed_summary`, 200 строк шума воркеров + `"500 passed"` в хвосте), и моим реальным немокнутым прогоном `run_full_suite` на временном `tests/` с 2 тестами — итоговая строка `"2 passed in 0.68s"` осталась в конце вывода без `-o console_output_style=classic` (не понадобился). |
| 3 (AC-6) | OK | Дифф `.github/workflows/ci.yml` приложен к PLAN.md, шаг «unit-тесты» задания `python` вызывает `python3 -m pytest tests -n auto -p no:cacheprovider -p timeout -p xdist -o timeout=120` (без `-v`, 120 = `stack.PER_TEST_TIMEOUT_SEC`, сверено); остальные два шага CI не меняются. Проверил `git apply --check` на чистом дереве этой ветки — применяется без конфликтов. `.github/` в фактическом diff кода не тронут (дифф — только приложение к PLAN.md, роль его не применяла) — защищённый путь соблюдён. |
| 4 (AC-7) | OK | `tests/test_acceptance.py` несёт `RunFullSuiteUsesWorkersAndXdistTest` (два новых метода): (а) команда содержит `-n <FULL_SUITE_WORKERS>` и `-p xdist`; (б) `FULL_SUITE_WORKERS = 1` даёt валидную `-n 1`; (в) прогнал `tests.test_acceptance`, `tests.test_fsm_autogate`, `tests.test_stack` — 36 тестов, все зелёные, ни одно существующее утверждение не тронуто (diff подтверждает — только добавление). |
| 5 (AC-8) | OK | PLAN.md, «Проверено исполнением»: «до — `unittest discover` — 438с в CI; после — `pytest tests -n 8` — 140с, 2084 passed, 511 subtests». |

## Замечания

Пусто — блокеров и замечаний уровня major/minor не найдено.

## Реестр замечаний

Пусто (итерация 1, замечаний не заведено).

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_acceptance tests.test_fsm_autogate tests.test_stack -v` — 36 тестов, все зелёные (модули, затронутые диффом + единственный потребитель `run_full_suite`, `fsm_autogate`).
- `python3 -m unittest discover -s tasks/01M291M2Z76M84GVP25J387A66/acceptance_tests -v` — 7 тестов приёмочной планки задачи (AC-1/AC-2/AC-3/AC-4/AC-5/AC-7а/AC-7б), все зелёные.
- Реальный (немокнутый) вызов `orchestrator.acceptance.run_full_suite(root)` на временном каталоге `tests/` с 2 тестами: вывод pytest подтверждает фактическую загрузку `pytest-xdist` (`created: 14/14 workers`, `plugins: timeout-2.4.0, xdist-3.8.0`), `GREEN: True`, итоговая строка `"2 passed in 0.68s"` — не мок, а действительное поведение с установленным в venv `pytest-xdist==3.8.0`.
- `git apply --check` на приложенном к PLAN.md диффе `.github/workflows/ci.yml` (записан во временный файл под `tasks/<id>/`, сразу удалён после проверки) на чистом дереве кодовой ветки этой задачи — применяется без конфликтов.
- Сверил `orchestrator/config.py::PER_TEST_TIMEOUT_SEC` (=120) со значением `-o timeout=120` в приложенном диффе CI — совпадает, как заявлено в PLAN «Известное ограничение».
- `python3 scripts/codebase_map.py` (регенерация) на HEAD ветки — diff только в строке `built_at_sha` (содержимое карты не изменилось несмотря на правку `orchestrator/*.py`); по правилу скила («built_at_sha не читай как признак дефекта», сверка по содержимому без этой строки) регенерация в коммите задачи не требовалась. Изменение отменено (`git checkout -- docs/codebase-map.md`), рабочее дерево чистое.
- `git status --short` до и после проверок — рабочее дерево чисто (кроме нематериализуемого `tasks/01M291M2Z76M84GVP25J387A66/`), `python3 -m py_compile` трёх изменённых файлов — без ошибок.
- Полный набор `tests/` в этом шаге не гонял (решение Оператора 05.09) — его зелёность на коммите 745bf21f подтверждена статусом CI из пакета (14 проверок, зелёный).

## Предложения системе

Пусто.
