---
task: 01M6PAJ61D4PYAP79ADRPA6MWV
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Ядро раннера compose

## Подход
Раннер `compose` — ещё одна ветка узла прогона по отчёту
(`acceptance._report_run`): все места с отчётом (планка `run`/`collect`,
`run_plank`, `run_repeat`, полный набор, двусторонний прогон, гейт исходов)
уже сходятся в нём, поэтому ветка `_compose_report_run` закрывает их разом, а
вызывающим остаётся довести id задачи (`task_id`/`compose_task_id`).

Ключевые решения:
- **Запись** (`targets.py`): поля `COMPOSE_FIELDS` влиты в `PROFILE_FIELDS`
  (оттуда — и в `COMPONENT_FIELDS`), все необязательны в общем списке;
  правила раннера — один узел `_check_compose` для профиля и компонента
  (обязательные поля, `workdir`, `report: junit-xml`, запрет
  `install`/`tools`/`checks_local`/`env`, каталоги под левой частью
  монтирования, каталог планки после раскладки). `env` проверяется по
  разделу `description` до сведения (`_check_local_values`), у плоской
  записи — в `check` (`local=False`); после сведения у `compose` допустим
  только `PATH` из `machine.path`. Умолчание `command` — `_with_compose_command`
  рядом с `_with_long_lived_pairs` в `load()`; в проверках загрузки
  (`layers`, запрет повторов) — `_compose_fields`. `PROFILE_PROJECT_RUNNERS`
  (= `pytest-own` + `compose`) заменил сравнение с `pytest-own` там, где
  `compose` проходит те же проверки (`machine.path`, `workdir`/`env`,
  `project_profile.reported`, `test_integrity._own_profile`).
- **Прогон** (`acceptance.py`, секция «раннер `compose`»): порядок отказов
  до любого вызова `docker` — процесс роли (`runner.in_role_environment`),
  нет id задачи, `DOCKER_HOST` не `unix://`, нет `docker`, `workdir`, пути
  места вне монтирования, `git ls-files --error-unmatch` файла окружения,
  нет шаблона; затем `info/exclude` (`.artel-report`, файл окружения), копия
  шаблона, сокеты Docker (`DOCKER_HOST` либо `context inspect`, плюс
  `/var/run/docker.sock`), `config --format json`, отказы по собранной
  конфигурации (`_compose_config_refusal`), перекрытие (`_compose_override`)
  в файл временного каталога, `up -d --wait <зависимости>`, `run --rm -T -w`,
  итог — `outcome.parse_junit` по файлу отчёта под левой частью монтирования.
  Снятие стенда — в `finally` (`_compose_teardown`: `kill` на таймауте и
  исключении, затем `down -v --remove-orphans [--rmi local]`, общий предел;
  превышение — запись журнала задачи с именем проекта). Каждый вызов
  `docker` — `_compose_call` в своём сеансе с пределом и окружением
  `compose_env` (не `os.environ`).
- **Пределы**: предел места = переданный + `compose_up_down_sec` (иначе
  `config.COMPOSE_UP_DOWN_SEC`); `config`/`context inspect` — меньшее из
  `COMPOSE_CONFIG_TIMEOUT_SEC` и остатка, `up` — из `COMPOSE_UP_TIMEOUT_SEC` и
  остатка, `run` — остаток (≤ 0 — таймаут без `run`).
- **Ключ итога**: у `compose` в данные `_report_suite_result_key` входят
  поля `compose_*` (кроме `compose_up_down_sec`) и `COMPOSE_OVERRIDE_RULE`;
  у прочих раннеров данные ключа не меняются.
- **Раскладка планки** у `compose` — та же, что у `pytest-own` (`laid_own =
  own or _compose(...)` в `run`/`collect`/`run_plank`): планка попадает под
  `long_lived_dir`, то есть под монтирование.
- Имя проекта: `artel-<id строчными>-<8 hex>` (`os.urandom`), id — в
  `_report_run(task_id=…)`; у `run()`/`collect()` — имя каталога планки,
  у `full_suite` — передаётся только профилю `compose` (вызов прочих
  профилей прежний, его подменяют десятки тестов).

**ANSWER-1 (уточнение требований 3 и 7)** сверен с кодом, правок не
потребовал:
- требование 7 первично — `acceptance._compose_report_run` первой
  проверкой зовёт `runner.in_role_environment()` и отказывает
  `COMPOSE_ROLE_REFUSAL` до проверки id задачи, `DOCKER_HOST`, поиска
  `docker` и копии шаблона. Фоновый `suite-run` снимает только
  `ARTEL_ROLE` (`suite_run.py:925-926`), `HOME` дома роли остаётся —
  признак роли срабатывает, отказ тот же (AC-12, случай без `ARTEL_ROLE`);
- повтор с зерном, `suite-run`, `plank-run` долгоживущего файла работают
  вне процесса роли — по переданному id (AC-9 тесты гоняют без признака
  роли);
- помощника окружения Docker для роли нет: `acceptance.compose_env`
  строит окружение только из окружения пульта (требование 6), ветки
  окружения роли в нём нет; `runner.py` не менялся.
Перепроверка после ANSWER-1: три долгоживущих файла задачи — 134 passed,
1 skipped (AC-17, Docker на машине нет).

