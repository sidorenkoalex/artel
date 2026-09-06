---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: plan
author_role: developer
status: ready
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
- ANSWER-4 (второй заход, закрывает AC-7): реальный прогон планки этой
  задачи в предыдущей итерации показал 27/28 — красным оставался только
  `test_ac7_per_test_timeout.py`. Причина — не значение таймаута
  (`-o timeout=…` из шага 1 передавалось верно), а интерпретатор:
  `subprocess.run(["python3", ...])` резолвит `python3` по PATH
  ВЫЗЫВАЮЩЕГО процесса пульта (гейты/`amend-tests` зовут `acceptance.py`
  из своего окружения, не из `runner.role_env` — тот PATH с `venv/bin`
  первым существует только у роли), а `pytest-timeout` установлен только
  в `.artel/venv`, куда системный/pyenv `python3` не обязан попадать.
  Добавлена `stack.pytest_python_executable()` — `config.VENV_DIR/bin/
  python3`, если существует, иначе `sys.executable`; `acceptance.
  _pytest_command()` собирает команду через неё, не голым `"python3"`.
  Та же функция переиспользована в `stack._venv_packages_check()` —
  ok/warn-детали теперь называют интерпретатор, которым пульт реально
  гоняет тесты (второй пункт ANSWER-4, помимо AC-12).
- Отклонение от буквальной формулировки ANSWER-4 («передавать `-p
  pytest_timeout` явно»): эмпирическая проверка (`python3 -m pytest ...
  -p pytest_timeout`, живой прогон) показала `ValueError: Plugin already
  registered under a different name` — `pytest-timeout` регистрирует
  entry point под именем `timeout` (`pytest11 = timeout = pytest_timeout`
  в его собственном `setup.cfg`), а `-p pytest_timeout` подгружает модуль
  по ИМПОРТИРУЕМОМУ имени (не найдя entry point с таким именем) под
  ДРУГИМ именем регистрации — последующая автозагрузка того же модуля
  через entry points валит pluggy конфликтом имён. С намерением ANSWER-4
  (громкая ошибка при отсутствии плагина, не тихий пропуск) без этого
  бага справляется `-p timeout` (каноническое имя entry point) —
  эмпирически проверено и для отсутствующего имени (`ImportError` с
  ненулевым returncode), и для установленного (идемпотентно, поведение
  не меняется). Реализовано `-p timeout`, не `-p pytest_timeout` —
  рационале в докстринге `acceptance._pytest_command()`.

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
   строк диффа в `scripts/guard.py`) и зелёным `test_ac6_marker_
   scanning_regression.py`.
6. ANSWER-4 (закрытие AC-7 полностью): `stack.pytest_python_executable()`
   — интерпретатор venv для подпроцесса pytest вместо голого `"python3"`
   из PATH вызывающего процесса; `acceptance._pytest_command()` — общая
   сборка команды обоих раннеров через эту функцию плюс явная загрузка
   `pytest-timeout` по имени `-p timeout` (требования 1, 4, 8; AC-1,
   AC-3, AC-7, AC-12).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 6 |
| 2 | 2 |
| 3 | 5 (не тронуто — регресс) |
| 4 | 3, 4, 6 |
| 5 | 1 |
| 6 | 4 |
| 7 | 2 (только фикстуры AC-11), 5 (остальное не тронуто) |
| 8 | 3, 6 |

## Влияние на систему

- `orchestrator/acceptance.py::run()`/`run_full_suite()` — единственные
  вызывающие: `orchestrator/fsm_advance.py` (гейты `tests_writing`,
  `in_dev`, автогейт), `orchestrator/amend.py`. Контракт возврата
  (`(зелено, хвост)`, вырожденные случаи, `location_note`, таймаут ВСЕГО
  прогона) не изменён — проверено прогоном `tests/test_acceptance.py`
  (5/5 зелёных) и полной приёмочной планки этой задачи: 28/28 pytest-
  тестов зелёные (`python3 -m pytest tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/
  acceptance_tests -p no:cacheprovider`, 125с), включая ранее
  заблокированные AC-5/AC-6/AC-7/AC-9.
