---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: plan
author_role: developer
status: escalate
schema_version: 4
---

# PLAN: P1a — раннер pytest в пульте: acceptance, dry_run, amend и их тесты

## Подход

Механика одного перехода (unittest -> pytest), пять требований SPEC —
одним диффом (см. «Оценка объёма» SPEC, монолит подтверждён Оператором):

- `orchestrator/acceptance.py::run()`/`run_full_suite()` зовут
  `python3 -m pytest <путь> -p no:cacheprovider` вместо
  `python3 -m unittest discover` (требования 1, 5): `cwd` прогона (уже
  существовавший параметр `code_root`/`root`) — единственный способ,
  которым pytest находит и код ветки задачи, и `pyproject.toml` корня
  (требования 4/6, таймаут отдельного теста).
- `orchestrator/amend.py::_RUN_SUMMARY` — регулярка ищет сводку pytest
  (`N passed`/`M failed, N passed ... in Xs`) вместо строки unittest `Ran
  N tests… OK/FAILED` (требование 2). `tests/test_amend.py::
  RunSummaryTest` — фикстуры мигрированы на реалистичный pytest-вывод,
  проверяемое поведение (сводка называет исход и число тестов) не
  изменено (AC-11).
- `orchestrator/stack.py` — новая именованная константа
  `PER_TEST_TIMEOUT_SEC = 120` (требование 4, источник значения для
  `pyproject.toml`); `_venv_packages_check()` при расхождении версий
  добавляет ОТДЕЛЬНУЮ фразу про `pytest`, если он в числе расходящихся
  (отсутствует ИЛИ не та версия) — не только имя в общем списке через
  запятую (требование 8, AC-12). `orchestrator/doctor.py` не тронут:
  `check_stack()` он вызывает уже сегодня, новая деталь долетает до него
  без правки (докстринг `test_ac12_doctor_pytest_named.py` подтверждает
  этот же вывод явно).
- Новый `pyproject.toml` (корень репозитория) — `[tool.pytest.ini_options]`
  с `testpaths = ["tests"]`, `python_files = ["test_*.py"]`,
  `timeout = 120` (требование 6; число синхронизировано руками с
  `stack.PER_TEST_TIMEOUT_SEC` — TOML не умеет читать оттуда, комментарий
  в обоих местах указывает на другое).
- Требование 3 (разбор `# AC-n:`/redness-маркеров, `scripts/guard.py`) —
  не входит в зону, не тронуто; требование 7 (сценарии/утверждения
  существующих `tests/*.py` не переписаны под идиомы pytest) —
  единственная правка тестового кода зоны `tests/` — фикстуры
  `RunSummaryTest` (AC-11), остальное не тронуто.
- Побочный дефект, найденный и исправленный по ходу (не отдельное
  требование SPEC, но необходим для требования 1): `subprocess.
  TimeoutExpired.stdout`/`.stderr` возвращаются `bytes`, а не `str`,
  несмотря на `text=True`, если процесс успел дать частичный вывод до
  срабатывания таймаута — наблюдаемая особенность `subprocess.run` в
  этом окружении (Python 3.13.12), не документированный контракт
  `text=`. Со старым `unittest discover` это молчало: одиночный
  зависший тест не даёт вывода раньше своего же зависания. pytest
  печатает заголовок сессии («test session starts», «collected N
  items») СРАЗУ, до прогона теста — конкатенация `(exc.stdout or "") +
  (exc.stderr or "")` в этот момент падала `TypeError: can't concat str
  to bytes` (поймано прогоном `tests/test_acceptance.py::
  RunFullSuiteTest::test_timeout_is_not_green`, ранее зелёным случайно —
  `SLEEPING_TEST` не печатает ничего до сна). Добавлена
  `acceptance._timeout_text()` — приводит оба потока к `str` независимо
  от того, что фактически вернул `subprocess`.

## Шаги

1. `orchestrator/acceptance.py` — `run()`/`run_full_suite()` на pytest,
   `-p no:cacheprovider`, `_timeout_text()` (требования 1, 5; AC-1, AC-2,
   AC-3, AC-8).
