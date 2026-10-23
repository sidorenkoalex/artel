---
task: 01M5N9V4S984GRRXSMBK5JX7V1
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: docs/codebase-map.md, tests/
budget_usd: 30
---

# SPEC: ADR-0027, часть А1 — общие фикстуры-песочницы в стиле pytest и их подключение для тестов и планки

## Контекст
ADR-0027 «Новые тесты артели в стиле pytest» (`docs/adr/0027-pytest-style-tests.md`,
принят Оператором 23.10.2026) переводит новые тесты артели на стиль pytest.
Песочницы `tests/sandbox.py` сейчас доступны только как классы
`unittest.TestCase` (`TmpDirTest` :683, `TmpRootTest` :1581,
`InitializedTmpRootTest` :1765, `RealGitSandbox` :1897,
`OriginRealGitSandbox` :2011, `LightTransitionSandbox` :2124), и тесту
в стиле pytest взять их нечем. Эта часть (А1) даёт фикстуры-переходники
над теми же классами и подключает их корневым `conftest.py`, чтобы
фикстуры видели и `tests/`, и планка `tasks/<id>/acceptance_tests/`.
Правила guard (А2), приложения к скилам и инвариант изоляции (Б) идут
отдельными частями.

Особенности, на которые опираются требования (сверено ТЗ с пином 8cff887c):
импорт `tests.sandbox` меняет состояние процесса (`shutil.which` :141,
`config.ROLES`/`MODELS_LOCAL` :437–440, `config.TWO_SIDED_OBSERVATION = False`
:446); `unittest.TestCase.doCleanups()` вне раннера unittest проглатывает
ошибку уборки и только возвращает `False`; корневой `conftest.py` —
защищённый путь (маска `**/conftest.py`), правка — только приложением PLAN.

## Требования

1. Новый модуль `tests/fixtures.py` несёт фикстуры pytest `tmp_dir`,
   `tmp_root`, `initialized_tmp_root`, `real_git`, `origin_real_git`,
   `light_transition`, эквивалентные классам `TmpDirTest`, `TmpRootTest`,
   `InitializedTmpRootTest`, `RealGitSandbox`, `OriginRealGitSandbox`,
   `LightTransitionSandbox` соответственно.
2. Способ — переходник: фикстура создаёт экземпляр класса (`cls()`),
   вызывает `setUp()` и отдаёт экземпляр (тест берёт его атрибуты и
   методы; перечень по классам — в PLAN); на завершении вызывает
   `doCleanups()` и при возврате `False` поднимает `RuntimeError` с
   текстом причины (не `assert`).
3. Если `setUp()` упал — фикстура вызывает `doCleanups()` и поднимает
   исходное исключение повторно.
4. `tests/sandbox.py` не меняется; модуль `tests.sandbox` импортируется
   внутри фикстур, не на уровне модуля `tests/fixtures.py`.
5. Настройки классов (`PATCHED_ATTRS`, `REAL_RETRY_PAUSE`,
   `ARTEL_CLONE_IS_ROOT`, `TASK_TITLE`) фикстуры не повторяют и не
   переопределяют — действуют значения по умолчанию классов.
6. Подключение `pytest_plugins = ["tests.fixtures"]` в корневом
   `conftest.py` — Приложением 1 к PLAN.md (раздел «Материалы»),
   исполняется без изменений.
7. Собственные тесты задачи не полагаются на подключение из корневого
   `conftest.py`: импортируют фикстуры из `tests.fixtures` явно, а
   видимость фикстур планке проверяют во временном проекте со своим
   `conftest.py`, повторяющим строку приложения.
8. Тесты задачи — новый файл в `tests/`, сам в стиле pytest (функции,
   `parametrize`); у каждой тестовой функции — строка «Ловит мутацию:».
9. Существующие тесты не правятся и остаются зелёными; адресный прогон —
   по одному-два файла на каждый класс песочницы (список — в PLAN).

## Критерии приёмки

AC-1. `tests/fixtures.py` определяет фикстуры pytest `tmp_dir`, `tmp_root`, `initialized_tmp_root`, `real_git`, `origin_real_git`, `light_transition`; каждая отдаёт экземпляр соответствующего класса `tests/sandbox.py` (`TmpDirTest`, `TmpRootTest`, `InitializedTmpRootTest`, `RealGitSandbox`, `OriginRealGitSandbox`, `LightTransitionSandbox`) после его `setUp()`.

AC-2. Для фикстуры `tmp_dir` (`parametrize` по фикстурам): каталог экземпляра временный во время теста и удалён после завершения фикстуры.

AC-3. Для остальных пяти фикстур (`parametrize` по фикстурам): во время теста подменены пути `config` класса (`ALL_CONFIG_ATTRS`; у `RealGitSandbox`/`OriginRealGitSandbox` — по его подготовке), корень временный; после завершения фикстуры подмены сняты (значения `config` прежние) и корень удалён.

