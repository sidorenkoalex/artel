---
task: 01M51YKZNES22DZQY13D3QKF89
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/sandbox.py, orchestrator/acceptance.py, orchestrator/targets.py, orchestrator/config.py, orchestrator/project_profile.py, orchestrator/advance_gates/two_sided.py, orchestrator/fsm.py, orchestrator/amend.py, orchestrator/plank_run.py, orchestrator/fsm_autogate.py, orchestrator/doctor/, tests/
budget_usd: 60
---

# SPEC: D1а: код проекта в одноразовом контейнере Docker (круг 2)

## Контекст
Основание — ADR-0023, «Поправка 16.10.2026: механизм — контейнер Docker»
(пункты 1–3, 5, 7; пункт 6 — задача D2, пункт 4 — задача D1б). Сейчас пульт
исполняет код проекта на хосте с полным окружением Оператора. `_pytest_env`
(`orchestrator/acceptance.py:69-89`) копирует `os.environ` целиком.
`_pytest_command` (`acceptance.py:35-65`) всегда ставит интерпретатор venv
пульта и `-p timeout`. Полный набор жёстко берёт `<корень>/tests` (`:1172`)
и дописывает `-n … -p xdist` (`:1176`). У внешнего проекта это не работает:
у sled тесты лежат в `backend/tests`, а `pytest-timeout` и `pytest-xdist`
нет. `test_profile.install` (`orchestrator/targets.py:41-53`) описан, но не
исполняется, поля `sandbox` в проверке нет.

Мест запуска кода проекта восемь. Семь названы в ТЗ: `acceptance.py:448`
(`run`), `:556` (`collect`), `:665` (`run_repeat`), `:932` (`run_plank`),
`:1324` и `:1345` (`_run_full_suite_now` с наблюдением и без), `:1373`
(`_run_full_suite_to_log`). Восьмое — `_run_side` в
`orchestrator/advance_gates/two_sided.py:227-235`, двусторонний прогон смены
ожидания. Его зовут гейт `in_dev -> verifying`
(`advance_gates/test_integrity.py:1527`) и наблюдение (`:1429`), деревом
служит временный `git worktree` клона (`two_sided.py:300`). Вопреки ТЗ (стр.
19), этот гейт процесс запускает сам.

Автогейт приёмки (`fsm_autogate.py:326`) и `approve` на acceptance
(`fsm.py:1294`) зовут `acceptance.acceptance_suite`, а тот —
`full_suite(root, task_id)` без команды профиля (`acceptance.py:1847-1848`).
Гейт мержа (`fsm_merge_gate.py:962-967`) передаёт в `full_suite` только
`command` (`docs/backlog.md:185`, строка 07.10).

Решения Оператора. ANSWER-1 (16.10.2026, вариант A по всем вопросам):
носитель профиля — `project_profile.Profile`; гейт мержа входит в п.6 без
правки `fsm_merge_gate.py`; `image` обязателен только при `sandbox:
required` и наличии `test_profile`; фикстуры `tests/` получают `sandbox:
off` без смены утверждений; том кэша и переменные кэша входят в контейнер
прогона в первой части, где появляется контейнер; «полный набор зелёный»
держит пульт. ANSWER-2 (16.10.2026): `two_sided.py` входит в зоны
(отказ стороны при `required`, ответ 1); `required` без профиля или без
`image` — именованный отказ (ответ 2); правило фикстур по свойству (ответ
3); путь прогона выбирается по проекту ЗАДАЧИ, а не по каталогу (ответ 4);
задача полного набора — из `suite_lock.my_task_id()` (ответ 5); ключ
повторного использования итога при `required` (ответ 6); восьмое место
входит в фиксацию путей артели (ответ 7).

## Требования

1. Запись проекта несёт поле `sandbox` со значениями `required | off`.
   Отсутствие поля означает `required` для любого проекта, без исключения по
   имени. Иное значение — отказ `targets.check` с названием записи и поля.
   У артели (`sandbox: off`) ни один путь запуска не меняется. До правки
   argv, `cwd` и окружение каждого из восьми мест запуска для артели
   (семь мест ТЗ и `two_sided._run_side`) фиксируются тестами и остаются
   неизменными. При `off` `docker` не запускается.
2. Подполя `test_profile` (все необязательные, профиль артели без них
   остаётся правильным):
   - `runner`: `pult-pytest` (по умолчанию, сегодняшнее поведение) |
     `pytest-own` (команда профиля как есть: без интерпретатора пульта,
     `-p timeout` и `-n/-p xdist`; пульт по-прежнему дописывает свои
     аргументы гейтов — `--collect-only -q`, `--junitxml`,
     `-o junit_logging=system-out`, `-p no:cacheprovider`);
   - `workdir`: каталог прогона относительно корня репозитория. После
     `realpath` он обязан остаться внутри рабочей копии, причём и в проверке
     записи, и в момент прогона на самом каталоге прогона. Симлинк из
     репозитория проекта, уводящий наружу, даёт именованный отказ прогона;
   - `env`: блочное отображение строк (новый вид `mapping`; `yamlmini` не
     меняется). Имена из точного перечня секретов (`secret_env_names`
     провайдеров, `GITHUB_TOKEN`, `GH_TOKEN`) — отказ проверки, сверка по
     точному имени, не по подстроке;
   - `image`: имя образа Docker с тегом. Обязательно при `sandbox: required`
     у записи с `test_profile`; запись без `test_profile` проходит проверку
     без `image`.
   Полный набор при `pytest-own` берёт каталог из `workdir` и
   `long_lived_dir`, а не `<корень>/tests`. Новые подполя и `sandbox` доходят
   до потребителей через `project_profile.Profile` (поля `runner`, `workdir`,
   `env`, `image`, `sandbox`) — это единый источник профиля, чтение
   `targets.target()` в обход `project_profile` не допускается.