2. `orchestrator/amend.py::_RUN_SUMMARY`/`_run_summary()` — регулярка
   pytest-сводки (требование 2; AC-4, AC-5); `tests/test_amend.py::
   RunSummaryTest` — фикстуры под pytest-формат (AC-11).
3. `orchestrator/stack.py` — `PER_TEST_TIMEOUT_SEC` (требование 4),
   явное упоминание `pytest` в WARN `_venv_packages_check` (требование
   8; AC-12).
4. `pyproject.toml` (новый) — `testpaths`/`python_files`/`timeout`
   (требование 6; AC-9, AC-7 частично — конфигурация, сам прогон
   собирает шаг 1).
5. Регресс требования 3 (маркеры `# AC-n:`/redness, `scripts/guard.py`)
   — файл вне зоны, не тронут; неизменность подтверждена структурно (0
   строк диффа в `scripts/guard.py`) — сам регресс-тест `test_ac6_
   marker_scanning_regression.py` заблокирован дефектом планки, см.
   «Эскалация».

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 5 (не тронуто — регресс) |
| 4 | 3, 4 |
| 5 | 1 |
| 6 | 4 |
| 7 | 2 (только фикстуры AC-11), 5 (остальное не тронуто) |
| 8 | 3 |

## Влияние на систему

- `orchestrator/acceptance.py::run()`/`run_full_suite()` — единственные
  вызывающие: `orchestrator/fsm_advance.py` (гейты `tests_writing`,
  `in_dev`, автогейт), `orchestrator/amend.py`. Контракт возврата
  (`(зелено, хвост)`, вырожденные случаи, `location_note`, таймаут ВСЕГО
  прогона) не изменён — проверено прогоном существующих
  `tests/test_acceptance.py` (18/18 зелёных) и части `acceptance_tests/`
  этой же задачи (см. «Контекст» эскалации ниже).
- `orchestrator/amend.py::_run_summary()` — единственный вызывающий:
  `_cmd_amend_tests` (запись в журнал `AMEND_ACTION`). Формат детали
  события меняется (unittest -> pytest wording), смысл (зелёный/красный
  исход, число тестов) — нет; `tests/test_amend.py` (26/26 зелёных
  после миграции фикстур AC-11) и сквозной AC-4/AC-11 проверены.
- `orchestrator/stack.py::check_stack()` — потребители: `orchestrator/
  doctor.py` (напрямую), CI не читает эту функцию. Новая ветка WARN не
  меняет статус `ok`-сценария (проверено `test_matching_versions_
  produce_no_venv_warn`, остаётся зелёным).
- `pyproject.toml` — новый файл корня; не влияет на CI (джоб `python`
  всё ещё `python3 -m unittest discover`, требование 6/раздел «Не
  входит» этого не трогает) и не влияет на инструменты, которые уже
  что-то ищут в `pyproject.toml` (в репозитории такого не было —
  `find`-проверка на старте).
- Никакие тесты/гейты/лимиты не ослаблены: таймауты ВСЕГО прогона
  (`config.ACCEPTANCE_TIMEOUT_SEC`/`FULL_SUITE_TIMEOUT_SEC`) не тронуты,
  добавлен только НОВЫЙ таймаут отдельного теста (строже, не слабее).
  Откат — `git revert` этого коммита плюс возврат `_RUN_SUMMARY`/команды
  `run()`/`run_full_suite()` к unittest-варианту (оба варианта
  зафиксированы в истории git).

## Риски

- `.artel/venv` этого рабочего каталога уже несёт `pytest==9.1.1`
  (новее закреплённого в `requirements.lock` на момент резолва —
  `pytest==9.1.1` совпадает, проверено `pip freeze`/venv напрямую) —
  расхождений не найдено, венв согласован.
- См. «Эскалация» — главный риск этой сдачи: `tasks/<id>/
  acceptance_tests/_util.py` отсутствует, 4 из 12 файлов планки не
  собираются под pytest вовсе.

## Эскалация