- `orchestrator/amend.py::_run_summary()` — единственный вызывающий:
  `_cmd_amend_tests` (запись в журнал `AMEND_ACTION`). Формат детали
  события меняется (unittest -> pytest wording), смысл (зелёный/красный
  исход, число тестов) — нет; `tests/test_amend.py` (23/23 зелёных
  после миграции фикстур AC-11) и сквозной AC-4/AC-11/AC-5 проверены.
- `orchestrator/stack.py::check_stack()`/`pytest_python_executable()` —
  потребители: `orchestrator/doctor.py` (напрямую через `check_stack()`),
  `orchestrator/acceptance.py::_pytest_command()` (новый потребитель этой
  задачи). CI не читает эти функции. Новая ветка WARN не меняет статус
  `ok`-сценария (проверено `test_matching_versions_produce_no_venv_warn`,
  остаётся зелёным); `tests/test_stack.py` (10/10 зелёных).
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
- Закрыто (прошлая итерация, `tasks/<id>/acceptance_tests/_util.py`
  отсутствовал в артефактной ветке — эскалация): ANSWER-3 закрыла файл
  через `amend-tests` (коммит `16cffbcc`), ANSWER-4 закрыла остаток
  причины AC-7 (интерпретатор pytest-подпроцесса) — см. «Подход» выше.
  Планка этой задачи прогнана целиком: 28/28 зелёных.
- `-p timeout` (не `-p pytest_timeout`) — единственная рабочая форма
  явной загрузки плагина без конфликта имён pluggy (см. «Подход»);
  если pytest-timeout когда-нибудь сменит каноническое имя entry point
  в новой мажорной версии, это же место придётся поправить — риск
  зафиксирован докстрингом `_pytest_command()`, не только здесь.

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

## Возврат — конфликт подтяжки main

Причина возврата: подтяжка `origin/main` в ветку задачи конфликтовала
в двух файлах — `orchestrator/acceptance.py` и `docs/codebase-map.md`
(со стороны main прилетел коммит 1d8a1b6b, задача 01M1SHJTT0V5…:
обработка критерия `ci` в `acceptance.summary()`). Разрешено по
ANSWER-5, обе стороны сохранены целиком, ни одна ветка логики не
выброшена:

- `orchestrator/acceptance.py` — конфликт был только в блоке `import`:
  HEAD нёс `from . import config, gitcmd, stack` (раннер pytest этой
  задачи), main — `from . import ci, config, gitcmd` (критерий `ci`
  автогейта). Слито в один импорт `from . import ci, config, gitcmd,
  stack` — обе стороны используют разные имена модуля, конфликта смысла
  нет, только текстовое совпадение строки импорта. Тело функций
  (`run()`, `run_full_suite()`, `_pytest_command()`, `_timeout_text()`
  этой задачи; `summary()` с обработкой `ci_ns`/`ci.verifying_status()`
  из main) не конфликтовало — auto-merge принял обе стороны без правки.
- `docs/codebase-map.md` — автосгенерированный файл, конфликт из-за
  разошедшихся снапшотов (main успел смержить деление `orchestrator/
  doctor.py` на пакет `orchestrator/doctor/*.py` и добавить
  `orchestrator/pull.py`, эта ветка — переход `acceptance.py` на
  pytest). Взята сторона main целиком (`git checkout --theirs`), затем
  карта перегенерирована `python3 scripts/codebase_map.py` заново по
  правилам скила (подтяжка main меняет `*.py` не через Edit — тот же
  случай, что и described в conventions-core) — итоговый файл несёт
  ОБЕ стороны: секция `doctor/*` от main и обновлённые импорты
  `acceptance.py` (`ci`, `stack`) от этой задачи.
- `tests/test_amend.py` — авто-merge разрешил конфликт без маркеров
  (изменения в разных участках файла), проверено `grep` на маркеры
  конфликта — чисто.

