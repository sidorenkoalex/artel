---
task: 01M51YKZNES22DZQY13D3QKF89
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py, tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py, tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py, tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py, tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py, tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py, tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py, tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py, tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py, tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py, tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py, tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py, tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py, tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py, tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py, tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py, tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py, tests/test_01m45fk56dwmnbrka1vwm12h19_spec_zones.py, tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py, tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py, tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py, tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py, tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py, tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py, tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py, tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py, tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py, tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py, tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py, tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py, tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py, tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py, tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py, tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py, tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py, tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py, tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py, tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py, tests/test_full_suite_profile_timeout.py, tests/test_invariants.py, tests/test_project_profile_gates.py, tests/test_sandbox.py; в) пути-признаки (гейты): orchestrator/advance_gates/plan_appendix.py, orchestrator/advance_gates/two_sided.py, orchestrator/fsm_autogate.py; в) защищённые пути: tests/test_invariants.py; в) SPEC требует приложения PLAN; г) budget_usd 60 ≥ 45; д) ТЗ ссылается на ADR: ADR-0002, ADR-0023."
spec_sha: 3e389bdbb1086d40b1aa58fda147b33d68ef2491
schema_version: 5
---

# SPEC-AUDIT: D1а: код проекта в одноразовом контейнере Docker (круг 2)

Визит 3. Проверен SPEC.md с sha содержимого
3e389bdbb1086d40b1aa58fda147b33d68ef2491 (`git hash-object` совпал).
Отклонения визита 2 (перечень фикстур, строка 3 матрицы ANSWER-1,
`amend.py:715,718`, восьмое место запуска, `required` без профиля,
задача полного набора, `test_invariants.py`) в SPEC закрыты; ниже — что
осталось и что нашлось заново.

## ТЗ и SPEC

ТЗ → SPEC: пп. 1–8 ТЗ и критерии приёмки ТЗ перенесены (треб. 1–3, 7, 8,
11–13; AC-1–AC-22). Решения ANSWER-1 (1–5) и ANSWER-2 (1–7) отражены:
носитель `Profile` (треб. 2), гейт мержа без правки `fsm_merge_gate.py`
(треб. 11), `image` только при `required` + профиль (треб. 2, AC-3),
правило фикстур и явное ослабление сквозного сценария (треб. 14), том
кэша в первой части с контейнером (деление, D1а-1б п.1), отказ стороны
`two_sided` (треб. 6), отказ `required` без профиля/`image` (треб. 5),
выбор по проекту задачи (треб. 4), `suite_lock.my_task_id()` (треб. 10),
ключ (треб. 9), восьмое место в фиксации (треб. 1, AC-2). Деление на 3
части — по рамке ТЗ и ANSWER-2 ответ 4 («деление на большее число частей
допускается»).

SPEC → ТЗ: требований вне ТЗ/ответов нет. Отступление от буквы ANSWER-2
ответ 4: `advance_gates/plan_appendix.py:58` выведен из перечня временных
деревьев прогона (SPEC треб. 4, последний абзац) — подтверждено кодом:
`plan_appendix.py:58-65` заводит worktree только для `git apply`, модуль
не импортирует `acceptance` (карта). Отступление обосновано, отклонением
не считаю.

Расхождение: ТЗ п.5 и SPEC треб. 8 не называют, какие файлы — «файлы
блокировки в `workdir`» (`uv.lock`? `poetry.lock`? `requirements*.txt`?),
и где живёт результат установки. Хеш хранится на проект
(`.artel/projects/<имя>/`), а деревья прогона разные (рабочие копии задач,
`suite_run.py:474` `_base_copy`, `appendix_tree.py:272`,
`fsm_merge_gate.py:191`, контейнеры `--rm`): если `install` ставит
зависимости в каталог дерева (типично `uv sync` → `.venv` в проекте),
вторая рабочая копия при неизменном хеше остаётся без зависимостей. Рабочим
вариант будет, только если цель установки — в томе кэша (например,
`UV_PROJECT_ENVIRONMENT` через `test_profile.env`), но SPEC этого не
говорит. → отклонение 5.

## Факты против кода

