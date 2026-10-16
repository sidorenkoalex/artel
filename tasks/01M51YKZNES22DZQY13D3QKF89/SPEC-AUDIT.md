---
task: 01M51YKZNES22DZQY13D3QKF89
type: spec_audit
author_role: spec_auditor
status: ready
verdict: fail
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py, tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py, tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py, tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py, tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py, tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py, tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py, tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py, tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py, tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py, tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py, tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py, tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py, tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py, tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py, tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py, tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py, tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py, tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py, tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py, tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py, tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py, tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py, tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py, tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py, tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py, tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py, tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py, tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py, tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py, tests/test_full_suite_profile_timeout.py, tests/test_invariants.py, tests/test_project_profile_gates.py, tests/test_sandbox.py; в) пути-признаки (гейты): orchestrator/fsm_autogate.py; в) защищённые пути: tests/test_invariants.py; г) budget_usd 60 ≥ 45; д) ТЗ ссылается на ADR: ADR-0002, ADR-0023"
spec_sha: f66310826d16763be4918533fefca061a87f0134
schema_version: 5
---

# SPEC-AUDIT: D1а: код проекта в одноразовом контейнере Docker (круг 2)

## ТЗ и SPEC
Решения ANSWER-1 (ответы 1–5 и «закрыть в SPEC» отклонения аудита) в SPEC
перенесены: `project_profile.py` в зонах, вывод проекта/задачи из `cwd` и
`task_id`, гейт мержа в п.6/AC-14, `image` только при `required` с
`test_profile`, фикстуры на `sandbox: off` отдельным требованием 9,
том кэша в D1а-1, «полный набор зелёный» — в «Не входит» с пометкой
«держит пульт», точный набор флагов (AC-7), `-e ИМЯ=значение` (AC-9),
`realpath(workdir)` в момент прогона (AC-4). Отклонения 1–9 прошлого
визита закрыты по существу, кроме указанного ниже.

Расхождения:
1. **ТЗ п.4 «прогон на хосте вместо контейнера запрещён (fail-closed)»
   против правила SPEC требования 3 «`cwd`, не заданный … — путь артели,
   как сейчас».** По коду `cwd` не задают `orchestrator/amend.py:715`
   (`acceptance.collect(tdir)`) и `:718` (`acceptance.run(tdir)`) —
   путь `_amend_plank_only`, который проходит любая задача без перечня
   долгоживущих файлов, в том числе задача внешнего проекта
   (`amend.py:620-686`; `tdir = wt_path / "tasks" / task_id`, `:626`).
   При `cwd=None` прогон идёт с `config.ROOT` (`acceptance.py:439`,
   `:550`) — по правилу SPEC это «путь артели», т.е. планка внешнего
   `required`-проекта исполняется на хосте с полным окружением пульта.
   Буквальное выполнение SPEC нарушает п.4 ТЗ. Чинится без правки
   вызывающих (например, проект/задача из `tdir`, когда `cwd` не задан),
   но SPEC обязан это сказать.
2. **ТЗ п.4/цель задачи против неполного перечня мест запуска.** Восьмое
   место исполнения кода проекта — `orchestrator/advance_gates/two_sided.py:227-235`
   (`subprocess.run(acceptance._pytest_command(...), cwd=tree,
   env=acceptance._pytest_env())`), двусторонний прогон смены ожидания;
   зовётся для внешних проектов с профилем (`advance_gates/test_integrity.py:1495-1528`,
   `two_sided.run(workspace.task_repo(task_id), …)`) и в наблюдении
   (`test_integrity.py:1429`). Дерево — `git worktree` клона проекта во
   временном каталоге: код проекта на хосте, окружение пульта целиком,
   интерпретатор пульта. ТЗ перечисляет семь мест и утверждает, что гейты
   «сами процессов не запускают» — это неверно для `two_sided.py`; SPEC
   повторяет перечень, файла нет ни в зонах, ни в «Не входит». Решать
   Оператору (зона или явное «не входит» с fail-closed отказом при
   `required`), но SPEC обязан это место назвать.
