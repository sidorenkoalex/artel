---
task: 01M6P22XBCQS49HE92YGAB25N9
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, orchestrator/project_profile.py, orchestrator/acceptance.py, orchestrator/advance_gates/two_sided.py, orchestrator/advance_gates/test_integrity.py, orchestrator/runner.py, orchestrator/doctor/project_checks.py, orchestrator/doctor/orphans.py, orchestrator/doctor/cli.py, orchestrator/config.py, docs/codebase-map.md, tests/
budget_usd: 85
---

# SPEC: Раннер тестов внешнего проекта в контейнере Docker Compose

## Контекст
Доверенный внешний проект, тесты которого требуют служб (СУБД, брокер,
кэш) и идут в контейнере сервиса Compose-файла проекта, под раннером
`pytest-own` не исполним: голый pytest на машине не видит служб, команда
`docker compose … run` в профиле пишет отчёт по пути машины, которого нет
в контейнере, свой `HOME` отрезает Docker от его конфигурации, службы
никто не поднимает и не снимает (ТЗ, факт 5). Поправка Оператора
05.11.2026 к ADR-0023 (77e9ca9ca) разрешает такому проекту раннер
`compose` с перекрытием пульта и доступ шага роли к Docker только при
этом профиле. Задача вводит раннер во все места прогона с отчётом
(`acceptance._report_run` и его потребители), в окружение шага роли и в
`doctor`.

Опыт 05.11 вне пульта (ТЗ, факт 6): `up -d --wait` — 6 с, сборка образа —
177 с, полный набор `-n 8` — 176 с; JUnit-отчёт под смонтированным
каталогом читается с машины, `classname` — от рабочего каталога
контейнера (= `workdir`) без перевода; `down -v --remove-orphans` — 1 с.

Второй вариант SPEC: учтены вердикт аудита (SPEC-AUDIT.md, 14
отклонений) и ответ Оператора ANSWER-1.md на вопросы 1–5. Утверждения о
Docker CLI и Compose, не проверенные опытом (в шаге роли программы
`docker` нет), помечены «опытом не проверено».

## Требования

### Часть 1 — ядро раннера

1. **Вид раннера и поля записи.** `runner: compose` входит в
   `targets.PROFILE_RUNNERS`, допустим в `test_profile` и в `components:`.
   Поля записи (подполя профиля и поля компонента, одни имена):
   - `compose_file` — путь Compose-файла в дереве (обязательно);
   - `compose_service` — имя сервиса тестов (обязательно);
   - `compose_env_file` — путь файла окружения Compose в дереве
     (обязательно);
   - `compose_env_template` — путь шаблона, из которого пульт копирует
     `compose_env_file` (обязательно);
   - `compose_mount` — ровно одна пара строкой
     `<каталог дерева>:<каталог в контейнере>`: слева относительный путь
     каталога (правило вида `dir`, `.` — корень дерева), справа абсолютный
     путь (обязательно);
   - `compose_up_down_sec` — слагаемое предела на подъём и снятие служб,
     целое > 0 (необязательно, требование 9);
   - `command` — команда pytest в контейнере; при `compose`
     необязательна, без неё — `["pytest"]`; у прочих раннеров
     обязательность `command` прежняя (`targets.py:57`).

   Поля `compose_*` при другом раннере — отказ загрузки с именем поля.
   `compose` проходит те же проверки и ветки, что `pytest-own`:
   `project_profile.reported`, `acceptance._own` (или его аналог для
   `compose`), `test_integrity._own_profile`, `workdir`, `machine.path`
   (`targets.py:755-773`).
2. **Проверка загрузки.** Отказ загрузки, текст которого называет поле:
   путь `compose_file`/`compose_env_file`/`compose_env_template`/левая
   часть `compose_mount` абсолютный или с `..`; правая часть
   `compose_mount` не абсолютна; нет `report: junit-xml`; есть `install`,
   `tools` или `checks_local`; есть `env` — проверяется по полю `env`
   раздела `description` (профиля или компонента) до сведения разделов,
   так как после сведения `machine.path` лежит в `env["PATH"]`
   (`targets.py:776-793`). `machine.path` при `compose` допустим (у
   компонента — по прежнему правилу единственного компонента) и задаёт
   только `PATH` вызова `docker` (требование 6), в контейнер не идёт.
