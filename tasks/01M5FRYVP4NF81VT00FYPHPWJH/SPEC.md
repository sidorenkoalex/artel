---
task: 01M5FRYVP4NF81VT00FYPHPWJH
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/acceptance.py, orchestrator/targets.py, orchestrator/fsm.py, orchestrator/advance_gates/mandate.py, orchestrator/advance_gates/outcome_integrity.py, orchestrator/advance_gates/two_sided.py, orchestrator/advance_gates/refusal_classes.py, orchestrator/doctor/orphans.py, orchestrator/liveness.py, tests/
budget_usd: 40
---

# SPEC: G3а-2б-2: запрет повторов через плагины pytest и переносы из приёмок

## Контекст
Шестая часть G3а волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`,
«Решение» п. 4: итог прогона берётся только из отчёта, повторы внутри
прогона запрещены). Сегодня прогон по отчёту (`orchestrator/acceptance.py`,
`_report_argv`) не запрещает плагины повторов pytest (`rerunfailures`,
`flaky`), а в `junit-xml` повторы не видны (`retries` всегда 0) — упавший
и перезапущенный тест выглядит зелёным. Вторая часть задачи — переносы из
независимых проверок приёмок G2б-2, G3а-1а, G3а-1б, G3а-2а: три копии
детали перехода с гейта SPEC, каталоги выписок гейтов без маркера владельца
(записи `git worktree` остаются после обрыва), слишком широкое признание
«Чем покрыто после» в мандате при профиле в границе, дубли текстов
действий гейта неослабления по исходам.

Граница задачи: новое поведение — только у профиля с `from_components` и
`report`; у артели и у записи `test_profile` команды, разбор и исходы
прежние побайтно. Исключения — общая константа детали гейта SPEC (перенос
11, текст не меняется) и маркер владельца выписок (перенос 18, пишется и у
артели, вывод прежний).

## Требования

1. **Запрет повторов в команде.** В `_report_argv`
   (`orchestrator/acceptance.py`) у профиля с `from_components` и `report`
   при команде pytest (`is_pytest_command(head)`) пульт добавляет
   `-p no:rerunfailures -p no:flaky` к каждому прогону. Эти четыре
   элемента стоят сразу за командой профиля (поле `command` записи), до
   аргументов подмножества, целей долгоживущих, `--ignore`,
   `-p no:cacheprovider` и `report_args`. Условие — то же, что
   `advance_gates.acceptance.in_outcome_bounds`
   (`project_profile.reported(profile)` и `from_components`), повторённое в
   `_report_argv` без импорта `in_outcome_bounds` на уровне модуля (круговой
   импорт). `_pytest_command`, команды артели и `test_profile` — прежние
   побайтно.
2. **Признак запрета в ключе итога.** В данные ключа
   `_report_suite_result_key` у профиля из требования 1 добавляется поле
   `"no_rerun_plugins": true`; у прочих профилей данные ключа прежние.
3. **Отказ `targets.check`.** `targets.check` отказывает компоненту записи
   `components:` с `report`, в `command`, `report_args`, `select` или в
   значении `env.PYTEST_ADDOPTS` которого есть запрещённый аргумент.
   Запрещённым считается:
   - элемент, равный `--reruns`, `--reruns-delay`, `--force-flaky`,
     `--max-runs`, или начинающийся с одного из них и `=`;
   - пара соседних элементов `-p`, `<x>` и один элемент, начинающийся с
     `-p`, где `<имя>` — второй элемент пары или остаток элемента после
     `-p`, со снятыми пробельными символами по краям, и `<имя>` —
     `rerunfailures`, `pytest_rerunfailures`, `flaky` или
     `flaky.flaky_pytest_plugin` (то есть `-p`, `" rerunfailures"` и один
     элемент `"-p rerunfailures"` — тоже запрещённый аргумент).
   Значение `env.PYTEST_ADDOPTS` разбивается по правилам командной строки
   POSIX (модуль `shlex`), к элементам применяется то же правило. Кроме
   того, `targets.check` отказывает компоненту с `report`, у которого в
   `env.PYTEST_PLUGINS` (значение разбивается по запятой, у частей сняты
   пробельные символы по краям) есть часть `rerunfailures`,
   `pytest_rerunfailures`, `flaky` или `flaky.flaky_pytest_plugin`. Запись
   `test_profile` не проверяется.
4. **Перенос 11 — одна деталь гейта SPEC.** Единственный источник детали
   — константа `advance_gates.tests_writing.SPEC_GATE_PASSED_DETAIL`;
   `orchestrator/fsm.py` пишет деталь перехода из неё (импорт из
   `advance_gates.tests_writing` внутри функции, как `fsm.py:792`, не на
   уровне модуля: `advance_gates/acceptance.py` импортирует `fsm` на
   уровне модуля, модульный импорт дал бы цикл), литерала «гейт SPEC пройден —
   приёмочные тесты до кода» в тексте `orchestrator/fsm.py` нет. Текст
   детали не меняется; `orchestrator/auto.py` не меняется.
5. **Перенос 18 — маркер владельца выписок.** Новая константа
   `liveness.GATE_OWNER_MARKER = ".artel-gate-owner"`.
   `outcome_integrity._gate` и `two_sided.run` пишут в каталог выписки
   маркер с содержимым `str(os.getpid())` сразу за `mkdtemp`, до
   `git worktree add`; маркер пишется при любом профиле, в том числе у
   артели (вывод прежний).
6. **Перенос 18 — сироты выписок.** В `doctor/orphans.py`
   `_temp_owner_alive` для каталогов `artel-outcome-*` и
   `artel-two-sided-*` возвращает только
   `liveness.owner_alive(path, GATE_OWNER_MARKER)`; каталог без маркера —
   сирота. Ветка этих каталогов в `_temp_owner_alive` стоит до общей
   проверки маркера канарейки (`liveness.owner_alive(path)`): живой
   маркер канарейки `.artel-canary-owner` без маркера гейта владельцем не
   считается. `_orphan_temp_dirs` включает такие каталоги без живого
   владельца, поэтому проверка `orphans-temp` (без `--fix`) тоже называет
   их — ожидаемое изменение вывода `doctor`. `_fix_orphan_temp_dirs`
   удаляет каталоги `artel-outcome-*` и `artel-two-sided-*` без живого
   владельца; `git worktree prune` выполняется в каждом клоне проекта
   (`_project_clones`) только если этим вызовом удалён хотя бы один такой
   каталог, иначе git не вызывается. Код уборки зовёт `_project_clones`
   по имени модуля `orchestrator.doctor.orphans` (подмена атрибута этого
   модуля действует на уборку). Тесты уборки подменяют
   `orchestrator.doctor.orphans._project_clones` на клон во временном
   каталоге теста и зовут `doctor._fix_orphan_temp_dirs()` напрямую, не
   `cmd_doctor(fix=True)`; git в настоящих клонах пульта тест не вызывает.
   Новых имён в фасаде `doctor` нет.
7. **Перенос 20 — граница мандата вне `in_outcome_bounds`.** Вне
   `in_outcome_bounds` ячейка «Чем покрыто после», содержащая только путь
   не `*.py` (`src/a.test.ts`) в области, — отказ; подслучаи:
   `test_profile`, `test_profile` с `runner: pytest-own` и `report`,
   компонент без `report`.
8. **Перенос 21 — сужение признания при профиле в границе.** При профиле в
   границе (`_component_covered`, `orchestrator/advance_gates/mandate.py`)
   «Чем покрыто после» отдельным токеном или в кавычках признаёт только
   путь файла. Разбиение ячейки на токены — прежнее (`_TOKEN_SPLIT_RE`,
   `mandate.py:392`), снятие выделения `*`/`_` по краям — прежнее
   (`strip("*_")`); после этого токен — путь, только если он полностью
   совпадает с `[\w][\w./-]*\.\w+` с необязательным хвостом `:<число>`,
   и путь — в `weakening_scope`. Идентификатор своего компонента в
   обратных кавычках — покрытие, как прежде. «`src/`», «src/**»,
   «src/a.test.ts::x», «src/a.test.ts.» без компонента — не покрытие;
   «src/a.test.ts,» — покрытие (запятая — разделитель токенов). Прежнее
   правило путей `*.py` (`_PY_PATH_RE`, поиск внутри ячейки) не меняется.
9. **Перенос 22.** `refusal_classes.OUTCOME_MERGE_PREPARE_ACTION =
   "merge отклонён: гейт неослабления по исходам — подготовка"`; в
   `REFUSAL_CLASSES` её класс — «чинит Оператор».
10. **Перенос 23.** `outcome_integrity.MERGE_REFUSAL_ACTION` и
    `outcome_integrity.MERGE_PREPARE_ACTION` берутся из `refusal_classes`
    (`OUTCOME_MERGE_REFUSAL_ACTION`, `OUTCOME_MERGE_PREPARE_ACTION`);
    литералов обоих текстов действий в тексте
    `orchestrator/advance_gates/outcome_integrity.py` нет;
    `refusal_classes` остаётся без импортов пакета.
11. Тесты детерминированы, без сети и без Node; существующие тесты не
    правятся.

## Критерии приёмки

AC-1. У компонента записи `components:` с `report` и командой pytest каждый прогон `_report_argv` несёт `-p no:rerunfailures -p no:flaky` сразу за элементами поля `command` записи — до аргументов подмножества, целей долгоживущих, `--ignore`, `-p no:cacheprovider` и `report_args`; у артели и у записи `test_profile` аргументы прогона побайтно прежние (сверка с копией прежнего состава в тесте), `_pytest_command` не меняется.

AC-2. Тест сверяет условие добавления `-p no:rerunfailures -p no:flaky` в `_report_argv` с `in_outcome_bounds` на четырёх видах профиля — артель, `test_profile`, `test_profile` с `runner: pytest-own` и `report`, компонент с `report`: флаги есть ровно тогда, когда `in_outcome_bounds(profile)` истинно (при команде pytest).

AC-3. Ключ итога `_report_suite_result_key` у `test_profile` с `report` равен sha256 словаря данных прежнего состава (копия словаря в тесте); у компонента с `report` ключ этому прежнему значению не равен, а его данные несут `"no_rerun_plugins": true`.

AC-4. `targets.check` отказывает компоненту с `report` на каждой форме запрещённого аргумента — элемент `--reruns`, `--reruns-delay`, `--force-flaky`, `--max-runs`; каждый из них с `=<значение>`; пара `-p`, `<имя>`; элемент `-p<имя>` для каждого `<имя>` из `rerunfailures`, `pytest_rerunfailures`, `flaky`, `flaky.flaky_pytest_plugin` — в каждом из полей `command`, `report_args`, `select` и в значении `env.PYTEST_ADDOPTS` (разбор `shlex`); а также на пробельных формах — пара элементов `-p`, `" rerunfailures"` и один элемент `"-p rerunfailures"` (с пробелом) — в каждом из этих четырёх полей (в `env.PYTEST_ADDOPTS` — в кавычках, чтобы `shlex` дал такие элементы). Та же запись под `test_profile` отказа по запрету повторов не получает — для полей, допустимых у `test_profile`: `command` и `env.PYTEST_ADDOPTS` при `runner: pytest-own` (поля `select` и `report_args` у `test_profile` в критерий не входят); компонент без запрещённых аргументов отказа тоже не получает.

AC-5. После сквозного `approve` на `spec_gate` деталь записи перехода равна `advance_gates.tests_writing.SPEC_GATE_PASSED_DETAIL`, константа входит в `auto._LEGIT_FIRST_ENTRY_DETAILS`, а в тексте `orchestrator/fsm.py` нет литерала «гейт SPEC пройден — приёмочные тесты до кода»; `import orchestrator.advance_gates.acceptance` первым импортом в чистом интерпретаторе (подпроцесс) проходит без ошибки.

AC-6. `liveness.GATE_OWNER_MARKER == ".artel-gate-owner"`; `outcome_integrity._gate` и `two_sided.run` пишут в каталог выписки файл маркера с содержимым `str(os.getpid())` до вызова `git worktree add` (при профиле артели — тоже).

AC-7. Каталог `artel-outcome-*` или `artel-two-sided-*` во временном каталоге без маркера или с маркером мёртвого pid попадает в `_orphan_temp_dirs` (проверку `orphans-temp`); с маркером `.artel-gate-owner` живого pid — не попадает; с живым маркером канарейки `.artel-canary-owner` и без маркера `.artel-gate-owner` — попадает (сирота).

AC-8. При подменённом `orchestrator.doctor.orphans._project_clones` (клон во временном каталоге теста; тест проверяет, что подмена вызвана, иначе тест проваливается) прямой вызов `doctor._fix_orphan_temp_dirs()`, не `cmd_doctor(fix=True)`: каталог выписки с живым владельцем остаётся, его запись `git worktree` в клоне — тоже; каталог с мёртвым владельцем удалён, и его запись `git worktree` в клоне убрана (`git worktree prune`); когда этим вызовом не удалён ни один каталог `artel-outcome-*`/`artel-two-sided-*`, git не вызывается.

AC-9. Вне `in_outcome_bounds` ячейка «Чем покрыто после», содержащая только путь `src/a.test.ts` в области, получает отказ мандата — для `test_profile`, для `test_profile` с `runner: pytest-own` и `report` и для компонента без `report`.

AC-10. При профиле в границе «Чем покрыто после» признаёт покрытием путь файла отдельным токеном или в кавычках (токены — прежним `_TOKEN_SPLIT_RE`, выделение `*`/`_` по краям снято) при полном совпадении с `[\w][\w./-]*\.\w+` и необязательным `:<число>` и пути в `weakening_scope`, а также идентификатор своего компонента в обратных кавычках; ячейка «src/a.test.ts,» — покрытие; не признаёт «`src/`», «src/**», «src/a.test.ts::x» и «src/a.test.ts.» без компонента; путь `*.py` внутри ячейки признаётся, как прежде.

AC-11. `refusal_classes.OUTCOME_MERGE_PREPARE_ACTION == "merge отклонён: гейт неослабления по исходам — подготовка"` и `refusal_classes.REFUSAL_CLASSES[OUTCOME_MERGE_PREPARE_ACTION]` — класс «чинит Оператор».

AC-12. `outcome_integrity.MERGE_REFUSAL_ACTION == refusal_classes.OUTCOME_MERGE_REFUSAL_ACTION` и `outcome_integrity.MERGE_PREPARE_ACTION == refusal_classes.OUTCOME_MERGE_PREPARE_ACTION`; `orchestrator/advance_gates/refusal_classes.py` не импортирует ничего из пакета `orchestrator`; в тексте `orchestrator/advance_gates/outcome_integrity.py` нет литералов «merge отклонён: гейт неослабления по исходам — подготовка» и текста `refusal_classes.OUTCOME_MERGE_REFUSAL_ACTION`.

AC-13. `targets.check` отказывает компоненту с `report`, у которого `env.PYTEST_PLUGINS` после разбиения по запятой и снятия пробелов по краям частей содержит `rerunfailures`, `pytest_rerunfailures`, `flaky` или `flaky.flaky_pytest_plugin` (каждое имя отдельно, в том числе среди других плагинов и с пробелами вокруг запятой); компонент с `env.PYTEST_PLUGINS` без этих имён отказа не получает.

## Оценка объёма и деление

Сработавшие сигналы: число файлов зоны — 9 (порог 5); число критериев
приёмки — 13 (порог 10).

**Обоснование монолита (материал для решения Оператора).** Честно: атомарной
смены механики здесь нет — требования 1–3 (запрет повторов: `acceptance.py`,
`targets.py`) и каждый перенос по отдельности самостоятельно мержимы.
Доводы за одну задачу:
- состав G3а-2б-2 уже задан решением Оператора 21.10 о делении G3а-2б
  (ТЗ, «Факты»); это и есть результат нарезки;
- переносы мелкие (константа, маркер, сужение регулярки, два текста), а
  пол рекомендации — $25 на задачу: нарезка на 2–4 части дала бы $50–100
  против рамки ТЗ $30–40;
- зоны частей пересекаются (`outcome_integrity.py` — у переносов 18 и 23),
  так что части шли бы под замком зон последовательно, без выигрыша
  параллельности.

Если Оператор предпочтёт нарезку, естественные границы: (а) требования 1–3
— `orchestrator/acceptance.py`, `orchestrator/targets.py`; (б) переносы 11,
22, 23 — `orchestrator/fsm.py`, `orchestrator/advance_gates/refusal_classes.py`,
`orchestrator/advance_gates/outcome_integrity.py`; (в) перенос 18 —
`orchestrator/liveness.py`, `orchestrator/advance_gates/outcome_integrity.py`,
`orchestrator/advance_gates/two_sided.py`, `orchestrator/doctor/orphans.py`;
(г) переносы 20–21 — `orchestrator/advance_gates/mandate.py`.

`budget_usd: 40` — верх рамки ТЗ ($30–40); калибровочная таблица для 9
файлов зоны рекомендует больше — рамка Оператора приоритетна, поднять
потолок вправе только он.

## Не входит

- Ошибка уровня файла и «новый модуль» — G3а-2б-1.
- Строка в `docs/operator-session.md` о правке SPEC.md после эскалации
  (перенос 12) — `doc-commit` Оператора.
- Шаблонная таблица `it.each` и `suite('AC-n: …')` в запретах (перенос 13)
  — G3б.
- Облегчённый стенд медленных долгоживущих файлов (переносы 17 и 24) —
  бэклог ускорения набора.
- Записи по тестам в кэше итога — бэклог.
- Выбор компонентов по диффу, заменяемые тесты — G3б.
- Отдельная обработка каталогов выписок процессов, начатых до этой задачи
  (без маркера): уборка считает их сиротами — принятая цена (отказ
  подготовки гейта, не пропуск).
- Прочие плагины повторов (например, `pytest-retry`) и `pytest_plugins` в
  `conftest.py` проекта — бэклог Оператора.
- Изменение `_pytest_command`, команд и разбора артели и `test_profile`,
  проверки записи `test_profile` в `targets.check`.
- Правка `orchestrator/auto.py`, `orchestrator/advance_gates/tests_writing.py`,
  `orchestrator/doctor/cli.py`, `orchestrator/doctor/__init__.py` (новых
  имён в фасаде `doctor` нет) и прочих путей «Только чтение» ТЗ.
- Зелёный набор `tests/` без правок существующих тестов — её держит пульт.

## Материалы

- ТЗ: `tasks/01M5FRYVP4NF81VT00FYPHPWJH/TZ.md`.
- `docs/adr/0026-project-components-and-outcome-gates.md`, «Решение» п. 4.
- Адреса: `orchestrator/acceptance.py:37` (`_pytest_command`), `:709`
  (`is_pytest_command`), `:725` (`_report_argv`), `:3170`
  (`_report_suite_result_key`); `orchestrator/advance_gates/acceptance.py:213`
  (`in_outcome_bounds`); `orchestrator/fsm.py:1266`;
  `orchestrator/advance_gates/tests_writing.py:623`; `orchestrator/auto.py:313`;
  `orchestrator/advance_gates/outcome_integrity.py:65-66`, `:556` (`_gate`);
  `orchestrator/advance_gates/two_sided.py:433` (`run`);
  `orchestrator/advance_gates/refusal_classes.py:92`;
  `orchestrator/doctor/orphans.py:82` (`_temp_owner_alive`), `:106`, `:118`;
  `orchestrator/liveness.py:27-39` (образец маркеров, `owner_alive`);
  образец маркера каталога — `canary._owned_temp_dir`.
- В ТЗ нет строки «Порядок: после …» (порядок «после G3а-2б-1» назван в
  «Фактах» без id), поэтому поля `merge_after` нет; пересечение зон с
  G3а-2б-1 сериализует замок зон.