**ANSWER-3 (эскалация по `skipif` закрыта)**: Оператор поправил
`tests/test_01m6paj61d4pyap79adrpa6mwv_compose_docker.py:259` командой
`amend-tests` (5c6f5b7e6): причина пропуска — строковая константа, условие
`SKIP_REASON is not None` и тело теста прежние. Ветка задачи уже на этом
коммите; код не менялся. Перепроверка: 134 passed, 1 skipped.

Оценка SPEC ($60) совпадает с объёмом PLAN: 11 файлов зоны, расхождения нет.

## Шаги
1. `targets.py`, `project_profile.py`: вид раннера, поля, проверки записи,
   умолчание `command`, поля `Profile`, `reported` для `compose`.
2. `config.py`: `COMPOSE_UP_DOWN_SEC`, `COMPOSE_CONFIG_TIMEOUT_SEC`,
   `COMPOSE_UP_TIMEOUT_SEC`, `COMPOSE_TEARDOWN_TIMEOUT_SEC`.
3. `acceptance.py`: ветка `_compose_report_run`, публичные помощники
   (`find_docker`, `compose_env`, `compose_project_name`,
   `COMPOSE_PROJECT_PREFIX`, `COMPOSE_RUN_LABELS`), `task_id` в
   `_report_run`/`run_repeat`/`run_full_suite`/`run_plank`
   (`compose_task_id`) и внутренних вызовах, ключ итога.
4. Передача id: `advance_gates/outcome_integrity.py` (`_rerun(task_id=)`,
   оба `report_run`), `advance_gates/two_sided.py` (`run`/`_run_side`/
   `_run_side_report`), `advance_gates/acceptance.py` (`run_repeat`),
   `suite_run.py` (оба `run_full_suite`), `plank_run.py`
   (`compose_task_id` у долгоживущего файла), `test_integrity.py`
   (`_own_profile` и `two_sided.run(task_id=)`).
5. `docs/codebase-map.md` — `python3 scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 3, 4 |
| 4 | 3 |
| 5 | 3 |
| 6 | 3 |
| 7 | 3 |
| 8 | 3 |
| 9 | 2, 3 |
| 10 | 3 |
| 11 | 1, 3 (ветки прочих раннеров не тронуты; планка AC-16) |
| 12 | 5 |
| 13 | тесты test_author (долгоживущие + планка) |

Проверка: `tests/test_01m6paj61d4pyap79adrpa6mwv_compose_record.py` 57/57,
`…_compose_run.py` 72/72, `…_compose_docker.py` 5 passed + 1 skipped
(Docker на машине шага нет — именованная причина); `plank-run` — 8 passed
(AC-16 и места передачи id). Своих тестов сверх долгоживущих файлов задачи
не добавлено: AC-1…AC-17 ими покрыты целиком.

## Влияние на систему
- Прежние раннеры: ветка `compose` включается только по `runner: compose`;
  argv, окружение и ключ `pytest-own`/`pult-pytest` прежние (планка
  `test_prior_runners_unchanged.py` зелёная). Новые параметры (`task_id`,
  `compose_task_id`) необязательны; сигнатуры `report_run`, `run_repeat`,
  `run_full_suite`, `run_plank`, `two_sided.run`, `_rerun` расширены
  ключевыми параметрами со значением по умолчанию.
- `PROFILE_FIELDS` дополнен полями `compose_*`: перечень «(известны: …)» в
  тексте отказа неизвестного подполя стал длиннее (тексты тестами не
  сверяются). Текст отказа `machine.path` при чужом раннере прежний.
- Гейты, лимиты, инварианты не ослаблены: новые проверки только добавляют
  отказы (`compose`); граница гейта исходов `in_outcome_bounds` не
  менялась.
- Существующие тесты: прогнаны файлы профиля/записи, мест прогона,
  двустороннего прогона, гейта исходов, `plank-run`, `suite-run`, выкладки
  планки (вторая пачка из 10 файлов — 168 passed). Красный — только `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`
  (4 подслучая `two_sided._run_side`): тест ставит случайный PATH без
  `/usr/bin`, а git в шаге роли — обёртка `role_bin/git`, которой нужен
  `python3` (`exec: python3: not found`, код 127) → `git worktree add` не
  удаётся и pytest не зовётся. Воспроизведено вне теста
  (`gitcmd.in_repo` с PATH без `/usr/bin` → 127); от правки не зависит, в
  CI (настоящий git) не проявляется.
- Откат — revert коммита задачи; данных и схемы БД правка не меняет.

## Риски
- Утверждения о Docker CLI, не проверенные опытом (как и в SPEC): вывод
  `config --format json` как JSON, `context inspect --format
  '{{.Endpoints.docker.Host}}'`, `run -T`; прогон с настоящим Docker
  (`test_ac17_real_docker_compose_run`) на машине шага пропущен — его стоит
  прогнать Оператору на машине с Docker и образом `alpine:3`.
- Снятие группы процессов пульта сигналом извне стенд не снимает (SPEC,
  «Не входит»; строка `doctor` — часть 2).

## Предложения системе
- Окружение шага роли: тесты, подставляющие случайный PATH без системных
  каталогов (`test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`), краснеют в
  шаге из-за обёртки `role_bin/git` (ей нужен `python3` в PATH) — класс
  «тест зависит от того, что git — бинарь»; обёртке стоит звать
  интерпретатор абсолютным путём.
- Bash шага отклоняет `ls`, `cd …&&…` и `env PATH=…` — список файлов
  каталога документов задачи получить нечем, кроме чтения известных имён.

