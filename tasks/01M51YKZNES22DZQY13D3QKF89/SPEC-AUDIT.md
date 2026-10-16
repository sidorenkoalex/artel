---
task: 01M51YKZNES22DZQY13D3QKF89
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py, tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py, tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py, tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py, tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py, tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py, tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py, tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py, tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py, tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py, tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py, tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py, tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py, tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py, tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py, tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py, tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py, tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py, tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py, tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py, tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py, tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py, tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py, tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py, tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py, tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py, tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py, tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py, tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py, tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py, tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py, tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py, tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py, tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py, tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py, tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py, tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py, tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py, tests/test_full_suite_profile_timeout.py, tests/test_invariants.py, tests/test_project_profile_gates.py, tests/test_sandbox.py; в) пути-признаки (гейты): orchestrator/advance_gates/plan_appendix.py, orchestrator/advance_gates/two_sided.py, orchestrator/fsm_autogate.py; в) защищённые пути: tests/test_invariants.py; в) SPEC требует приложения PLAN; г) budget_usd 60 ≥ 45; д) ТЗ ссылается на ADR: ADR-0002, ADR-0023."
spec_sha: c4aadfd074a28770cc09a7a12c01b9c1be1e636e
schema_version: 5
---

# SPEC-AUDIT: D1а: код проекта в одноразовом контейнере Docker (круг 2)

Визит 4. Проверен SPEC.md с sha содержимого
c4aadfd074a28770cc09a7a12c01b9c1be1e636e (`git hash-object` совпал).
Глубина — полная. Восемь отклонений визита 3 закрыты решением Оператора
на гейте SPEC 16.10.2026, и их правка в SPEC внесена; заново они не
поднимаются. Ниже только новые находки по коду.

## ТЗ и SPEC

- ТЗ п.1 (поле `sandbox`, фиксация путей артели) → SPEC треб. 1, AC-1,
  AC-2. Семь мест стали восемью по ANSWER-2, ответ 7. Соответствует.
- ТЗ п.2 (подполя `runner`/`workdir`/`env`/`image`) → треб. 2, AC-3,
  AC-8, AC-16. `image` сужен до записей с `test_profile` (ANSWER-1,
  ответ 3); добавлено `lock_files` (решение на гейте, п.5). Соответствует.
- ТЗ п.3 (контейнер) → треб. 3, AC-9–AC-11. «Рабочая копия» заменена
  «каталогом прогона» (ANSWER-2, ответ 4), запрет `config.ROOT` — решение
  на гейте, п.1. Соответствует.
- ТЗ п.4 (таймаут, ошибка Docker) → треб. 7, AC-12, AC-13. Соответствует,
  но см. отклонение 4: для `run_repeat` «именованный отказ, а не красные
  тесты» требует смены договора с вызывающим вне зон.
- ТЗ п.5 (установка) → треб. 8, AC-15. Отметка хеша перенесена из
  `.artel/projects/<имя>/` в дерево прогона решением на гейте, п.5.
  Соответствует; последствие — отклонение 5.
- ТЗ п.6 (один источник команды) → треб. 11, AC-19; в п.6 вошёл и гейт
  мержа (ANSWER-1, ответ 2). Соответствует.
- ТЗ п.7 (`doctor`) → треб. 12, AC-20. Соответствует.
- ТЗ п.8 (тесты с подставным `docker`) → треб. 13, AC-2–AC-20.
  Соответствует.
- Критерии ТЗ (учебный проект, `docker ps -a`, остановленный Docker) →
  AC-21, AC-22 как ручные критерии PLAN (ANSWER-1, ответ 5). Соответствует.
- В SPEC нет требований, которых не было бы ни в ТЗ, ни в ANSWER-1/2, ни
  в решении на гейте.

## Факты против кода

Подтвердилось:
- `_pytest_command` — `acceptance.py:35-65`: подставляет интерпретатор
  venv пульта (`:58-61`), ставит `-p timeout` и `-o timeout` (`:62-64`).
  `_pytest_env` копирует `os.environ` (`acceptance.py:69-89`, `:85`).
- Места запуска: `run` (`acceptance.py:448`), `collect` (`:556`),
  `run_repeat` (`:665`), `run_plank` (`:932`), `_run_full_suite_now`
  (`:1324`, `:1345`), `_run_full_suite_to_log` (`:1373`),
  `two_sided._run_side` (`advance_gates/two_sided.py:222-240`), его
  временное дерево — `:300`.