Подтвердилось (рабочий каталог, `daec8455`-карта):
- `acceptance.py:35-65` `_pytest_command` (venv пульта, `-p timeout`),
  `:69-89` `_pytest_env` (`dict(os.environ)`), места `:448`, `:556`,
  `:665`, `:932`, `:1324`, `:1345`, `:1373`; `:1172` `root / "tests"`,
  `:1175-1176` `-n … -p xdist`; `:1609-1640` `suite_result_key`;
  `:1740-1758` повторное использование; `:1847-1848` `full_suite(root,
  task_id)` без `command`; `:439` `cwd=None` → `config.ROOT`.
- `two_sided.py:222-240` `_run_side` (`subprocess.run`, `_pytest_env`),
  `:300` `tempfile.mkdtemp` + `git worktree add`; сбой стороны → строка
  `refusals` (`two_sided.py:341-349`) → `GateRefusal`
  (`test_integrity.py:1532-1535`) — AC-14 реализуем.
- `test_integrity.py:1429` (наблюдение), `:1527` (гейт); `fsm.py:212`,
  `:266`, `:688`, `:885`, `:1294`; `fsm_autogate.py:326`;
  `fsm_merge_gate.py:191`, `:682`, `:962-967`; `runner.py:570`,
  `pull_main.py:69`, `fsm_advance.py:746`, `canary.py:1376` — все зовут
  `fsm._pull_main_or_escalate`; `cmd_advance` — единственный вход
  `_cmd_advance` (`fsm.py:717,743`; вызывающие `artel.py:1952`,
  `runner.py:193`, `auto.py:480,810`).
- `amend.py:626`, `:715`, `:718` (`collect(tdir)`/`run(tdir)` без `cwd`).
- `suite_lock.py:155` `my_task_id`; `targets.py:41-53`, `:99-100`;
  `project_profile.py:63-74`; `workspace.py:146-150`;
  `advance_gates/acceptance.py:363,378`; `appendix_tree.py:272`;
  `suite_run.py:474,524,564`.
- `targets.yaml:43` `sandbox: off`; в `targets.yaml` одна запись — `artel`.
  `yamlmini.scalar` отдаёт `off` строкой `'off'`, вложенное отображение
  `env` разбирается уже сейчас (проверено вызовом `yamlmini.mapping`).
- Перечень фикстур треб. 14: `grep -l "test_profile:" tests/*.py` — 35
  файлов, минус `test_invariants.py` = 34; `ARTEL_TEST_PROFILE` — 12
  файлов, из них 8 вне первого списка; dict-записи — `test_profile.py:120,
  124, 149, 166`. Итого 43 — совпадает.

Неточности (несущественные): `random_profile` —
`test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:37`, не `:38`; в
матрице ANSWER-2 «42 файла» против 43 в SPEC.

Не подтвердилось / не учтено SPEC:
- Носитель `sandbox`. SPEC треб. 2 требует, чтобы `sandbox` доходил до
  потребителей полем `project_profile.Profile`, и запрещает
  `targets.target()` в обход `project_profile`. Но `Profile` строится
  только из подполей `test_profile` (`project_profile.py:63-85`,
  `repo_context.profile_of`, `repo_context.py:139-151`), а `sandbox` —
  поле записи. У записи `required` без `test_profile` (треб. 5, AC-7)
  `Profile` нет вовсе (`decide` → `skip`, `project_profile.py:145-146`).
  Откуда тогда функции запуска узнают `required`, SPEC не называет. →
  отклонение 4.
- «Проект задачи не определён» (треб. 4, AC-6). В коде проект задачи не
  бывает «не определён»: `store.task_target` (`store.py:701-707`) и
  `workspace.task_target` (`workspace.py:52-58`) при отсутствии строки
  задачи или БД отдают артель, `full_suite` без БД берёт
  `config.DEFAULT_TARGET` (`acceptance.py:1727-1729`). Если реализовать
  через эти функции, ветка отказа AC-6 мертва (fail-open: задача без
  строки → путь артели на хосте). Если ввести строгое «нет строки → отказ»,
  ломается путь артели в тестах без БД (`full_suite(self.root,
  "ENV-FAIL")`, `tests/test_full_suite_reuse.py:46`) — это противоречит
  AC-2. SPEC не определяет «не определён». → отклонение 3.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `sandbox: maybe` пропущен; запись без поля трактуется как `off` (видно по отказу `image` у записи с профилем без `sandbox`) |