AC-4. Ошибка уборки (`doCleanups()` возвращает `False`) на завершении фикстуры поднимает `RuntimeError` с текстом причины, а не завершается тихим успехом; тест ловит мутацию «проверка возврата `doCleanups()` убрана».

AC-5. Падение `setUp()` внутри фикстуры: уборка (`doCleanups()`) выполнена — зарегистрированные к моменту падения действия уборки отработали, и исходное исключение поднято наружу.

AC-6. Импорт `tests.fixtures` (в процессе, где `tests.sandbox` ещё не импортирован) не меняет `config.TWO_SIDED_OBSERVATION`, `config.ROLES` и `shutil.which`; тест ловит мутацию «импорт `tests.sandbox` на уровне модуля `tests/fixtures.py`».

AC-7. Во временном проекте с `conftest.py`, несущим `pytest_plugins = ["tests.fixtures"]`, фикстура из `tests.fixtures` видна тесту под `tasks/<id>/acceptance_tests/` при флагах гейта (`-p no:cacheprovider -p timeout -o timeout=…`); проверка — прогоном pytest подпроцессом.

AC-8. Методы класса работают через фикстуру: `git()` у экземпляра из `real_git` и `state()` у экземпляра из `light_transition` выполняются и возвращают результат без ошибки.

AC-9. Тесты задачи лежат в новом файле `tests/`, написаны функциями pytest (не классами `unittest.TestCase`), используют `parametrize`, у каждой тестовой функции есть строка «Ловит мутацию:»; фикстуры импортированы из `tests.fixtures` явно, `tests/sandbox.py` и существующие файлы `tests/` в диффе ветки не изменены.

## Оценка объёма и деление
Сигналов «подозрения на большой объём» нет: 9 критериев приёмки, зоны — `docs/codebase-map.md` и новые файлы в `tests/`, бюджет $30 ниже порога сигнала. Деление не требуется.

## Не входит
- Правила guard для фикстур, скрытых пропусков и скрытых вариантов (часть А2).
- Приложения к скилам и инвариант изоляции фикстур (часть Б).
- Настройки классов в фикстурах (`PATCHED_ATTRS`, `REAL_RETRY_PAUSE`, `ARTEL_CLONE_IS_ROOT`, `TASK_TITLE` — параметризация фикстур).
- Перевод существующих тестов на фикстуры; правка `tests/sandbox.py` и любых существующих файлов `tests/` (в `tests/` — только новые файлы: `tests/fixtures.py` и тесты задачи).
- Правка корневого `conftest.py` сверх Приложения 1; в ветке он не правится — только приложением PLAN.
- Полный зелёный набор `tests/` и CI ветки — её держит пульт; адресный прогон существующих тестов по классам песочниц — в PLAN (требование 9), отдельного AC нет.
- Подключение фикстур в чужих проектах: они гоняются в своём дереве, корневой `conftest.py` артели на них не действует.
- Только чтение: `tests/sandbox.py`, `conftest.py`, `docs/adr/0027-pytest-style-tests.md`, `orchestrator/config.py`, `orchestrator/acceptance.py`, `pyproject.toml`, `skills/test-authoring.md`, `tests/test_invariants.py`.

## Материалы
- ТЗ: `tasks/01M5N9V4S984GRRXSMBK5JX7V1/TZ.md`; ADR: `docs/adr/0027-pytest-style-tests.md`.
- Приложение 1 к PLAN.md (защищённый путь; решение Оператора 23.10.2026, ADR-0027 п. 2), переносится в PLAN без изменений; контекст хунка сверен с `conftest.py` (строки 24–29):

```diff
diff --git a/conftest.py b/conftest.py
index ada960f..4f0de0b 100644
--- a/conftest.py
+++ b/conftest.py
@@ -24,6 +24,12 @@ import pytest
 
 from orchestrator.config import ARTEL_ROLE_ENV
 
+# Общие фикстуры-песочницы в стиле pytest (ADR-0027): видны тестам
+# `tests/` и планке `tasks/<id>/acceptance_tests/`. Модуль импортирует
+# `tests.sandbox` только внутри фикстур — подключение не меняет состояние
+# процесса для прогонов, которые песочницу не берут.
+pytest_plugins = ["tests.fixtures"]
+
 # Флаги pytest, за которыми следует отдельное значение — не позиционный
 # аргумент-путь (тот же список, что нёс `bash_guard._PYTEST_VALUE_FLAGS`).
 _VALUE_FLAGS = {"-k", "-m", "-p", "-o", "-c", "-n", "--maxfail",
```

- Независимая проверка черновика ТЗ 24.10 подтвердила механику пробами: переходник на `TmpRootTest` и `RealGitSandbox`; `pytest_plugins` в корневом `conftest.py` при запуске из корня, из чужого каталога с абсолютным путём, с флагами гейта и с `--rootdir=<дерево>`.
