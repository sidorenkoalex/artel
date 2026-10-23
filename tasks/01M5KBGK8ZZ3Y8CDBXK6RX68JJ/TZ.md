---
task: 01M5KBGK8ZZ3Y8CDBXK6RX68JJ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Тест argv гейта полного набора не зависит от имени интерпретатора

# Тест argv гейта полного набора не зависит от имени интерпретатора

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-20 (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии, раздел находок; в сводке отчёта — один из пяти красных тестов полного прогона). Ссылки сверены с `origin/main` 71ce9904.

- Тест `tests/test_suite_run.py:331` (`class GateArgvTest(TmpRootTest)`), метод `test_gate_call_argv_unchanged` (`:333`–`:346`): подменяет `acceptance.subprocess.run`, вызывает `acceptance.run_full_suite(self.root)` и сравнивает фактический argv с ожиданием `acceptance._pytest_command("tests") + ["-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"]`, которое вычисляется ПОСЛЕ выхода из подмены.
- Первый элемент обеих сторон даёт `orchestrator/acceptance.py:37` (`_pytest_command`) через `stack.pytest_python_executable()` (`orchestrator/acceptance.py:61`–`:64`). Функция `orchestrator/stack.py:626` (`pytest_python_executable`) ищет `config.VENV_DIR/bin/python3`, затем venv главной копии через `orchestrator/stack.py:587` (`_main_copy_root`), а тот зовёт `subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=_MODULE_ROOT, …)` (`orchestrator/stack.py:611`); не нашла — возвращает `sys.executable`.
- `acceptance.subprocess` — общий модуль `subprocess`, поэтому подмена теста перехватывает и вызов git внутри `_main_copy_root`: внутри подмены ответ git — строка «1 passed in 0.1s», путь главной копии вычисляется неверно, и фактический argv получает `sys.executable`; ожидание вне подмены получает настоящий путь `…/.artel/venv/bin/python3` главной копии.
- Расхождение видно только там, где `config.VENV_DIR` (`orchestrator/config.py:123`, корень копии + `.artel/venv`) отсутствует — в рабочей копии `git worktree` (так устроена копия ревизии) — и процесс запущен не как `python3`: при запуске `.artel/venv/bin/python -m pytest` (команда `skills/code-revision.md:12`) `sys.executable` оканчивается на `python`, ожидание — на `python3`, тест красный независимо от кода; при запуске `.artel/venv/bin/python3` строки совпадают случайно, тест зелёный.
- Утверждение метода сегодня слабее, чем выглядит: ожидание собирается той же функцией `_pytest_command`, что и фактический argv, поэтому правка самой `_pytest_command` (потерянный `-p timeout`, другой порядок флагов) метод не краснит — ловится только расхождение между `_pytest_command` и `run_full_suite`.
- Тест требования 3 — охранный: на текущем коде зелёный. Красный тест задачи — требование 2; тесту нужен импорт `stack` (`from orchestrator import stack`).
- Мандат Оператора 23.10 на правку ожидания этого метода — есть.

## Требования

