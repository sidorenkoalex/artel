---
task: 01M51YKZNES22DZQY13D3QKF89
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/sandbox.py, orchestrator/acceptance.py, orchestrator/targets.py, orchestrator/config.py, orchestrator/project_profile.py, orchestrator/fsm_autogate.py, orchestrator/fsm.py, orchestrator/doctor/, tests/
budget_usd: 60
---

# SPEC: D1а: код проекта в одноразовом контейнере Docker (круг 2)

## Контекст
Основание — ADR-0023, «Поправка 16.10.2026: механизм — контейнер Docker»
(пункты 1–3, 5, 7; пункт 6 — задача D2, пункт 4 — задача D1б). Сейчас пульт
исполняет код проекта на хосте с полным окружением Оператора: `_pytest_env`
(`orchestrator/acceptance.py:69-89`) копирует `os.environ` целиком, а
`_pytest_command` (`acceptance.py:35-65`) всегда ставит интерпретатор venv
пульта и `-p timeout`. Полный набор жёстко берёт `<корень>/tests` (`:1172`)
и дописывает `-n … -p xdist` (`:1176`) — у внешнего проекта (sled: тесты в
`backend/tests`, без `pytest-timeout`/`pytest-xdist`) это не работает.
`test_profile.install` (`orchestrator/targets.py:41-53`) описан, но не
исполняется; поля `sandbox` в проверке нет. Семь мест запуска:
`acceptance.py:448` (`run`), `:556` (`collect`), `:665` (`run_repeat`), `:932`
(`run_plank`), `:1324` и `:1345` (`_run_full_suite_now` с наблюдением и без),
`:1373` (`_run_full_suite_to_log`).

Автогейт приёмки (`fsm_autogate.py:326`) и `approve` на acceptance
(`fsm.py:1294`) зовут `acceptance.acceptance_suite`, а тот —
`full_suite(root, task_id)` без команды профиля (`acceptance.py:1847-1848`);
гейт мержа (`fsm_merge_gate.py:962-967`) передаёт в `full_suite` только
`command` (`docs/backlog.md:185`, строка 07.10). Правка п.6 по существу
ложится в `acceptance.py`.

Решения Оператора (ANSWER-1, 16.10.2026, вариант A по всем вопросам):
носитель профиля — `project_profile.Profile` (файл в зонах), вызывающие места
запуска не меняются, проект и задача выводятся внутри `acceptance.py`; гейт
мержа входит в п.6 без правки `fsm_merge_gate.py`; `image` обязателен только
при `sandbox: required` и наличии `test_profile`; фикстуры `tests/` получают
`sandbox: off` без смены утверждений; том кэша и переменные кэша входят в
контейнер прогона уже в первой части; «полный набор зелёный» держит пульт.

## Требования

1. Запись проекта несёт поле `sandbox` со значениями `required | off`;
   отсутствие поля означает `required` для любого проекта, без исключения по
   имени; иное значение — отказ `targets.check` с названием записи и поля.
   У артели (`sandbox: off`) ни один путь запуска не меняется: до правки
   argv, `cwd` и окружение каждого из семи мест запуска для артели
   зафиксированы тестами и остаются неизменными.
2. Подполя `test_profile` (все необязательные, профиль артели без них
   остаётся правильным):
   - `runner`: `pult-pytest` (по умолчанию, сегодняшнее поведение) |
     `pytest-own` (команда профиля как есть: без интерпретатора пульта,
     `-p timeout` и `-n/-p xdist`; пульт по-прежнему дописывает свои
     аргументы гейтов — `--collect-only -q`, `--junitxml`,
     `-o junit_logging=system-out`, `-p no:cacheprovider`);
   - `workdir`: каталог прогона относительно корня репозитория; после
     `realpath` обязан остаться внутри рабочей копии — и в проверке записи,
     и в момент прогона на самой рабочей копии (симлинк из репозитория
     проекта, уводящий наружу, — именованный отказ прогона);
   - `env`: блочное отображение строк (новый вид `mapping`; `yamlmini` не
     меняется); имена из точного перечня секретов (`secret_env_names`
     провайдеров, `GITHUB_TOKEN`, `GH_TOKEN`) — отказ проверки, сверка по
     точному имени, не по подстроке;
   - `image`: имя образа Docker с тегом; обязательно при `sandbox: required`
     у записи с `test_profile`; запись без `test_profile` проверку проходит
     без `image`.
   Полный набор при `pytest-own` берёт каталог из `workdir` и
   `long_lived_dir`, а не `<корень>/tests`. Новые подполя доходят до
   потребителей через `project_profile.Profile` (поля `runner`, `workdir`,
   `env`, `image`, `sandbox`) — единый источник профиля; чтение
   `targets.target()` в обход `project_profile` не допускается.