3. Модуль `orchestrator/sandbox.py` — одна функция исполнения кода проекта.
   Проверка `sandbox: required` — первое условие внутри каждой из семи
   функций запуска `acceptance.py`; при `off` — прежний код без изменений.
   Контейнер запускается так:
   - `docker run --rm --name artel-<проект>-<задача или run>-<случайный суффикс>`;
   - `--network none`;
   - `--user <uid>:<gid>` Оператора, `--cap-drop ALL`,
     `--security-opt no-new-privileges`;
   - лимиты памяти и процессора — константы `config.py`;
   - каталог прогона (рабочая копия или временное дерево — требование 4)
     монтируется по тому же абсолютному пути на запись; `.git` клона проекта
     — по тому же пути только на чтение; каталог отчётов прогона
     (`--junitxml`, журнал) — по тому же пути на запись; именованный том
     кэша `artel-<проект>-cache`; других монтирований нет;
   - окружение — только `test_profile.env`, `HOME=/tmp`,
     `PYTHONPYCACHEPREFIX` во временный каталог контейнера, `XDG_CACHE_HOME`
     и `UV_CACHE_DIR` (путь в томе кэша). Каждая переменная передаётся формой
     `-e ИМЯ=значение`; `-e ИМЯ` без значения и `--env-file` не
     используются; переменные окружения пульта не передаются;
   - рабочий каталог — `workdir`;
   - иных флагов `docker run`, кроме перечисленных, нет (в том числе
     `--privileged`, `--pid`/`--ipc host`, повторного `--network`,
     `--volumes-from`, `--env-file`).
   Сокет Docker, `~/.ssh`, связка ключей, токены, БД и журналы пульта в
   контейнер не попадают.
4. Путь прогона выбирается по проекту задачи прогона, а не по каталогу
   (ANSWER-2, ответ 4).
   - Основной признак — задача прогона: явный параметр либо единый контекст
     задачи, который ставит точка входа гейта или команды, знающая задачу.
     Для полного набора это `suite_lock.my_task_id()` (требование 10).
     Раскладка каталога прогона или каталога планки
     (`.artel/projects/<проект>/worktrees/<id>`, `workspace.path`) — только
     запасной признак, когда контекста задачи нет.
   - Если контекст задачи есть и проект задачи `required`, прогон идёт
     только в контейнере, в каком бы каталоге он ни шёл: в рабочей копии, во
     временной копии базы или во временном дереве гейта
     (`advance_gates/acceptance.py:363,378`, `appendix_tree.py:272`,
     `fsm_merge_gate.py:191`, `advance_gates/two_sided.py:300`,
     `suite_run.py:474`). Каталог прогона монтируется по тому же пути.
   - Путь артели — только когда проект задачи — артель либо когда
     контекста задачи нет и каталог прогона (и каталог планки) лежит вне
     `.artel/projects/`. Контекст задачи есть, а проект задачи не определён —
     именованный отказ без `docker run` и без pytest на хосте.
   - Контекст задачи ставят или задачу передают минимальные точки входа,
     поимённо: `orchestrator/fsm.py` — `cmd_advance` (диспетчер
     `fsm_advance.*`, через него идут гейты `advance_gates/acceptance.py`,
     `advance_gates/tests_writing.py`, `advance_gates/test_integrity.py` →
     `two_sided.py`), `_pull_main_or_escalate` (через него идёт
     `pull.evaluate` → `acceptance.run` из `runner.py:570`,
     `pull_main.py:69`, `fsm_advance.py:746`, `fsm_merge_gate.py:682`,
     `canary.py:1376`) и `cmd_approve` (автогейт, `approve` на acceptance,
     гейт мержа), если контекст нужен ему отдельно;
     `orchestrator/amend.py` — `cmd_amend_tests` (в том числе
     `amend.py:715,718`, `collect(tdir)`/`run(tdir)` без `cwd`);
     `orchestrator/plank_run.py` — `cmd_plank_run`. Правка в этих модулях —
     только постановка контекста или передача задачи, логика гейтов и
     команд не меняется. `orchestrator/advance_gates/plan_appendix.py:58`
     (временное дерево только для `git apply`) местом запуска кода проекта не
     является и не меняется.
5. Запись `required` (в том числе без поля `sandbox`) без `test_profile` или
   с профилем без `image` даёт именованный отказ прогона во всех функциях
   запуска и в `two_sided._run_side`: не запускаются ни `docker`, ни pytest
   на хосте (ANSWER-2, ответ 2).
6. Двусторонний прогон (`advance_gates/two_sided.py`, ANSWER-2, ответ 1):
   при `sandbox: required` у проекта задачи `_run_side` возвращает
   именованный отказ стороны, pytest на хосте не запускается. Этот отказ
   блокирует переход `in_dev -> verifying`, а не засчитывает проверку
   пройденной. При `off` код `_run_side` прежний.
