---
task: 01M5QG7KXQWJDEWRHAWZFQBXET
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/, docs/codebase-map.md
budget_usd: 40
---

# SPEC: Сведение тестов, волна 2б-4 — тесты гейтов отчётов компонентов в `tests/test_report_outcome_module.py` с доказательством мутациями; тексты сообщений модуля

## Контекст
Строка бэклога «Периодическая консолидация тестов артели» (решение Оператора
23.10.2026); основание — ADR-0027 п. 8 и ADR-0020 п. 8. Мандат Оператора
23.10.2026: «Волна сведения тестов по note; после бери все остальные модули в
работу - даю мандат». Параллельно идут не больше двух волн (решение Оператора
24.10.2026); параллельно идёт 2а-1б (01M5QAEPC6RF097YQ43T3Y56D9), файлы не
пересекаются. Волна 2б-3 (01M5PT190RWC6984CDQVZ242GN) смержена 24.10
(25bc133c); по её сверке заведена строка бэклога 24.10 «Тексты сообщений при
провале в tests/test_report_outcome_module.py (волна 2б-3)». Факты ТЗ
сверены с origin/main ec948ea4; аналитик повторно сверил с деревом ветки
число строк, байтов, заявок и строки, названные ниже.

Исходный файл волны — `tests/test_component_report_gates.py` (далее crg):
- 507 строк (30 510 байт), 13 тестов, 13 заявок «Ловит мутацию»; не
  долгоживущий; около 11,5 с суммарно;
- импорт из `tests.report_outcome_sandbox` (:30–32): `ENTRY_HEAD,
  REQUIRE_ASSERTIONS, VITEST_BASE, VITEST_REPORT_ARGS, Fake, ReportSandbox,
  block, junit, vitest_report, vitest_test`;
- определения модуля: `profile` (:35), `check` (:44), `UNKNOWN` (:51), `GREEN`
  (:54), `Reached(Exception)` (:345);
- классы: `AcceptanceSuiteChecksLocalTest(unittest.TestCase)` (:58, свой
  `setUp` с `Path(tmp.name).resolve()`), `ReportArgvTest(ReportSandbox)`
  (:138), `InstallLockTest(unittest.TestCase)` (:190, зовёт
  `self.addCleanup` :200), `SuiteRunParseReportedTest(unittest.TestCase)`
  (:225), `MergeGateComponentsTest(ReportSandbox)` (:251),
  `SuiteRunKeyTest(ReportSandbox)` (:317), `ChecksLocalFromRecordTest(
  ReportSandbox)` (:349), `EmptyInstallTest(ReportSandbox)` (:479);
- методы тестовых классов без утверждений: `suite` :65, `approve` :106,
  `two_components` :253, `selected` :269, `check_script` :354,
  `checked_case` :370, `journal` :379, `merge` :416; методов с
  утверждениями у классов файла нет; вложенные `tree` :108 и `fake` :306
  остаются вложенными;
- `subTest`: :81, :96 — литеральные, без общего состояния; :178 —
  нелитеральный (`sys.executable`); :334, :396 — с общим состоянием (`case`
  строится до цикла, после цикла :411 считается 4 запуска);
- подмены — только `patch.object` (около 25 мест); `if __name__ ==
  "__main__"` — :506.

Утверждения подготовки песочницы, которые зовут тесты crg:
`ReportSandbox.profile` (:396 песочницы; напрямую в crg :328, :494 и внутри
`junit_component`, `vitest_component`), `table` (:477, :479), `accepted_major`
(:488), `cache_flag` (:494). Метод песочницы `ReportSandbox.assert_unknown`
(:422) никем не вызывается и не меняется.

Целевой модуль — `tests/test_report_outcome_module.py` (волна 2б-3): 1344
строки (79 514 байт), 26 тестов, фикстура `box` поверх
`_sandbox(ReportSandbox)`. Имён `profile`, `check`, `UNKNOWN`, `GREEN`,
`Reached` на его верхнем уровне нет; локальные переменные `profile` (:408,
:476, :511) и `outcome` (:476, :511) есть в существующих тестах. Из
песочницы модулю недостаёт только `VITEST_REPORT_ARGS` и `block`; остальные
имена crg (`dataclasses`, `threading`, `types`, `fsm`, `fsm_merge_gate`,
`outcome`) — из стандартной библиотеки и пульта. Тест
`test_ac9_timeout_kills_group_not_green` модуля (предел компонента 1 с) дал
красный контроль `mutation-run` с `-n auto` и зелёный — с `--workers 4`.

