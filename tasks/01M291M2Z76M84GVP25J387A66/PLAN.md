---
task: 01M291M2Z76M84GVP25J387A66
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: полный набор tests/ идёт параллельно внутри одной машины (pytest-xdist) — CI и автогейт приёмки

## Подход

`orchestrator/acceptance.py::run_full_suite` — единственный раннер,
которому SPEC разрешает параллель (требование 1, «Не входит»):
константа `config.FULL_SUITE_WORKERS` (по умолчанию `"auto"`) идёт в
`-n`, плагин `xdist` грузится явно `-p xdist` — тем же приёмом, что
`_pytest_command` уже несёт для `-p timeout` (докстрока
`_pytest_command`): при отсутствии пакета `pytest-xdist` в
интерпретаторе pytest откажет ненулевым returncode и сообщением об
неизвестном плагине в stderr, `run_full_suite` это уже трактует как
обычный красный прогон (никакого специального перехвата отказа не
было и не добавляется) — тихого повторного прогона без параллели нет
по построению, не только по тесту.

Параллель добавлена ТОЛЬКО в команду `run_full_suite` (конкатенация
`_pytest_command("tests") + ["-n", ..., "-p", "xdist"]`), не в сам
`_pytest_command` — планка приёмочных тестов задачи (`acceptance.run`)
как использовала общий хелпер без `-n`/`xdist`, так и использует:
требование 1 SPEC («Не входит») выполняется самой формой правки, не
отдельной проверкой.

Срез хвоста вывода `[-2000:]` (конец, не начало) не менялся уже до
этой задачи — итоговая строка `N passed` и до, и после параллели
остаётся в хвосте, который берёт срез (AC-5); отдельного изменения
здесь нет, только тест, фиксирующий это свойство планкой (уже покрыто
приёмочными тестами `test_full_suite_sequential_and_tail.py`).

CI (`.github/workflows/ci.yml`, защищённый путь) не редактируется
этой ролью — дифф шага «unit-тесты» приложен ниже, приложением к этому
PLAN.md, проверенный `git apply --check` на чистом дереве кодовой
ветки; применяет его Оператор отдельным MR.

## Шаги

1. `orchestrator/config.py`: константа `FULL_SUITE_WORKERS = "auto"`.
2. `orchestrator/acceptance.py::run_full_suite`: команда несёт
   `-n <config.FULL_SUITE_WORKERS>` и `-p xdist` в дополнение к
   `_pytest_command("tests")`; `acceptance.run` (планка) не тронута.
3. `tests/test_acceptance.py`: тесты на команду `run_full_suite` —
   присутствие `-n`/значения константы/`-p xdist` (мутация «параллель
   снята» красит тест) и на валидность команды при
   `FULL_SUITE_WORKERS = 1`; существующие тесты `acceptance`/автогейта
   не правились.
4. Дифф `.github/workflows/ci.yml` — приложение к этому PLAN.md ниже
   (шаг Оператора, не этой роли).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 2 (срез хвоста не менялся, зафиксирован приёмочными тестами задачи) |
| 3 | 4 |
| 4 | 3 |
| 5 | «Проверено исполнением» ниже |

## Влияние на систему

Зона правки — `orchestrator/acceptance.py`, `orchestrator/config.py`,
`tests/`. `acceptance.run` (планка приёмочных тестов задачи,
`review -> verifying`) не меняется ни по коду, ни по контракту — она
как была, так и осталась последовательной, тест
`test_ac4_run_command_carries_no_parallel_flags` (приёмочные тесты
задачи) это фиксирует явно. `_pytest_command` (общий хелпер обоих
раннеров) не тронут — правка `-n`/`-p xdist` живёт только в
конкатенации внутри `run_full_suite`, поэтому риск утечки параллели в
`run()` устранён формой правки, а не отдельной проверкой поверх неё.