7. По таймауту и на любом исключении контейнер останавливается командой
   `docker kill <имя>`, затем пульт убеждается, что контейнера нет. Ошибка
   самого Docker (демон недоступен, нет образа, коды выхода `docker run`
   125–127) — именованный инфраструктурный отказ, а не «красные тесты».
   Прогон на хосте вместо контейнера запрещён (fail-closed, ADR-0002).
   Разбор вывода, наблюдение, замок полных прогонов машины и предел по
   профилю работают как сейчас.
8. Перед прогоном при `sandbox: required` и непустом `install`: если хеш
   файлов блокировки в `workdir` изменился с прошлой успешной установки (хеш
   хранится в области проекта `.artel/projects/<имя>/`), пульт исполняет
   `install` отдельным одноразовым контейнером с тем же образом и
   монтированиями, но с сетью по умолчанию. Кэш пакетов — том
   `artel-<проект>-cache` (требование 3), смонтированный в установку и в
   прогоны; путь задаётся переменными `XDG_CACHE_HOME` и `UV_CACHE_DIR`. Сбой
   установки — именованный отказ прогона.
9. Ключ повторного использования итога полного набора (`suite_result_key`,
   `acceptance.py:1609-1640`; использование — `full_suite`, `:1740-1758`) при
   `sandbox: required` включает `sandbox`, `runner`, `workdir`, `image` (имя
   с тегом) и хеш файлов блокировки установки (требование 8). При `off` ключ
   не меняется ни на байт (ANSWER-2, ответ 6).
10. Задача полного набора (`_run_full_suite_now`, `acceptance.py:1313`;
    `_run_full_suite_to_log`, `:1361`; `run_full_suite`, `:1115`) берётся из
    `suite_lock.my_task_id()` (`suite_lock.py:155-163`). `None` (прогон
    `notes`) — путь артели. Задача есть, проект `required`, а профиль не
    прочитан — именованный отказ. Сигнатуры не меняются (ANSWER-2, ответ 5).
11. Один источник команды профиля: автогейт приёмки, `approve` на acceptance
    и гейт мержа берут команду, `runner` и `workdir` профиля проекта задачи
    тем же путём, что `suite-run`, `plank-run`, `preflight`,
    `acceptance-dry-run`: `full_suite(root, task_id)` сам берёт их из профиля
    проекта задачи по `task_id`. `fsm_merge_gate.py` не правится;
    `fsm_autogate.py` и `fsm.py` правятся под это требование, только если
    правки в `acceptance.py` для него недостаточно.
12. `doctor` для проектов с `sandbox: required` проверяет, что демон Docker
    отвечает, что образ `image` есть локально (при отсутствии печатает
    команду сборки), и делает живую пробу: одноразовый контейнер проекта не
    открывает внешний адрес и не видит переменных пульта. Для `sandbox: off`
    проверки не выполняются и запуск не блокируют.
13. Тесты в `tests/` детерминированы и не требуют Docker: вместо `docker` —
    подставной исполняемый файл, записывающий argv и код выхода. Каждое
    боевое место запуска и каждая боевая точка входа из требования 4 покрыты
    тестом: при задаче внешнего `required`-проекта прогон не идёт на хосте
    (подставной `docker` или именованный отказ), в том числе при прогоне во
    временном каталоге вне `.artel/projects/`. Живой запуск с настоящим
    Docker — проба `doctor` и ручной критерий Оператора в PLAN, не тест
    набора.