3. **Поиск `docker` и прогон.** Программу `docker` пульт ищет по `PATH`
   вызывающего (`shutil.which`); не найдена — отказ запуска с именем
   `docker`. Идентификатор прогона `<прогон>` — 8 строчных
   шестнадцатеричных знаков, новый на каждый вызов места. Имя проекта
   Compose — `artel-<id задачи строчными>-<прогон>`, только `[a-z0-9-]`.
   Деревом прогона здесь и ниже названо дерево, в котором идёт место
   (рабочая копия, копия базы, дерево стороны `two_sided`/гейта исходов).
4. **Сборка конфигурации и перекрытие** (ADR-0023, поправка 05.11, п. 2).
   Перед сборкой пульт копирует `compose_env_template` в
   `compose_env_file` дерева прогона (перезапись на каждом прогоне).
   Сборка — `docker compose --project-name <имя> --project-directory
   <каталог compose_file в дереве прогона> -f <compose_file в дереве
   прогона> --env-file <compose_env_file в дереве прогона> config
   --format json` (вывод — JSON; опытом не проверено). В собранной
   конфигурации пульт снимает `ports` у каждого сервиса, ставит
   `internal: true` каждой сети, включая неявную `default` (нет в
   конфигурации — добавляет), ставит контейнерам и сетям метки живого
   прогона `artel.run-pid`, `artel.run-host`, `artel.run-started` (pid,
   хост и время старта процесса пульта, ведущего прогон, — тройка
   `lease.process_alive`) и пишет результат одним файлом во временный
   каталог прогона. Стенд поднимается только этим файлом: все команды
   стенда — `docker compose --project-name <имя> --project-directory
   <каталог compose_file в дереве прогона> -f <файл пульта> …`.
5. **Отказы запуска по собранной конфигурации** (проверяются по выводу
   `config`, не по исходному файлу; стенд не поднимается, `up`/`run` не
   зовутся), текст называет сервис, сеть или том:
   - сервис с `network_mode`;
   - сеть с `external: true`;
   - монтирование сокета Docker: bind-монтирование, чей источник после
     `realpath` равен `realpath` сокета Docker или является каталогом, его
     содержащим; сокет Docker — `realpath` пути `unix://` из `DOCKER_HOST`
     окружения вызова и `realpath` `/var/run/docker.sock`, если он есть;
   - `container_name` у любого сервиса — без условий;
   - явное `name:` сети или тома, не равное `<имя проекта>` и не
     начинающееся с `<имя проекта>_`.
   Compose-файл проекта пульт не правит.
6. **Окружение вызова `docker` вне процесса роли** (ANSWER-1, вопрос 1):
   ровно переменные `PATH`, `DOCKER_CONFIG`, `DOCKER_HOST` (только если
   задан в окружении пульта), `LANG`/`LC_ALL` (если заданы у пульта) и
   `TMPDIR`; `HOME` и прочие переменные пульта не передаются. `PATH` —
   каталоги `machine.path` записи (если задано), затем каталог найденной
   программы `docker` (без разрешения ссылки), затем
   `acceptance._OWN_SYSTEM_PATH_DIRS` (`acceptance.py:156`), без повторов;
   `PATH` вызывающего служит только для поиска `docker`. `DOCKER_CONFIG`
   — заданный у пульта, иначе `<дом Оператора>/.docker`. Подстановка
   `${…}` Compose видит только эти переменные; окружение pytest в
   контейнере — из Compose-файла и файла окружения проекта.
7. **Окружение вызова `docker` в процессе роли** (ANSWER-1, вопрос 3).
   Процесс роли распознаётся `runner.in_role_environment()`
   (`runner.py:1364-1381`). В нём `DOCKER_CONFIG` и `DOCKER_HOST` берутся
   из окружения процесса; нет любой из двух — отказ запуска с именем
   переменной, конфигурация Docker пульта не читается. Прочий состав —
   как в требовании 6.