- `run_cwd = cwd if cwd is not None else config.ROOT` — `acceptance.py:439`.
  `amend.py:715,718` зовёт `collect(tdir)`/`run(tdir)` без `cwd`, при этом
  `tdir = wt_path / "tasks" / task_id` (`amend.py:626`, `:695`), так что
  рабочую копию задачи из `tdir` вывести можно.
- Полный набор: `tests_dir = root / "tests"` (`acceptance.py:1172`),
  `-n … -p xdist` (`:1175-1176`), замок `_machine_lock` (`:1266-1290`).
- `suite_lock.my_task_id` — `suite_lock.py:155-163`.
- Деградация «нет БД — артель»: `store.py:701-707`, `workspace.py:52-58`,
  `acceptance.py:1727-1729`.
- `suite_result_key` — `acceptance.py:1609-1640`, использование в
  `full_suite` — `:1740-1758`. `full_suite(root, task_id)` в
  `acceptance_suite` — `:1847-1848`. Гейт мержа — `fsm_merge_gate.py:958-967`.
- Точки входа: `fsm._pull_main_or_escalate` (`fsm.py:212`, `pull.evaluate`
  на `:266`), его вызывающие `runner.py:570`, `pull_main.py:69`,
  `fsm_advance.py:746`, `fsm_merge_gate.py:682`, `canary.py:1376`;
  `cmd_advance` (`fsm.py:688`), `cmd_approve` (`fsm.py:885`), `approve` на
  acceptance (`fsm.py:1294`), автогейт (`fsm_autogate.py:326`, вызов из
  `fsm_advance.py:334`). Других боевых вызывающих функций запуска нет
  (grep по `orchestrator/`: `pull.py:664,666`, `plank_run.py:187`,
  `notes.py:1040`, `suite_run.py:524,564`, `amend.py:545,549,715,718`,
  `advance_gates/acceptance.py:169,402,405`,
  `advance_gates/tests_writing.py:560,563`, `fsm_merge_gate.py:962-967`).
- Временные деревья: `suite_run.py:474`, `appendix_tree.py:272`,
  `fsm_merge_gate.py:191`, `advance_gates/acceptance.py:363,378`.
- Профиль: `targets.py:41-53`, `targets.py:99-100`, `Profile` —
  `project_profile.py:63-74`, `workspace.path` — `workspace.py:146-150`.
  `sandbox: off` у артели — `targets.yaml:43`, других записей в
  `targets.yaml` нет.
- Перечень фикстур требования 14: grep `test_profile:` по `tests/*.py` дал
  35 файлов, то есть 34 перечня и `tests/test_invariants.py`. Grep
  `ARTEL_TEST_PROFILE` дал перечень (б) плюс файлы, уже вошедшие в (а).
  `tests/test_invariants.py:187` — комментарий, `:189` —
  `seed_artel_targets()`. `base_entry`/`random_profile` —
  `test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:31-34,37-53`. Вызовы на
  `:120`, `:124`, `:149`, `:166`. Неизвестное подполе `runner` со
  значением `"x"` — `:103-104`.

Неточно:
- Ф1. «`_kill_group` (`acceptance.py:1334,1388`)» (SPEC, треб. 7). На
  деле `_kill_group` стоит на `:1332`, `:1337` (исключение под
  наблюдением), `:1385`, `:1388`; на `:1334` — разбор вывода. Мест четыре,
  а не два. Если исполнитель заменит только названные, `:1337` и `:1385`
  останутся.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `sandbox: "on"` проходит `targets.check`; отсутствие поля трактуется как `off` для имени `artel` |
