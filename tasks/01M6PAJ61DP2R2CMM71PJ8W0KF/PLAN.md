---
task: 01M6PAJ61DP2R2CMM71PJ8W0KF
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Окружение роли и doctor для compose

## Подход
Требование 12 — без правок кода: `runner.py`, `runner.role_env` и
`stack.ROLE_ENV_ALLOWLIST` не трогаются; AC-1 держат планка и
долгоживущий `tests/test_01m6paj61dp2r2cmm71pj8w0kf_role_env_compose.py`.

Две строки `doctor` на общем вызове `docker`:

- `doctor/project_checks.py`: константы `DOCKER_CALL_TIMEOUT_SEC = 10` и
  `GROUP_GONE_PROBES = 100000` (читаются при каждом вызове через модуль);
  помощник `_docker_call(argv, env, cwd, timeout)` — `doctor.subprocess.Popen`
  с `start_new_session=True`, по пределу `os.killpg(<группа>, SIGKILL)`,
  сбор лидера `proc.wait()` и не больше `GROUP_GONE_PROBES` проб
  `os.killpg(<группа>, 0)` без пауз (`PermissionError` — группа есть,
  `ProcessLookupError` — нет; правило `liveness._group_exists`). Окружение —
  `acceptance.compose_env(profile, docker)` части 1 (у строки «забытые
  стенды» профиль `None`: `PATH` — каталог `docker` и `_OWN_SYSTEM_PATH_DIRS`;
  у строки записи — профиль компонента с `machine.path` в `env.PATH`).
- Строка записи `compose` — `compose_record_checks(name)`: одна строка
  `project-compose-<проект>` на проект с компонентом/`test_profile` раннера
  `compose` (`project_profile.component_profiles`); файлы клона,
  `docker compose -f <file> --env-file <template> config --services` в
  клоне, `docker compose version --short` ≥ 2.1.1; исход — худший.
  Регистрируется в `cli.all_checks` в цикле проектов.
- Строка «забытые стенды пульта» — `doctor/orphans.py`:
  `check_compose_stands(conn)` и `_fix_compose_stands(conn)`, экспорт в
  фасаде рядом с прочими именами `orphans`; строка `compose-stands`
  регистрируется в `all_checks` после `check_orphans` вне ветки годного
  `targets.load()`, починка — в блоке `--fix` `cmd_doctor`. Порядок отказов:
  процесс роли → слой не прочитан → нет `compose` → нет `docker` → адрес
  демона не `unix://` → `ps`/`network ls`. Разбор `Labels` — фрагмент без
  `=` приклеивается к значению предыдущей метки; форма имени
  `^artel-[0-9a-z]{26}-[0-9a-f]{8}$`; живость — pid жив и
  `doctor.process_start_time(pid) <= artel.run-started`, без хоста.
  `down` — `docker compose --project-name <имя> down --remove-orphans` в
  пустом `tempfile.mkdtemp()`, предел `config.COMPOSE_TEARDOWN_TIMEOUT_SEC`.

## Шаги
1. `project_checks.py`: константы, `_docker_call`, строка записи `compose`;
   регистрация в `cli.all_checks`.
2. `orphans.py`: строка «забытые стенды» и починка; экспорт в
   `doctor/__init__.py`; регистрация в `all_checks` и `cmd_doctor(fix=True)`.
3. Регенерация `docs/codebase-map.md`; прогон планки и затронутых тестов.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 12 | — (код не меняется; проверяют AC-1 планка и долгоживущий файл) |
| 13 | снято |
| 14 | 1 (вызов `docker`), 2 |
| 15 | 1 |
| 16 | 3 |
| 17 | планка и долгоживущие файлы test_author; свои тесты не нужны |

## Влияние на систему
Новые строки `doctor` только читают Docker; снимает стенды лишь `--fix` и
только стенды правильной формы с мёртвой разобранной тройкой меток.
`check_orphans` не меняется (строка вне её списка). Без проекта `compose`
строка — `skip` без вызова `docker`, починка при `conn=None` ничего не
делает — прежние тесты `doctor` (в т. ч. `test_doctor_closed_ref_fix.py`)
не затрагиваются. В процессе роли обе строки — `skip`. Откат — revert
merge-коммита.

## Проверка
- `plank-run 01M6PAJ61DP2R2CMM71PJ8W0KF`: 30 passed.
- Долгоживущие `tests/test_01m6paj61dp2r2cmm71pj8w0kf_*.py`: 26 passed.
- `tests/test_doctor*.py` (9 файлов): 194 passed; ещё 27 файлов `tests/`,
  зовущих `all_checks`/`cmd_doctor`/`project_checks`, и
  `test_codebase_map.py`: 369 passed.
- `docs/codebase-map.md` регенерирована.

## Риски
- На macOS группа исчезает не мгновенно — поэтому сбор лидера до проб и
  большое число проб; исчерпание — исход по пределу, без исключения.