При проверке реализации прогоном обнаружен блокирующий дефект ВНЕ зоны
этой задачи: 4 из 12 файлов `tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/
acceptance_tests/` (`test_ac5_amend_journal.py`,
`test_ac6_marker_scanning_regression.py`, `test_ac7_per_test_timeout.py`,
`test_ac9_pyproject_config.py`) несут `from _util import ...`, а сам
файл `_util.py` в артефактной ветке отсутствует — не был закоммичен
шагом test_author (коммит `5bece4e1`, `git show 5bece4e1 --stat` несёт
11 файлов, `_util.py` среди них нет). Прогон подтверждает: `pytest
<файл> --collect-only` на каждом из четырёх даёт `ModuleNotFoundError:
No module named '_util'`.

Это не «расхождение кода с тестом» (мой обычный случай «код чинится под
тесты») — файла с ожидаемым содержимым просто нет физически, и я не
могу восстановить его ТОЧНОЕ содержимое (в отличие от кода, для теста
важна экземплярная форма фикстуры: конкретные строки маркеров, номера
строк для `guard.scan_acceptance_tests`, точный контракт возврата
`read_pytest_config`). `acceptance_tests/` не входит в `zones:` SPEC и
залочен конвенцией (tasks/T023) — добавление файла в этот каталог вне
моего права.

Критично: `orchestrator/acceptance.py::run()` прогоняет ВЕСЬ каталог
`acceptance_tests/` ОДНИМ вызовом pytest — ошибка коллекции ОДНОГО
файла (`Interrupted: N errors during collection`, ненулевой
`returncode`) красит ВСЮ сессию, то есть красит все 12 файлов планки,
не только четыре сломанных. Приёмочная планка этой задачи не станет
зелёной НИ ПРИ КАКОЙ реализации кода, пока `_util.py` не появится.

Явно проверил: это НЕ блокирует переход `in_dev -> review`
(`orchestrator/fsm_advance.py::in_dev` сверяет только diff
`tests_locked_sha` — есть ли посторонняя правка `acceptance_tests/`
после лока, — не запускает `acceptance.run()`), поэтому сдаю код с
`status: escalate`, а не останавливаю работу целиком. Следующий гейт,
которому это будет важно (автогейт acceptance/`fsm_autogate.py`,
условие «`acceptance.run()` зелёный»), с этим дефектом не пройдёт
структурно, независимо от качества кода.

### Вопросы

1. Кто добавляет `tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/acceptance_tests/
   _util.py`? Варианты: (a) задача возвращается в `tests_writing`,
   test_author довносит файл повторным шагом; (b) Оператор коммитит файл
   в артефактную ветку сам; (c) Оператор явно разрешает мне (developer)
   добавить файл со следующим шагом — тогда использую предложенное ниже
   содержимое (выведено из точных `assert`'ов всех четырёх заблокированных
   файлов, не придумано произвольно). Блокирует: полную зелёную приёмку
   планки и прохождение автогейта acceptance. Дефолт при молчании: (a)
   — файлы `acceptance_tests/` создаёт test_author, не developer.
2. Если выбран вариант (c) — устраивает ли предложенное содержимое
   `_util.py` ниже? Блокирует: не блокирует старт следующего шага (могу
   начать с вопроса 1 без ответа на этот), но экономит итерацию при
   совместном ответе. Дефолт при молчании: содержимое неутверждено,
   следующий шаг разработчика проверяет и правит сам перед коммитом.

Предложенное содержимое `_util.py` (для варианта (c) вопроса 1) —
выведено построчно из `assertEqual`/`assertIn`/`assertRegex` четырёх
заблокированных файлов:

```python
"""Общие фикстуры/утилиты приёмочных тестов этой задачи (AC-5, AC-6,
AC-7, AC-9) — вне `test_*.py`-маски `scripts/guard.py::
scan_acceptance_tests`/`scan_redness_markers` (см. докстринги
`test_ac6_marker_scanning_regression.py`/`test_ac7_per_test_timeout.py`):
буквальный текст AC-маркеров здесь не должен читаться guard'ом как
разметка ЭТОЙ задачи.
"""
import tomllib
from pathlib import Path

# test_ac6: тест AC-1 покрыт, AC-2 manual, AC-3 skip; докстринг несёт
# валидный маркер красноты для scan_redness_markers (пишется и как
# test_ac.py, и как test_ok.py).
MIXED_PLANK = '''"""Зелёный с рождения: образец планки для регресс-теста
разбора guard.py (AC-1 покрыт тестом, AC-2/AC-3 — manual/skip)."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)


# AC-2: manual — Оператор проверяет глазами на приёмке
# AC-3: skip — временно не тестируется, обоснование в PLAN.md
'''

# test_ac6: планка БЕЗ маркера красноты (для контроля scan_redness_markers).
NO_MARKER_PLANK = '''import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
'''

# test_ac5: правка Оператора поверх AC_TEST_BOTH_COVERED — две ПРОХОДЯЩИЕ
# проверки AC-1, AC-2 manual (та же форма, что AC_TEST_AMENDED,
# tests/test_amend.py:400, для этой же цели в тестах amend.py).
AC_TEST_TWO_PASSING = '''"""Правка Оператора: две проверки AC-1 вместо
одной (сводка журнала amend-tests, AC-5)."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac1_first_criterion_again(self):
        self.assertEqual(1 + 1, 2)


# AC-2: manual — Оператор проверяет глазами на приёмке
'''


def read_pytest_config(repo_root: Path) -> dict | None:
    """{testpaths, python_files, timeout} из `pyproject.toml`
    (`[tool.pytest.ini_options]`) корня `repo_root`; `None` — файла нет
    или секции нет (test_ac7/test_ac9 требуют именно эти три ключа)."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return data.get("tool", {}).get("pytest", {}).get("ini_options")
```

### Контекст

- Реализованы и подтверждены прогоном все требования SPEC, для которых
  это возможно вне заблокированных файлов: `orchestrator/acceptance.py`,
  `orchestrator/amend.py`, `orchestrator/stack.py`, новый
  `pyproject.toml`, `tests/test_amend.py` (фикстуры AC-11).
- 8 из 12 файлов `acceptance_tests/` этой задачи зелёные под pytest
  (`test_ac1_ac2_run.py`, `test_ac3_run_full_suite.py`,
  `test_ac4_run_summary.py`, `test_ac8_pytest_cache_excluded.py`,
  `test_ac10_full_suite_manual.py` — manual, без тестового кода,
  `test_ac11_run_summary_fixture_migration.py`,
  `test_ac12_doctor_pytest_named.py`) — 38/38 pytest-тестов зелёные.
- Юнит-тесты зоны `tests/` зелёные: `tests/test_amend.py` (26/26),
  `tests/test_acceptance.py` (18/18 внутри общего прогона выше),
  `tests/test_stack.py` (10/10), `tests/test_doctor.py` (151/151 + 3
  subtests), `tests/test_invariants.py` (45/45 + 215 subtests).
- Заблокированы (только коллекцией, не логикой): `test_ac5_amend_
  journal.py`, `test_ac6_marker_scanning_regression.py`,
  `test_ac7_per_test_timeout.py`, `test_ac9_pyproject_config.py` —
  `ModuleNotFoundError: No module named '_util'`.

### Блокирует

Полное закрытие AC-5, AC-6, AC-7, AC-9 (4 из 12 критериев приёмки) и
любой будущий зелёный прогон `acceptance.run()` ЭТОЙ задачи целиком
(коллекция всего каталога — одна pytest-сессия, одна ошибка красит всё).
НЕ блокирует переход `in_dev -> review` (гейт не запускает
`acceptance.run()` — см. выше), поэтому код сдан этим шагом, а не
отложен.

## Предложения системе

- `scripts/guard.py` (класс проблемы, не конкретный файл): guard
  проверяет СТРУКТУРУ SPEC/PLAN/REVIEW, но не проверяет, что каждый
  `from <модуль>` внутри `acceptance_tests/*.py` физически резолвится в
  файл того же каталога — коммит test_author без `_util.py` (эта
  задача) прошёл guard молча и обнаружился только прогоном pytest на
  шаге разработчика, на итерацию позже, чем мог бы. Статический
  collect-only (без исполнения тестов, тем же принципом «не исполнять
  содержимое», что уже документирован в guard.py) на выходе из
  `tests_writing` мог бы поймать это раньше.