| AC-2 | да | `_pytest_env` без `PYTHONPYCACHEPREFIX`; потерян `-p timeout` у артели; `cwd` у `run(cwd=None)` не `config.ROOT`; при `off` вызван `docker` |
| AC-3 | частично | секрет по подстроке отказан; `image` не требуется при `required`. «Выход `workdir` за рабочую копию после `realpath`» на этапе `targets.check` не имеет базы: рабочей копии у записи на этапе проверки нет (`targets.check(name, entry)`, `targets.py:139`), клона в тестах может не быть — тест поймает только `..`/абсолютный путь; символические ссылки — только AC-4 |
| AC-4 | да | проверка `realpath(workdir)` только при `targets.check`, не в момент прогона |
| AC-5 | да | пропущена постановка контекста в `cmd_amend_tests` или `cmd_plank_run`; прогон во временном дереве вне `.artel/projects/` уходит на хост |
| AC-6 | нет в первой фразе | «проект не определён» не задан (отклонение 3) — нет входа, на котором тест отличит отказ от пути артели; вторая и третья фразы проверяемы |
| AC-7 | да | `required` без `image` запускает `docker` с пустым образом; без профиля — pytest на хосте |
| AC-8 | да | `pytest-own` оставил `-p timeout`/интерпретатор пульта; потерян `-p no:cacheprovider` |
| AC-9 | да | лишний `--privileged`/второй `--network`; `--network host` |
| AC-10 | да, но см. отклонение 1 | монтирование `~/.ssh`/сокета; `.git` на запись. Не ловит монтирование корня пульта как «каталога прогона» (`amend.py:715,718`) |
| AC-11 | да | `-e PATH` без значения; утечка выставленной в окружении пульта переменной |
| AC-12 | да для точечных мест | нет `docker kill` по таймауту; kill по другому имени. Для полного набора — ни в одной части (отклонение 2) |
| AC-13 | да для точечных мест | код 125 засчитан красным прогоном; повтор на хосте. Для полного набора — ни в одной части (отклонение 2) |
| AC-14 | да | `_run_side` при `required` гоняет pytest на хосте; отказ стороны не попадает в `refusals` |
| AC-15 | частично | повторная установка при неизменном хеше ловится; но «файлы блокировки» не названы (отклонение 5) — тест сам выберет набор, мутация «хеш не включает `uv.lock`» не ловится, если тест выбрал другой файл |
| AC-16 | частично | `-n xdist` при `pytest-own` ловится; как сочетаются `workdir` и `long_lived_dir` (оба относительно корня репозитория?) — не задано, точный argv тест зафиксировать не может (отклонение 6) |
| AC-17 | да | `_run_full_suite_*` при задаче внешнего `required` идёт на хосте; `None` даёт отказ |
| AC-18 | да | ключ без `image`; ключ артели сменился. Не ловит пересборку образа под тем же тегом (отклонение 7) |
| AC-19 | да | автогейт зовёт `full_suite` без команды профиля внешнего проекта |
| AC-20 | частично | неотвечающий демон, нет образа — ловится; живая проба треб. 12 (сеть, переменные) автоматическим критерием не покрыта, только ручной пробой D1а-2 |
| AC-21 | ручной | — |
| AC-22 | ручной | — |

## Зоны

Зоны родителя (frontmatter) покрывают требования: `sandbox.py`,
`acceptance.py`, `targets.py`, `config.py`, `project_profile.py`,
`two_sided.py`, точки входа `fsm.py`/`amend.py`/`plank_run.py` (ANSWER-2
ответ 4 разрешил поимённо), `fsm_autogate.py`, `doctor/`, `tests/`.
Защищённых путей в зонах нет; `tests/test_invariants.py` исключён с
пометкой «только приложением PLAN» — по коду правка не нужна
(`test_invariants.py:187-189` → `seed_artel_targets()` →
`_PROJECT_TARGET_ENTRY`, `tests/sandbox.py:1057`, получающий `off`).
Песочница ролей не расширяется.

Зоны частей: D1а-1а (`targets.py`, `project_profile.py`, `tests/`),
D1а-1б, D1а-2 — достаточны для своих требований; `suite_run.py`,
`fsm_merge_gate.py` — только чтение, и правка им не нужна при выводе
задачи из `suite_lock.my_task_id()` и профиля по `task_id` внутри
`full_suite`.

