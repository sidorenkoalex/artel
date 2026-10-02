---
task: 01M3Y7G6T3MK7A899521VF9N7B
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Прогоны pytest пульта не исполняют устаревший байткод из worktree

## Подход
В `orchestrator/acceptance.py` рядом с `_pytest_command` — контекстный
менеджер `_pytest_env()`: `tempfile.mkdtemp(prefix="artel-pycache-")` в
системном временном каталоге (вне `cwd` прогона и вне `config.ROOT`),
копия `os.environ` плюс `PYTHONPYCACHEPREFIX` на этот каталог, уборка в
`finally` — значит, и после `TimeoutExpired`, и после любого другого
исключения. Все три `subprocess.run` (`run`, `collect`, `run_full_suite`)
обёрнуты в `with _pytest_env() as env:` и получают `env=env`. Прочие
переменные не меняются, `runner.role_env` не используется.

Уборка — `_remove_cache_dir` с повторами (5 попыток по 0,2 с), последняя
— `ignore_errors=True`. Причина найдена прогоном: на таймауте
`subprocess.run` убивает главный процесс pytest, а рабочие процессы xdist
ещё дописывают `.pyc`, и `rmtree` падал `OSError: Directory not empty`
(`tests/test_acceptance.py::RunFullSuiteTest::test_timeout_is_not_green`
покраснел на первой версии с `TemporaryDirectory`). Сбой уборки не
подменяет исход прогона.

## Шаги
1. `orchestrator/acceptance.py`: `_pytest_env`, `_remove_cache_dir`, `env=`
   в три вызова; `tests/test_acceptance_pycache.py` — свойства, не
   покрытые долгоживущим файлом задачи; регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`_pytest_env`, уборка в `finally`) |
| 2 | 1 (`env=env` в `run`, `collect`, `run_full_suite`) |
| 3 | 1 (`dict(os.environ)` + одна переменная) |
| 4 | 1 (`tempfile.mkdtemp` в системном временном каталоге) |
| 5 | 1 (вызов с `-n … -p xdist` в том же `with`) |
| 6 | 1 (`tests/test_acceptance_pycache.py`; AC-1…AC-6 — долгоживущий `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`) |

Тесты `tests/test_acceptance_pycache.py` (у каждого «Ловит мутацию: …»,
каждая проверена временной мутацией — тест красный, код возвращён):
- `test_cache_dir_removed_after_non_timeout_exception` — уборка после
  `FileNotFoundError` по всем трём входам (мутация «уборка только в
  `except TimeoutExpired` и на успехе»: 3 failed);
- `test_existing_prefix_in_pult_environment_is_overridden` — заданная у
  пульта переменная перекрывается, `os.environ` не меняется (мутация
  `setdefault`: 6 failed);
- `test_cleanup_retries_when_late_writer_blocks_rmtree` — повтор уборки
  после `OSError` (мутация «один rmtree без повтора»: 1 failed).

Прогон: `python3 -m pytest tests/test_acceptance_pycache.py
tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py
tasks/01M3Y7G6T3MK7A899521VF9N7B/acceptance_tests tests/test_acceptance.py
tests/test_acceptance_collect.py -p no:cacheprovider -p timeout -o
timeout=120` — 37 passed, 41 subtests passed.

## Влияние на систему
Меняется только окружение дочернего pytest в трёх функциях; через них идут
автогейт приёмки, полный набор на подтверждении приёмки и гейте мержа,
прогон планки после подтяжки main, сухой сбор на tests_writing,
amend-tests и doc-commit. Все они получают свежий кеш, то есть компилируют
исходники заново: несколько секунд на прогон, зато ложных красных от
устаревшего `.pyc` больше нет. Флаги команды pytest, таймауты, разбор
вывода и коды возврата не тронуты; существующие тесты не правились.
Откат — revert коммита.

## Риски
- Процесс xdist, переживший таймаут и уборку, может заново создать
  подкаталоги в удалённом префиксе: остаток в системном временном
  каталоге, на исход прогона он не влияет.
- Если `TMPDIR` пульта указан внутрь `config.ROOT`, требование 4 нарушится.
  Сейчас это `/var/folders/...`, отдельной проверки нет.

## Предложения системе
- В шаге роли не работают `ls`/`cat`/`rm` в Bash (`command not found`), а
  `for … ; done` упирается в подтверждение. Временные файлы мутаций
  пришлось удалять через `python3 -c "os.remove(...)"`; среда роли
  (`.artel/home`, PATH шага) расходится с тем, что ожидает скил
  coding-standards о мутационной проверке.
