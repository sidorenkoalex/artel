---
task: 01M6PAJ61D4PYAP79ADRPA6MWV
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Ядро раннера compose

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–13 → шаги 1–5 (13 — тесты test_author).
- Шаги — единицы размера MR (запись, константы, ветка прогона, передача id, карта); подход (одна ветка `_compose_report_run` в узле `_report_run`, через который уже идут все места с отчётом) с архитектурой не конфликтует.
- «Влияние на систему» = diff: изменены ровно 10 файлов зоны SPEC + `docs/codebase-map.md`; в `tests/` — только три долгоживущих файла задачи (под локом); существующие тесты не тронуты. Откат — revert, данных/схемы правка не меняет.
- ANSWER-1 (требование 7 первично), ANSWER-2/3 (причина `skipif` — строковая константа через `amend-tests` 5c6f5b7e6; условие и тело не менялись) учтены.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `PROFILE_RUNNER_COMPOSE` в `PROFILE_RUNNERS`; `COMPOSE_FIELDS` в `PROFILE_FIELDS`; `PROFILE_PROJECT_RUNNERS` заменил сравнение с `pytest-own` в `machine.path`, `workdir/env`, `reported`, `_own_profile`; умолчание `command` — `_with_compose_command` в `load()` рядом с `_with_long_lived_pairs`, в `layers`/запрете повторов — `_compose_fields` (targets.py:1215-1217). |
| 2 | OK | `_check_compose` (targets.py): обязательные поля, `workdir`, `report: junit-xml`, `install/tools/checks_local`, `env` (description до сведения — `_check_local_values`; плоская запись — `local=False`), каталоги под левой частью, планка без раскладки и `plank_layout`; вид `mount` — ровно одна пара, правая часть абсолютна. |
| 3 | OK | `find_docker` (`shutil.which`); имя `artel-<id строчными>-<os.urandom(4).hex()>` + проверка `[a-z0-9-]`; без `task_id` — `COMPOSE_NO_TASK_REFUSAL` до `docker`. Передача id: `run_repeat`, `_seed_repeats_escalate`, `run_full_suite`/`suite_run` (оба), `run_plank(compose_task_id)` с откатом на `task_id`, `plank_run.py:269`, `two_sided`, `outcome_integrity` (оба `report_run`, `_rerun` и его вызовы), `full_suite` (только у `compose`), `components_full_suite` → `full_suite` (outcome_integrity `_full_run`). Прочие вызовы `run_full_suite` (`notes.py`, `mutation_run.py`) идут без профиля/вне зоны. |
| 4 | OK | Порядок: `DOCKER_HOST` → `git ls-files --error-unmatch` → шаблон → `info/exclude` → копия; `config --format json` с `--project-name`/`--project-directory`/`-f`/`--env-file`, предел `COMPOSE_CONFIG_TIMEOUT_SEC`; перекрытие `_compose_override` (без `ports`, `internal: true` у всех сетей и `default`, метки) — файл во временном каталоге, стенд — только им. |
| 5 | OK | `_compose_config_refusal`: `network_mode`, `volumes_from`, `container_name`, `external`, чужое `name:` сети/тома (`<проект>2_db` не проходит), `driver_opts` у `local`/без драйвера, bind-источник/`secrets.file`/`configs.file` на литерал сокета или по `realpath` (`DOCKER_HOST`, иначе `context inspect`, плюс `/var/run/docker.sock`). `tcp://` — отказ до сборки. |
| 6 | OK | `compose_env`: ровно `PATH` (machine.path → каталог docker → `_OWN_SYSTEM_PATH_DIRS`, без повторов), `DOCKER_CONFIG` (иначе `<HOME>/.docker`), `DOCKER_HOST`/`LANG`/`LC_ALL` если заданы, `TMPDIR`; одно и то же для каждого вызова (`context`, `config`, `up`, `run`, `kill`, `down`). |
| 7 | OK | `runner.in_role_environment()` — первая проверка `_compose_report_run`, текст `COMPOSE_ROLE_REFUSAL` дословно; до любого `docker` и копии шаблона. |
| 8 | OK | `up -d --wait <depends_on>` только при зависимостях; провал `up` → отказ с выводом + `down`; `run --rm -T -w <образ workdir>`; отчёт `<left>/.artel-report/<прогон>.xml`, удаляется свой файл и пустой каталог; `finally` — `_compose_teardown` (`kill` на таймауте/исключении/остатке ≤ 0, затем `down -v --remove-orphans [--rmi local]`, общий предел `COMPOSE_TEARDOWN_TIMEOUT_SEC`, превышение — `store.journal` задачи с именем проекта). |
| 9 | OK | deadline = переданный предел + `compose_up_down_sec`/`COMPOSE_UP_DOWN_SEC`; `context`/`config` — min(константа, остаток); `up` — min(`COMPOSE_UP_TIMEOUT_SEC`, остаток); `run` — остаток, ≤ 0 → таймаут без `run`. Константы в `config.py`. |
| 10 | OK | `data["compose"]` (поля без `compose_up_down_sec` + `COMPOSE_OVERRIDE_RULE`) только у `compose`; `command` уже входит в ключ. |
| 11 | OK | Ветка `compose` включается только по `runner: compose`; новые параметры необязательны; данные ключа прочих раннеров прежние; планка `test_prior_runners_unchanged.py` зелёная. |
| 12 | OK | Карта регенерирована: сборка `render()` по коду ветки совпала с `docs/codebase-map.md` построчно без `built_at_sha` (14471 = 14471). |
| 13 | OK | Долгоживущие файлы: подменённый `docker` в PATH, `exec sleep` (`os.execv`), снятие групп в уборке, сокет-файл песочницы, `HOME`+метка, снят `ARTEL_ROLE`; тест с настоящим Docker — `skipif` с причиной-константой (ANSWER-3), проба 10 с, `pull_policy: never`. Группы планки/долгоживущих размечены. |