8. **Жизненный цикл, отчёт и пути.**
   - Службы, от которых зависит сервис (`depends_on` в собранной
     конфигурации), — `up -d --wait <службы>`; зависимостей нет — `up` не
     зовётся. Провал `up` — отказ прогона с выводом Compose, исход тестов
     не засчитан.
   - Прогон — `run --rm -w <образ workdir> <сервис> <command> <цели>
     --junitxml <путь отчёта в контейнере> …`; образ `workdir` — его путь
     по `compose_mount`; `workdir` вне левой части `compose_mount` — отказ
     запуска.
   - Отчёт — `<каталог дерева>/.artel-report/<прогон>.xml` под левой
     частью `compose_mount`; pytest получает путь в контейнере, пульт
     читает файл с машины; итог — по отчёту; каталог `.artel-report`
     убирается после прогона. `.artel-report` и `compose_env_file` внесены
     в `info/exclude` дерева прогона (как в `acceptance._link_deps`).
   - Путь машины в аргументах места, лежащий под левой частью
     `compose_mount`, переводится в путь контейнера; не лежащий под ней —
     отказ запуска с именем пути.
   - После прогона — всегда `down -v --remove-orphans` с тем же именем
     проекта (у сервиса без `image:` — с `--rmi local`), в том числе по
     таймауту, отказу после сборки, исключению и снятию группы процессов.
   - Двусторонний прогон и гейт исходов для `compose` идут веткой отчёта
     (`_report_run`), без `-p <плагин пульта>` и `PYTHONPATH` пульта.
9. **Время.** Предел прогона места `compose` — прежний предел места плюс
   `compose_up_down_sec` записи, без него — `config.COMPOSE_UP_DOWN_SEC`
   (новая константа, 300 с: сборка образа 177 с, подъём 6 с, снятие 1 с —
   ТЗ, факт 6). Таймаут снимает и стенд (требование 8).
10. **Ключ итога.** Смена любого поля `compose_*` (кроме
    `compose_up_down_sec`), `command` или правила перекрытия меняет ключ
    `acceptance._report_suite_result_key`; правило перекрытия
    представлено в ключе константой модуля `acceptance`, которую меняет
    любая правка правила.
11. **Прежние раннеры.** У `pytest-own` и `pult-pytest` argv, окружение и
    ключ итога прогонов побайтно прежние.

### Часть 2 — окружение роли и `doctor`

12. **Каталог Docker задачи для шага роли** (ANSWER-1, вопрос 3, вариант
    Г). «Задача с профилем `compose`» — проект задачи несёт `runner:
    compose` в `test_profile` или хотя бы в одном компоненте
    (`project_profile.components`). На каждый шаг роли такой задачи пульт
    собирает каталог `<runner.COMPOSE_ROLE_DIR>/<id задачи>/`, где
    `runner.COMPOSE_ROLE_DIR` — константа модуля `runner`, равная
    `config.ROOT / ".artel" / "compose-role"` (`config.py` не правится);
    каталог не внутри рабочей копии задачи, не в доме роли и не в
    `.artel/projects/<имя>/tasks/`. Сборка — во временный каталог рядом с
    атомарной заменой прежнего. Содержимое ровно такое:
    - `bin/docker` — ссылка на программу `docker`, найденную по `PATH`
      пульта; других записей в `bin/` нет;
    - `config/config.json` — копия `config.json` из `DOCKER_CONFIG`
      пульта (требование 6) без ключей `credsStore`, `credHelpers`,
      `auths`, `currentContext`; файла нет у пульта — `{}`;
    - `config/cli-plugins/docker-compose` — ссылка на дополнение Compose,
      найденное первым из `<DOCKER_CONFIG пульта>/cli-plugins/docker-compose`
      и системных каталогов дополнений Docker; других записей нет.
    `docker` или дополнение не найдены — `OSError` с именем, как у
    отсутствующего инструмента манифеста (агент не запускается).
    Адрес службы — `DOCKER_HOST` пульта, если задан, иначе адрес текущего
    контекста Docker пульта из вывода `docker context inspect --format
    '{{.Endpoints.docker.Host}}'` (опытом не проверено).
13. **`runner.role_env` для задачи с профилем `compose`** дописывает в
    конец `PATH` роли каталог `bin/` требования 12 и ставит
    `DOCKER_CONFIG` — на `config/`, `DOCKER_HOST` — на адрес требования
    12. `stack.ROLE_ENV_ALLOWLIST` не меняется, перечень разрешённых
    команд роли не меняется. У прочих профилей, у артели, у вызова без
    `project`/`task_id` и при непрочитанной записи проекта (`TargetsError`)
    окружение роли побайтно прежнее, исключения нет.