1. В `tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged` интерпретатор берётся из одной подмены на весь метод: `mock.patch.object(acceptance.stack, "pytest_python_executable", return_value="/fake/venv/bin/python3")` действует и на вызов `acceptance.run_full_suite(self.root)`, и на сборку ожидания. Ожидание записывается полным списком-литералом, а не вызовом `acceptance._pytest_command`: `["/fake/venv/bin/python3", "-m", "pytest", "tests", "-p", "no:cacheprovider", "-p", "timeout", "-o", f"timeout={stack.PER_TEST_TIMEOUT_SEC}", "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"]`; сравнение — `assertEqual` всего argv. Докстринг метода называет обе мутации, которые он ловит: флаги `suite-run` или иной порядок в прогоне гейта и правку общей части команды `_pytest_command`.
2. Новый тест в `tests/test_suite_run.py` (новый класс, например `GateArgvInterpreterIndependenceTest`) воспроизводит условие ревизии без сети: временный репозиторий git с файлом `.artel/venv/bin/python3` и его рабочая копия `git worktree add` без `.artel/venv`; подменяются `stack._MODULE_ROOT` (на рабочую копию), `config.VENV_DIR` (на несуществующий каталог) и `stack.sys.executable` (на `/fake/bin/python`). Под этими подменами тест запускает `GateArgvTest("test_gate_call_argv_unchanged")` через `unittest.TestResult` и проверяет `result.wasSuccessful()`. На текущем коде теста — красный (ожидание получает `…/.artel/venv/bin/python3` главного репозитория, фактический argv — `/fake/bin/python`); после требования 1 — зелёный.
3. Новый тест: при подмене `acceptance.stack.pytest_python_executable` фактический argv `acceptance.run_full_suite` начинается с её значения — пульт не обходит функцию выбора интерпретатора голым `python3` или `sys.executable` (утверждение, которое прежде держалось только равенством двух вызовов одной функции).
4. Код пульта не меняется: `orchestrator/acceptance.py` и `orchestrator/stack.py` — только чтение. Остальные методы `tests/test_suite_run.py` не правятся и остаются зелёными. Независимость от имени интерпретатора проверяется автоматически требованием 2.

## Меняемое поведение существующих тестов

Ослабление тестов разрешено: tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged

Метод `tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged`: ожидание argv перестаёт вычисляться вызовом `acceptance._pytest_command` вне подмены и становится литералом при подменённом `acceptance.stack.pytest_python_executable` (требование 1). Мандат Оператора 23.10.

Матрица неослабления:

| Свойство | Сейчас держит | Что меняется | Чем покрыто после | Решение |
|---|---|---|---|---|
| Прогон гейта по умолчанию не получает флаги `suite-run` (`-vv`, вывод в файл) и не меняет порядок путей | `GateArgvTest::test_gate_call_argv_unchanged` (сравнение с `_pytest_command` + флаги параллели) | ожидание — литерал вместо вызова функции | тот же метод, `assertEqual` всего argv с литералом (требование 1) | сохраняется |
| Общая часть команды pytest (`-m pytest`, `-p no:cacheprovider`, `-p timeout`, `-o timeout=…`) не меняется незаметно | ничем: ожидание собирала та же `_pytest_command` | литерал называет каждый элемент | тот же метод (требование 1) | усиливается |
| Первый элемент argv — интерпретатор, выбранный `stack.pytest_python_executable`, а не голый `python3` или `sys.executable` | косвенно: равенство двух вызовов одной функции | функция подменена значением, которого нет в природе | новый тест требования 3 и литерал требования 1 | сохраняется явной проверкой |
| Порядок поиска интерпретатора (`VENV_DIR`, venv главной копии, `sys.executable`) | не этот метод: тесты `stack.pytest_python_executable` в других файлах | не меняется | прежние тесты, код `orchestrator/stack.py` не меняется | вне задачи |
| Вердикт метода не зависит от имени интерпретатора процесса и от вида копии (главная или `git worktree`) | не держит: красный под `python` в рабочей копии `git worktree` | подмена снимает зависимость | новый тест требования 2 | усиливается |

Зоны: tests/test_suite_run.py

Только чтение: orchestrator/acceptance.py, orchestrator/stack.py, orchestrator/config.py, tests/sandbox.py (`TmpRootTest`, `RealGitSandbox` — не меняются), skills/code-revision.md (команда запуска набора — не меняется); вызывающие `_pytest_command` и `run_full_suite` (код пульта не меняется, они не затрагиваются): orchestrator/advance_gates/two_sided.py, orchestrator/advance_gates/test_integrity.py, orchestrator/notes.py, orchestrator/suite_lock.py, orchestrator/suite_run.py.

Не входит: правка `stack._main_copy_root` или `stack.pytest_python_executable` (выбор интерпретатора пульта верен; ошибка — в границе подмены теста); поиск других тестов, подменяющих `acceptance.subprocess.run` вокруг кода, который зовёт `_main_copy_root`, — отдельной строкой бэклога после этой задачи; четыре таймаута pytest-timeout тестов волны G из того же прогона ревизии (строка бэклога 344).

Бюджет: $10.