Сверка волны 2б-3 (24.10):
- в `test_ac16_node_modules_read_only_shared_and_substitution_refused`
  (старый `report_outcome` :1481 → модуль :1059) `pytest.raises(OSError)`
  потерял текст «запись в node_modules»;
- метка бывшего `subTest` не доходит до сообщений внутри функции модуля
  `assert_unknown` (:141) у вызовов :260 (`test_ac1`, старый
  `subTest(stdout=…, report=…)` :641), :290 (`test_ac2_empty_…`; значение
  есть в контексте, нет формы `report=`) и :442 (`test_ac4_ac6_sled_…`;
  значение теряется);
- в модуле принят суффикс `+ "; " + f"report={label!r}"` (сообщения
  :249–258, :437–448).

Гейт ёмкости диффа — 262 144 байта; оценка диффа задачи — около 65 КБ.

`mutation-run` (с 24.10) принимает `--workers <n>`, `--wait-lock <минуты>`
(сумма с `--wait` — не больше 9 минут), `--copy-table`. Предел части —
1500 с. Один прогон crg — несколько секунд; модуля после свода — около 20 с
при `--workers 4`.

Шаг роли — 2700 с. Пульт сам коммитит рабочую копию разработчика в пределах
зон. Роль на Claude пишет в каталог документов задачи и в `$TMPDIR` командой
`python3`. guard прослеживает помощника с утверждениями только при вызове
`self.<метод>` или голым именем функции своего модуля либо
`tests/sandbox.py`; текст сообщения `assert` нормализатор отбрасывает.
Мандат выдаётся командой `answer`.

## Требования

1. Мутации «до». Для каждой из 13 заявок crg — патч к коду `orchestrator/` в
   `tasks/<id>/mutation-<nnn>.diff`, номера подряд с 001. Патч реализует ровно
   мутацию заявки; у заявки с несколькими альтернативами — по патчу на каждую,
   если они не одинаковы по смыслу.
2. Таблица «до» — одной частью командой `mutation-run <id> --ref base --tests
   tests/test_component_report_gates.py --workers 4 --copy-table --wait-lock
   4`. Вывод `--wait` — в PLAN, раздел «Мутации до», дословно, с шапкой и всеми
   строками.
3. У каждой мутации «до» и «после» в PLAN — строка падения из лога прогона
   патча (файл:строка упавшего утверждения).
4. Не доказательство — мутация, «убитая» ошибкой сбора, импорта, setup или
   только утверждением подготовки песочницы (`profile`, `table`,
   `accepted_major`, `cache_flag`): такой патч переписывается. Исходы «итог
   неизвестен», «патч не применяется», «патч трогает тесты», «не прогнана» —
   патч переписывается и прогоняется заново. Мутация, не убитая никем, —
   находка в PLAN.
5. Красный контроль — повтор тем же вызовом в следующем шаге; повторный
   красный контроль — `escalate`, тесты и пределы не трогать. Ожидание замка
   — только `--wait-lock`; циклы и сценарии ожидания запрещены.
6. Временные файлы в рабочей копии не создаются. Допустимы только файл
   первого уровня каталога документов задачи с расширением не `.md` и
   именем не `test_*`/`mutation-*` либо файл в `$TMPDIR`, созданный командой
   `python3`. К концу каждого шага `git status --porcelain` называет только
   `tests/test_report_outcome_module.py`, удаление
   `tests/test_component_report_gates.py` и `docs/codebase-map.md` (только
   вывод генератора).
7. Свод: 13 тестов crg — функции в `tests/test_report_outcome_module.py` в
   стиле pytest. Имена, уже определённые или импортированные в модуле,
   повторно не импортируются; недостающие имена — тем же источником, что в
   crg (:15–32); `unittest` и неиспользуемый `json` не переносятся. `if
   __name__ == "__main__"` не переносится.
8. Определения `profile`, `check`, `UNKNOWN`, `GREEN`, `Reached` переносятся
   дословно. Если имя совпадает с именем верхнего уровня модуля (определённым
   или импортированным), определение получает префикс `crg_`/`CRG_`
   (перечень — в PLAN). Совпадение с локальной переменной существующего теста
   (`profile`, `outcome`) префикса не требует; локальные переменные 26 тестов
   не переименовываются.
