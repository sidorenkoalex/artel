---
task: 01M5N9V4S984GRRXSMBK5JX7V1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: ADR-0027, часть А1 — общие фикстуры-песочницы в стиле pytest

## Подход
Новый модуль `tests/fixtures.py`: шесть фикстур pytest без аргументов
(`tmp_dir`, `tmp_root`, `initialized_tmp_root`, `real_git`,
`origin_real_git`, `light_transition`), каждая — `yield from
_sandbox(<класс>)` с импортом класса `tests.sandbox` внутри тела фикстуры
(требование 4: импорт песочницы меняет состояние процесса).

Общий генератор `_sandbox(cls)`:
- `obj = cls()`, `obj.setUp()`; при сбое `setUp` (любое `BaseException`) —
  уборка `_run_cleanups(obj)`, ошибки уборки — `exc.add_note(...)`,
  повторный `raise` исходного исключения (требование 3);
- `yield obj`;
- уборка `_run_cleanups(obj)`; при ошибках — `RuntimeError` с текстом
  `уборка песочницы <Класс> упала: <repr>; <repr>` (требование 2).

`_run_cleanups` снимает действия со стека `obj._cleanups` по одному
(`pop()` — обратный порядок регистрации), зовёт каждое, исключения
собирает в список и не останавливается на упавшем. Действие,
зарегистрированное во время уборки, исполняется тем же циклом — как у
`unittest.TestCase.doCleanups()`. Сам `doCleanups()` не используется:
вне раннера unittest он проглатывает текст ошибки (решение Оператора на
гейте SPEC 24.10.2026).

Фикстуры без аргументов (не берут `request`): долгоживущий файл задачи
гоняет их вручную `<фикстура>.__wrapped__()` (записка test_author).
Настройки классов (`PATCHED_ATTRS` и др.) фикстуры не трогают
(требование 5) — экземпляр создаётся ровно из класса `tests/sandbox.py`.

Атрибуты и методы, доступные тесту через экземпляр (наследуются как есть):
- `tmp_dir` → `TmpDirTest`: `tdir`;
- `tmp_root` → `TmpRootTest`: `root`, `retry_pauses`, `use_role_map`,
  `use_catalog_fixture`, `capture`, `addCleanup`;
- `initialized_tmp_root` → `InitializedTmpRootTest`: то же после
  `catalog.cmd_init`;
- `real_git` → `RealGitSandbox`: `root`, `git`, `checkout`,
  `add_synced_origin`;
- `origin_real_git` → `OriginRealGitSandbox`: то же + `add_origin`;
- `light_transition` → `LightTransitionSandbox`: `task_row`, `state`,
  `set_state`, `write_plan_ready`, `write_acceptance_plank`,
  `advance_from_in_dev`.

Подключение для `tests/` и планки — `pytest_plugins = ["tests.fixtures"]`
в корневом `conftest.py` (защищённый путь) — Приложением 1 ниже, без
изменений против SPEC. В ветке `conftest.py` не правится.

Тесты задачи (AC-2…AC-8) — долгоживущий файл
`tests/test_01m5n9v4s984grrxsmbk5jx7v1_fixtures.py` (test_author, в стиле
pytest, явный импорт `tests.fixtures`); AC-9 — планка. Свойств сверх
покрытых этими файлами реализация не вводит, своих тестов не добавляю.

## Шаги
1. `tests/fixtures.py` — переходник `_sandbox`, `_run_cleanups`,
   `_cleanup_message` и шесть фикстур; регенерация
   `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).
2. Приложение 1 (корневой `conftest.py`) — переносится в PLAN без
   изменений; `git apply --check` на чистом дереве ветки — применяется.
3. Проверка: долгоживущий файл задачи, планка (`plank-run`), адресный
   прогон существующих тестов по классам песочниц.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 2 |
| 7 | 3 (долгоживущий файл импортирует `tests.fixtures` явно; AC-7 — временный проект подпроцессом) |
| 8 | 3 (долгоживущий файл test_author) |
| 9 | 3 |

Прогоны (24.10.2026, рабочий каталог шага):
- `python3 -m pytest tests/test_01m5n9v4s984grrxsmbk5jx7v1_fixtures.py -p no:cacheprovider -p timeout -o timeout=120` — 43 passed.
- `artel.py plank-run 01M5N9V4S984GRRXSMBK5JX7V1` — 2 passed, код выхода 0.
- Адресный прогон существующих тестов (требование 9), по файлу на класс:
  `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py` (`TmpDirTest`),
  `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py` (`LightTransitionSandbox`, поверх `TmpRootTest`),
  `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py` (`InitializedTmpRootTest`),
  `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py` (`RealGitSandbox`),
  `tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py` (`OriginRealGitSandbox`)
  вместе с файлом задачи — 73 passed, 49 subtests passed.
- `git apply --check` Приложения 1 на чистом дереве ветки — применяется (см. «Влияние на систему»).

## Влияние на систему
- `tests/sandbox.py` и существующие файлы `tests/` не меняются; в ветке
  новые файлы — только `tests/fixtures.py` (+ карта кодовой базы).
- До применения Приложения 1 модуль никем не подключён — поведение
  существующих прогонов не меняется. После применения корневой
  `conftest.py` импортирует `tests.fixtures` в каждом прогоне; модуль на
  уровне модуля импортирует только `pytest` — состояние процесса
  (`config.ROLES`, `config.TWO_SIDED_OBSERVATION`, `shutil.which`) не
  меняется (AC-6 проверяет подпроцессом). Новые имена фикстур
  (`tmp_dir`, `tmp_root`, …) не совпадают со встроенными pytest
  (`tmp_path`, `tmpdir`); фикстура, объявленная в файле теста с тем же
  именем, по правилам pytest перекрывает плагин — существующие тесты на
  `unittest.TestCase` фикстуры не берут вовсе.
- Гейты, лимиты, guard и инварианты не затрагиваются.
- Откат: revert merge-коммита задачи (вместе с ним снимается и
  приложение `conftest.py`); без приложения `tests/fixtures.py` инертен.

## Риски
- Фикстура полагается на закрытый атрибут `unittest.TestCase._cleanups`
  (список `(function, args, kwargs)`) — стабилен с Python 3.1, им же
  пользуется `doCleanups()`; смена формы в будущей версии Python уронит
  все фикстуры сразу и громко (долгоживущий файл задачи покраснеет).

## Предложения системе
- Песочница bash шага разработчика отказывает в `sed -i` и heredoc с
  `{`/кавычками — ручная временная мутация сторожа и `git apply --check`
  из stdin без записи файла недоступны; проверку приложения пришлось
  делать сценарием python. Команда пульта `appendix-check <id>`
  (прогон `git apply --check` по приложениям PLAN) сняла бы обход.

## Приложение 1: подключение фикстур в корневом conftest.py

Защищённый путь (маска `**/conftest.py`); решение Оператора 23.10.2026,
ADR-0027 п. 2; текст — из SPEC без изменений.

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
