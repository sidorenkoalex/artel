---
task: 01M52EEDEYV14658X8VFNHCW8K
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, orchestrator/project_profile.py, tests/
budget_usd: 25
---

# SPEC: D0-1: профиль test_profile — подполя runner, workdir, env и фиксация мест запуска

## Контекст
Часть 1 из 3 задачи D0 (родитель 01M52CQB468758M2NAA15C15ZE — внешний
доверенный проект без песочницы), основание — ADR-0023, вторая поправка
16.10.2026. Чтобы пульт мог прогонять тесты чужого стека, профиль тестов
проекта (`test_profile` в `targets.yaml`, проверка —
`orchestrator/targets.py::_check_profile`) должен уметь описать
собственный раннер проекта, каталог прогона и окружение. В этой части
вводятся только описание и проверка подполей и их доставка в
`project_profile.Profile`; поведение мест запуска тестов не меняется, а
их текущие argv, `cwd` и окружение фиксируются тестами, чтобы следующие
части D0 меняли их наблюдаемо.

## Требования

1. `test_profile` (`orchestrator/targets.py`) получает три необязательных
   подполя. Профиль без них остаётся правильным и ведёт себя как сейчас.
2. `runner`: допустимы ровно значения `pult-pytest` (значение по
   умолчанию при отсутствии подполя) и `pytest-own`; любое иное значение
   — отказ `targets.check`.
3. `workdir` — каталог прогона относительно корня репозитория;
   `targets.check` отказывает абсолютному пути и пути, в котором `..` —
   сегмент пути (как у вида `dir`, `orchestrator/targets.py:300-301`):
   `a/../b` — отказ, `a..b` — проходит.
4. `env` — блочное отображение строк (новый вид подполя `mapping` в
   проверке профиля; `orchestrator/yamlmini.py` не меняется).
   `targets.check` отказывает, называя в тексте отказа `test_profile` и
   `env`: значению `env`, не являющемуся отображением; значению
   переменной, не являющемуся строкой (в том числе int, bool и `None`,
   которые даёт разбор `yamlmini.scalar`, `orchestrator/yamlmini.py:57-62`);
   имени переменной из точного перечня секретов. Перечень секретов —
   имена `secret_env_names()` всех провайдеров реестра
   `orchestrator/providers/__init__.py::PROVIDERS` на момент проверки (не
   литералы имён), плюс `GITHUB_TOKEN`, `GH_TOKEN`. Сверка — по точному
   имени.
5. `workdir` и `env` допустимы только при `runner: pytest-own`:
   `targets.check` отказывает им при `runner: pult-pytest`, в том числе
   когда `runner` не задан (значение по умолчанию).
6. Подполя `runner`, `workdir`, `env` доходят до потребителей полями
   `project_profile.Profile` (`orchestrator/project_profile.py`). При
   отсутствии подполя: `Profile.runner` = `"pult-pytest"`,
   `Profile.workdir` = `""` (корень репозитория), `Profile.env` — пустое
   отображение. Существующие построения `Profile` через именованные
   аргументы без новых полей (`tests/test_project_profile_gates.py:210`,
   `tests/test_network_address_gate.py:178`) остаются рабочими без правки
   этих тестов. Потребителей в этой части не меняют.
7. Тестами в `tests/` зафиксированы argv, `cwd` и окружение каждого из
   восьми мест запуска тестов для артели на текущем коде:
   `acceptance.run`, `acceptance.collect`, `acceptance.run_repeat`,
   `acceptance.run_plank`, `acceptance._run_full_suite_now` с `observe` и
   без него, `acceptance._run_full_suite_to_log`, `two_sided._run_side`.
   Пути команды:
   - `acceptance.run`, `acceptance.collect`, `acceptance.run_repeat` —
     оба пути: `command=None` и `command=[python3, -m, pytest]` (профиль
     артели, `targets.yaml:46`);
   - `acceptance._run_full_suite_now` (с `observe` и без) и
     `acceptance._run_full_suite_to_log` — путь `command=None` и путь
     `command=[python3, -m, pytest]`, поданный через
     `acceptance.run_full_suite` (`orchestrator/acceptance.py:1115`):
     сами эти функции параметра `command` не имеют;
   - `acceptance.run_plank` (`orchestrator/acceptance.py:923`) и
     `two_sided._run_side` (`orchestrator/advance_gates/two_sided.py:222`)
     параметра `command` не имеют — фиксируется их единственный
     сегодняшний путь.
8. Текст отказа `targets.check` для неверного `runner`, `workdir` или
   `env` называет `test_profile` и имя подполя — по образцу
   `orchestrator/targets.py:281` («подполе 'test_profile.<подполе>' — …»).

## Критерии приёмки

AC-1. `targets.check` отказывает записи, у которой `test_profile.env`
(при `runner: pytest-own`) содержит имя из перечня секретов — любое из
`secret_env_names()` провайдеров реестра
`orchestrator/providers/__init__.py::PROVIDERS`, `GITHUB_TOKEN`,
`GH_TOKEN`; сверка идёт по точному имени (имя, отличающееся от секретного
регистром или суффиксом, проходит). Перечень берётся из реестра: при
подменённом в тесте наборе имён провайдера (`secret_env_names()`
возвращает новое имя) `targets.check` отказывает этому новому имени, а
имени, исключённому из подменённого набора, — нет (если оно не
`GITHUB_TOKEN`/`GH_TOKEN` и не названо другим провайдером).

AC-2. `targets.check` отказывает записи, у которой `test_profile.workdir`
(при `runner: pytest-own`) — абсолютный путь или путь с сегментом `..`
(`a/../b` — отказ); `workdir` `a..b`, где `..` — не сегмент, проходит.