14. **`doctor`: строка «забытые стенды пульта»** (`doctor/orphans.py`,
    регистрация и `--fix` — `doctor/cli.py`):
    - контейнеры и сети, у которых метка `com.docker.compose.project`
      начинается с `artel-`, а тройка меток `artel.run-*` отсутствует или
      по `lease.process_alive` мертва, — `warn` с именами; пульт читает их
      из `docker ps -a --filter label=com.docker.compose.project --format
      '{{json .}}'` и `docker network ls --filter
      label=com.docker.compose.project --format '{{json .}}'` (поля
      `Names`/`Name` и `Labels` — формат Docker); `--fix` зовёт
      `docker compose --project-name <имя> down -v --remove-orphans` на
      каждый такой проект (без `-f`; опытом не проверено); стенды живых
      прогонов не трогаются;
    - каталог `<runner.COMPOSE_ROLE_DIR>/<id>/`, задача которого не
      существует или в `done`/`killed`, — `warn` с путём; `--fix` удаляет;
      каталог живой задачи не трогается;
    - нет ни одного проекта с профилем `compose` — `skip` без вызова
      `docker`.
15. **`doctor`: строка проверки записи `compose`**
    (`doctor/project_checks.py`): `compose_file` и `compose_env_template`
    есть в клоне; сервис `compose_service` есть в выводе `docker compose
    -f <compose_file> --env-file <compose_env_template> config --services`
    в клоне; `docker compose version` отвечает и не ниже 2.1.1 (`up
    --wait`, ANSWER-1, вопрос 5); иначе `fail` с причиной, у версии — с
    найденной версией. Проект без `compose` — строки нет.
16. **Документация**: `docs/codebase-map.md` регенерирована в каждой
    части.
17. **Форма тестов** (ТЗ, «Критерии приёмки», «Безопасность тестов»).
    Обязательные тесты — без настоящего Docker: программа `docker`
    подменена исполнителем в каталоге `PATH` теста, который записывает
    argv и окружение, отвечает на `config`/`ps`/`network ls`/`version`/
    `context inspect` заданным текстом и пишет отчёт в смонтированный
    каталог дерева. Необязательные тесты с настоящим Docker пропускаются
    при его отсутствии с именованной причиной: прогон вымышленного
    Compose-файла с образом из локального кэша, без сети, с `down -v` в
    `finally`; `docker compose version` в окружении шага роли. Проекты —
    вымышленные во временной песочнице; `config.ROOT`, `DOCKER_CONFIG` и
    `runner.COMPOSE_ROLE_DIR` — каталоги песочницы; никогда — настоящий
    клон, настоящий локальный слой, настоящий `~/.docker`; в текстах
    тестов — ни имён, ни адресов реальных проектов.

## Критерии приёмки

AC-1. Запись с `runner: compose` и полями требования 1 загружается в `test_profile` и в `components:`; запись `compose` с `machine.path` загружается; без `command` команда в контейнере — `["pytest"]`.

AC-2. Отказ загрузки с именем поля: `compose` без `report: junit-xml`; путь `compose_file`, `compose_env_file`, `compose_env_template` или левая часть `compose_mount` абсолютный или с `..`; правая часть `compose_mount` не абсолютна; `compose` с `install`, `tools` или `checks_local`; `compose` с `env` в разделе `description`; поле `compose_*` при другом раннере. Профиль `pytest-own` без `command` по-прежнему отказ «нет подполя».

AC-3. Прогон планки профиля `compose`: argv прогона — `docker compose --project-name artel-<id строчными>-<8 hex> --project-directory <каталог compose_file в дереве прогона> -f <файл пульта> run --rm -w <образ workdir> <сервис> pytest <цели> --junitxml <путь в контейнере> …`; путь отчёта в контейнере соответствует `<каталог дерева>/.artel-report/<прогон>.xml` на машине; итог — по отчёту, прочитанному с машины.

AC-4. Сборка конфигурации — `config` с тем же `--project-name` и `--project-directory`, `-f <compose_file>` и `--env-file <compose_env_file>` дерева прогона; перед ней `compose_env_file` перезаписан копией `compose_env_template`. В файле пульта у каждой сети, включая `default`, — `internal: true`, ни у одного сервиса нет `ports`, у контейнеров и сетей — метки `artel.run-pid`, `artel.run-host`, `artel.run-started`.

