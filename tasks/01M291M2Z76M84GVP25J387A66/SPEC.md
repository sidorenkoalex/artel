---
task: 01M291M2Z76M84GVP25J387A66
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/acceptance.py, orchestrator/config.py, tests/
budget_usd: 25
---

# SPEC: полный набор tests/ идёт параллельно внутри одной машины (pytest-xdist) — CI и автогейт приёмки

## Контекст

Замер 11.09 (копилка «Тесты — узкое место конвейера»): задание CI
«Синтаксис и тесты оркестратора» (`.github/workflows/ci.yml`,
`python3 -m unittest discover -s tests -v`, один процесс) занимает
438 с из ~460 с прогона; автогейт приёмки (`fsm_autogate.py` ->
`acceptance.run_full_suite`) гонит тот же набор через pytest
(`acceptance._pytest_command("tests")`) тоже последовательно, ~8 минут;
каждая подтяжка main на гейте мержа — новый цикл CI. Замер на машине
Оператора: `pytest tests -n 8` — 2084 passed, 511 subtests за 140 с, ни
одного падения: тесты изолированы, параллель держат. `pytest-xdist`
уже объявлен в манифесте стека и `requirements.lock` (P0 05.09,
01M1REVEZ1) и ставится в CI, но не используется.

## Требования

1. `acceptance.run_full_suite` запускает полный набор с параллелью:
   `-n <workers>`, где число рабочих — константа
   `config.FULL_SUITE_WORKERS` (значение по умолчанию `"auto"`, то есть
   по числу ядер; строка или целое, передаётся в `-n` как есть).
   Плагин xdist загружается явно (`-p xdist`) тем же приёмом, что
   `-p timeout` в `_pytest_command`: при его отсутствии в
   интерпретаторе — громкий отказ, не тихий последовательный прогон.
   Планка (`acceptance.run`) остаётся последовательной — она короткая
   и её вывод читает Оператор.
2. Хвост вывода, который автогейт пишет в журнал, при xdist сохраняет
   итоговую строку `N passed` — проверить, что `-q`/группировка вывода
   рабочих не теряет её (при необходимости `-p no:cacheprovider` и
   `-o console_output_style=classic`).
3. Дифф `.github/workflows/ci.yml` (защищённый путь) — приложением к
   PLAN.md, проверенный `git apply --check`: шаг «unit-тесты» задания
   `python` вызывает `python3 -m pytest tests -n auto -p no:cacheprovider
   -p timeout -p xdist -o timeout=<PER_TEST_TIMEOUT_SEC>` тем же
   набором ключей, что `_pytest_command` (без `-v`; дублирование
   констант в YAML — назвать в PLAN как известное ограничение, значение
   брать из `stack.PER_TEST_TIMEOUT_SEC`). Шаг «tests.test_invariants на
   минимальной версии Python» не меняется. Шаг «прогон tests/ не меняет
   набор ссылок репозитория» остаётся после тестов как есть.
4. Тесты `tests/test_acceptance_full_suite.py` (или существующий файл,
   несущий `run_full_suite`): (а) команда содержит `-n` со значением
   константы и `-p xdist` (мутация «параллель снята» — красная);
   (б) при `FULL_SUITE_WORKERS = 1` команда всё равно валидна;
   (в) существующие тесты `acceptance`/автогейта зелёные без правки
   утверждений.
5. Замер в PLAN: время `run_full_suite` до и после на машине
   разработчика (одной строкой в «Проверено исполнением»).

## Критерии приёмки

AC-1. `acceptance.run_full_suite` вызывает pytest с ключом
`-n <значение config.FULL_SUITE_WORKERS>` и явной загрузкой плагина
`-p xdist`.

AC-2. `config.FULL_SUITE_WORKERS` — новая константа со значением по
умолчанию `"auto"` (строка либо целое, передаётся в `-n` как есть).

AC-3. Отсутствие плагина xdist в интерпретаторе, которым
`run_full_suite` запускает pytest, даёт громкий отказ (не тихий
последовательный прогон) — тем же приёмом, что уже несёт явная
загрузка `-p timeout` в `_pytest_command`.

AC-4. `acceptance.run` (планка приёмочных тестов задачи) остаётся
последовательным прогоном — без `-n`/`-p xdist`.

AC-5. Хвост вывода `run_full_suite`, который автогейт приёмки пишет в
журнал, при параллельном прогоне xdist сохраняет итоговую строку
`N passed` (при необходимости команда несёт `-p no:cacheprovider` и/или
`-o console_output_style=classic`, чтобы группировка вывода рабочих её
не съедала).

AC-6. Дифф `.github/workflows/ci.yml` приложен к PLAN.md и проверен
`git apply --check` на чистом дереве: шаг «unit-тесты» задания `python`
вызывает `python3 -m pytest tests -n auto -p no:cacheprovider -p timeout
-p xdist -o timeout=<PER_TEST_TIMEOUT_SEC>` (без `-v`; значение таймаута
берётся из `stack.PER_TEST_TIMEOUT_SEC`, дублирование числа литералом в
YAML названо в PLAN как известное ограничение); шаг
«tests.test_invariants на минимальной версии Python» и шаг «прогон
tests/ не меняет набор ссылок репозитория» (идущий после шага тестов)
остаются без изменений.

AC-7. Тесты `tests/test_acceptance_full_suite.py` (либо существующий
файл, несущий тесты `run_full_suite`, — `tests/test_acceptance.py`)
проверяют: (а) команда `run_full_suite` содержит `-n` со значением
константы `config.FULL_SUITE_WORKERS` и `-p xdist` — мутация «параллель
снята» красит этот тест; (б) при `config.FULL_SUITE_WORKERS = 1`
команда остаётся валидной; (в) существующие тесты `acceptance`/
автогейта остаются зелёными без правки их утверждений.

AC-8. PLAN.md несёт замер времени `run_full_suite` до и после на
машине разработчика — одной строкой в разделе «Проверено исполнением».

## Не входит

- Матрица заданий CI на нескольких машинах.
- Двойной прогон push + pull_request на один sha (отдельная строка
  копилки).
- Отказ гейта мержа от повторного цикла CI при документном сдвиге main
  (отдельная строка копилки).
- Перевод планки приёмочных тестов задачи (`acceptance.run`) на
  параллельный прогон — она остаётся последовательной (требование 1).

## Материалы

- Копилка «Тесты — узкое место конвейера», замер 11.09.
- `orchestrator/stack.py::THIRD_PARTY_EXCEPTIONS` — `pytest-xdist` уже
  объявлен допустимой сторонней зависимостью (SPEC
  01M1REVEZ1HESMJ7AFD5A9MEJ8).