Замечание по зоне `amend.py`: правка там ограничена «постановкой контекста
или передачей задачи» (треб. 4). Закрыть отклонение 1 передачей `cwd` в
`amend.py:715,718` эта формулировка не разрешает; решение — либо внутри
`acceptance.run/collect` (каталог прогона при `cwd=None` и `required` —
рабочая копия задачи, а не `config.ROOT`), либо явное разрешение
Оператора.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `runner: pytest-own` снимает `-p timeout` и `-o timeout=…` | Таймаут отдельного теста и громкий отказ при отсутствии `pytest-timeout`, `acceptance.py:41-51,63-65`, `:409-418` | не остаётся для `pytest-own`; остаётся общий таймаут прогона (`ACCEPTANCE_TIMEOUT_SEC`, предел полного набора) | общий таймаут + `docker kill` (AC-12); отдельный тест — не покрыто | ослабление задано ТЗ п.2 прямо; в SPEC строки нет — назвать явно на гейте |
| Отсутствие `sandbox` = `required` | Сегодня запись без поля — прогон на хосте | ужесточение | AC-1, AC-7 | ок |
| Фикстуры `tests/` получают `sandbox: off` (43 файла) | Сценарии артели и внешнего проекта хостовым путём, ANSWER-1/ANSWER-2 матрицы | остаётся для `off`; путь `required` сквозным тестом не покрыт | новые модульные тесты с подставным `docker` (AC-5, AC-9–AC-14) | решено ANSWER-1 ответ 3, ANSWER-2 ответ 3; мандата нет — на гейте |
| `two_sided._run_side` при `required` — отказ стороны | Двусторонний прогон, `test_integrity.py:1527`; `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py` | для `required` проверка недоступна, переход отказывает | AC-14 | решено ANSWER-2 ответ 1 |
| Ключ `suite_result_key` при `required` | Повтор только на том же дереве, Python, пакетах и команде, `acceptance.py:1632-1635` | частично: «пакеты» пульта для контейнера ничего не говорят, содержимое образа в ключ не входит | AC-18 — по имени образа с тегом; пересборка образа под тем же тегом — не покрыто | отклонение 7 |
| Полный набор в контейнере: таймаут и отказ Docker | Таймаут полного набора снимает группу процессов, `acceptance.py:1330-1338`, `:1384-1391` (`_kill_group`) | под контейнером `killpg` снимает только клиент `docker`, контейнер продолжает работать | треб. 7 требует `docker kill`, но AC-12/AC-13 для полного набора не входят ни в одну часть | отклонение 2 |
| Наблюдение полного набора (`_process_snapshot`, `_workers`) | `acceptance.py:189-288`, `:1329-1342` | процессы контейнера (VM Docker Desktop) снимок хоста не видит — «работает как сейчас» (треб. 7) буквально невыполнимо, метрики числа процессов станут неверны | не покрыто | уточнить на гейте: метрики наблюдения при `required` — как есть или с пометкой |

## Пути обхода гейтов

1. **Корень пульта как «каталог прогона».** `amend.py:715,718` зовут
   `collect(tdir)`/`run(tdir)` без `cwd`, и каталог прогона —
   `config.ROOT` (`acceptance.py:439`), корень пульта с `.artel/state.db`,
   журналами и областями всех проектов. Треб. 3 / AC-10: «каталог прогона
   монтируется по тому же пути на запись», «других монтирований нет».
   Исполнитель, выполнив SPEC буквально, смонтирует корень пульта на запись
   в контейнер внешнего проекта; AC-10 это пропустит (монтирование ровно
   «каталог прогона»), а свойство треб. 3 «БД и журналы пульта в контейнер
   не попадают» нарушено. → отклонение 1.
2. **Окно между частями.** После D1а-1б полный набор (`_run_full_suite_*`)
   у `required`-проекта ещё идёт на хосте до D1а-2 (D1а-1б «Не входит»:
   полный набор). Записей `required` в `targets.yaml` сейчас нет, но
   порядок D2 (sled) относительно D1а-2 SPEC не закрепляет: подключённый
   после D1а-1б sled гонял бы полный набор интерпретатором пульта на хосте.
   → в отклонение 2 (порядок мержа: D2 не раньше D1а-2).
