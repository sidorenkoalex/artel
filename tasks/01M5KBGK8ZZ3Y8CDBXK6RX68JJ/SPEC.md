---
task: 01M5KBGK8ZZ3Y8CDBXK6RX68JJ
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/test_suite_run.py
budget_usd: 40
---

# SPEC: Тест argv гейта полного набора не зависит от имени интерпретатора

## Контекст
Находка ревизии кода 22.10 CR-2026-10-22-20. Метод
`tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged`
(`tests/test_suite_run.py:333`) подменяет `acceptance.subprocess.run` и
вызывает `acceptance.run_full_suite(self.root)`, а ожидание собирает
вызовом `acceptance._pytest_command("tests")` уже ПОСЛЕ выхода из подмены.
Первый элемент обеих сторон даёт `stack.pytest_python_executable()`
(`orchestrator/stack.py:626`), который при отсутствии `config.VENV_DIR`
ищет venv главной копии через `stack._main_copy_root`, а тот зовёт
`subprocess.run(["git", "rev-parse", "--git-common-dir"], …)`
(`orchestrator/stack.py:611`). `acceptance.subprocess` — общий модуль
`subprocess`, поэтому внутри подмены вызов git перехвачен, и фактический
argv получает `sys.executable`, а ожидание вне подмены — настоящий
`…/.artel/venv/bin/python3` главной копии. В рабочей копии `git worktree`
без `.artel/venv` при запуске `.artel/venv/bin/python -m pytest`
(`skills/code-revision.md:12`) метод красный независимо от кода. Кроме того,
утверждение слабее, чем выглядит: ожидание собирает та же
`_pytest_command`, так что правка её общей части метод не краснит.

## Требования

1. В `tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged`
   интерпретатор берётся из одной подмены на весь метод:
   `mock.patch.object(acceptance.stack, "pytest_python_executable",
   return_value="/fake/venv/bin/python3")` действует и на вызов
   `acceptance.run_full_suite(self.root)`, и на сборку ожидания. Ожидание
   записывается полным списком-литералом, а не вызовом
   `acceptance._pytest_command`:
   `["/fake/venv/bin/python3", "-m", "pytest", "tests", "-p",
   "no:cacheprovider", "-p", "timeout", "-o",
   f"timeout={stack.PER_TEST_TIMEOUT_SEC}", "-n",
   str(config.FULL_SUITE_WORKERS), "-p", "xdist"]`; сравнение —
   `assertEqual` всего argv. Докстринг метода называет обе мутации, которые
   он ловит: флаги `suite-run` или иной порядок в прогоне гейта и правку
   общей части команды `_pytest_command`. Для литерала тест импортирует
   `stack` (`from orchestrator import stack`).
2. Новый тест в `tests/test_suite_run.py` (новый класс, например
   `GateArgvInterpreterIndependenceTest`) воспроизводит условие ревизии без
   сети: временный репозиторий git с файлом `.artel/venv/bin/python3` и его
   рабочая копия `git worktree add` без `.artel/venv`; подменяются
   `stack._MODULE_ROOT` (на рабочую копию), `config.VENV_DIR` (на
   несуществующий каталог) и `stack.sys.executable` (на `/fake/bin/python`).
   Под этими подменами тест запускает
   `GateArgvTest("test_gate_call_argv_unchanged")` через
   `unittest.TestResult` и проверяет `result.wasSuccessful()`. На коде
   `tests/test_suite_run.py` до требования 1 этот тест красный (ожидание
   получает `…/.artel/venv/bin/python3` временного главного репозитория,
   фактический argv — `/fake/bin/python`); после требования 1 — зелёный.
3. Новый тест в `tests/test_suite_run.py`: при подмене
   `acceptance.stack.pytest_python_executable` фактический argv
   `acceptance.run_full_suite` начинается с её значения — пульт не обходит
   функцию выбора интерпретатора голым `python3` или `sys.executable`. Тест
   охранный: на текущем коде зелёный.
4. Код пульта не меняется: `orchestrator/acceptance.py` и
   `orchestrator/stack.py` — только чтение. Остальные существующие методы
   `tests/test_suite_run.py` не правятся; новые тесты, модульные помощники
   и импорты в этом файле допустимы.

## Критерии приёмки

AC-1. В `GateArgvTest::test_gate_call_argv_unchanged` подмена
`acceptance.stack.pytest_python_executable` значением
`"/fake/venv/bin/python3"` охватывает и вызов
`acceptance.run_full_suite(self.root)`, и сборку ожидания; ожидание —
список-литерал `["/fake/venv/bin/python3", "-m", "pytest", "tests", "-p",
"no:cacheprovider", "-p", "timeout", "-o",
f"timeout={stack.PER_TEST_TIMEOUT_SEC}", "-n",
str(config.FULL_SUITE_WORKERS), "-p", "xdist"]`, без вызова
`acceptance._pytest_command`; сравнение — `assertEqual` всего argv.

AC-2. Докстринг `GateArgvTest::test_gate_call_argv_unchanged` называет обе
ловимые мутации: флаги `suite-run` или иной порядок в прогоне гейта и правку
общей части команды `_pytest_command`.