3. Модуль `orchestrator/sandbox.py` — одна функция исполнения кода проекта.
   Проверка `sandbox: required` — первое условие внутри каждой из семи
   функций запуска; при `off` — прежний код без изменений. Сигнатуры функций
   запуска и их вызывающие (`pull.py`, `plank_run.py`, `amend.py`,
   `advance_gates/acceptance.py`, `advance_gates/tests_writing.py`,
   `suite_run.py`, `notes.py`, `fsm_merge_gate.py`) не меняются. Проект и
   задачу функции запуска выводят сами: точечные — из `cwd` по раскладке
   `.artel/projects/<проект>/worktrees/<id>` (`workspace.path`), полный
   набор — из своего `task_id`. `cwd`, не заданный или лежащий вне области
   проектов `.artel/projects/`, — путь артели, как сейчас. `cwd` внутри
   области проекта, но не рабочая копия задачи по раскладке, у проекта с
   `sandbox: required` — именованный отказ, прогона на хосте нет. Контейнер
   запускается так:
   - `docker run --rm --name artel-<проект>-<задача или run>-<случайный суффикс>`;
   - `--network none`;
   - `--user <uid>:<gid>` Оператора, `--cap-drop ALL`,
     `--security-opt no-new-privileges`;
   - лимиты памяти и процессора — константы `config.py`;
   - рабочая копия монтируется по тому же абсолютному пути на запись; `.git`
     клона проекта — по тому же пути только на чтение; каталог отчётов
     прогона (`--junitxml`, журнал) — по тому же пути на запись; именованный
     том кэша `artel-<проект>-cache`; других монтирований нет;
   - окружение — только `test_profile.env`, `HOME=/tmp`,
     `PYTHONPYCACHEPREFIX` во временный каталог контейнера, `XDG_CACHE_HOME`
     и `UV_CACHE_DIR` (путь в томе кэша); каждая переменная передаётся
     формой `-e ИМЯ=значение`; `-e ИМЯ` без значения и `--env-file` не
     используются; переменные окружения пульта не передаются;
   - рабочий каталог — `workdir`;
   - иных флагов `docker run`, кроме перечисленных, нет (в том числе
     `--privileged`, `--pid`/`--ipc host`, повторного `--network`,
     `--volumes-from`, `--env-file`).
   Сокет Docker, `~/.ssh`, связка ключей, токены, БД и журналы пульта в
   контейнер не попадают.
4. По таймауту и на любом исключении контейнер останавливается командой
   `docker kill <имя>`, затем пульт убеждается, что контейнера нет. Ошибка
   самого Docker (демон недоступен, нет образа, коды выхода `docker run`
   125–127) — именованный инфраструктурный отказ, а не «красные тесты»;
   прогон на хосте вместо контейнера запрещён (fail-closed, ADR-0002). Разбор
   вывода, наблюдение, замок полных прогонов машины и предел по профилю
   работают как сейчас.
5. Перед прогоном при `sandbox: required` и непустом `install`: если хеш
   файлов блокировки в `workdir` изменился с прошлой успешной установки (хеш
   хранится в области проекта `.artel/projects/<имя>/`), пульт исполняет
   `install` отдельным одноразовым контейнером с тем же образом и
   монтированиями, но с сетью по умолчанию. Кэш пакетов — том
   `artel-<проект>-cache` (требование 3), смонтированный в установку и в
   прогоны; путь задаётся переменными `XDG_CACHE_HOME` и `UV_CACHE_DIR`. Сбой
   установки — именованный отказ прогона.
6. Один источник команды профиля: автогейт приёмки, `approve` на acceptance
   и гейт мержа берут команду, `runner` и `workdir` профиля проекта задачи —
   тем же путём, что `suite-run`, `plank-run`, `preflight`,
   `acceptance-dry-run`: `full_suite(root, task_id)` сам берёт их из профиля
   проекта задачи по `task_id`. `fsm_merge_gate.py` не правится;
   `fsm_autogate.py` и `fsm.py` — только если правки в `acceptance.py` для
   этого недостаточно.
7. `doctor` для проектов с `sandbox: required` проверяет: демон Docker
   отвечает; образ `image` есть локально (при отсутствии печатает команду
   сборки); живая проба — одноразовый контейнер проекта не открывает внешний
   адрес и не видит переменных пульта. Для `sandbox: off` проверки не
   выполняются и запуск не блокируют.
8. Тесты в `tests/` детерминированы и не требуют Docker: вместо `docker` —
   подставной исполняемый файл, записывающий argv и код выхода. Живой запуск
   с настоящим Docker — проба `doctor` и ручной критерий Оператора в PLAN,
   не тест набора.
