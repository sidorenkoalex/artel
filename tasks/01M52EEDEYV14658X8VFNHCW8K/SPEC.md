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
   `targets.check` отказывает абсолютному пути и пути, содержащему `..`.
4. `env` — блочное отображение строк (новый вид подполя `mapping` в
   проверке профиля; `orchestrator/yamlmini.py` не меняется).
   `targets.check` отказывает имени переменной из точного перечня
   секретов: имена `secret_env_names()` провайдеров
   (`orchestrator/providers/`), `GITHUB_TOKEN`, `GH_TOKEN`. Сверка — по
   точному имени.
5. `workdir` и `env` допустимы только при `runner: pytest-own`:
   `targets.check` отказывает им при `runner: pult-pytest`, в том числе
   когда `runner` не задан (значение по умолчанию).
6. Подполя `runner`, `workdir`, `env` доходят до потребителей полями
   `project_profile.Profile` (`orchestrator/project_profile.py`);
   при отсутствии подполя `runner` поле `Profile.runner` равно
   `pult-pytest`. Потребителей в этой части не меняют.
7. Тестами в `tests/` зафиксированы argv, `cwd` и окружение каждого из
   восьми мест запуска тестов для артели на текущем коде:
   `acceptance.run`, `acceptance.collect`, `acceptance.run_repeat`,
   `acceptance.run_plank`, `acceptance._run_full_suite_now` с `observe` и
   без него, `acceptance._run_full_suite_to_log`, `two_sided._run_side` —
   по обоим путям команды: `command=None` и
   `command=[python3, -m, pytest]` (профиль артели, `targets.yaml:46`).

## Критерии приёмки

AC-1. `targets.check` отказывает записи, у которой `test_profile.env`
(при `runner: pytest-own`) содержит имя из перечня секретов — любое из
`secret_env_names()` провайдеров, `GITHUB_TOKEN`, `GH_TOKEN`; сверка идёт
по точному имени.

AC-2. `targets.check` отказывает записи, у которой `test_profile.workdir`
(при `runner: pytest-own`) — абсолютный путь или путь, содержащий `..`.

AC-3. `targets.check` отказывает записи, у которой `test_profile.runner`
— значение, отличное от `pult-pytest` и `pytest-own`.

AC-4. `targets.check` отказывает записи, у которой задан `workdir` или
`env` при `runner: pult-pytest`, и такой же записи без подполя `runner`
(значение по умолчанию).

AC-5. Профиль без подполей `runner`, `workdir`, `env` проходит
`targets.check` и даёт `project_profile.Profile` с `runner` =
`pult-pytest`.

AC-6. Профиль с `runner: pytest-own`, относительным `workdir` без `..` и
`env` из строк без имён секретов проходит `targets.check`, и
`project_profile.Profile` несёт заданные значения `runner`, `workdir`,
`env`.

AC-7. Фиксирующие тесты argv, `cwd` и окружения восьми мест запуска
(`acceptance.run`, `collect`, `run_repeat`, `run_plank`,
`_run_full_suite_now` с `observe` и без, `_run_full_suite_to_log`,
`two_sided._run_side`) по обоим путям команды (`command=None` и
`command=[python3, -m, pytest]`) зелёные на текущем коде этих мест.

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