Требований сверх ТЗ не найдено (п.9 о фикстурах — из ANSWER-1, ответ 3).

## Факты против кода
Подтвердилось: `acceptance.py:35-65`, `:69-89`, места `:448`, `:556`,
`:665`, `:932`, `:1324`, `:1345`, `:1373`, `:1172`, `:1176`, `:1847-1848`;
`fsm_autogate.py:326`; `fsm.py:1294`; `fsm_merge_gate.py:962-967`;
`project_profile.py:63-74` (`Profile` без новых полей); `workspace.py:146-150`
(`path` = `projects_root()/<target>/worktrees/<id>`); `targets.py:41-53`,
`:99-100` (`load` проверяет каждую запись); `targets.yaml:43` —
`sandbox: off`; `tests/test_acceptance_collect.py:57`,
`tests/test_acceptance_seed_repeat.py:82` — временный `cwd`; перечень 35
файлов требования 9 совпадает с `grep -l "test_profile:" tests/*.py`.

Не подтвердилось / неточно:
1. **Перечень фикстур требования 9 («сверено по коду main») неполон.**
   Запись `test_profile` без `sandbox` строят и файлы без литерала
   `test_profile:`:
   - своя запись проекта + `ARTEL_TEST_PROFILE` из `tests/sandbox.py`:
     `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py:43-52,110-112`,
     `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py:168`,
     `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py:43`,
     `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:202`,
     `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py:117`,
     `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py:91`,
     `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py:107`,
     `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py:311`. После
     правки такая запись — `required` с профилем без `image`, и
     `targets.load` (`targets.py:99-100`) отказывает всему файлу. Правило
     SPEC «файл, берущий запись из `tests/sandbox.py` (`ARTEL_TEST_PROFILE`/
     `artel_target_entry`), правится, только если пишет `test_profile`
     сам» эти файлы из правки исключает. Дописать `sandbox: off` в сам
     `ARTEL_TEST_PROFILE` нельзя без двойного ключа в `artel_target_entry`
     (`tests/sandbox.py:1097-1104`: `_PROJECT_TARGET_ENTRY`, который по
     требованию 9 тоже получает `sandbox: off`, + `ARTEL_TEST_PROFILE`).
   - dict-записи: `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:120`
     (`targets.check(name, dict(base_entry(name), test_profile=profile))`
     ждёт успеха) и `:123-124` (тот же профиль в файл, затем
     `targets.load()`); `base_entry` (`:31-34`) — без `sandbox`, профиль
     `random_profile` — без `image`. По новому правилу — отказ; SPEC
     запрещает править `base_entry` и утверждения, а правка входа внутри
     тела метода (`:120`, `:124`) по букве требования 9 («входные строки
     фикстур») не названа. Строка 3 матрицы ANSWER-1 («тот же тест без
     правки») этим фактом опровергается.
2. `tests/test_invariants.py` (защищённый путь, `config.py:756`) стоит в
   перечне требования 9, но `test_profile:` в нём только в комментарии
   (`:187`); запись он берёт `seed_artel_targets()` (`:189`). Правка ему не
   нужна, а перечень приглашает править защищённый файл без оговорки
   о приложении PLAN.
3. «Полный набор — из своего `task_id`» (SPEC требование 3; D1а-2,
   требование 1): у `_run_full_suite_now` (`acceptance.py:1313`),
   `_run_full_suite_to_log` (`:1361`) и `run_full_suite` (`:1115`)
   параметра `task_id` нет; `suite_run.py:524`, `:564` зовут
   `run_full_suite` без задачи, база `suite-run` идёт во временной копии
   (`suite_run.py:474`, `mkdtemp`). Источник есть —
   `suite_lock.my_task_id()` (`suite_lock.py:155-163`), — но SPEC его не
   называет; «из `cwd`» для полного набора не годится (корни — временные
   каталоги `appendix_tree.py:272`, `fsm_merge_gate` scratch).