9. Фикстуры `tests/` (решение Оператора, ANSWER-1, ответ 3). Записи
   target'ов с `test_profile` во входных строках фикстур получают
   `sandbox: off`: записи артели — как в боевом `targets.yaml:43`, записи
   внешних проектов — тоже `off`, путь `required` покрывают новые тесты с
   подставным `docker` (требование 8). Общий шаблон записи
   `_PROJECT_TARGET_ENTRY` в `tests/sandbox.py` (на нём `artel_target_entry`,
   `declared_without_profile` и запись внешнего проекта `make_project_repo`)
   получает `sandbox: off`. Утверждения существующих тестов не меняются —
   меняются только входные строки фикстур; `base_entry` в
   `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:31-34` (запись без
   профиля) не правится. Перечень файлов, в которых сегодня есть запись с
   `test_profile:` без `sandbox` (сверено по коду main): `tests/sandbox.py`,
   `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`,
   `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`,
   `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`,
   `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`,
   `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`,
   `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`,
   `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`,
   `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`,
   `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py`,
   `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`,
   `tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py`,
   `tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py`,
   `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`,
   `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`,
   `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`,
   `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`,
   `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`,
   `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`,
   `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`,
   `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`,
   `tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py`,
   `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`,
   `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`,
   `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`,
   `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`,
   `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`,
   `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`,
   `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`,
   `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`,
   `tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py`,
   `tests/test_full_suite_profile_timeout.py`, `tests/test_invariants.py`,
   `tests/test_project_profile_gates.py`, `tests/test_sandbox.py`. Файл,
   берущий запись из `tests/sandbox.py` (`ARTEL_TEST_PROFILE`/
   `artel_target_entry`), правится только если пишет `test_profile` сам.
   Ослабление, которое это решение принимает: сквозной сценарий внешнего
   проекта (`tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py:346-474`)
   идёт путём `off`; путь `required` проверяется модульно новыми тестами с
   подставным `docker`, не сквозным тестом. Мандата на ослабление тестов
   нет: если гейт неослабления отметит правку фикстур, решение — на гейте.

## Критерии приёмки

AC-1. `targets.check` отказывает записи с `sandbox`, отличным от `required`
и `off`, называя запись и поле; запись без поля `sandbox` трактуется как
`required` для любого имени проекта.

AC-2. Для артели (`sandbox: off`) argv, `cwd` и окружение каждого из семи
мест запуска (`run`, `collect`, `run_repeat`, `run_plank`,
`_run_full_suite_now` с наблюдением и без, `_run_full_suite_to_log`)
совпадают с зафиксированными до правки; `docker` не запускается.

AC-3. `targets.check` отказывает: `workdir`, выходящему после `realpath` за
рабочую копию; `env` с именем из точного перечня секретов (`secret_env_names`
провайдеров, `GITHUB_TOKEN`, `GH_TOKEN`) — при этом имя, лишь содержащее
такое имя подстрокой, не отказывается; записи с `sandbox: required` и
`test_profile` без `image`. Запись с `sandbox: required` без `test_profile`
проходит проверку без `image`. Профиль артели без новых подполей проверку
проходит.

AC-4. При `sandbox: required` `workdir`, который в рабочей копии в момент
прогона после `realpath` уходит за её пределы (симлинк), даёт именованный
отказ прогона: ни `docker run`, ни pytest на хосте не запускаются.

AC-5. При `sandbox: required` функции запуска определяют проект и задачу
без смены сигнатур: точечные — из `cwd` по раскладке
`.artel/projects/<проект>/worktrees/<id>`, полный набор — из `task_id`; имя
контейнера — `artel-<проект>-<задача или run>-<суффикс>`. `cwd` внутри
области проекта с `required`, не являющийся рабочей копией задачи по
раскладке, — именованный отказ без `docker run` и без pytest на хосте; `cwd`
вне области проектов идёт путём артели, как сейчас.

AC-6. При `runner: pytest-own` argv прогона — команда профиля без
интерпретатора пульта, без `-p timeout` и `-n/-p xdist`, с аргументами гейтов
пульта (`--collect-only -q`, `--junitxml`, `-o junit_logging=system-out`,
`-p no:cacheprovider`) по месту запуска; без `runner` поведение равно
`pult-pytest`.

