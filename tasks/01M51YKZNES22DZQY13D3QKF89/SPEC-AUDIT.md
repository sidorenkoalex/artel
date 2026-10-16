---
task: 01M51YKZNES22DZQY13D3QKF89
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py, tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py, tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py, tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py, tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py, tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py, tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py, tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py, tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py, tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py, tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py, tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py, tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py, tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py, tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py, tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py, tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py, tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py, tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py, tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py, tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py, tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py, tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py, tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py, tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py, tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py, tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py, tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py, tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py, tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py, tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py, tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py, tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py, tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py, tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py, tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py, tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py, tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py, tests/test_full_suite_profile_timeout.py, tests/test_invariants.py, tests/test_project_profile_gates.py, tests/test_sandbox.py; в) пути-признаки (гейты): orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/plan_appendix.py, orchestrator/advance_gates/two_sided.py, orchestrator/fsm_autogate.py; в) защищённые пути: tests/test_invariants.py; в) SPEC требует приложения PLAN; г) budget_usd 60 ≥ 45; д) ТЗ ссылается на ADR: ADR-0002, ADR-0023."
spec_sha: 5e5c060ba905d29453c09e4aeeb881e08881b861
schema_version: 5
---

# SPEC-AUDIT: D1а: код проекта в одноразовом контейнере Docker (круг 2)

Визит 5. Проверен SPEC.md с sha содержимого
5e5c060ba905d29453c09e4aeeb881e08881b861 (`git hash-object` совпал).
Глубина — полная. Семь отклонений визита 4 закрыты решением Оператора на
гейте SPEC №2 (16.10.2026); их правка в SPEC внесена и сверена по коду,
заново они не поднимаются. Восемь отклонений визита 3 закрыты решением
№1 и тоже не поднимаются. Ниже — сверка и новые находки.

## ТЗ и SPEC

- ТЗ п.1 → треб. 1, AC-1, AC-2: восемь мест вместо семи (ANSWER-2,
  ответ 7). Соответствует.
- ТЗ п.2 → треб. 2, AC-3, AC-8, AC-16. При `required` допустим только
  `pytest-own` (решение №2, п.3), `lock_files` (решение №1, п.5), пути от
  корня репозитория (решение №1, п.6). Соответствует.
- ТЗ п.3 → треб. 3, AC-9–AC-11. Журнал не монтируется, вместо него запрет
  `config.LOGS` (решение №2, п.2). `PYTHONUNBUFFERED=1` для
  `_run_full_suite_to_log` (решение №2, п.1). Соответствует.
- ТЗ п.4 → треб. 7, AC-12, AC-13; для `run_repeat` — треб. 15, AC-23
  (решение №2, п.4). Для остальных мест «отказ, а не красные тесты»
  доведён только до возврата функции, но не до вызывающих — см.
  отклонение 1.
- ТЗ п.5 → треб. 8, AC-15. Отметка — в области проекта, вне дерева
  (решение №2, п.5). Набор флагов и окружение контейнера установки не
  заданы — см. отклонение 2.
- ТЗ п.6 → треб. 11, AC-19, гейт мержа (ANSWER-1, ответ 2).
  Соответствует.
- ТЗ п.7 → треб. 12, AC-20. ТЗ п.8 → треб. 13. Критерии ТЗ → AC-21,
  AC-22 (ручные). Соответствует.
- ANSWER-2, ответ 4 (выбор по задаче, запасной признак — раскладка) →
  треб. 4, AC-5, AC-6. Для полного набора треб. 10 и AC-17 дают «`None` —
  путь артели» без запасного признака. Это расходится с треб. 4 — см.
  отклонение 3.
- Требований сверх ТЗ, ANSWER-1/2 и решений на гейте в SPEC нет.

## Факты против кода

Подтвердилось (рабочий каталог, `29a46cd3`):
- `_kill_group` стоит на `orchestrator/acceptance.py:1332`, `:1337`,
  `:1385`, `:1388`. `PYTHONUNBUFFERED` — `:1368-1372`.
- `run_repeat` — `acceptance.py:649`; пустой список означает «зелёно»
  (`:676-677`). `_seed_repeats_escalate` —
  `advance_gates/acceptance.py:148-187`, единственный вызов из `:425`.