14. Фикстуры `tests/` (ANSWER-1, ответ 3; ANSWER-2, ответ 3) — правило по
    свойству: каждая запись target'а с `test_profile`, которую строит тест,
    получает во входе `sandbox: off`. Правило касается литерала YAML,
    склейки своей записи с `ARTEL_TEST_PROFILE` и dict-записи. Общий шаблон
    `_PROJECT_TARGET_ENTRY` в `tests/sandbox.py` (на нём
    `artel_target_entry`, `declared_without_profile` и запись внешнего
    проекта `make_project_repo`) тоже получает `sandbox: off`. Утверждения
    существующих тестов не меняются; `base_entry` (`:31-34`) и
    `random_profile` (`:38-52`) в
    `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py` не правятся.
    Известные на main файлы (43):
    - с литералом `test_profile:` (34): `tests/sandbox.py`,
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
      `tests/test_full_suite_profile_timeout.py`,
      `tests/test_project_profile_gates.py`, `tests/test_sandbox.py`;
    - со своей записью проекта и `ARTEL_TEST_PROFILE` (8):
      `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
      `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`,
      `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`,
      `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`,
      `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`,
      `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`,
      `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`,
      `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`;
    - с dict-записью (1): `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`
      (`:120`, `:124`, `:149`, `:166` — вход
      `dict(base_entry(name), sandbox="off", test_profile=…)`).
    Запись, найденная по тому же свойству вне перечня, правится тем же
    правилом. `tests/test_invariants.py` в перечень не входит: правка ему не
    нужна (`test_profile:` там только в комментарии `:187`, запись берётся
    из `seed_artel_targets()`, `:189`); это защищённый путь, и если правка
    всё же понадобится, то только приложением PLAN. Ослабление, которое это
    решение принимает: сквозной сценарий внешнего проекта
    (`tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py:346-474`) идёт
    путём `off`, а путь `required` проверяется модульно новыми тестами с
    подставным `docker`. Метод
    `test_profile.py::test_ac1_valid_profile_and_entry_without_profile_pass`
    проверяет годность профиля только при `off`, годность при `required` с
    `image` берёт на себя AC-3. Мандата на ослабление тестов нет: если гейт
    неослабления отметит правку входа, решение принимается на гейте.

## Критерии приёмки

AC-1. `targets.check` отказывает записи с `sandbox`, отличным от `required`
и `off`, называя запись и поле; запись без поля `sandbox` трактуется как
`required` для любого имени проекта.

AC-2. Для артели (`sandbox: off`) argv, `cwd` и окружение каждого из восьми
мест запуска (`run`, `collect`, `run_repeat`, `run_plank`,
`_run_full_suite_now` с наблюдением и без, `_run_full_suite_to_log`,
`two_sided._run_side`) совпадают с зафиксированными до правки; `docker` не
запускается.

AC-3. `targets.check` отказывает: `workdir`, выходящему после `realpath` за
рабочую копию; `env` с именем из точного перечня секретов (`secret_env_names`
провайдеров, `GITHUB_TOKEN`, `GH_TOKEN`), при этом имя, лишь содержащее
такое имя подстрокой, не отказывается; записи с `sandbox: required` и
`test_profile` без `image`. Запись с `sandbox: required` и годным профилем с
`image` проверку проходит. Запись с `sandbox: required` без `test_profile`
проверку проходит. Профиль артели без новых подполей проверку проходит.

AC-4. При `sandbox: required` `workdir`, который в каталоге прогона в момент
прогона после `realpath` уходит за его пределы (симлинк), даёт именованный
отказ прогона: ни `docker run`, ни pytest на хосте не запускаются.

AC-5. При задаче внешнего проекта с `sandbox: required` каждое боевое место
запуска (`run`, `collect`, `run_repeat`, `run_plank`, полный набор,
`two_sided._run_side`) и каждая точка входа требования 4 (`fsm.cmd_advance`
и гейты за ним, `fsm._pull_main_or_escalate`, `fsm.cmd_approve`,
`amend.cmd_amend_tests`, в том числе путь `amend.py:715,718` без `cwd`,
`plank_run.cmd_plank_run`) не запускают pytest на хосте: прогон идёт через
подставной `docker` либо даёт именованный отказ. Так же и при каталоге
прогона во временном каталоге вне `.artel/projects/`. Имя контейнера —
`artel-<проект>-<задача или run>-<суффикс>`.

AC-6. Контекст задачи есть, а проект задачи не определён — именованный
отказ без `docker run` и без pytest на хосте. Контекста задачи нет, а
каталог прогона или каталог планки лежит в рабочей копии задачи по раскладке
`.artel/projects/<проект>/worktrees/<id>` проекта с `required` — контейнер.
Контекста нет, каталог вне `.artel/projects/` — путь артели, как сейчас.

AC-7. Запись проекта задачи `required` (в том числе без поля `sandbox`) без
`test_profile` или с профилем без `image` даёт именованный отказ в каждой
функции запуска и в `two_sided._run_side`: подставной `docker` не вызван,
pytest на хосте не запущен.

AC-8. При `runner: pytest-own` argv прогона — команда профиля без
интерпретатора пульта, без `-p timeout` и `-n/-p xdist`, с аргументами гейтов
пульта (`--collect-only -q`, `--junitxml`, `-o junit_logging=system-out`,
`-p no:cacheprovider`) по месту запуска; без `runner` поведение равно
`pult-pytest`.

AC-9. При `sandbox: required` флаги `docker run` в argv подставного `docker`
— ровно перечень требования 3: `--rm`, `--name artel-<проект>-<задача или
run>-<суффикс>`, `--network none` (один раз), `--user <uid>:<gid>`,
`--cap-drop ALL`, `--security-opt no-new-privileges`, лимиты памяти и
процессора из констант `config.py`, рабочий каталог `workdir`, монтирования
AC-10 и переменные AC-11. Любого иного флага (`--privileged`, `--pid`/`--ipc
host`, повторного `--network`, `--volumes-from`, `--env-file` и прочих) нет.

AC-10. При `sandbox: required` монтирования контейнера прогона — ровно
каталог прогона (тот же путь, запись), `.git` клона (тот же путь, только
чтение), каталог отчётов (тот же путь, запись) и том кэша
`artel-<проект>-cache`. Других монтирований нет (в том числе сокета Docker,
`~/.ssh`, БД и журналов пульта).

AC-11. При `sandbox: required` каждый `-e` в argv `docker run` несёт
`ИМЯ=значение`, и имена берутся только из перечня: подполя
`test_profile.env`, `HOME=/tmp`, `PYTHONPYCACHEPREFIX`, `XDG_CACHE_HOME`,
`UV_CACHE_DIR`. `-e ИМЯ` без значения и `--env-file` отсутствуют;
переменная, выставленная в окружении пульта, в argv `docker` не попадает.

AC-12. При таймауте и при исключении во время прогона вызывается `docker
kill <имя>` и затем проверка отсутствия контейнера.

AC-13. Код выхода `docker run` 125, 126, 127 и недоступность демона дают
именованный инфраструктурный отказ, отличимый от красных тестов; pytest на
хосте в этом случае не запускается.

AC-14. При `sandbox: required` у проекта задачи двусторонний прогон смены
ожидания (`two_sided.run` из гейта `in_dev -> verifying`) возвращает
именованный отказ стороны, pytest на хосте не запускается, и переход
`in_dev -> verifying` отказан, а не пропущен. В наблюдении
(`test_integrity.py:1429`) сторона записана с этим отказом, прогона на хосте
нет.

AC-15. При `sandbox: required` и непустом `install` установка отдельным
контейнером (тот же образ и монтирования, без `--network none`) запускается
при первом прогоне и при смене хеша файлов блокировки в `workdir` и не
запускается при неизменном хеше после успешной установки. Сбой установки —
именованный отказ прогона, хеш при этом не обновляется.

AC-16. При `runner: pytest-own` полный набор берёт каталог из `workdir` и
`long_lived_dir`, а не `<корень>/tests`, и не дописывает `-n/-p xdist`.

AC-17. Задача полного набора берётся из `suite_lock.my_task_id()`: при
задаче внешнего `required`-проекта полный набор (`suite-run` во временной
копии базы, дерево приложений `appendix_tree.suite_tree`, scratch гейта
мержа) идёт через подставной `docker`. При `None` — путь артели. При задаче
`required`-проекта с непрочитанным профилем — именованный отказ.

AC-18. При `sandbox: required` ключ `suite_result_key` различается при смене
любого из `sandbox`, `runner`, `workdir`, `image` и хеша файлов блокировки,
и сохранённый итог с другим ключом гейту не засчитывается. При `off` ключ
байт в байт равен ключу до правки.

AC-19. Автогейт приёмки, `approve` на acceptance и гейт мержа для задачи
внешнего проекта запускают полный набор командой, `runner` и `workdir` его
профиля — той же, что `suite-run` для той же задачи.

AC-20. `doctor` для проекта с `sandbox: required` сообщает о неотвечающем
демоне Docker и об отсутствии образа `image` (с командой сборки в выводе);
для проекта с `sandbox: off` эти проверки не выполняются.

AC-21. Ручной критерий Оператора (PLAN, живой Docker): учебный проект во
временном каталоге с `sandbox: required` и `runner: pytest-own`. Тест,
читающий `os.environ`, не видит переменных пульта, кроме перечисленных в
требовании 3; тест с выходом на внешний адрес падает; тест, пишущий вне
рабочей копии, не оставляет следов на хосте.

AC-22. Ручной критерий Оператора (PLAN, живой Docker): по таймауту контейнер
снят, `docker ps -a` его не показывает; при остановленном Docker Desktop
прогон проекта с `required` — именованный отказ, не прогон на хосте.

## Оценка объёма и деление

Сработавшие сигналы: число файлов зоны ≥ 5 (12 элементов `zones:`); число
критериев приёмки ≥ 10 (22); `budget_usd` ≥ `SPLIT_SIGNAL_BUDGET_USD`
(рамка ТЗ $60). Калибровка (`config.BUDGET_CALIBRATION_TABLE`) для 12 файлов
зоны и 22 критериев даёт уровень ~$85 — выше рамки ТЗ $60. ТЗ на этот случай
само задаёт деление на D1а-1 (пп. 1–4, 8 для точечных прогонов) и D1а-2
(полный набор, пп. 5–7). ANSWER-2 добавил в D1а-1 восьмое место запуска,
постановку контекста задачи в трёх модулях-точках входа и 9 файлов фикстур и
разрешил делить на большее число частей (ответ 4). Одна D1а-1 с 10 зонами
вышла бы за рамку $45, поэтому она режется по границе «поля и фикстуры /
исполнение»; D1а-2 остаётся как была.

Решение — **нарезка на 3 части**:
- D1а-1а — поля записи и профиля (`targets.py`, `project_profile.Profile`),
  фиксация тестами argv/`cwd`/окружения восьми мест запуска артели до
  правки исполнения, перевод фикстур на `sandbox: off`. Самостоятельно
  мержима: исполнение не меняется ни у кого; артель в `targets.yaml:43`
  уже `off`; записей `required` в `targets.yaml` нет до D2; фикстуры
  получают `off` в той же части, где появляется проверка `image`.
- D1а-1б — опирается на поля D1а-1а: `sandbox.py` с контейнером, перевод
  четырёх точечных мест запуска, отказ стороны `two_sided._run_side`,
  выбор пути по проекту задачи и постановка контекста в точках входа,
  fail-closed отказы. Мержима после D1а-1а: у артели путь `off`
  неизменен и держится фиксацией D1а-1а.
- D1а-2 — опирается на `sandbox.py` D1а-1б: полный набор в контейнере с
  задачей из `suite_lock.my_task_id()`, установка зависимостей, ключ
  повторного использования, единый источник команды профиля, `doctor`.
  Мержима после D1а-1б, артель по-прежнему на `off`.

Фиксация путей артели (требование 1, AC-2) — в D1а-1а, D1а-1б и D1а-2 её
держат неизменной. Зона `targets.py` нужна только D1а-1а: проверку всех
подполей профиля несёт она.

## Деление

### D1а-1а: поля sandbox и профиля, фиксация путей артели, фикстуры

Зоны: orchestrator/targets.py, orchestrator/project_profile.py, tests/
Порядок: первая, без зависимостей
Рамка: $35

Основание — ADR-0023, «Поправка 16.10.2026: механизм — контейнер Docker»;
часть 1 из 3 задачи D1а. SPEC родителя — источник требований и решений
Оператора ANSWER-1 и ANSWER-2 от 16.10.2026. Профиль `test_profile`
(`orchestrator/targets.py:41-53`): поля `sandbox` в проверке нет, у артели в
`targets.yaml:43` уже стоит `sandbox: off`. Носитель профиля для
потребителей — `project_profile.Profile`
(`orchestrator/project_profile.py:63-74`). Исполнение кода проекта эта часть
не меняет.

Требуется:

1. Поле записи проекта `sandbox`: `required | off`. Отсутствие — `required`
   для любого проекта, без исключения по имени; иное значение — отказ
   `targets.check` с названием записи и поля (ADR-0023 п.9).
2. Подполя `test_profile` (все необязательные, профиль артели без них
   остаётся правильным), проверка всех — в `targets.check`:
   - `runner`: `pult-pytest` (по умолчанию) | `pytest-own`;
   - `workdir`: каталог относительно корня репозитория, после `realpath`
     обязан остаться внутри рабочей копии;
   - `env`: блочное отображение строк (новый вид `mapping`; `yamlmini` не
     меняется); имена из точного перечня секретов (`secret_env_names`
     провайдеров, `GITHUB_TOKEN`, `GH_TOKEN`) — отказ, сверка по точному
     имени, не по подстроке;
   - `image`: имя образа Docker с тегом; обязательно при `sandbox: required`
     у записи с `test_profile`; запись без `test_profile` проходит проверку
     без `image`.
   Неверное значение подполя отказывает с названием подполя и
   `test_profile`, как сегодня у прежних подполей. Новые подполя и `sandbox`
   доходят до потребителей полями `project_profile.Profile` (`runner`,
   `workdir`, `env`, `image`, `sandbox`).
3. До любой правки исполнения зафиксировать тестами argv, `cwd` и окружение
   каждого из восьми мест запуска для артели: `acceptance.run`, `collect`,
   `run_repeat`, `run_plank`, `_run_full_suite_now` (с наблюдением и без),
   `_run_full_suite_to_log`, `advance_gates/two_sided._run_side`.
4. Фикстуры `tests/` — требование 14 SPEC родителя целиком: правило по
   свойству (каждая запись с `test_profile`, которую строит тест, получает
   во входе `sandbox: off`), перечень 43 файлов, исключение
   `tests/test_invariants.py`, `base_entry` и `random_profile` не
   правятся, утверждения не меняются, мандата на ослабление нет.
5. Тесты детерминированы, без Docker: проверка полей профиля (в том числе
   годность профиля при `required` с `image`), фиксация восьми мест.

Критерии приёмки:
- `targets.check` отказывает неверному `sandbox` с названием записи и поля;
  отсутствие поля — `required` для любого имени;
- проверка подполей по пп. 2 (включая точное имя секрета, не подстроку;
  годный профиль с `image` при `required` проходит; запись без профиля
  проходит без `image`);
- argv, `cwd` и окружение восьми мест запуска артели зафиксированы тестами.

Не входит: исполнение в контейнере, `sandbox.py`, выбор пути по задаче,
отказ `two_sided` (D1а-1б); полный набор, установка, ключ, единый источник
команды, `doctor` (D1а-2); полный зелёный набор `tests/` — его держит
пульт. Только чтение: `docs/backlog.md`, `targets.yaml`. Правка вне зон —
эскалация.

### D1а-1б: песочница Docker для точечных прогонов и двустороннего прогона

Зоны: orchestrator/sandbox.py, orchestrator/acceptance.py, orchestrator/config.py, orchestrator/project_profile.py, orchestrator/advance_gates/two_sided.py, orchestrator/fsm.py, orchestrator/amend.py, orchestrator/plank_run.py, tests/
Порядок: после части 1
Рамка: $50

Основание — ADR-0023, «Поправка 16.10.2026: механизм — контейнер Docker»;
часть 2 из 3 задачи D1а. SPEC родителя — источник требований и решений
Оператора ANSWER-1 и ANSWER-2 от 16.10.2026. Опирается на часть 1
(D1а-1а): поле `sandbox`, подполя `runner`/`workdir`/`env`/`image`, поля
`project_profile.Profile`, фиксация тестами argv/`cwd`/окружения восьми мест
запуска артели, фикстуры на `sandbox: off`. Сейчас `_pytest_env`
(`orchestrator/acceptance.py:69-89`) копирует `os.environ` целиком, а
`_pytest_command` (`:35-65`) ставит интерпретатор пульта и `-p timeout`.
Точечные места запуска — `acceptance.py:448` (`run`), `:556` (`collect`),
`:665` (`run_repeat`), `:932` (`run_plank`). Восьмое место —
`advance_gates/two_sided.py:227-235` (`_run_side`, временный `git worktree`
клона, `:300`).

Требуется:

1. `orchestrator/sandbox.py` — одна функция исполнения кода проекта, с
   контейнером ровно по требованию 3 SPEC родителя (флаги, монтирования
   каталога прогона по тому же пути, `.git` клона только на чтение, каталог
   отчётов, том кэша `artel-<проект>-cache`, переменные `-e ИМЯ=значение`
   только из перечня, включая `XDG_CACHE_HOME`/`UV_CACHE_DIR`, рабочий
   каталог `workdir`, никаких иных флагов). Проверка `sandbox: required` —
   первое условие внутри `run`, `collect`, `run_repeat`, `run_plank`; при
   `off` — прежний код. `runner: pytest-own` — argv по требованию 2 SPEC
   родителя. `realpath(workdir)` проверяется на каталоге прогона в момент
   прогона.
2. Выбор пути по проекту задачи — требование 4 SPEC родителя: контекст
   задачи — основной признак, раскладка каталога — запасной; при `required`
   контейнер в любом каталоге прогона (в том числе во временном дереве
   приложений `advance_gates/acceptance.py:363,378`); контекст есть, проект
   не определён — отказ. Контекст ставят или задачу передают только
   `fsm.py` (`cmd_advance`, `_pull_main_or_escalate`, при необходимости
   `cmd_approve`), `amend.py` (`cmd_amend_tests`), `plank_run.py`
   (`cmd_plank_run`); правка там — только постановка контекста или
   передача задачи.
3. Запись `required` без профиля или без `image` — именованный отказ в
   четырёх точечных функциях и в `_run_side` (требование 5 SPEC родителя).
4. `two_sided._run_side` при `required` у проекта задачи — именованный
   отказ стороны, блокирующий `in_dev -> verifying`; при `off` код прежний
   (требование 6 SPEC родителя).
5. Таймаут, исключение, ошибка Docker — требование 7 SPEC родителя:
   `docker kill <имя>` и проверка отсутствия, именованный инфраструктурный
   отказ, запрет хостового прогона.
6. Тесты детерминированы, без Docker, с подставным `docker`: точный набор
   флагов, монтирований и переменных; выбор контейнера только при
   `required`; каждое точечное место и каждая точка входа п.2 при задаче
   внешнего `required`-проекта не гоняют pytest на хосте, в том числе во
   временном каталоге вне `.artel/projects/`; отказ без проекта; отказ
   `required` без `image`; отказ стороны `two_sided`; `docker kill`;
   отказ при ошибке Docker; неизменность восьми путей артели по фиксации
   D1а-1а.

Критерии приёмки:
- AC-2, AC-4–AC-14 SPEC родителя для точечных мест и `two_sided._run_side`;
- ручной критерий Оператора в PLAN: учебный проект во временном каталоге
  с `sandbox: required` и `runner: pytest-own` через `plank-run` — тест,
  читающий `os.environ`, не видит переменных пульта, кроме перечисленных;
  тест с выходом на внешний адрес падает; тест, пишущий вне рабочей копии
  на хосте, не оставляет следов; по таймауту контейнер снят и `docker ps
  -a` его не показывает; при остановленном Docker Desktop — именованный
  отказ, не прогон на хосте.

Не входит: полный набор в контейнере, установка зависимостей, ключ
повторного использования, единый источник команды профиля, `doctor`
(D1а-2); прогон двусторонней проверки в контейнере — отдельная задача;
проверка полей в `targets.check` (D1а-1а); полный зелёный набор `tests/` —
его держит пульт. Только чтение: `docs/backlog.md`, `targets.yaml`,
`orchestrator/targets.py`, `orchestrator/fsm_merge_gate.py`. Правка вне зон
— эскалация.

### D1а-2: полный набор в контейнере, установка зависимостей, doctor

Зоны: orchestrator/sandbox.py, orchestrator/acceptance.py, orchestrator/config.py, orchestrator/project_profile.py, orchestrator/fsm_autogate.py, orchestrator/fsm.py, orchestrator/doctor/, tests/
Порядок: после части 2
Рамка: $45

Основание — ADR-0023, «Поправка 16.10.2026: механизм — контейнер Docker»;
часть 3 из 3 задачи D1а. SPEC родителя — источник требований и решений
Оператора ANSWER-1 и ANSWER-2 от 16.10.2026. Опирается на части 1 и 2:
поля профиля, `orchestrator/sandbox.py` с контейнером и fail-closed
отказами, выбор пути по проекту задачи, фиксация восьми мест запуска
артели. Сейчас полный набор жёстко берёт `<корень>/tests`
(`acceptance.py:1172`) и дописывает `-n … -p xdist` (`:1176`);
`test_profile.install` не исполняется; ключ `suite_result_key`
(`acceptance.py:1609-1640`) не несёт ни `sandbox`, ни `image`. Автогейт
(`fsm_autogate.py:326`) и `approve` (`fsm.py:1294`) зовут `full_suite(root,
task_id)` без команды профиля (`acceptance.py:1847-1848`), гейт мержа
(`fsm_merge_gate.py:962-967`) передаёт только `command`.

Требуется:

1. Полный набор: проверка `sandbox: required` — первое условие внутри
   `_run_full_suite_now` (с наблюдением и без) и `_run_full_suite_to_log`;
   при `off` — прежний код. При `required` — запуск через `sandbox.py` с
   теми же флагами, монтированиями, окружением и отказами, что в части 2.
   Задача — из `suite_lock.my_task_id()` (требование 10 SPEC родителя):
   `None` — путь артели; задача `required`-проекта без прочитанного профиля
   — отказ; без профиля или без `image` — отказ (требование 5). Сигнатуры и
   вызывающие (`suite_run.py`, `notes.py`, `fsm_merge_gate.py`) не
   меняются. При `runner: pytest-own` каталог — из `workdir` и
   `long_lived_dir`, без `-n/-p xdist`.
2. Установка зависимостей — требование 8 SPEC родителя; сбой — отказ, хеш
   не обновляется.
3. Ключ повторного использования — требование 9 SPEC родителя: при
   `required` в ключе `sandbox`, `runner`, `workdir`, `image`, хеш
   блокировки; при `off` ключ не меняется ни на байт.
4. Один источник команды профиля — требование 11 SPEC родителя;
   `fsm_merge_gate.py` не правится.
5. `doctor` — требование 12 SPEC родителя.
6. Тесты детерминированы, без Docker: полный набор при задаче внешнего
   `required`-проекта во временной копии базы `suite-run`
   (`suite_run.py:474`), в дереве приложений (`appendix_tree.py:272`) и в
   scratch гейта мержа (`fsm_merge_gate.py:191`) идёт через подставной
   `docker`; повтор установки только при смене хеша; ключ; единый источник
   команды; проверки `doctor`; неизменность путей артели.

Критерии приёмки:
- AC-2, AC-15–AC-20 SPEC родителя;
- ручной критерий Оператора в PLAN: учебный проект с `sandbox: required` и
  `runner: pytest-own` — полный набор (`suite-run`) идёт в контейнере,
  наблюдения AC-21 и AC-22 те же; живая проба `doctor` проходит.

Не входит: запись sled и меры круга 1 (D2); стенд docker compose (D1б); шаг
роли в контейнере; белый список хостов установки; сборка образов пультом;
Linux и Codex; песочница для артели; прогон двусторонней проверки в
контейнере; полный зелёный набор `tests/` — его держит пульт. Только
чтение: `docs/backlog.md`, `targets.yaml`, `orchestrator/targets.py`,
`orchestrator/fsm_merge_gate.py`, `orchestrator/suite_run.py`. Правка вне
зон — эскалация.

## Не входит

- Запись sled в `targets.yaml` и меры круга 1 (задача D2, ADR-0023 п.6).
- Стенд docker compose с базами и очередями (задача D1б, ADR-0023 п.4).
- Шаг роли в контейнере.
- Белый список хостов для установки (`install_hosts` из ADR-0023 п.10
  отменён поправкой 16.10).
- Сборка образов пультом: образ собирает Оператор вручную.
- Linux и Codex.
- Песочница для артели (у неё `sandbox: off`).
- Прогон двусторонней проверки (`two_sided.py`) в контейнере — отдельная
  задача; здесь при `required` только именованный отказ стороны
  (ANSWER-2, ответ 1).
- Правка `docs/backlog.md` и `targets.yaml` — только чтение.
- Правка `fsm_merge_gate.py`, `suite_run.py`, `notes.py`, `pull.py`,
  `pull_main.py`, `runner.py`, `canary.py`,
  `advance_gates/acceptance.py`, `advance_gates/tests_writing.py`,
  `advance_gates/test_integrity.py`, `orchestrator/advance_gates/plan_appendix.py`,
  `appendix_tree.py`: контекст задачи ставят точки входа требования 4.
- Логика гейтов и команд в `fsm.py`, `amend.py`, `plank_run.py` — там только
  постановка контекста задачи или её передача (ANSWER-2, ответ 4).
- Сквозной тест пути `required` для внешнего проекта: сквозной сценарий
  `external_flow` идёт путём `off`, путь `required` проверяется модульно
  (ANSWER-1, ответ 3).
- Правка `tests/test_invariants.py`: не нужна (требование 14).
- Полный зелёный набор `tests/` — его держит пульт (ANSWER-1, ответ 5).

## Материалы

- `docs/adr/0023-role-step-sandbox.md`, «Поправка 16.10.2026».
- `tasks/01M51YKZNES22DZQY13D3QKF89/ANSWER-1.md`, `ANSWER-2.md` — решения
  Оператора и матрицы неослабления; `SPEC-AUDIT.md` — отклонения визита 2
  (1–7), закрытые этим SPEC.
- Поправка к строке 3 матрицы ANSWER-1 («тот же тест без правки»): по коду
  `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:120,124` вызывает
  `targets.check`/`targets.load` на `base_entry` с профилем без `image`, и
  без правки входа это был бы отказ. Тест правится во входе (`sandbox="off"`),
  утверждения те же (ANSWER-2, ответ 3).
- Метод того же файла с неизвестным подполем `runner` и значением `"x"`:
  после введения `runner` отказ по неверному значению обязан по-прежнему
  называть `runner` и `test_profile` (требование 2 части D1а-1а).
- `docs/backlog.md:185` (строка 07.10) — единый источник команды профиля.
- `orchestrator/acceptance.py:35-89, 439, 448, 550, 556, 665, 932, 1115,
  1172, 1176, 1313, 1324, 1345, 1361, 1373, 1609-1640, 1740-1758,
  1847-1848`; `orchestrator/advance_gates/two_sided.py:227-235, 300`;
  `orchestrator/advance_gates/test_integrity.py:1429, 1527`;
  `orchestrator/fsm.py:212, 266, 688, 885, 1294`;
  `orchestrator/amend.py:626, 715, 718`; `orchestrator/suite_lock.py:155-163`;
  `orchestrator/targets.py:41-53, 99-100`;
  `orchestrator/project_profile.py:63-74`; `orchestrator/workspace.py:146-150`;
  `orchestrator/fsm_autogate.py:326`; `orchestrator/fsm_merge_gate.py:191,
  682, 962-967`; `orchestrator/suite_run.py:474, 524, 564`;
  `orchestrator/appendix_tree.py:272`.