| AC-2 | да | при `off` в env попадает `XDG_CACHE_HOME`, меняется `cwd` или argv; при `off` вызывается `docker` |
| AC-3 | да | секрет сверяется подстрокой (`MY_GH_TOKEN_X` отказан) либо не сверяется; `workdir: ../x` проходит; `required`+профиль без `image` проходит |
| AC-4 | да | `realpath` не проверяется — симлинк наружу доходит до `docker run` |
| AC-5 | да | точка входа не ставит контекст, прогон во временном каталоге уходит на хост |
| AC-6 | да | нет строки задачи → путь артели вместо отказа |
| AC-7 | да | запись `required` без `image` запускает pytest на хосте |
| AC-8 | да | `pytest-own` оставляет `-p timeout` или интерпретатор пульта |
| AC-9 | да | лишний флаг (`--privileged`) или потерян `--cap-drop ALL` |
| AC-10 | частично | лишний `-v $HOME/.ssh` ловится; монтирование журнала `config.LOGS/suite-run/<id>` на запись — нет (отклонение 2) |
| AC-11 | да | `-e PATH` без значения, `--env-file`, утечка `GH_TOKEN` пульта |
| AC-12 | да | по таймауту не вызван `docker kill` |
| AC-13 | частично | для `run`/`collect`/`run_plank` код 125 читается как красный прогон — ловится; для `run_repeat` канала отказа нет (отклонение 4) |
| AC-14 | да | `_run_side` при `required` даёт зелёную сторону или гоняет pytest |
| AC-15 | да | установка при неизменном хеше; отметка обновлена после сбоя |
| AC-16 | да | полный набор `pytest-own` берёт `<корень>/tests` или дописывает `-n` |
| AC-17 | да | `my_task_id()` не читается — полный набор `required` идёт на хост |
| AC-18 | частично | ключ gate-итога без ID образа ловится; base-ключ `suite_run.py:511,533` не охвачен (отклонение 6) |
| AC-19 | да | автогейт зовёт полный набор без `runner`/`workdir` профиля |
| AC-20 | да | `doctor` молчит при неотвечающем демоне |
| AC-21 | ручной | — (живой Docker, PLAN) |
| AC-22 | ручной | — (живой Docker, PLAN) |

## Зоны

- Зоны родителя покрывают требования, кроме двух мест:
  - Договор `run_repeat` (отклонение 4). Его единственный вызывающий —
    `advance_gates/acceptance.py:169-176`, а этот файл в «Не входит».
    Отличить инфраструктурный отказ от красных повторов можно только там.
  - Base-ключ итога `suite_run.py:511,533` (отклонение 6); `suite_run.py` —
    только чтение.
- Защищённые пути не трогаются; правка `tests/test_invariants.py`, если
  понадобится, — только приложением PLAN (треб. 14). Песочница ролей не
  расширяется.
- Деление: D1а-1а — `targets.py`, `project_profile.py`, `tests/`. Этого
  достаточно: фиксацию восьми мест делают тестами, без правки
  исполнения. Зоны D1а-1б и D1а-2 повторяют зоны родителя по своим пунктам.

## Матрица неослабления

Строки ANSWER-1, ANSWER-2 и две строки решения на гейте (снятие
`-p timeout` при `pytest-own`, наблюдение под контейнером) на месте.
Не хватает строк:

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Окружение полного набора с журналом при `required` — закрытый перечень AC-11 без `PYTHONUNBUFFERED` | Небуферизованный вывод: на пределе времени успевшая часть чисел не теряется, `acceptance.py:1365-1372` | не остаётся: `docker kill` съест буфер Python в контейнере (stdout — канал, не терминал), либо исполнитель нарушит AC-11 | не покрыто | вопрос Оператору (отклонение 1) |
| Канал инфраструктурного отказа в `run_repeat` | Повтор с неизвестным исходом зелёным не считается, `acceptance.py:658-660,676-683`, `advance_gates/acceptance.py:169-176` | не определено: отказ — либо `[]` (зелёный повтор), либо `RedTest` (ложная эскалация «зависит от зерна») | не покрыто | вопрос Оператору (отклонение 4) |

## Пути обхода гейтов

- П1. Монтирование журнала. Треб. 3: «каталог отчётов прогона
  (`--junitxml`, журнал) — по тому же пути на запись». Журнал `suite-run`
  лежит в `config.LOGS/suite-run/<id>/` (`suite_run.py:131-134`,
  `suite_lock.py:40-49`), рядом с замком машины `lock.json`. Если читать
  треб. 3 буквально, этот каталог монтируется на запись, и код проекта
  может переписать замок и чужие логи. AC-10 запрещает только `-v` на сам
  `.artel/`, поэтому такое монтирование его проходит. При этом журнал
  пишет хост через `stdout=fh` (`acceptance.py:1371-1373`), и монтирование
  ему не нужно. Это отклонение 2.