AC-3. Правка общей части `acceptance._pytest_command` (например, потерянный
`-p timeout` или другой порядок её флагов) делает
`GateArgvTest::test_gate_call_argv_unchanged` красным.

AC-4. В `tests/test_suite_run.py` есть новый тест, который во временном
репозитории git с файлом `.artel/venv/bin/python3` и его рабочей копии
`git worktree add` без `.artel/venv`, при подменённых `stack._MODULE_ROOT`
(рабочая копия), `config.VENV_DIR` (несуществующий каталог) и
`stack.sys.executable` (`/fake/bin/python`), запускает
`GateArgvTest("test_gate_call_argv_unchanged")` через `unittest.TestResult`
и утверждает `result.wasSuccessful()`; без сети.

AC-5. Тест AC-4 красный при прежнем теле
`GateArgvTest::test_gate_call_argv_unchanged` (ожидание через
`acceptance._pytest_command` вне подмены) и зелёный при теле по AC-1.

AC-6. В `tests/test_suite_run.py` есть новый тест: при подменённом
`acceptance.stack.pytest_python_executable` первый элемент фактического argv
`acceptance.run_full_suite` равен её значению; тест зелёный на текущем коде
пульта и красный, если `run_full_suite`/`_pytest_command` ставит первым
элементом голый `python3` или `sys.executable` в обход этой функции.

AC-7. Существующие методы `tests/test_suite_run.py`, кроме
`GateArgvTest::test_gate_call_argv_unchanged`, не изменены. Новые тесты,
модульные помощники и импорты в этом файле допустимы.

AC-8. Дифф ветки задачи относительно базы вне `tests/test_suite_run.py` и
`docs/codebase-map.md` пуст: в частности, `orchestrator/acceptance.py`,
`orchestrator/stack.py`, `orchestrator/config.py` и `tests/sandbox.py` не
изменены.

## Оценка объёма и деление
Сработавший сигнал: `budget_usd` ≥ $30 (потолок $40 — решение Оператора на
гейте SPEC 23.10.2026 по калибровке: 8 критериев, одна зона). Прочих
сигналов нет: одна зона (`tests/test_suite_run.py`), 8 критериев приёмки.

Материал для решения о монолите: зона задачи — один файл, правка метода
(требование 1) и тест, красный на прежнем теле метода (требование 2),
описывают одно свойство; разнесённые по разным задачам, они либо оставляют
красный тест требования 2 в main, либо мержат правку метода без проверки
её смысла. Тест требования 3 — охранный и мал. Резать нечего.

## Не входит

- Правка кода пульта: `orchestrator/acceptance.py`, `orchestrator/stack.py`,
  `orchestrator/config.py`, `tests/sandbox.py` (`TmpRootTest`,
  `RealGitSandbox`), `skills/code-revision.md` и вызывающие
  `_pytest_command`/`run_full_suite` (`orchestrator/advance_gates/two_sided.py`,
  `orchestrator/advance_gates/test_integrity.py`, `orchestrator/notes.py`,
  `orchestrator/suite_lock.py`, `orchestrator/suite_run.py`) — только чтение.
  `orchestrator/config.py` и `tests/` входят в общие зоны
  (`config.COMMON_ZONES`), и гейт зон их правку не остановит — неизменность
  держит AC-8.
- Правка `stack._main_copy_root` или `stack.pytest_python_executable`:
  выбор интерпретатора пульта верен, ошибка — в границе подмены теста.
- Поиск других тестов, подменяющих `acceptance.subprocess.run` вокруг кода,
  который зовёт `_main_copy_root`, — отдельной строкой бэклога после этой
  задачи.
- Четыре таймаута pytest-timeout тестов волны G из того же прогона ревизии
  (строка бэклога 344).
- «Остальные методы `tests/test_suite_run.py` остаются зелёными» — полный
  зелёный набор `tests/`, его держит пульт.

## Материалы

- ТЗ: `tasks/01M5KBGK8ZZ3Y8CDBXK6RX68JJ/TZ.md`; отчёт ревизии
  `docs/audits/code-revision-2026-10-22.md` (копия ревизии), находка
  CR-2026-10-22-20.
- Мандат Оператора 23.10 и матрица неослабления по методу
  `tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged` —
  в ТЗ (раздел «Меняемое поведение существующих тестов»). Смена ожидания
  здесь — не смена скалярного литерала (вызов функции → список-литерал),
  поэтому раздела «Меняемое поведение» в SPEC нет. Гейт неослабления тестов
  читает мандат только из `tasks/<id>/ANSWER-n.md`
  (`orchestrator/advance_gates/test_integrity.py:1074`, `_answer_mandate`),
  не из ТЗ: на рубеже `in_dev -> verifying` изменённое утверждение метода
  будет находкой, пока строка
  `Ослабление тестов разрешено: tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged`
  не придёт командой `answer` (`docs/operator-gates.md`, гейт эскалации, п.6).
- Бюджет: ТЗ называет $10; поставлено $40 — решение Оператора на гейте SPEC
  23.10.2026 (круг 1) по калибровке (`config.recommended_budget_usd` для 7–8
  критериев и одной зоны — $40).
- Мандат на правку ожидания `test_gate_call_argv_unchanged` Оператор
  передаёт строкой ANSWER на следующем гейте SPEC (решение гейта 23.10.2026,
  круг 1).
