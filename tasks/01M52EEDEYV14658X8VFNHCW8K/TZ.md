---
task: 01M52EEDEYV14658X8VFNHCW8K
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: D0-1: профиль test_profile — подполя runner, workdir, env и фиксация мест запуска

Родительская задача: 01M52CQB468758M2NAA15C15ZE — D0: внешний доверенный проект без песочницы — профиль чужого стека и чистое окружение тестов
Зоны: orchestrator/targets.py, orchestrator/project_profile.py, tests/
Порядок: первая, без зависимостей
Рамка: $25

Основание — ADR-0023, вторая поправка 16.10.2026; часть 1 из 3 задачи
D0 (внешний доверенный проект без песочницы).

1. `test_profile` (`orchestrator/targets.py`) получает необязательные
   подполя; профиль без них остаётся правильным и ведёт себя как сейчас:
   `runner`: `pult-pytest` (по умолчанию) | `pytest-own`, иное — отказ;
   `workdir` — каталог прогона относительно корня репозитория,
   `targets.check` отказывает абсолютному пути и пути с `..`; `env` —
   блочное отображение строк (новый вид подполя `mapping`; `yamlmini` не
   меняется), `targets.check` отказывает имени из точного перечня секретов
   (`secret_env_names()` провайдеров, `GITHUB_TOKEN`, `GH_TOKEN`), сверка
   по точному имени. `workdir` и `env` допустимы только при
   `runner: pytest-own`: `targets.check` отказывает им при `pult-pytest`, в
   том числе при `runner` по умолчанию. Поле `sandbox` не вводится.
2. Подполя доходят до потребителей полями `project_profile.Profile`
   (`orchestrator/project_profile.py`); потребителей в этой части не
   меняем.
3. Тестами зафиксировать argv, `cwd` и окружение каждого из восьми мест
   запуска для артели (`acceptance.run`, `collect`, `run_repeat`,
   `run_plank`, `_run_full_suite_now` с `observe` и без, 
   `_run_full_suite_to_log`, `two_sided._run_side`) на текущем коде — по
   обоим путям команды: `command=None` и `command=[python3, -m, pytest]`
   (`targets.yaml:46`).

Критерии приёмки: `targets.check` отказывает `env` с именем секрета,
`workdir` с `..` или абсолютным путём, неизвестному `runner`, `workdir` или
`env` при `pult-pytest` и при `runner` по умолчанию; профиль без новых
подполей проходит и даёт `Profile` с `runner` = `pult-pytest`; фиксирующие
тесты мест запуска по обоим путям команды зелёные на текущем коде. Не
входит: правка `orchestrator/acceptance.py`, `two_sided.py` и вызывающих
модулей; запись sled в `targets.yaml` (только чтение).