AC-7. При `sandbox: required` флаги `docker run` в argv подставного `docker`
— ровно перечень требования 3: `--rm`, `--name artel-<проект>-<задача или
run>-<суффикс>`, `--network none` (один раз), `--user <uid>:<gid>`,
`--cap-drop ALL`, `--security-opt no-new-privileges`, лимиты памяти и
процессора из констант `config.py`, рабочий каталог `workdir`, монтирования
AC-8 и переменные AC-9; любого иного флага (`--privileged`, `--pid`/`--ipc
host`, повторного `--network`, `--volumes-from`, `--env-file` и прочих) нет.

AC-8. При `sandbox: required` монтирования контейнера прогона — ровно рабочая
копия (тот же путь, запись), `.git` клона (тот же путь, только чтение),
каталог отчётов (тот же путь, запись) и том кэша `artel-<проект>-cache`;
других монтирований нет (в том числе сокета Docker, `~/.ssh`, БД и журналов
пульта).

AC-9. При `sandbox: required` каждый `-e` в argv `docker run` несёт
`ИМЯ=значение`, и имена — только из перечня: подполя `test_profile.env`,
`HOME=/tmp`, `PYTHONPYCACHEPREFIX`, `XDG_CACHE_HOME`, `UV_CACHE_DIR`; `-e ИМЯ`
без значения и `--env-file` отсутствуют; переменная, выставленная в
окружении пульта, в argv `docker` не попадает.

AC-10. При таймауте и при исключении во время прогона вызывается `docker
kill <имя>` и затем проверка отсутствия контейнера.

AC-11. Код выхода `docker run` 125, 126, 127 и недоступность демона дают
именованный инфраструктурный отказ, отличимый от красных тестов; pytest на
хосте в этом случае не запускается.

AC-12. При `sandbox: required` и непустом `install` установка отдельным
контейнером (тот же образ и монтирования, без `--network none`) запускается
при первом прогоне и при смене хеша файлов блокировки в `workdir` и не
запускается при неизменном хеше после успешной установки; сбой установки —
именованный отказ прогона, хеш при этом не обновляется.

AC-13. При `runner: pytest-own` полный набор берёт каталог из `workdir` и
`long_lived_dir`, а не `<корень>/tests`, и не дописывает `-n/-p xdist`.

AC-14. Автогейт приёмки, `approve` на acceptance и гейт мержа для задачи
внешнего проекта запускают полный набор командой, `runner` и `workdir` его
профиля — той же, что `suite-run` для той же задачи.

AC-15. `doctor` для проекта с `sandbox: required` сообщает о неотвечающем
демоне Docker и об отсутствии образа `image` (с командой сборки в выводе);
для проекта с `sandbox: off` эти проверки не выполняются.

AC-16. Ручной критерий Оператора (PLAN, живой Docker): учебный проект во
временном каталоге с `sandbox: required` и `runner: pytest-own` — тест,
читающий `os.environ`, не видит переменных пульта, кроме перечисленных в
требовании 3; тест с выходом на внешний адрес падает; тест, пишущий вне
рабочей копии, не оставляет следов на хосте.

AC-17. Ручной критерий Оператора (PLAN, живой Docker): по таймауту контейнер
снят, `docker ps -a` его не показывает; при остановленном Docker Desktop
прогон проекта с `required` — именованный отказ, не прогон на хосте.

## Оценка объёма и деление

Сработавшие сигналы: число файлов зоны ≥ 5 (9 элементов `zones:`); число
критериев приёмки ≥ 10 (17); `budget_usd` ≥ `SPLIT_SIGNAL_BUDGET_USD`
(рамка ТЗ $60). Калибровка (`config.BUDGET_CALIBRATION_TABLE`) для 9 файлов
зоны и 17 критериев даёт уровень ~$85 — выше рамки ТЗ $60. ТЗ на этот случай
само задаёт деление: D1а-1 (пп. 1–4, 8 для `run`, `collect`, `run_repeat`,
`run_plank`) и D1а-2 (полный набор, пп. 5–7); том кэша и переменные кэша
перенесены в D1а-1 решением Оператора (ANSWER-1, ответ 4), рамки частей —
прежние.

Решение — **нарезка на 2 части** по указанию ТЗ:
- D1а-1 — механика: поля записи и профиля (`targets.py`,
  `project_profile.Profile`), `sandbox.py`, фиксация путей артели, перевод
  четырёх точечных мест запуска, перевод фикстур на `sandbox: off`.
  Множества монтирований и переменных фиксируются здесь в окончательном
  виде (с томом кэша). Самостоятельно мержима: у артели (`sandbox: off`)
  поведение не меняется, записи с `required` в `targets.yaml` нет до D2,
  полный набор работает как сейчас.
- D1а-2 — опирается на `sandbox.py` и поля D1а-1: полный набор в контейнере,
  установка зависимостей, единый источник команды профиля (включая гейт
  мержа), `doctor`. Без D1а-1 мержить нечего; после неё — мержима, артель
  по-прежнему на `off`.