AC-5. Отказ запуска с именем сервиса или сети, `up` и `run` не зовутся: собранная конфигурация (ответ `config`) несёт `network_mode` у сервиса; сеть `external: true`; bind-монтирование сокета Docker, в том числе источником-ссылкой на сокет и каталогом, содержащим сокет (сокет — путь `unix://` из `DOCKER_HOST` теста).

AC-6. Отказ запуска с именем: `container_name` у сервиса; `name:` сети, не равное имени проекта и без префикса `<имя проекта>_`; такое же `name:` тома; имя вида `<имя проекта>2_db`.

AC-7. Путь машины в аргументах места вне левой части `compose_mount` — отказ запуска с именем пути; путь под ней — в argv переведён в путь контейнера.

AC-8. `down -v --remove-orphans` с тем же именем проекта вызывается при зелёном исходе, красном исходе, таймауте и исключении; у сервиса без `image:` — с `--rmi local`. Провал `up` — отказ прогона с текстом вывода Compose, исход тестов не засчитан.

AC-9. Последовательные прогоны базы и головы одного места и одновременные прогоны разных процессов получают разные имена проекта Compose; имя — из id задачи строчными, только `[a-z0-9-]`.

AC-10. Двусторонний прогон (`two_sided`) и гейт исходов (`outcome_integrity`) для профиля `compose` идут веткой отчёта: в argv нет `-p <плагин пульта>`, в окружении нет `PYTHONPATH` пульта.

AC-11. Вне процесса роли окружение вызова `docker` — ровно `PATH`, `DOCKER_CONFIG`, `TMPDIR`, а также `DOCKER_HOST`, `LANG`, `LC_ALL`, только если заданы у пульта; `HOME` и прочих переменных пульта нет; `PATH` — ровно каталоги `machine.path`, каталог подменённого `docker` и `_OWN_SYSTEM_PATH_DIRS` в этом порядке, без каталогов `PATH` вызывающего; `DOCKER_CONFIG` без значения у пульта — `<HOME пульта>/.docker`.

AC-12. В процессе роли (`ARTEL_ROLE` задан, а также фоновый вызов без `ARTEL_ROLE` с домом роли в `HOME`) `DOCKER_CONFIG` и `DOCKER_HOST` вызова — из окружения процесса; без `DOCKER_CONFIG` или без `DOCKER_HOST` — отказ запуска с именем переменной, `docker` не вызывается, конфигурация Docker пульта не читается.

AC-13. После прогона `compose` каталога `.artel-report` под смонтированным каталогом нет; `.artel-report` и `compose_env_file` внесены в `info/exclude` дерева прогона.

AC-14. Предел времени прогона места `compose` больше предела того же места без стенда на `compose_up_down_sec` записи, без поля — на `config.COMPOSE_UP_DOWN_SEC`; по таймауту стенд снимается.

AC-15. Смена `compose_file`, `compose_service`, `compose_env_file`, `compose_env_template`, `compose_mount`, `command` или константы правила перекрытия меняет ключ `_report_suite_result_key`.

AC-16. Профили `pytest-own` и `pult-pytest`: argv, окружение и ключ итога прогонов побайтно прежние.

AC-17. `runner.role_env` для задачи с профилем `compose` (в `test_profile` или в одном из компонентов): последний элемент `PATH` — `<COMPOSE_ROLE_DIR>/<id>/bin`, в нём ровно одна запись — ссылка `docker` на найденную программу; `DOCKER_CONFIG` — `<…>/<id>/config`, в `config.json` нет ключей `credsStore`, `credHelpers`, `auths`, `currentContext`, прочие ключи копии пульта на месте; в `config/cli-plugins/` ровно одна запись — ссылка `docker-compose`; `DOCKER_HOST` — значение пульта, без него — ответ подменённого `docker context inspect`.

AC-18. Повторная сборка каталога задачи убирает посторонние записи, подложенные в `bin/` и `cli-plugins/` после прошлой сборки; без найденного `docker` или дополнения Compose `role_env` поднимает `OSError` с именем.

AC-19. У `pytest-own`, `pult-pytest`, артели, вызова без проекта и при непрочитанной записи проекта окружение `role_env` побайтно прежнее, исключения нет, каталог задачи не создаётся; `stack.ROLE_ENV_ALLOWLIST` не изменён.