9. Стенды:
   - тесты классов на `ReportSandbox` берут стенд фикстурой `box`;
   - для `AcceptanceSuiteChecksLocalTest` фикстура файла
     `checks_stand(tmp_dir)` возвращает
     `types.SimpleNamespace(tree=tmp_dir.tdir.resolve())` (тело `setUp`),
     помощники `suite`/`approve` берут `stand.tree`;
   - `InstallLockTest` берёт `tmp_dir` ради `addCleanup`;
   - `SuiteRunParseReportedTest` — без фикстуры.
10. Методы тестовых классов без утверждений — функции модуля: первый
    параметр — стенд, тело дословно, `self.` заменено именем параметра.
    Совпадающие имена — с префиксом бывшего класса; переименовывается
    функция, не локальная переменная.
11. Утверждения и проверяемые свойства не меняются: ожидания дословно;
    литерал остаётся литералом, константа — константой (равенство значений
    доводом не считается).
    - `pytest.raises(..., match=re.escape(<текст>))` — только где исходник
      проверял текст; голый `assertRaises(E)` → `pytest.raises(E)`, текст
      `msg=` — `pytest.fail(box.note(<текст>))` последней строкой блока
      `pytest.raises`.
    - Литеральные наборы `subTest` без общего состояния (:81, :96) —
      `parametrize` литералами.
    - Нелитеральный набор (:178) и наборы с общим состоянием (:334, :396;
      общее состояние — объект, созданный до цикла и читаемый в нём или после
      него) — прежним циклом, ярлык — в тексте сообщения каждого утверждения
      подслучая.
12. Дубль удаляется только если (а) каждую его мутацию по таблице «до» убивает
    и другой сохраняемый тест того же исходного файла и (б) каждый литерал и
    вид каждого утверждения удаляемого теста есть в сохраняемом. Удалённые
    дубли — в PLAN. Тест, чью мутацию не убил никто, не удаляется. У каждой
    перенесённой функции — строка «Ловит мутацию:».
13. Тексты сообщений модуля (строка бэклога 24.10):
    - в `test_ac16_…` (:1059) текст возвращается строкой
      `pytest.fail(box.note("запись в node_modules"))` последней в блоке
      `pytest.raises`;
    - функция модуля `assert_unknown` (:141) получает последний
      необязательный параметр `case: str = ""`, сообщения её тела становятся
      `box.note(…) + case`, иных отличий тела нет; метод песочницы
      `ReportSandbox.assert_unknown` не меняется;
    - вызов :260 передаёт `"; " + f"stdout={stdout!r}; report={label!r}"`,
      вызовы :290 и :442 — `"; " + f"report={label!r}"`.

    Утверждения и их вид не меняются. Других правок 26 существующих тестов
    модуля нет.
14. Таблица «после» — командой `mutation-run <id> --ref worktree --tests
    tests/test_report_outcome_module.py --workers 4 --copy-table --wait-lock 4`
    теми же патчами; вывод — в PLAN, раздел «Мутации после», дословно. Перед
    прогоном — пустой вывод `git status --porcelain -- orchestrator/`.
15. Для каждой мутации, убитой «до» тестом T, «после» её убивает функция, в
    которую перенесён T, тем же по тексту утверждением (соответствие — в
    PLAN). Дерево `orchestrator/` ревизий обеих шапок совпадает, sha256
    каждого патча совпадает. При подтяжке main с изменением `orchestrator/`
    «до» прогоняется заново.
16. Под ролью адресно прогоняется только `tests/test_report_outcome_module.py`.
    Время «до» и «после» — по контрольным прогонам `mutation-run`; число
    тестов и строк до и после — в PLAN.
17. `tests/test_component_report_gates.py` удаляется. Мандат — `answer` только
    на этот путь; удаление утверждения без переноса, ослабление сравнения,
    `skip`/`xfail`, подъём пределов не разрешены.
    `tests/test_report_outcome_module.py` мандатом не покрыт: правка его 26
    тестов — только требование 13.
18. Ограничение зон по смыслу. В `tests/` — только удаление
    `tests/test_component_report_gates.py` и правка
    `tests/test_report_outcome_module.py`. Не меняются
    `tests/report_outcome_sandbox.py`, переходной модуль
    `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`,
    `tests/test_invariants.py`, `tests/fixtures.py`, `tests/sandbox.py`,
    `tests/fd_wait.py`, `tests/test_outcome_integrity_added_lines.py`, файлы
    волны 2а-1б (`tests/test_outcome_gate_module.py`,
    `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`) и код
    `orchestrator/`. `docs/codebase-map.md` — только вывод генератора.
19. Независимая проверка (повтор `mutation-run`, сравнение утверждений по AST)
    — сессией при Операторе до approve на merge_gate.