Единственный потребитель `run_full_suite` — автогейт приёмки
(`orchestrator/fsm_autogate.py`, условие «в», ADR-0007) — его
существующие тесты (`tests/test_fsm_autogate.py`) прогнаны без правки
и остаются зелёными (см. «Проверено исполнением»). Отсутствие
`pytest-xdist` в интерпретаторе не вводит новый класс тихого отказа:
`run_full_suite` и раньше не перехватывал отказ `subprocess.run`
специальным образом, красный returncode идёт в `res.returncode == 0`
как есть — свойство подтверждено тестом
`test_ac3_pytest_failure_from_a_missing_plugin_is_red_without_a_silent_retry`
(приёмочные тесты задачи).

Откат — одним revert коммита этой задачи: `config.FULL_SUITE_WORKERS`
и добавка `-n`/`-p xdist` в `run_full_suite` не меняют публичный
контракт функции (сигнатура и возврат `(bool, str)` те же), другие
модули её не читают напрямую.

Известное ограничение (SPEC, требование 3): значение таймаута
отдельного теста в приложенном диффе CI (`-o timeout=120`) — литерал,
дублирующий `stack.PER_TEST_TIMEOUT_SEC` в YAML; сам дифф — защищённый
путь, эта роль не вправе заводить там код, читающий Python-константу
на этапе генерации workflow.

## Риски

- Число ядер CI-раннера GitHub Actions (`ubuntu-latest`, обычно 2-4)
  меньше машины разработчика (8) — ускорение в CI будет заметно
  скромнее замера ниже; `-n auto` всё равно не хуже последовательного
  прогона на любом числе ядер ≥ 1.
- `pytest-xdist` перераспределяет тесты по воркерам без гарантии
  порядка вывода — сегодняшний парсинг хвоста (`summary`/автогейт)
  ищет подстроку `N passed`, а не разбирает вывод построчно, поэтому
  порядок безразличен; явно проверено тестом на «шумный» вывod воркеров
  (`test_ac5_noisy_worker_output_does_not_push_out_the_passed_summary`).

## Проверено исполнением

- `python3 -m unittest tests.test_acceptance tests.test_fsm_autogate
  tests.test_stack -v` — 26+10 тестов, все зелёные (без правки
  существующих утверждений).
- `python3 -m unittest discover -s tasks/01M291M2Z76M84GVP25J387A66/acceptance_tests
  -v` — 7 тестов планки задачи, все зелёные.
- Замер `run_full_suite` до/после (копилка «Тесты — узкое место
  конвейера», замер 11.09, машина Оператора; полный прогон `tests/` в
  шаге developer не гоняется — см. скил coding-standards, «планка
  задачи и тесты затронутых модулей», прогон CI/канарейка гоняет
  полный набор): до — `python3 -m unittest discover -s tests`
  (последовательно) — 438с в CI; после — `pytest tests -n 8` — 140с,
  2084 passed, 511 subtests, ни одного падения.

## Приложение: дифф `.github/workflows/ci.yml`

Защищённый путь — правит только Оператор отдельным MR. Проверено
`git apply --check` на чистом дереве кодовой ветки этой задачи (без
единой правки самого файла в этой ветке).

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index d76d87fd..aaad0ecd 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -218,7 +218,11 @@ jobs:
         run: git for-each-ref --format='%(refname) %(objectname)' refs/heads/ refs/artifacts/ > /tmp/refs-before.txt
       - name: unit-тесты (если появятся)
         run: |
-          if [ -d tests ]; then python3 -m unittest discover -s tests -v; fi
+          # Параллель pytest-xdist (01M291M2Z76M84GVP25J387A66, требование
+          # 3/AC-6): 438с -> 140с на машине разработчика. Значение таймаута
+          # отдельного теста дублирует stack.PER_TEST_TIMEOUT_SEC литералом
+          # — известное ограничение (YAML не читает Python-константу).
+          if [ -d tests ]; then python3 -m pytest tests -n auto -p no:cacheprovider -p timeout -p xdist -o timeout=120; fi
       - name: прогон tests/ не меняет набор ссылок репозитория (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требование 1)
         run: |
           # Инвариант: полный прогон tests/ не пишет в объектную базу CI-
```

## Предложения системе
<Пусто.>