Зона `targets.py` в D1а-2 не нужна: проверку всех подполей профиля несёт
D1а-1. Фиксация argv/`cwd`/окружения всех семи мест артели (п.1) идёт в
D1а-1, D1а-2 держит её неизменной.

## Деление

### D1а-1: песочница Docker для точечных прогонов

Зоны: orchestrator/sandbox.py, orchestrator/acceptance.py, orchestrator/targets.py, orchestrator/config.py, orchestrator/project_profile.py, tests/
Порядок: первая, без зависимостей
Рамка: $45

Основание — ADR-0023, «Поправка 16.10.2026: механизм — контейнер Docker»
(пункты 1–3, 5, 7); часть 1 из 2 задачи D1а (SPEC родителя — источник
требований и решений Оператора ANSWER-1 от 16.10.2026). Сейчас пульт
исполняет код проекта на хосте с полным окружением Оператора: `_pytest_env`
(`orchestrator/acceptance.py:69-89`) копирует `os.environ` целиком;
`_pytest_command` (`acceptance.py:35-65`) всегда ставит интерпретатор venv
пульта и `-p timeout`. Семь мест запуска: `acceptance.py:448` (`run`), `:556`
(`collect`), `:665` (`run_repeat`), `:932` (`run_plank`), `:1324` и `:1345`
(`_run_full_suite_now`, с наблюдением и без), `:1373`
(`_run_full_suite_to_log`). Профиль `test_profile`
(`orchestrator/targets.py:41-53`): поля `sandbox` в проверке нет, у артели в
`targets.yaml` уже стоит `sandbox: off`. Носитель профиля для потребителей —
`project_profile.Profile` (`orchestrator/project_profile.py:63-74`). Docker
Desktop 28.4 на машине Оператора работает. Записи sled в `targets.yaml` нет
(её вносит D2).

Требуется:

1. Поле записи проекта `sandbox`: `required | off`; отсутствие — `required`
   для любого проекта, без исключения по имени; иное значение — отказ
   `targets.check` с названием записи и поля (ADR-0023 п.9). До правки
   зафиксировать тестами argv, `cwd` и окружение каждого из СЕМИ мест запуска
   для артели (`sandbox: off`) и держать их неизменными; при `off` `docker`
   не запускается.
2. Подполя `test_profile` (все необязательные, профиль артели без них
   остаётся правильным) — проверка всех в `targets.check`:
   - `runner`: `pult-pytest` (по умолчанию, сегодняшнее поведение) |
     `pytest-own` (команда профиля как есть: без интерпретатора пульта,
     `-p timeout` и `-n/-p xdist`; пульт по-прежнему дописывает свои
     аргументы гейтов — `--collect-only -q`, `--junitxml`,
     `-o junit_logging=system-out`, `-p no:cacheprovider`);
   - `workdir`: каталог прогона относительно корня репозитория, после
     `realpath` обязан остаться внутри рабочей копии; кроме проверки записи,
     `realpath(workdir)` проверяется на самой рабочей копии в момент прогона
     — симлинк, уводящий наружу, даёт именованный отказ без `docker run` и
     без прогона на хосте;
   - `env`: блочное отображение строк (новый вид `mapping`; `yamlmini` не
     меняется); имена из точного перечня секретов (`secret_env_names`
     провайдеров, `GITHUB_TOKEN`, `GH_TOKEN`) — отказ проверки, сверка по
     точному имени, не по подстроке;
   - `image`: имя образа Docker с тегом; обязательно при `sandbox: required`
     у записи с `test_profile`; запись без `test_profile` проходит проверку
     без `image`.
   Новые подполя и `sandbox` доходят до потребителей полями
   `project_profile.Profile` (`runner`, `workdir`, `env`, `image`,
   `sandbox`) — единый источник профиля; чтение `targets.target()` в обход
   `project_profile` не допускается.