## Критерии приёмки

AC-1. В каталоге документов задачи первым уровнем лежат патчи
`mutation-<nnn>.diff`, номера подряд с 001 без пропусков; каждый патч меняет
только файлы под `orchestrator/`. В PLAN каждая из 13 заявок crg
сопоставлена патчу (патчам — у заявки с несколькими не одинаковыми по смыслу
альтернативами), у каждого патча названо, что он меняет.

AC-2. В PLAN есть раздел «Мутации до» с выводом одной части `mutation-run
<id> --ref base --tests tests/test_component_report_gates.py --workers 4
--copy-table --wait-lock 4`, перенесённым дословно, с шапкой и всеми
строками; в таблице есть каждый патч набора.

AC-3. У каждой мутации в PLAN для таблиц «до» и «после» приведена строка
падения из лога прогона патча (файл:строка упавшего утверждения).

AC-4. Ни одна мутация не засчитана доказательством, если её убили только
ошибка сбора, импорта, setup или только утверждение подготовки песочницы
(`profile`, `table`, `accepted_major`, `cache_flag`). Ни одна мутация с
исходом «итог неизвестен», «патч не применяется», «патч трогает тесты» или
«не прогнана» не засчитана ни убитой, ни выжившей. Мутации, которые «до» не
убил никто, перечислены в PLAN находками.

AC-5. `git status --porcelain` рабочей копии к концу шага называет только
`tests/test_report_outcome_module.py`, удаление
`tests/test_component_report_gates.py` и `docs/codebase-map.md`. Файлы
первого уровня каталога документов задачи с расширением не `.md`, кроме
патчей `mutation-<nnn>.diff`, не называются `test_*` и `mutation-*`.

AC-6. Файла `tests/test_component_report_gates.py` на ветке нет. В
`tests/test_report_outcome_module.py` нет тестовых классов, `subTest`, блока
`if __name__ == "__main__"` и импорта `unittest`; имена, определённые или
импортированные в модуле до свода (в том числе `json`), повторно не
импортируются; `VITEST_REPORT_ARGS` и `block` импортируются
из `tests.report_outcome_sandbox`.

AC-7. Определения `profile`, `check`, `UNKNOWN`, `GREEN`, `Reached` лежат в
`tests/test_report_outcome_module.py` и по `ast.dump` тела равны исходным;
имя, совпавшее с именем верхнего уровня модуля, несёт префикс
`crg_`/`CRG_`, перечень таких переименований есть в PLAN. Локальные
переменные 26 существующих тестов не переименованы.

AC-8. В модуле есть фикстура `checks_stand(tmp_dir)`, возвращающая
`types.SimpleNamespace(tree=tmp_dir.tdir.resolve())`; функции из
`AcceptanceSuiteChecksLocalTest` и помощники `suite`/`approve` берут
`stand.tree`. Функции из классов на `ReportSandbox` берут фикстуру `box`;
функция из `InstallLockTest` — `tmp_dir`; функция из
`SuiteRunParseReportedTest` — без фикстуры.

AC-9. Методы `suite`, `approve`, `two_components`, `selected`,
`check_script`, `checked_case`, `journal`, `merge` — функции модуля: первый
параметр — стенд, тело дословно с заменой `self.` именем параметра;
совпадающие имена несут префикс бывшего класса, локальные переменные не
переименованы. `tree` и `fake` остаются вложенными.

AC-10. Ожидания 13 перенесённых тестов совпадают с исходными дословно:
литерал остался литералом, константа — константой; ни одно сравнение не
ослаблено. `pytest.raises` с `match=re.escape(...)` стоит только там, где
исходник проверял текст; на месте голого `assertRaises(E)` —
`pytest.raises(E)`, а текст `msg=` — строкой `pytest.fail(box.note(<текст>))`
последней в блоке `pytest.raises`.

AC-11. Наборы `subTest` :81 и :96 — `parametrize` литералами; наборы :178,
:334, :396 — прежним циклом в одной функции, ярлык подслучая есть в тексте
сообщения каждого утверждения подслучая.

AC-12. У каждой перенесённой функции есть строка «Ловит мутацию:». Каждый
тест crg, не перенесённый в модуль, перечислен в PLAN удалённым дублем с его
мутациями, и для него выполнены условия (а) и (б) требования 12; тест, чью
мутацию не убил никто, не удалён.