3. **Повтор итога после пересборки образа.** Ключ при `required` несёт
   `image` «имя с тегом» (треб. 9). Образ, пересобранный Оператором под тем
   же тегом (сломанный или с другими версиями пакетов), отдаёт сохранённый
   зелёный итог до `FULL_SUITE_REUSE_MAX_AGE_SEC` без прогона. Сегодня ту же
   роль для хоста играет отпечаток пакетов (`acceptance.py:1632-1633`). →
   отклонение 7.
4. **Мёртвая ветка отказа.** «Контекст есть, проект не определён» при
   реализации через `store.task_target`/`workspace.task_target` никогда не
   срабатывает: отсутствие строки задачи → артель → хост. → отклонение 3.

## Вердикт

**concerns** — SPEC вести дальше можно, отклонения решаемы Оператором на
гейте (уточнением SPEC или строкой решения):

1. **Каталог прогона = корень пульта** (`amend.py:715,718`;
   `acceptance.py:439`; SPEC треб. 3, треб. 4, AC-10). При `required` и
   `cwd=None` SPEC не говорит, что монтируется; буквальное исполнение
   монтирует `config.ROOT` с БД пульта. Нужно: правило «каталог прогона при
   `required` не может быть `config.ROOT` или содержать `.artel/` пульта» с
   критерием (подставной `docker` не получает `-v` на `config.ROOT`), и
   источник каталога для `cwd=None` (рабочая копия задачи) — внутри
   `acceptance.py` либо разрешением передать `cwd` в `amend.py`.
2. **Критерии полного набора потеряны при делении** (SPEC «Деление»,
   D1а-1б «Критерии приёмки: … для точечных мест», D1а-2 «Критерии
   приёмки: AC-2, AC-15–AC-20»). AC-7, AC-9–AC-13 (отказ без `image`,
   точные флаги, монтирования, переменные, `docker kill` по таймауту,
   коды 125–127) для `_run_full_suite_now`/`_run_full_suite_to_log` не
   входят ни в одну часть, а там таймаут сегодня — `_kill_group`
   (`acceptance.py:1334,1388`), который контейнер не снимет. Нужно: в
   D1а-2 — «AC-7, AC-9–AC-13 для полного набора»; порядок D2 не раньше
   D1а-2.
3. **«Проект задачи не определён» не определён** (SPEC треб. 4, AC-6;
   `store.py:701-707`, `workspace.py:52-58`, `acceptance.py:1727-1729`).
   Нужно: назвать условие (нет строки задачи / БД непригодна / имени нет в
   `targets.yaml`) и как оно сочетается с сегодняшней деградацией «нет БД —
   артель» и AC-2.
4. **Носитель `sandbox` у записи без профиля** (SPEC треб. 2;
   `project_profile.py:63-85,145-146`; `repo_context.py:139-151`). `Profile`
   есть только при `test_profile`, а треб. 5 требует знать `required` у
   записи без него. Нужно: функция `project_profile` (не поле `Profile`),
   отдающая `sandbox` записи, — и снятие запрета чтения в этом месте.
5. **Файлы блокировки и цель установки** (SPEC треб. 8, AC-15). Нужно:
   перечень файлов блокировки (или подполе профиля) и правило, где лежат
   установленные зависимости, чтобы хеш на проект был верен для любого
   дерева прогона (рабочие копии, `suite_run.py:474`, `appendix_tree.py:272`,
   `fsm_merge_gate.py:191`).
6. **`workdir` и пути прогона** (SPEC треб. 2, треб. 3, AC-16, AC-3).
   Не задано, от чего отсчитываются `long_lived_dir` и долгоживущие пути
   `extra` (`acceptance.py:366` — «пути от `cwd` прогона», сейчас от корня
   репозитория), когда рабочий каталог контейнера — `workdir`; и база
   `realpath` в `targets.check`, где рабочей копии нет. Нужно: одна строка
   правила (например, «все пути профиля — от корня репозитория, пульт
   переводит их в абсолютные»).
7. **Ключ повторного использования и пересборка образа** (SPEC треб. 9,
   AC-18; `acceptance.py:1632-1635`). Нужно: ID образа (`docker image
   inspect --format {{.Id}}`) вместо или вместе с именем с тегом — либо
   явное решение Оператора, что имя с тегом достаточно.
8. **Матрица**: снятие `-p timeout` при `pytest-own` (таймаут отдельного
   теста) и «наблюдение как сейчас» под контейнером в SPEC строк не имеют
   (`acceptance.py:41-51,409-418`; `:189-288`) — назвать явно на гейте.