3. Модуль `orchestrator/sandbox.py` — одна функция исполнения кода проекта.
   Проверка `sandbox: required` — первое условие внутри `run`, `collect`,
   `run_repeat`, `run_plank`; при `off` — прежний код без изменений.
   Сигнатуры этих функций и их вызывающие (`pull.py`, `plank_run.py`,
   `amend.py`, `advance_gates/acceptance.py`, `advance_gates/tests_writing.py`)
   не меняются: проект и задачу функция выводит из `cwd` по раскладке
   `.artel/projects/<проект>/worktrees/<id>` (`workspace.path`). `cwd`, не
   заданный или лежащий вне области проектов `.artel/projects/`, — путь
   артели, как сейчас; `cwd` внутри области проекта, но не рабочая копия
   задачи по раскладке, у проекта с `required` — именованный отказ, прогона
   на хосте нет. Контейнер: `docker run --rm --name
   artel-<проект>-<задача или run>-<случайный суффикс>`; `--network none`;
   `--user <uid>:<gid>` Оператора, `--cap-drop ALL`,
   `--security-opt no-new-privileges`; лимиты памяти и процессора — константы
   `config.py`; рабочая копия монтируется по тому же абсолютному пути на
   запись, `.git` клона проекта — по тому же пути только на чтение, каталог
   отчётов прогона (`--junitxml`, журнал) — по тому же пути на запись,
   именованный том кэша `artel-<проект>-cache`, других монтирований нет;
   окружение — только `test_profile.env`, `HOME=/tmp`, `PYTHONPYCACHEPREFIX`
   во временный каталог контейнера, `XDG_CACHE_HOME` и `UV_CACHE_DIR` (путь
   в томе кэша), каждая переменная — формой `-e ИМЯ=значение`, без `-e ИМЯ`
   без значения и без `--env-file`; переменные окружения пульта не
   передаются; рабочий каталог — `workdir`; иных флагов `docker run`, кроме
   перечисленных, нет (в том числе `--privileged`, `--pid`/`--ipc host`,
   повторного `--network`, `--volumes-from`). Сокет Docker, `~/.ssh`, связка
   ключей, токены, БД и журналы пульта в контейнер не попадают.
4. По таймауту и на любом исключении контейнер останавливается `docker kill
   <имя>`, затем пульт убеждается, что контейнера нет. Ошибка самого Docker
   (демон недоступен, нет образа, коды выхода `docker run` 125–127) —
   именованный инфраструктурный отказ, а не «красные тесты»; прогон на хосте
   вместо контейнера запрещён (fail-closed, ADR-0002). Разбор вывода и
   предел по профилю работают как сейчас.
5. Тесты в `tests/` детерминированы и не требуют Docker: вместо `docker` —
   подставной исполняемый файл, записывающий argv и код выхода. Проверяется:
   точный набор флагов, монтирований и переменных по п.3 (в том числе
   отсутствие лишних), выбор контейнера только при `required`, вывод проекта
   и задачи из `cwd` и отказ вне раскладки, проверка `realpath(workdir)` в
   момент прогона, неизменность семи путей артели (п.1), `docker kill` по
   таймауту и исключению, именованный отказ при ошибке Docker и запрет
   запуска на хосте, проверка полей профиля.
6. Фикстуры `tests/`: записи target'ов с `test_profile` во входных строках
   фикстур получают `sandbox: off` (общий шаблон `_PROJECT_TARGET_ENTRY` в
   `tests/sandbox.py` — тоже); утверждения существующих тестов не меняются;
   `base_entry` в `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`
   не правится. Перечень файлов — требование 9 SPEC родителя. Сквозной
   сценарий внешнего проекта (`tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py`)
   идёт путём `off`; путь `required` покрывают новые тесты с подставным
   `docker`. Мандата на ослабление тестов нет: если гейт неослабления
   отметит правку фикстур, решение — на гейте.

Критерии приёмки:
- у артели argv, `cwd` и окружение всех семи мест запуска не изменились;
- ручной критерий Оператора в PLAN: учебный проект во временном каталоге с
  `sandbox: required` и `runner: pytest-own` через `plank-run`: тест,
  читающий `os.environ`, не видит переменных пульта, кроме перечисленных в
  п.3; тест с выходом на внешний адрес падает; тест, пишущий вне рабочей
  копии на хосте, не оставляет следов; по таймауту контейнер снят и
  `docker ps -a` его не показывает; при остановленном Docker Desktop —
  именованный отказ, не прогон на хосте.

Не входит: полный набор в контейнере, установка зависимостей (`install`,
хеш блокировки, сеть по умолчанию), единый источник команды профиля для
автогейта, `approve` и гейта мержа, проверки `doctor` (часть 2 — D1а-2);
запись sled и меры круга 1 (D2); стенд docker compose (D1б); шаг роли в
контейнере; белый список хостов установки; сборка образов пультом; Linux и
Codex; песочница для артели; полный зелёный набор `tests/` — его держит
пульт. Только чтение: `docs/backlog.md`, `targets.yaml`. Правка вне зон —
эскалация.

### D1а-2: полный набор в контейнере, установка зависимостей, doctor

Зоны: orchestrator/sandbox.py, orchestrator/acceptance.py, orchestrator/config.py, orchestrator/project_profile.py, orchestrator/fsm_autogate.py, orchestrator/fsm.py, orchestrator/doctor/, tests/
Порядок: после части 1
Рамка: $45