- Ключ base-итога: `suite_run.py:511`, сохранение `:533`, а также
  `acceptance.py:1789-1793`. `suite_result_key` — `acceptance.py:1609-1640`.
- `suite_lock.my_task_id` — `suite_lock.py:155-163`: `None`, когда замок не
  за процессом или запись нечитаема (`_read`, `:52-57`).
- Временные деревья: `advance_gates/acceptance.py:363,378`,
  `suite_run.py:474` (это `tempfile.mkdtemp`, вне `.artel/projects/`),
  `appendix_tree.py:272`, `fsm_merge_gate.py:191`,
  `advance_gates/two_sided.py:300`.
- `config.LOGS = ROOT/.artel/logs` (`config.py:14`). Рабочая копия —
  `.artel/projects/<имя>/worktrees/<id>` (`workspace.py:146-150`), клон —
  `.artel/projects/<имя>/repo` (`repo_context.py:75-79`). Отметка установки
  в `.artel/projects/<проект>/` вне `worktrees/<id>` в смонтированное
  дерево не попадает.
- Остальные ссылки SPEC (места запуска, точки входа `fsm.py:212, 266, 688,
  885, 1294`, `amend.py:626, 715, 718`, `targets.py:41-53`,
  `project_profile.py:63-74`, перечень 43 фикстур) совпадают со сверкой
  визита 4, и код с тех пор не менялся.

Не учтено SPEC (основание для отклонений 1 и 4):
- Вызывающие `acceptance.run` трактуют «не зелено» по-разному.
  `advance_gates/acceptance.py:416-424` пишет «acceptance_tests красные… почини
  код (не тест)». `pull.py:667-672` эскалирует как «приёмочные тесты
  красные». `amend.py:549-559` и `amend.py:718-729` **принимают** «не
  зелено», если падения промаркированы «Красен до реализации», и коммитят
  планку.
- Исход полного набора определяется по префиксу текста
  (`_full_suite_outcome`, `acceptance.py:1064-1077`): всё, что не названо, —
  `FULL_SUITE_RED`.
- В тестах есть записи внешних проектов без `test_profile`, собственными
  литералами, а не через `_PROJECT_TARGET_ENTRY`:
  `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py:45-53,181`
  (класс `ExternalWithoutProfileTest`, `:424`),
  `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:84`,
  `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py:231`,
  `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py:224`,
  `tests/test_git_fixation.py:49`, `tests/test_branch_freshness_gate.py:569`.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `sandbox: "on"` проходит `targets.check`; отсутствие поля даёт `off` для имени `artel` |
| AC-2 | да | при `off` меняется argv, `cwd` или env либо вызывается `docker` |
| AC-3 | да | секрет сверяется подстрокой; `workdir: ../x` проходит; `required` без `image` или с `pult-pytest` по умолчанию проходит |
| AC-4 | да | `realpath` не проверяется, и симлинк наружу доходит до `docker run` |
| AC-5 | да | точка входа не ставит контекст — прогон во временном каталоге идёт на хосте |
| AC-6 | да | нет строки задачи → путь артели вместо отказа |
| AC-7 | да | `required` без `image` запускает pytest на хосте |
| AC-8 | да | `pytest-own` оставляет `-p timeout` или интерпретатор пульта |
| AC-9 | да, для прогона | лишний `--privileged`, потерян `--cap-drop ALL`. Для контейнера установки текст противоречит AC-15 (`--network none`) — отклонение 2 |
| AC-10 | да | `-v` на `config.LOGS/suite-run/<id>`, `~/.ssh` или `config.ROOT` |
| AC-11 | да, для прогона | `-e GH_TOKEN`, `-e PATH` без значения, `--env-file`. Окружение контейнера установки не задано — отклонение 2 |
| AC-12 | да | по таймауту не вызван `docker kill` |
| AC-13 | частично | на уровне возврата функции — да. Что `amend-tests` примет отказ как «красный по маркеру» (`amend.py:718-729`), не ловится — отклонение 1 |
| AC-14 | да | `_run_side` при `required` даёт зелёную сторону или гоняет pytest |
| AC-15 | частично | повтор установки при неизменном хеше, отметка после сбоя, `-v` каталога отметок — ловятся; утечка `-e` пульта в установку с сетью — нет (отклонение 2) |
| AC-16 | да | `pytest-own` берёт `<корень>/tests` или дописывает `-n` |
| AC-17 | частично | `my_task_id()` не читается — ловится; `None` при дереве `required`-проекта уходит на хост — по AC-17 это норма (отклонение 3) |
| AC-18 | да | ключ без ID образа или без хеша `lock_files` |
| AC-19 | да | автогейт зовёт полный набор без `runner`/`workdir` профиля |
| AC-20 | да | `doctor` молчит при неотвечающем демоне |
| AC-21 | ручной | — |
| AC-22 | ручной | — |
| AC-23 | да | отказ `run_repeat` даёт `[]` (зелёный повтор) или эскалацию о зерне |
| AC-24 | да | base-ключ при `required` без полей профиля; при `off` ключ меняется |