AC-13. В `test_ac16_node_modules_read_only_shared_and_substitution_refused`
блок `pytest.raises(OSError)` последней строкой несёт
`pytest.fail(box.note("запись в node_modules"))`. Функция модуля
`assert_unknown` имеет последний параметр `case: str = ""`, каждое сообщение
её тела — `box.note(…) + case`, иных отличий тела от main нет. Вызов на месте
:260 передаёт `"; " + f"stdout={stdout!r}; report={label!r}"`, вызовы на
местах :290 и :442 — `"; " + f"report={label!r}"`. Вид и операнды утверждений
26 существующих тестов, кроме названных текстов сообщений, не изменены;
`ReportSandbox.assert_unknown` не изменён.

AC-14. В PLAN есть раздел «Мутации после» с выводом `mutation-run <id> --ref
worktree --tests tests/test_report_outcome_module.py --workers 4 --copy-table
--wait-lock 4`, перенесённым дословно, и перед ним — пустой вывод `git status
--porcelain -- orchestrator/`. Каждая мутация, убитая «до» тестом T, «после»
убита функцией, в которую перенесён T, тем же по тексту утверждением;
соответствие приведено в PLAN.

AC-15. Шапки таблиц «до» и «после» согласованы: дерево `orchestrator/` их
ревизий совпадает, sha256 каждого патча в обеих шапках совпадает. В PLAN
названы число тестов, число строк и время по контрольным прогонам
`mutation-run` до и после свода.

AC-16. Diff ветки против базы — только удаление
`tests/test_component_report_gates.py`, правка
`tests/test_report_outcome_module.py` и `docs/codebase-map.md`, равный
выводу `python3 scripts/codebase_map.py` на дереве ветки. Перечисленные в
требовании 18 файлы и всё под `orchestrator/` не изменены. В модуле нет
`skip`/`xfail`, пределы не выше исходных.

## Оценка объёма и деление

Сработавшие сигналы:
- `budget_usd` ≥ $30 — ставка $40 из ТЗ;
- число критериев приёмки ≥ 10 — их 16.

Обоснование монолита (материал для решения Оператора на гейте SPEC).
Оператор уже нарезал ветвь B семейства outcome по волнам, 2б-4 — один
исходный файл; прогноз диффа около 65 КБ — четверть гейта ёмкости.
Внутри задачи части неделимы:
- перенос тестов без удаления crg оставляет полные дубли, удаление без
  переноса теряет покрытие;
- доказательство сравнивает убийства «до» на crg с убийствами «после» на
  сводном модуле при неизменном `orchestrator/`; мандат — один `answer` на
  путь crg;
- правка текстов сообщений (требование 13) идёт в тот же модуль и проверяется
  тем же прогоном «после»; отдельная задача правила бы тот же файл
  параллельно со сводом.

Зона — удаление одного файла и правка другого в `tests/` плюс регенерация
карты; резать по смыслу нечего.

## Не входит

- `tests/test_outcome_integrity_added_lines.py` — по смыслу гейт исходов,
  идёт вместе с волной 2а-2.
- Удаление переходного модуля
  `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py` и правка
  `tests/test_invariants.py:3131`, `docs/invariants.md:71` — коммит
  Оператора.
- Правка песочницы `tests/report_outcome_sandbox.py`.
- Изменение кода пульта `orchestrator/`; мутации — только во временной копии
  `mutation-run`.
- Правка 26 существующих тестов модуля сверх требования 13.
- Независимая проверка (требование 19) — делает сессия при Операторе, не роль.
- Полный зелёный набор `tests/` и зелёный CI ветки — их держит пульт.

## Материалы

- SPEC волны 2б-3: `refs/artifacts/01M5PT190RWC6984CDQVZ242GN`,
  `tasks/01M5PT190RWC6984CDQVZ242GN/SPEC.md`.
- ADR-0027 п. 8, ADR-0020 п. 8; `docs/backlog.md` — строки 23.10 и 24.10.

Только чтение: orchestrator/ (весь код пульта), orchestrator/acceptance.py,
orchestrator/reporters/outcome.py, orchestrator/advance_gates/mandate.py,
orchestrator/advance_gates/test_integrity.py,
orchestrator/advance_gates/capacity.py, orchestrator/mutation_run.py,
orchestrator/checkpoint.py, tests/report_outcome_sandbox.py,
tests/fixtures.py, tests/sandbox.py, scripts/guard.py,
scripts/codebase_map.py, tests/test_invariants.py, conftest.py,
pyproject.toml, targets.yaml, skills/test-authoring.md,
docs/adr/0027-pytest-style-tests.md,
docs/adr/0020-long-lived-acceptance-tests-in-tests.md, docs/backlog.md.