Основание — ADR-0023, «Поправка 16.10.2026: механизм — контейнер Docker»
(пункты 1–3, 5, 7); часть 2 из 2 задачи D1а (SPEC родителя — источник
требований и решений Оператора ANSWER-1 от 16.10.2026). Опирается на часть 1
(D1а-1): поле `sandbox`, подполя `test_profile` (`runner`, `workdir`, `env`,
`image`), их проверка в `targets.check` и поля `project_profile.Profile`,
модуль `orchestrator/sandbox.py` с контейнером прогона (точный набор флагов,
монтирований с томом кэша и переменных с `XDG_CACHE_HOME`/`UV_CACHE_DIR`) и
fail-closed отказами, фиксация тестами argv/`cwd`/окружения семи мест
запуска артели, фикстуры `tests/` на `sandbox: off`. Сейчас полный набор
жёстко берёт `<корень>/tests` (`acceptance.py:1172`) и дописывает
`-n … -p xdist` (`:1176`) — у sled нет `pytest-xdist`, тесты в
`backend/tests`; `test_profile.install` (`orchestrator/targets.py:41-53`)
описан, но не исполняется. Автогейт приёмки (`fsm_autogate.py:326`) и
`approve` на acceptance (`fsm.py:1294`) зовут `acceptance.acceptance_suite`,
а тот — `full_suite(root, task_id)` без команды профиля
(`acceptance.py:1847-1848`); гейт мержа (`fsm_merge_gate.py:962-967`)
передаёт только `command` (`docs/backlog.md:185`, строка 07.10).

Требуется:

1. Полный набор: проверка `sandbox: required` — первое условие внутри
   `_run_full_suite_now` (с наблюдением и без) и `_run_full_suite_to_log`;
   при `off` — прежний код без изменений. При `required` — запуск через
   `orchestrator/sandbox.py` с теми же флагами, монтированиями, окружением,
   `docker kill` по таймауту и исключению и именованным отказом при ошибке
   Docker, что в части 1; проект и задача — из `task_id` полного набора,
   сигнатуры и вызывающие (`suite_run.py`, `notes.py`, `fsm_merge_gate.py`)
   не меняются. Наблюдение, замок полных прогонов машины и предел по профилю
   работают как сейчас. Полный набор при `runner: pytest-own` берёт каталог
   из `workdir` и `long_lived_dir`, а не `<корень>/tests`, и не дописывает
   `-n/-p xdist`. argv, `cwd` и окружение семи мест запуска артели остаются
   равны зафиксированным частью 1.
2. Установка зависимостей. Перед прогоном при `sandbox: required` и
   непустом `install`: если хеш файлов блокировки в `workdir` изменился с
   прошлой успешной установки (хеш хранится в области проекта
   `.artel/projects/<имя>/`), пульт исполняет `install` отдельным одноразовым
   контейнером с тем же образом и монтированиями (включая том кэша
   `artel-<проект>-cache` части 1), но с сетью по умолчанию. Сбой установки
   — именованный отказ прогона, хеш при этом не обновляется.
3. Один источник команды профиля: автогейт приёмки, `approve` на acceptance
   и гейт мержа берут команду, `runner` и `workdir` профиля проекта задачи —
   тем же путём, что `suite-run`, `plank-run`, `preflight`,
   `acceptance-dry-run`: `full_suite(root, task_id)` сам берёт их из профиля
   проекта задачи по `task_id`. `fsm_merge_gate.py` не правится;
   `fsm_autogate.py` и `fsm.py` — только если правки в `acceptance.py` для
   этого недостаточно.
4. `doctor` для проектов с `sandbox: required`: демон Docker отвечает; образ
   `image` есть локально; живая проба — одноразовый контейнер проекта не
   открывает внешний адрес и не видит переменных пульта. Для `sandbox: off`
   проверки не выполняются и запуск не блокируют. Сборка образа пультом не
   входит: Оператор собирает его вручную, `doctor` при отсутствии печатает
   команду сборки.
5. Тесты в `tests/` детерминированы и не требуют Docker: вместо `docker` —
   подставной исполняемый файл, записывающий argv и код выхода. Проверяется:
   флаги, монтирования и переменные полного набора (те же, что в части 1,
   без лишних), выбор контейнера только при `required`, неизменность путей
   артели, `docker kill` по таймауту и исключению, именованный отказ при
   ошибке Docker и запрет запуска на хосте, повтор установки только при
   смене хеша, единый источник команды профиля для автогейта, `approve` и
   гейта мержа, проверки `doctor`. Живой запуск с настоящим Docker — проба
   `doctor` и ручной критерий Оператора в PLAN, не тест набора.