- П2. `run_repeat` с отказом в виде `[]`. AC-13 соблюдён по тексту, а
  гейт повторов (`advance_gates/acceptance.py:175`) пропускает отказ как
  зелёный повтор. Это отклонение 4.
- П3. Подделка отметки установки. Отметка лежит в рабочей копии, а та
  смонтирована в контейнер на запись (треб. 3, 8). Тест проекта может
  записать в отметку «нужный» хеш, и следующую установку пульт пропустит.
  Сверх того, `git add -A` чекпоинта (`checkpoint.py:1722`) закоммитит
  отметку в ветку задачи. Это отклонение 5.

## Вердикт

concerns. Отклонения (решение — за Оператором на гейте):

1. `PYTHONUNBUFFERED` против AC-11. `_run_full_suite_to_log` ставит
   `PYTHONUNBUFFERED=1` (`orchestrator/acceptance.py:1368-1372`), чтобы на
   пределе времени не терялся вывод. Закрытый перечень переменных
   (SPEC, треб. 3; AC-11) его не содержит, и строки матрицы нет. Варианты:
   добавить `PYTHONUNBUFFERED=1` в перечень AC-11 либо принять потерю
   строкой матрицы.
2. «Журнал» в монтированиях. Каталог журнала `suite-run` — журнал пульта
   рядом с `lock.json` (`orchestrator/suite_run.py:131-134`,
   `orchestrator/suite_lock.py:40-49`). Треб. 3 велит монтировать его на
   запись и тем противоречит своей же фразе «журналы пульта в контейнер не
   попадают»; AC-10 такое монтирование не ловит. Журнал пишет хост
   (`orchestrator/acceptance.py:1371-1373`). Предложение: журнал не
   монтируется, AC-10 дополняется запретом `-v` на `config.LOGS` и всё под
   ним.
3. `runner: pult-pytest` при `sandbox: required` не определён. Команда по
   умолчанию — интерпретатор venv пульта
   (`orchestrator/acceptance.py:58-61`). В контейнере его нет: venv не
   смонтирован, треб. 3. Прогон упадёт кодом 127 и будет назван
   инфраструктурным отказом Docker, хотя причина — профиль. SPEC (треб. 2,
   AC-8) не говорит, что значит `pult-pytest` в контейнере. Варианты:
   отказ `targets.check` для `required` без `runner: pytest-own`, либо
   `python3` образа с `-p timeout`/`-p xdist`.
4. Отказ `run_repeat` неотличим от результата. Договор «пустой список —
   зелёно» (`orchestrator/acceptance.py:649-683`) не даёт канала для
   именованного отказа AC-13. Вызывающий
   `orchestrator/advance_gates/acceptance.py:169-176` вне зон (SPEC, «Не
   входит»). Буквальное исполнение даёт либо обход гейта повторов (`[]`),
   либо ложную эскалацию о зерне.
5. Отметка установки в рабочей копии. Место задано решением на гейте,
   п.5, но SPEC не говорит, что отметку не видит контейнер и что она не
   попадает в git. Рабочая копия смонтирована на запись (треб. 3), отметку
   можно подделать изнутри. `git add -A` чекпоинта
   (`orchestrator/checkpoint.py:1722`) закоммитит её в ветку задачи, и она
   войдёт в дерево `suite_tree_hash`. Нужно уточнение: имя или путь
   отметки вне смонтированного дерева либо исключение из индекса.
6. Ключ base-итога не охвачен. Треб. 9 и AC-18 говорят только о
   gate-итоге `full_suite` (`orchestrator/acceptance.py:1740-1758`).
   Base-итог считается тем же `suite_result_key` в `suite_run.py:511`,
   сохраняется в `:533` (файл только для чтения) и в
   `orchestrator/acceptance.py:1790-1792`. После пересборки образа под тем
   же тегом итог базы `required`-проекта будет взят повторно. Нужно
   решение: base-ключ при `required` получает те же поля (задача — через
   `suite_lock.my_task_id()`, без правки `suite_run.py`) либо исключение
   строкой матрицы.
7. Ф1. Места `_kill_group` названы неполно: SPEC называет
   `orchestrator/acceptance.py:1334,1388`, а вызовы стоят на `:1332`,
   `:1337`, `:1385`, `:1388`.