## Замечания
Замечаний blocker/major/minor к разработчику нет.

Наблюдения (не дефекты кода, замечаниями не заводятся):
- `orchestrator/acceptance.py::_docker_sockets` — при заданном `DOCKER_HOST=unix://…` `docker context inspect` не зовётся; при этом текущий контекст Docker CLI и есть `DOCKER_HOST`, так что множество сокетов то же. Контекст с не-`unix://` адресом (tcp/ssh) при не заданном `DOCKER_HOST` молча пропускается — SPEC отказа на этот случай не требует; Оператору стоит решить в части 2 (`doctor`), нужен ли он.
- `tests/test_01m6paj61d4pyap79adrpa6mwv_compose_run.py::test_ac4_config_call_env_copy_and_pult_file` — ответ `config` в `base_config` всегда объявляет сеть `default`, поэтому ветку `networks.setdefault("default", {})` в `_compose_override` тест не различает (часть заявки «неявная default открыта»). Поведенчески ветка почти нейтральна: `docker compose config` выводит `default`, когда её использует сервис. Тест под локом — правка только `amend-tests` Оператора, если сочтёт нужной.
- Утверждения о Docker CLI, не проверенные опытом (`config --format json`, `context inspect --format`, `run -T`, повторная интерполяция `$` в файле пульта при `up`/`run`), и `test_ac17_real_docker_compose_run` на машине шага пропущен (Docker нет) — стоит прогнать Оператору на машине с Docker и `alpine:3`, как и предлагает PLAN.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 замечаний не заведено, прошлых итераций нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6paj61d4pyap79adrpa6mwv_compose_record.py tests/test_01m6paj61d4pyap79adrpa6mwv_compose_run.py tests/test_01m6paj61d4pyap79adrpa6mwv_compose_docker.py` — 134 passed, 1 skipped (AC-17 с настоящим Docker: Docker на машине нет), 63 с.
- `artel.py plank-run 01M6PAJ61D4PYAP79ADRPA6MWV` — 8 passed, код выхода pytest 0 (`test_prior_runners_unchanged.py`, `test_task_id_call_sites.py`).
- Временная мутация 1: `_compose_teardown(..., kill=False, ...)` — красные `test_ac8_run_timeout_kills_then_downs`, `test_ac8_exception_inside_run_kills_then_downs`, `test_ac8_no_run_when_nothing_left_after_up` (3 failed); код возвращён.
- Временная мутация 2: `compose_env` возвращает `dict(os.environ, **env)` — красные оба `test_ac11_docker_env_exact_outside_role[bare|set]`; код возвращён, после возврата `-k "ac11 or ac8_run_timeout"` — 3 passed, `git status --short` пуст.
- Карта: `scripts/codebase_map.build_modules` + `render` в памяти по коду ветки против `docs/codebase-map.md` без строк `built_at_sha:` — совпадение (14471 строк).
- `grep` вызовов `report_run(`/`run_full_suite(`/`run_repeat(`/`run_plank(` по `orchestrator/`: все места `compose` передают id (см. требование 3); `_task_own_profile` берёт `compose` через `_reported` (запись `compose` обязана нести `report`).
- `git diff --stat 75ec08d4…HEAD`: 10 файлов `orchestrator/` + карта; в `tests/` вне трёх залоченных файлов изменений нет — существующие утверждения не тронуты.

## Предложения системе
- Пакет ревью: `scripts/codebase_map.py` не имеет режима проверки без записи (`--check`/`--stdout`) — ревьюверу, которому код править нельзя, свежесть карты приходится сверять импортом `render()` вручную.
- Bash шага требует подтверждения на `grep` с некоторыми аргументами (`'networks.setdefault(...)'`) и на `$`-подстановки — простые read-only проверки ревью упираются в запрос подтверждения, которого в шаге никто не даст.