Критерии приёмки:
- у артели argv, `cwd` и окружение всех семи мест запуска не изменились;
- автогейт приёмки, `approve` на acceptance и гейт мержа для задачи внешнего
  проекта запускают полный набор той же командой, `runner` и `workdir`, что
  `suite-run` для той же задачи;
- ручной критерий Оператора в PLAN: учебный проект во временном каталоге с
  `sandbox: required` и `runner: pytest-own` — полный набор (`suite-run`)
  идёт в контейнере: тест, читающий `os.environ`, не видит переменных пульта,
  кроме перечисленных; тест с выходом на внешний адрес падает; тест, пишущий
  вне рабочей копии на хосте, не оставляет следов; по таймауту контейнер
  снят и `docker ps -a` его не показывает; при остановленном Docker Desktop
  — именованный отказ, не прогон на хосте; живая проба `doctor` проходит.

Не входит: запись sled и меры круга 1 (D2); стенд docker compose с базами и
очередями (D1б); шаг роли в контейнере; белый список хостов для установки
(`install_hosts` из ADR-0023 п.10 отменён поправкой 16.10); сборка образов
пультом; Linux и Codex; песочница для артели; проверка подполей профиля в
`targets.check` (часть 1); полный зелёный набор `tests/` — его держит пульт.
Только чтение: `docs/backlog.md`, `targets.yaml`, `orchestrator/targets.py`,
`orchestrator/fsm_merge_gate.py`. Правка вне зон — эскалация.

## Не входит

- Запись sled в `targets.yaml` и меры круга 1 (задача D2, ADR-0023 п.6).
- Стенд docker compose с базами и очередями (задача D1б, ADR-0023 п.4).
- Шаг роли в контейнере.
- Белый список хостов для установки (`install_hosts` из ADR-0023 п.10
  отменён поправкой 16.10).
- Сборка образов пультом: образ собирает Оператор вручную.
- Linux и Codex.
- Песочница для артели (у неё `sandbox: off`).
- Правка `docs/backlog.md` и `targets.yaml` — только чтение.
- Правка вызывающих мест запуска (`pull.py`, `plank_run.py`, `amend.py`,
  `advance_gates/acceptance.py`, `advance_gates/tests_writing.py`,
  `suite_run.py`, `notes.py`) и `fsm_merge_gate.py` — решение Оператора
  ANSWER-1, ответы 1–2.
- Сквозной тест пути `required` для внешнего проекта: сквозной сценарий
  `external_flow` идёт путём `off`, путь `required` проверяется модульно
  (ANSWER-1, ответ 3).
- Полный зелёный набор `tests/` — его держит пульт (ANSWER-1, ответ 5).

## Материалы

- `docs/adr/0023-role-step-sandbox.md`, «Поправка 16.10.2026».
- `tasks/01M51YKZNES22DZQY13D3QKF89/ANSWER-1.md` — решения Оператора и
  матрица неослабления; `SPEC-AUDIT.md` — отклонения 1–9, закрытые этим
  SPEC.
- `docs/backlog.md:185` (строка 07.10) — единый источник команды профиля.
- `orchestrator/acceptance.py:35-89, 384, 448, 512, 556, 649, 665, 923, 932,
  1172, 1176, 1324, 1345, 1373, 1697, 1807, 1847-1848`;
  `orchestrator/targets.py:41-53, 99-100`;
  `orchestrator/project_profile.py:63-74`; `orchestrator/workspace.py:146-150`;
  `orchestrator/fsm_autogate.py:326`; `orchestrator/fsm.py:1294`;
  `orchestrator/fsm_merge_gate.py:962-967`.
- Поправка к числу файлов фикстур: батч вопросов назвал 2 файла
  (`tests/sandbox.py`, `external_flow`); сверка по коду main —
  35 файлов `tests/` с записью `test_profile:` без `sandbox` (перечень —
  требование 9). Правило ответа 3 («входные строки фикстур → `sandbox:
  off`, утверждения те же») применено ко всем; объём правки — одна строка
  на запись.
- Прочтение «каталог вне раскладки — отказ» (ответ 1): в `tests/` функции
  запуска артели зовутся с произвольным временным `cwd`
  (`tests/test_acceptance_collect.py:57`,
  `tests/test_acceptance_seed_repeat.py:82` и др.); отказ для любого такого
  `cwd` сменил бы их утверждения вопреки ответу 3. Поэтому отказ —
  только для `cwd` внутри области проекта `.artel/projects/<проект>/` вне
  раскладки рабочей копии у проекта с `required`; `cwd` вне области
  проектов — путь артели (требование 3, AC-5).