AC-20. `doctor`, строка «забытые стенды пульта»: контейнеры и сети `artel-*` без меток или с мёртвой тройкой — `warn` с именами (ответ `docker ps`/`docker network ls` подменён); `--fix` зовёт `down -v --remove-orphans` с их именем проекта и не зовёт для стенда живого прогона; каталог `COMPOSE_ROLE_DIR/<id>` задачи в `done`/`killed` или без строки — `warn` с путём, `--fix` удаляет, каталог живой задачи на месте; без проекта `compose` — `skip`, `docker` не вызван.

AC-21. `doctor`, строка записи `compose`: нет `compose_file` или `compose_env_template` в клоне — `fail`; сервиса нет в ответе `config --services` — `fail` с именем сервиса; `docker compose version` не отвечает или ниже 2.1.1 (например, 2.0.1) — `fail` с найденной версией; 2.1.1 и выше — не `fail`.

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны — 12 (порог 5); критериев приёмки —
21 (порог 10); `budget_usd` $85 ≥ $30; зона задевает песочницу роли
(`runner.role_env`).

Предложение — **нарезка на 2 части** по границам зон:

1. «Ядро раннера `compose`» (требования 1–11, 16, 17; AC-1…AC-16) —
   запись, перекрытие, отказы, argv, отчёт, жизненный цикл, окружение
   вызова Docker вне и внутри процесса роли, метки живого прогона, ключ,
   время. Самостоятельно мержима: без профиля `compose` в `targets.yaml`
   поведение пульта побайтно прежнее (AC-16), раннер проверяется
   подменой `docker`. После неё — только неполнота: из шага роли
   проекта `compose` команды прогона пульта откажут «нет DOCKER_CONFIG»
   (требование 7), гейты пульта вне роли работают.
2. «Окружение роли и `doctor` для `compose`» (требования 12–17;
   AC-17…AC-21) — опирается на признак профиля, поиск `docker`,
   окружение вызова и метки части 1.

Альтернатива — монолит в рамке $85; решение на гейте SPEC за Оператором.

## Деление

### Ядро раннера compose

Зоны: orchestrator/targets.py, orchestrator/project_profile.py, orchestrator/acceptance.py, orchestrator/advance_gates/two_sided.py, orchestrator/advance_gates/test_integrity.py, orchestrator/config.py, docs/codebase-map.md, tests/
Порядок: первая, без зависимостей
Рамка: $60

Ввести вид раннера `runner: compose` для доверенного внешнего проекта
(ADR-0023, поправка 05.11.2026, пп. 1–2): тесты исполняются в контейнере
сервиса Compose-файла проекта, стенд поднимается на каждый прогон и
всегда снимается. Требования 1–11, 16, 17 и критерии AC-1…AC-16 SPEC
01M6P22XBCQS49HE92YGAB25N9 (с ответом Оператора ANSWER-1.md, вопросы 1,
2, 4, 5 и часть вопроса 3 о процессе роли) — переносятся дословно.
Только чтение: `orchestrator/suite_run.py`, `orchestrator/mutation_run.py`,
`orchestrator/advance_gates/outcome_integrity.py`,
`orchestrator/reporters/outcome.py`, `orchestrator/fsm_merge_gate.py`,
`orchestrator/stack.py`, `orchestrator/runner.py` (`in_role_environment`
— вызывается, не правится). Не входит: окружение шага роли и `doctor`
(часть 2), сборка и кэш образов, `mutation_run` в контейнере, правки
ADR-0023/0026, раннеры не на pytest, недоверенные проекты (D1б).
Существующий тест краснеет — эскалация с именем теста, без правки.

### Окружение роли и doctor для compose

Зоны: orchestrator/runner.py, orchestrator/doctor/project_checks.py, orchestrator/doctor/orphans.py, orchestrator/doctor/cli.py, docs/codebase-map.md, tests/
Порядок: после части 1
Рамка: $30

Опирается на раннер `compose` части 1 (ADR-0023, поправка 05.11.2026,
пп. 3–4; ANSWER-1.md, вопрос 3, вариант Г; вопрос 5). Требования 12–17 и
критерии AC-17…AC-21 SPEC 01M6P22XBCQS49HE92YGAB25N9 — переносятся
дословно. Поиск `docker`, окружение вызова, имя проекта и метки живого
прогона — из `orchestrator/acceptance.py` части 1, только чтение.
Только чтение: `orchestrator/stack.py`, `orchestrator/acceptance.py`.
Существующий тест краснеет — эскалация с именем теста, без правки.