4. Поведение прогона у `sandbox: required` записи без `test_profile` (нет
   `image`) не определено. Сегодня такой внешний проект гоняет планку
   командой пульта (`advance_gates/acceptance.py:387-405`, `command=None`);
   отсутствие `sandbox` теперь значит `required`, а образа нет. Отказ —
   меняет поведение сценариев с записями без профиля (не в перечне
   требования 9); прогон на хосте — нарушает ТЗ п.4.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `entry.get("sandbox", "off")`; исключение по имени `artel`; отказ без имени записи/поля |
| AC-2 | да | при `off` очищено/урезано окружение, пропал `-p timeout`, сменён `cwd`; вызов `docker` при `off`. Не ловит: место запуска вне семи (`amend.py:715,718` с `cwd=None` для внешнего проекта, `two_sided.py:234`) — см. «ТЗ и SPEC» 1–2 |
| AC-3 | да | сверка секрета подстрокой; `image` не требуется при `required`+профиль; `image` требуется без профиля; лексический `workdir` с `..` |
| AC-4 | да | `realpath` только в `targets.check`; симлинк в рабочей копии уводит `workdir` наружу и прогон идёт |
| AC-5 | частично | имя контейнера без проекта; `cwd` в области проекта вне раскладки идёт на хост. Не ловит: `cwd=None` при планке внешнего проекта (`amend.py:715-718`) — AC прямо относит его к пути артели |
| AC-6 | да | интерпретатор пульта/`-p timeout` при `pytest-own`; пропал `--junitxml`/`-p no:cacheprovider` |
| AC-7 | да | лишний флаг (`--privileged`, второй `--network`, `--env-file`); пропуск `--cap-drop ALL` |
| AC-8 | да | лишнее монтирование (сокет, `~/.ssh`); `.git` без `ro` |
| AC-9 | да | `-e ИМЯ` без значения; имя вне перечня; значение переменной пульта |
| AC-10 | да | нет `docker kill` в `except`/по таймауту; нет проверки отсутствия |
| AC-11 | да | код 125 как красные тесты; хостовый фолбэк |
| AC-12 | да | хеш пишется до успешной установки; установка при неизменном хеше; `--network none` у установки |
| AC-13 | да | `root/tests` при `pytest-own`; `-n/-p xdist` дописан |
| AC-14 | да | автогейт/`approve`/гейт мержа без `runner`/`workdir` профиля |
| AC-15 | да | проверки Docker при `off`; нет команды сборки |
| AC-16 | ручной | — (живой Docker, PLAN) |
| AC-17 | ручной | — (живой Docker, PLAN) |

## Зоны
1. `orchestrator/project_profile.py` в зонах — отклонение 3 прошлого
   визита закрыто; вызывающие вне зон по ответу 1 ANSWER-1.
2. `orchestrator/advance_gates/two_sided.py` — место исполнения кода
   проекта (см. «ТЗ и SPEC» 2) — ни в зонах, ни в «Не входит».
3. Перечень требования 9 не покрывает 9 файлов `tests/` («Факты против
   кода» 1): зона `tests/` их включает, но правило требования 9 правку
   запрещает — разработчик либо нарушит SPEC, либо эскалирует.
4. Защищённый `tests/test_invariants.py` в перечне без оговорки
   «только приложением PLAN» (`config.py:754-760`); по коду правка ему не
   нужна.
5. Песочница ролей не расширяется; `targets.yaml`, `docs/backlog.md`,
   `fsm_merge_gate.py`, `targets.py` (в D1а-2) — только чтение, верно.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Фикстуры перечня требования 9 получают `sandbox: off` | сценарии артели и внешних проектов, `tests/sandbox.py:1057-1104` | да, путь `off` | те же тесты без правки утверждений | ок (ANSWER-1, ответ 3) |