## Зоны

- Зоны родителя покрывают требования. `advance_gates/acceptance.py`
  добавлен только для треб. 15 (решение №2, п.4).
- `amend.py` и `pull.py`: первый в зонах только для постановки контекста,
  второй вне зон. Если Оператор решит отклонение 1 правкой вызывающих,
  `amend.py:549-559,718-729` придётся править сверх «только контекст».
  Нужна строка решения, иначе это правка вне разрешённого.
- `run_full_suite` (`acceptance.py:1115-1194`) не входит в «семь функций»,
  но для `pytest-own` его придётся менять: проверка `root / "tests"`
  (`:1172-1174`) и `-n -p xdist` (`:1175-1176`) стоят до
  `_run_full_suite_now`. Файл в зоне, AC-16 требует результата. Не
  отклонение.
- Защищённые пути не трогаются; `tests/test_invariants.py` — только
  приложением PLAN (треб. 14). Песочница ролей не расширяется.
- Деление (D1а-1а / D1а-1б / D1а-2) согласовано с требованиями и зонами
  частей.

## Матрица неослабления

Строки ANSWER-1, ANSWER-2 и решений на гейте на месте. Не хватает строк:

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `acceptance.run` при `required` может вернуть инфраструктурный отказ (Docker) | Обязательный прогон планки в `amend-tests` («инцидент опечатки 03.09»): «не зелено» допускается только как промаркированная краснота, `orchestrator/amend.py:549-559`, `:718-729` | не определено: отказ с `green=False` читается как краснота, и при маркерах планка коммитится без прогона | не покрыто (AC-13 проверяет только возврат функции) | вопрос Оператору (отклонение 1) |
| Контейнер установки `install` с сетью по умолчанию | Секреты пульта не уходят в код проекта: сегодня `install` не исполняется вовсе (`targets.py:41-53`) | не определено: треб. 8 задаёт образ, монтирования и сеть, но не флаги и окружение | не покрыто (AC-15 проверяет образ, монтирования и отсутствие `--network none`) | вопрос Оператору (отклонение 2) |

## Пути обхода гейтов

- П1. `amend-tests` без прогона. Сбор (`amend.py:714`) прошёл, а
  `docker run` прогона вернул 125–127 (демон упал между вызовами) или
  контейнер снят по таймауту. `run` возвращает `(False, «именованный
  отказ»)`, и AC-13 по тексту соблюдён. Но `amend.py:718-729` видит «не
  зелено», находит маркеры «Красен до реализации» и коммитит планку,
  которую не прогоняли. Смягчение: сбор идёт раньше и при недоступном
  Docker или образе падает сам. Окно остаётся для сбоя между сбором и
  прогоном. Отклонение 1.
- П2. Утечка окружения при установке. Треб. 8: «тем же образом и
  монтированиями, но с сетью по умолчанию». Исполнитель вправе собрать
  контейнер установки без `--user`, `--cap-drop ALL` и с окружением пульта
  (`os.environ`, как сегодня `_pytest_env`, `acceptance.py:69-89`). AC-15
  этого не ловит, а AC-9 и AC-11 сформулированы для прогона: AC-9 требует
  `--network none`, установке же по треб. 8 нужна сеть. Код установки
  проекта (скрипты сборки пакетов) получит токены при открытой сети.
  Отклонение 2.
