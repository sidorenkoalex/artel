---
task: 01M5N9V4S984GRRXSMBK5JX7V1
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: ADR-0027, часть А1: общие фикстуры-песочницы в стиле pytest и их подключение для тестов и планки

# ADR-0027, часть А1: общие фикстуры-песочницы в стиле pytest и их подключение для тестов и планки

## Факты

ADR-0027 «Новые тесты артели в стиле pytest» принят Оператором 23.10.2026 (`docs/adr/0027-pytest-style-tests.md`). Исполнение делится: А1 (эта задача) — фикстуры и подключение; А2 — правила guard для фикстур, скрытых пропусков и скрытых вариантов; Б — приложения к скилам и инвариант изоляции фикстур. Сверено с пином 8cff887c; независимая проверка черновика 24.10 проверила механику пробами (переходник на `TmpRootTest` и `RealGitSandbox`; `pytest_plugins` в корневом `conftest.py` при запуске из корня, из чужого каталога с абсолютным путём, с флагами гейта `-p no:cacheprovider -p timeout -o timeout=…` и с `--rootdir=<дерево>`).

- Песочницы `tests/sandbox.py` — классы `unittest.TestCase`: `TmpDirTest` (:683; только `tdir`, пути `config` не подменяет), `TmpRootTest` (:1581; `root`, `retry_pauses`, `git_spy`, `use_role_map()`, методы `use_role_map`, `use_catalog_fixture`, `capture`), `InitializedTmpRootTest` (:1765; плюс `cmd_init`), `RealGitSandbox` (:1897; свой порядок подготовки, методы `git`, `checkout`, `add_synced_origin`; в `git()` — `self.assertEqual` :1959), `OriginRealGitSandbox` (:2011; `add_origin()`, `bare`), `LightTransitionSandbox` (:2124; `wt_path`, `in_repo_handlers`, `TASK`, `tdir`, `branch`, методы `task_row`, `state`, `set_state`, `write_plan_ready`, `write_acceptance_plank`, `advance_from_in_dev`). Список путей `config` — `ALL_CONFIG_ATTRS` (:90); `TmpRootTest.PATCHED_ATTRS` (:1599) по умолчанию равен ему. Возможностей, требующих раннера unittest (`self.id()`, `subTest`, `setUpClass`, `addClassCleanup`), песочницы не используют; шаблон `_real_git_template` кэшируется `functools.cache` в своём процессе (совместим с xdist).
- Импорт `tests.sandbox` меняет состояние процесса: `shutil.which` (:141), `config.ROLES`, `MODELS_LOCAL` (:437–440), `config.TWO_SIDED_OBSERVATION = False` (:446).
- `unittest.TestCase.doCleanups()` вне раннера unittest (без `_outcome`) проглатывает ошибку уборки и только возвращает `False` (проверено на Python 3.13).
- Корневой `conftest.py` — защищённый путь (`orchestrator/config.py:774`, маска `**/conftest.py`); правка — приложением PLAN; приложение к `conftest.py` заводит полный прогон на мерже. Корневой `conftest.py` загружается до сбора во всех раскладках прогона артели (планка выкладывается в `<рабочая копия>/tasks/<id>/`); `tests/__init__.py` есть. Чужие проекты гоняются в своём дереве — подключение на них не действует.

## Требования

1. Новый модуль `tests/fixtures.py` — фикстуры pytest `tmp_dir`, `tmp_root`, `initialized_tmp_root`, `real_git`, `origin_real_git`, `light_transition`, эквивалентные классам `TmpDirTest`, `TmpRootTest`, `InitializedTmpRootTest`, `RealGitSandbox`, `OriginRealGitSandbox`, `LightTransitionSandbox`. Способ — переходник: фикстура создаёт экземпляр класса (`cls()`), вызывает `setUp()`, отдаёт экземпляр (тест берёт его атрибуты и методы — перечень по классам в PLAN), на завершении вызывает `doCleanups()` и при возврате `False` поднимает `RuntimeError` с текстом причины (не `assert`). Если `setUp()` упал — `doCleanups()` и повторный подъём исключения. `tests/sandbox.py` не меняется; модуль `tests.sandbox` импортируется внутри фикстур, не на уровне `tests/fixtures.py`. Настройки классов (`PATCHED_ATTRS`, `REAL_RETRY_PAUSE`, `ARTEL_CLONE_IS_ROOT`, `TASK_TITLE`) фикстуры не повторяют — значения по умолчанию.
2. Подключение `pytest_plugins = ["tests.fixtures"]` в корневом `conftest.py` — Приложение 1 ниже (исполняется без изменений). Собственные тесты задачи не полагаются на подключение: импортируют фикстуры из `tests.fixtures` явно, а видимость фикстур планке проверяют во временном проекте со своим `conftest.py`, повторяющим строку приложения.
3. Тесты (новый файл в `tests/`, сам в стиле pytest — функции, `parametrize`; у каждой функции — «Ловит мутацию:»): (а) `parametrize` по фикстурам: для `tmp_dir` — каталог временный и после завершения удалён; для остальных — подменены пути `config` класса (`ALL_CONFIG_ATTRS`; у `RealGitSandbox` — по его подготовке), корень — временный, после завершения подмены сняты и корень удалён; (б) ошибка уборки в `doCleanups` даёт `RuntimeError`, а не тихий успех (мутация: проверка возврата убрана); (в) падение `setUp` — уборка выполнена, исключение поднято; (г) импорт `tests.fixtures` не меняет `config.TWO_SIDED_OBSERVATION`, `config.ROLES` и `shutil.which` (мутация: импорт `tests.sandbox` на уровне модуля); (д) временный проект с `conftest.py` (`pytest_plugins = ["tests.fixtures"]`) — фикстура видна тесту под `tasks/<id>/acceptance_tests/` при флагах гейта (прогон pytest подпроцессом); (е) методы класса (`git()` у `real_git`, `state()` у `light_transition`) работают через фикстуру.
4. Существующие тесты не правятся и остаются зелёными; адресный прогон — по одному-два файла на каждый класс песочницы (список в PLAN).

Зоны: docs/codebase-map.md, tests/

Ограничение зон по смыслу: в `tests/` — только новые файлы (`tests/fixtures.py` и тесты задачи).

Только чтение: tests/sandbox.py, conftest.py (защищённый; правка — Приложение 1), docs/adr/0027-pytest-style-tests.md, orchestrator/config.py, orchestrator/acceptance.py, pyproject.toml, skills/test-authoring.md, tests/test_invariants.py.

Не входит: правила guard для фикстур, скрытых пропусков и вариантов (часть А2); приложения к скилам и инвариант изоляции фикстур (часть Б); настройки классов в фикстурах; перевод существующих тестов.

Бюджет: $30.

## Приложения PLAN

### Приложение 1 (подключение общих фикстур): conftest.py

Защищённый путь; решение Оператора 23.10.2026 (ADR-0027, п. 2).

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