| Сквозной сценарий внешнего проекта идёт путём `off` | `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py:346-474` | для `off`; `required` — модульно | новые тесты с подставным `docker` (AC-7…AC-11) | ок, ослабление названо в SPEC (требование 9) |
| Проверка: `required` + профиль без `image` — отказ | «запись с профилем годна»: `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:120`, `:123-128` | нет без правки входа внутри тела метода (`base_entry` + профиль без `image` и без `sandbox`) | не покрыто: SPEC запрещает правку `base_entry`, ANSWER-1 считает тест неизменным | вопрос Оператору / правка требования 9 |
| Запись своя + `ARTEL_TEST_PROFILE` без `sandbox` | 8 файлов, «Факты против кода» 1 (напр. `merge_gate_applied.py:110-112`) | нет: `targets.load` отказывает (`targets.py:99-100`) | не покрыто: файлов нет в перечне, правило требования 9 исключает их правку | правка требования 9 |
| Внешний проект без профиля: прогон планки | `advance_gates/acceptance.py:387-405` (`command=None`) | не определено (`required` без `image`) | не покрыто | вопрос Оператору |

## Пути обхода гейтов
1. **Хостовый прогон через `cwd=None`.** Разработчик, исполняя правило
   «`cwd` не задан — путь артели» буквально, оставляет
   `amend.py:715-718` (`amend-tests` внешнего проекта без долгоживущих
   файлов) на хосте; AC-5 это прямо разрешает, AC-2 зелёный.
2. **Двусторонний прогон** (`two_sided.py:227-235`) остаётся хостовым для
   внешнего `required`-проекта: ни одно AC его не трогает.
3. **Повторное использование итога полного набора.** Ключ
   `suite_result_key` (`acceptance.py:1609-1640`) строится из
   `_pytest_command` пульта, `tests`, `-n/-p xdist` и не несёт ни
   `image`, ни режима `sandbox`/`runner`; `full_suite` отдаёт сохранённый
   итог «gate» без прогона (`acceptance.py:1740-1758`). Итог, полученный
   до смены образа (или вне контейнера), засчитывается гейту. Для D1а-2
   SPEC должен сказать, входят ли `image`/`runner`/`workdir` в ключ.

## Вердикт
fail — SPEC в нынешнем виде ведёт к прогону кода внешнего `required`-проекта
на хосте (против ТЗ п.4) и к гарантированной эскалации разработчика из-за
неполного перечня фикстур. Отклонения:
1. Правило «`cwd` не задан — путь артели» (SPEC требование 3, AC-5) при
   `orchestrator/amend.py:715,718` гоняет планку внешнего проекта на хосте
   (`acceptance.py:439,550`) — нарушение ТЗ п.4.
2. Восьмое место запуска `orchestrator/advance_gates/two_sided.py:227-235`
   (зовётся из `advance_gates/test_integrity.py:1429,1527`) не названо ни
   в требованиях, ни в зонах, ни в «Не входит» — нужно решение Оператора.
3. Перечень файлов фикстур требования 9 неполон:
   `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:120,123-124`
   (dict-записи; опровергает строку 3 матрицы ANSWER-1) и 8 файлов со
   своей записью + `ARTEL_TEST_PROFILE` (`merge_gate_applied.py:110-112`,
   `main_ci.py:168`, `project_docs_ref.py:43`, `project_area.py:202`,
   `merge_gate_merge_after.py:117`, `merge_gate_in_base.py:91`,
   `postmerge_map_interpreter.py:107`, `preflight.py:311`); правило
   «файл, берущий запись из `tests/sandbox.py`, не правится» их правку
   запрещает.
4. Поведение прогона у `required`-записи без `test_profile` (нет `image`)
   не определено (`advance_gates/acceptance.py:387-405`).
5. Источник задачи для `_run_full_suite_now`/`_run_full_suite_to_log`
   (`acceptance.py:1313,1361`) не назван: параметра `task_id` нет,
   `suite_run.py:524,564` зовут без задачи; годится
   `suite_lock.my_task_id()` (`suite_lock.py:155`).
6. Ключ повторного использования итога полного набора
   (`acceptance.py:1609-1640`, `:1740-1758`) не учитывает `image`/
   `runner`/`workdir` — сохранённый итог прошлого образа засчитывается.
7. Мелкое: защищённый `tests/test_invariants.py` в перечне требования 9
   без оговорки о приложении PLAN, хотя `test_profile:` в нём только
   в комментарии (`:187`).