- П3. Полный набор на хосте при `None`. Треб. 10 и AC-17 «`None` — путь
  артели» буквально разрешают хостовый прогон дерева `required`-проекта.
  `None` бывает, когда запись замка нечитаема (`suite_lock.py:52-57`) или
  когда `run_full_suite` вызван вне взятого замка. По треб. 4 и AC-6 в этом
  случае должен сработать запасной признак — раскладка
  `.artel/projects/<проект>/worktrees/<id>` и контейнер. Отклонение 3.

## Вердикт

concerns. Отклонения (решение — за Оператором на гейте):

1. **Инфраструктурный отказ `run` неотличим у вызывающих.** Треб. 7 и
   AC-13 требуют отказа, «отличимого от красных тестов». Но договор
   `run`/`collect` — `(bool, str)`, а канал отказа задан только для
   `run_repeat` (треб. 15). Вызывающие читают `green=False` как красноту.
   `orchestrator/amend.py:549-559` и `:718-729` принимают её при маркерах
   «Красен до реализации» — путь П1. `advance_gates/acceptance.py:416-424`
   и `pull.py:667-672` дают ложную подсказку «почини код». Для полного
   набора SPEC не говорит, в какой исход (`_full_suite_outcome`,
   `orchestrator/acceptance.py:1064-1077`) ляжет отказ; по умолчанию это
   `FULL_SUITE_RED`. Варианты:
   (а) отказ `run` при `required` блокирует `amend-tests` независимо от
   маркеров — правка `amend.py` сверх «только контекст»; вызывающие
   гейтов остаются как есть, переход и так отказан;
   (б) принять риск строкой матрицы: сбор идёт раньше прогона и ловит
   недоступный Docker.
   Для полного набора — назвать исход отказа (например, префикс
   `FULL_SUITE_NOT_STARTED`: без лога и без сохранения итога).
2. **Контейнер установки не закреплён.** Треб. 8
   (`SPEC.md`, «тем же образом и монтированиями, но с сетью по
   умолчанию») и AC-15 не задают флаги (`--rm`, `--name`, `--user`,
   `--cap-drop ALL`, `--security-opt no-new-privileges`, лимиты), окружение
   (закрытый перечень `-e ИМЯ=значение`, без окружения пульта) и предел
   времени с `docker kill`. AC-9 требует `--network none` для «`docker
   run` при `required`», и это противоречит установке. Предложение: AC-9
   (кроме `--network none`), AC-10 и AC-11 распространить на контейнер
   установки явно и задать предел установки константой `config.py`.
3. **`None` в полном наборе — без запасного признака.** Треб. 10 и AC-17
   («`None` — путь артели») расходятся с треб. 4 и AC-6, где без контекста
   задачи решает раскладка каталога (`orchestrator/suite_lock.py:52-57,
   155-163`). Предложение: при `None` действует запасной признак треб. 4.
   Тогда дерево в `.artel/projects/<required>/worktrees/<id>` — контейнер,
   иначе — путь артели, как для `notes`.
4. **Фикстуры без `test_profile`.** Правило треб. 14 касается только
   записей с `test_profile`. Записи внешних проектов без профиля после
   правки станут `required`, и треб. 5 даст им отказ в точечных прогонах:
   `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py:181`
   (`ExternalWithoutProfileTest`, `:424`; переход из `in_dev` доходит до
   `_acceptance_run_refuses`, `orchestrator/fsm_advance.py:803`),
   `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:84`,
   `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py:231`,
   `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py:224`.
   Утверждения в `external_flow.py:452-455` сломаются, если отказ
   использует действие `project_profile.REFUSAL_ACTION`. «Утверждения не
   меняются» и мандата нет, так что разработчику некуда деваться.
   Предложение: распространить правило `sandbox: off` на все записи
   внешних проектов, которые строят тесты (как ANSWER-1, ответ 3: «запись
   внешнего проекта в `external_flow`»), либо назвать имя действия отказа
   треб. 5, отличное от `project_profile.REFUSAL_ACTION`.