## Не входит

- Сборка и кэш образов (сборку при необходимости делает Compose); образы
  закрытых реестров из шага роли не скачиваются — принятое Оператором
  следствие ANSWER-1, вопрос 3.
- Мутационный прогон в контейнере (`orchestrator/mutation_run.py`):
  `mutation-run` зовётся только из CLI (`orchestrator/artel.py:2782`), ни
  один гейт его не зовёт, записи с раннером не по умолчанию он отказывает
  (`mutation_run.py:385-389`) — гейты задачи исполнимы, эскалация ТЗ по
  этому пункту не нужна.
- Правки ADR-0023 и ADR-0026 (состав полей записи в ADR-0026 п. 1) —
  поправкой Оператора отдельно.
- Раннеры не на pytest; недоверенные проекты (D1б).
- Правка файлов «только чтение» ТЗ: `orchestrator/suite_run.py`,
  `orchestrator/mutation_run.py`,
  `orchestrator/advance_gates/outcome_integrity.py`,
  `orchestrator/reporters/outcome.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/stack.py`, `docs/adr/0023-*.md`, `docs/adr/0026-*.md`.
  `runner.py` правится только в `role_env` и рядом с ним (константа
  `COMPOSE_ROLE_DIR`, сборка каталога задачи).
- Зелёность прежних тестов раннеров и всего `tests/` без правки — её
  держит пульт; существующий тест краснеет — эскалация с именем теста,
  без правки. Раздела «Меняемое поведение» нет: смена ожиданий
  существующих тестов не заявлена.

## Материалы

- ТЗ: `tasks/01M6P22XBCQS49HE92YGAB25N9/TZ.md` (факты 1–6).
- Ответ Оператора: `tasks/01M6P22XBCQS49HE92YGAB25N9/ANSWER-1.md`
  (вопросы 1–5, матрица неослабления). Решения и их проверка:
  вопрос 1 (`PATH` и состав окружения вызова) — AC-11; вопрос 2
  (`command`, `env`, `machine.path`) — AC-1, AC-2; вопрос 3 (вариант Г) —
  AC-12, AC-17…AC-20; вопрос 4 (`container_name`, `name:`) — AC-6;
  вопрос 5 (2.1.1) — AC-21. Все — против дублёров песочницы (подменённый
  `docker`, временные `config.ROOT`, `DOCKER_CONFIG`, `COMPOSE_ROLE_DIR`).
- Отступления от буквы ТЗ, принятые Оператором: окружение вызова несёт
  `PATH`/`LANG`/`LC_ALL`/`TMPDIR` (ТЗ, требование 5); `env` при `compose`
  — отказ (ТЗ, требование 1); в процессе роли — каталог задачи вместо
  каталога `docker` и `DOCKER_HOST` вместо контекста (ТЗ, требования
  5–6); четвёртая причина отказа (ТЗ, требование 2); порог 2.1.1 (ТЗ,
  требование 9).
- Аудит: `tasks/01M6P22XBCQS49HE92YGAB25N9/SPEC-AUDIT.md` — В0.1 →
  требование 1; В0.2 → требования 3, 17; В0.3/Г2 → требования 3, 4, 14
  (метки — в части 1); А1 → требования 3, 4; Б1 → AC-9; Б2/Е2 →
  требования 4, 5; Е1, Е3 → требование 5; Г4 → требование 13; матрица
  doctor → требование 14 (`skip` без проекта `compose`).
- ADR-0023, третья поправка 05.11.2026 (коммит 77e9ca9ca).
- Якоря: `orchestrator/acceptance.py` — `_own` :121, `_OWN_SYSTEM_PATH_DIRS`
  :156, `_own_path` :159, `_own_env` :189, `_link_deps` :583, `_report_env`
  :626, `_report_argv` :736, `_report_run` :806, `_report_suite_result_key`
  :3069; `orchestrator/runner.py` — `_allowlisted_env` :1186, `role_env`
  :1246, `in_role_environment` :1364; `orchestrator/targets.py` —
  `PROFILE_FIELDS` :56, `PROFILE_RUNNERS` :83, `PROFILE_OWN_RUNNER_ONLY`
  :85, `machine.path` :755-773, `_with_env` :776, подполя :1096-1103,
  компонент :1258-1265; `orchestrator/lease.py` — `process_alive` :399.