AC-3. `targets.check` отказывает записи, у которой `test_profile.runner`
— значение, отличное от `pult-pytest` и `pytest-own`.

AC-4. `targets.check` отказывает записи, у которой задан `workdir` или
`env` при `runner: pult-pytest`, и такой же записи без подполя `runner`
(значение по умолчанию).

AC-5. Профиль без подполей `runner`, `workdir`, `env` проходит
`targets.check` и даёт `project_profile.Profile` с `runner` =
`"pult-pytest"`, `workdir` = `""` и пустым `env`; `Profile`, построенный
именованными аргументами без новых полей (как в
`tests/test_project_profile_gates.py:210`), строится без ошибки и несёт
те же значения по умолчанию.

AC-6. Профиль с `runner: pytest-own`, относительным `workdir` без сегмента
`..` (в том числе `a..b`) и
`env` — отображением строк без имён секретов — проходит `targets.check`,
и `project_profile.Profile` несёт заданные значения `runner`, `workdir`,
`env`. `targets.check` отказывает при `runner: pytest-own` записи, у
которой `env` — не отображение (строка, список), и записи, у которой
значение переменной `env` — не строка (int, bool, `None` после разбора
`yamlmini`); текст отказа называет `test_profile` и `env`.

AC-7. Фиксирующие тесты argv, `cwd` и окружения восьми мест запуска
зелёные на текущем коде этих мест, по путям команды требования 7:
оба пути (`command=None` и `command=[python3, -m, pytest]`) у
`acceptance.run`, `collect`, `run_repeat`; путь `command=None` и путь с
`command` через `acceptance.run_full_suite` у `_run_full_suite_now` (с
`observe` и без) и `_run_full_suite_to_log`; единственный сегодняшний
путь у `run_plank` и `two_sided._run_side`. argv и `cwd` сравниваются на
точное равенство с ожидаемыми значениями. Ожидаемые argv и `cwd` —
литералы теста; вычисляемые части ожидания — только интерпретатор
(`stack.pytest_python_executable()`) и временные каталоги теста.
Строить ожидание вызовом `acceptance._pytest_command` или
`acceptance._pytest_env` запрещено.
Окружение сравнивается как разница с `os.environ` пульта на момент
вызова, по значениям, и без удалённых переменных; набор добавленных и
изменённых переменных у каждого места — ровно такой:
- `acceptance.run`, `acceptance.collect`, `acceptance.run_repeat`,
  `acceptance.run_plank`, `acceptance._run_full_suite_now` (с `observe` и
  без) — `PYTHONPYCACHEPREFIX` = каталог вне `cwd` прогона
  (`orchestrator/acceptance.py:86`);
- `acceptance._run_full_suite_to_log` — `PYTHONPYCACHEPREFIX` = каталог
  вне `cwd` прогона и `PYTHONUNBUFFERED` = `"1"`
  (`orchestrator/acceptance.py:1372`);
- `two_sided._run_side` — `PYTHONPYCACHEPREFIX` = каталог вне `cwd`
  прогона, `REPORT_ENV` (`ARTEL_TWO_SIDED_REPORT`) = путь отчёта этого
  вызова, `PYTHONPATH` начинается с `plugin_dir`
  (`orchestrator/advance_gates/two_sided.py:230-232`).
`PYTHONUNBUFFERED` = `"1"` — только у `_run_full_suite_to_log`;
`REPORT_ENV` и `PYTHONPATH` — только у `two_sided._run_side`.

AC-8. Отказ `targets.check` для неверных `runner`, `workdir` и `env`
несёт в тексте `test_profile` и имя подполя;
`tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py` (случай
неизвестного подполя `runner` со значением `"x"`, строки 103, 151-152)
остаётся зелёным без правки.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `runner` становится известным подполем `test_profile` (`orchestrator/targets.py`) | Отказ `targets.check` неизвестному подполю `runner` со значением `"x"` с текстом, называющим `test_profile` и `runner` — `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:103`, `:151-152` | остаётся: `"x"` — неверное значение `runner`, отказ требования 2 называет `test_profile` и `runner` (требование 8) | `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:151-152` без правки; AC-3, AC-8 | ок |

## Не входит

- Правка `orchestrator/acceptance.py`, `orchestrator/advance_gates/two_sided.py`
  и модулей, вызывающих места запуска: потребители новых подполей —
  следующие части D0.
- Запись проекта sled в `targets.yaml` и любая правка `targets.yaml` —
  только чтение.
- Поле `sandbox` в `test_profile` не вводится.
- Правка `orchestrator/yamlmini.py`.
- Правка `orchestrator/providers/` — перечень `secret_env_names()`
  только читается.

## Материалы

- ТЗ: `tasks/01M52EEDEYV14658X8VFNHCW8K/TZ.md`; родитель —
  01M52CQB468758M2NAA15C15ZE; ADR-0023, вторая поправка 16.10.2026.
- Проверка профиля сейчас: `orchestrator/targets.py` — `PROFILE_FIELDS`,
  `PROFILE_OPTIONAL`, `_check_profile`, `_profile_value_error`.
- Перечень секретов провайдеров: `secret_env_names()` в
  `orchestrator/providers/base.py`, `claude.py`, `codex.py`.
- Места запуска: `orchestrator/acceptance.py` — `run`, `collect`,
  `run_repeat`, `run_plank`, `_run_full_suite_now`,
  `_run_full_suite_to_log`, флаг `observed_full_suite`;
  `orchestrator/advance_gates/two_sided.py::_run_side`.
- `yamlmini.mapping` уже разбирает блочное отображение третьего уровня
  вложенности (`test_profile.env`) — проверено разбором образца.