Слияние закоммичено (`a221645f`, "Merge remote-tracking branch
'origin/main'..."). Прогон после слияния (все — в переднем плане,
синхронно, по правилу скила — полный `tests/` НЕ гонялся):

- Планка задачи целиком: `python3 -m pytest tasks/
  01M1TKP6AAY4W8GDGZNA9R0JZT/acceptance_tests -p no:cacheprovider` —
  28 passed за 125.59с.
- `tests/test_acceptance.py`, `tests/test_amend.py`,
  `tests/test_stack.py` — 41 passed.
- `tests/test_acceptance.py`, `tests/test_acceptance_tests_flow.py` —
  77 passed (модули критерия `ci`, названные ANSWER-5 прямо).
- Все `tests/test_guard*.py` (6 файлов) — 120 passed, 39 subtests
  passed.
- `tests/test_pull.py`, `tests/test_fsm_autogate.py`,
  `tests/test_fsm_map_conflict_autoresolve.py`,
  `tests/test_fsm_map_regen.py`, `tests/test_codebase_map.py`
  (модули, затронутые слиянием со стороны main) — 57 passed.

Код задачи (`orchestrator/acceptance.py`, `orchestrator/amend.py`,
`orchestrator/stack.py`, `pyproject.toml`) после слияния не менялся —
только разрешение конфликта импорта и регенерация карты.

## Возврат — замечания ревью, итерация 1 (R1-F1)

Причина возврата: REVIEW.md итерации 1 — замечание major R1-F1.
Комментарии `orchestrator/stack.py:53-58` и `pyproject.toml:1-9`
утверждали, что «расхождение [`PER_TEST_TIMEOUT_SEC`] и `pyproject.
toml[timeout]`] ловит `tests/test_stack.py`», но такого теста не было
— грепом подтверждено ревьювером, ни один тест `tests/` не сравнивал
эти два числа.

Закрыто добавлением реального теста, а не переписыванием комментариев
(первый вариант предложения ревью, не второй — защита реальнее
формулировки без неё): `tests/test_stack.py::ManifestConstantsTest::
test_per_test_timeout_matches_pyproject_toml` читает `pyproject.toml`
через стандартный `tomllib` (доступен без внешних зависимостей —
`stack.REQUIRED_PYTHON = (3, 11)`, `tomllib` в stdlib с 3.11) и
сравнивает `[tool.pytest.ini_options].timeout` с `stack.
PER_TEST_TIMEOUT_SEC`. Существующая формулировка комментариев в
`stack.py`/`pyproject.toml` («расхождение ловит `tests/test_stack.
py`») теперь ссылается на реально существующую защиту — сами
комментарии не тронуты, только их утверждение стало истинным.

Проверено принудительной рассинхронизацией: временная правка
`pyproject.toml` (`timeout = 120` -> `180`) даёт красный
`test_per_test_timeout_matches_pyproject_toml` (`AssertionError: 120
!= 180`), откат через `git checkout -- pyproject.toml` возвращает
дерево к исходному состоянию.

Прогон после правки (в переднем плане, синхронно):
- `tests/test_stack.py` — 11 passed (было 10, добавлен один тест).
- `tests/test_stack.py`, `tests/test_amend.py`, `tests/test_acceptance.
  py` — 42 passed.
- Планка задачи целиком (`tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/
  acceptance_tests`, `-p no:cacheprovider`) — 28 passed за 124.84с
  (AC-9 не задет правкой — `pyproject.toml` не менялся, только
  `tests/test_stack.py`).
- `python3 scripts/codebase_map.py` — перегенерирован (правка
  `tests/test_stack.py` подпадает под правило скила «правишь `*.py` в
  `tests/` — регенерируй карту»); диф — только `built_at_sha` (карта
  структурно не изменилась, тесты не входят в карту модулей верхнего
  уровня).

REVIEW.md — реестр замечаний: `R1-F1` размечен `fixed` с описанием
добавленного теста (перевод в `accepted` — решение ревьювера следующей
итерации, не самозакрытие).
