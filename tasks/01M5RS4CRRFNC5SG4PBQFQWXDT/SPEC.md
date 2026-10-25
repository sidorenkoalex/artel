---
task: 01M5RS4CRRFNC5SG4PBQFQWXDT
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/, docs/codebase-map.md
budget_usd: 50
---

# SPEC: Сведение тестов, волна 2а-2в-1 — песочницы гейта исходов G3б-2 в `tests/prior_outcome_sandbox.py`, 22 теста на `PriorSandbox` из `outcome_prior` в `tests/test_outcome_prior_module.py`; стиль pytest, доказательство мутациями

## Контекст
Строка бэклога «Периодическая консолидация тестов артели» (решение Оператора
23.10.2026); ADR-0027 п. 8 и ADR-0020 пп. 6, 8: старые тесты переводятся в
стиль pytest волнами консолидации, доказательство — множество убиваемых
мутаций, мандат Оператора по путям и независимая проверка. Порядок волн
(решение 23.10.2026): note → outcome → merge → suite-run → остальные; мандат
Оператора 23.10.2026 (дословно): «Волна сведения тестов по note; после бери
все остальные модули в работу - даю мандат»; до трёх волн одновременно
(решение 24.10.2026). Волны 2а-2а (01M5R0DPNHZ7N8YBXMH375SMEE, мерж c04d747b)
и 2а-2б (01M5RH875Q1JMVRM1TXNE6HNMW, мерж a8e57874) смержены 25.10:
песочница мержа — в `tests/merge_outcome_sandbox.py`, песочницы компонентов —
в `tests/components_outcome_sandbox.py`.

Файл волны (факты ТЗ сверены аналитиком на a8e57874):
- `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` — 1736 строк,
  113 352 байта, 44 теста; долгоживущий файл задачи
  01M5J0JYW3GZSSHHK3TYCYTQ3J (в `done`); импортёров нет. Докстринг — :1,
  импорты — :41–59, константы `GATE_MODULE` … `CLAIM` — :62–95, `Moved` —
  :98, `Link` — :103, `PriorSandbox(MergeOutcomeSandbox)` — :108, тестовые
  классы `Ac3GreenPriorTest` … `Ac13OwnerMarkerTest` — :381–879,
  `ReplacementSandbox` — :880, `StrictSandbox` — :1160, `env_lines` — :1300,
  `Ac32AddedFilesRemovedTest` — :1520, `Ac33SkippedMissingRedTest` — :1583,
  `Ac27MergeProofTest` — :1612, `Ac30OutOfBoundsTest` — :1708,
  `unittest.main()` — :1735.
- 14 классов этой задачи на `PriorSandbox` несут 22 теста. Оставшиеся 15
  классов и `env_lines` из имён песочниц читают ровно `Moved`,
  `ReplacementSandbox`, `StrictSandbox`.
- В `tests/test_outcome_gate_module.py` есть фикстура `box` (:813) и функции
  `refusal(box, rows: list, output: str, action: str, case: str = "")` (:821),
  `no_gate_refusal(box, rows: list, output: str, case: str = "")` (:834);
  `GATE_ACTIONS` — `tests/outcome_gate_sandbox.py:36`; `_sandbox(cls)` —
  `tests/fixtures.py:42`.
- Случайность — зерно `OutcomeGateSandbox.setUp`
  (`tests/outcome_gate_sandbox.py:258`), новое на каждый тест; из `self.rng`
  — имена, число и выбор файлов, порядок смеси исходов, номер и вид красного
  перепрогона базы (перечень — в ТЗ, раздел «Факты»).
- Один последовательный прогон файла — 135,3 с; тесты этой задачи — около
  59 с.

Размещение и деление выбраны Оператором в ТЗ: песочницы — новый модуль
(дописка в существующие модули песочниц дала бы вторые определения
констант), тесты — новый модуль (совпадения `OLD`, `BROKEN_ACTION`,
`PREPARE_ACTION`, фикстуры `box` с `tests/test_outcome_gate_module.py`,
другой стенд, размер). Волна разделена по стенду из-за гейта ёмкости диффа
(262 144 байта; одной задачей — около 230 КБ, эта часть — около 125 КБ):
классы на `ReplacementSandbox`/`StrictSandbox` и удаление долгоживущего
файла — задача 2а-2в-2, заводится после мержа этой.

guard прослеживает помощника с утверждениями только при вызове
`self.<метод>` по цепочке классов или голым именем функции своего модуля
либо `tests/sandbox.py` (`scripts/guard.py:1902`, :1926); текст сообщения
`assert` нормализатор отбрасывает (:1628–1629). Поэтому помощники исхода
становятся функциями модуля. `mutation-run` несёт `--workers <n>`,
`--wait-lock <минуты>` (сумма с `--wait` — не больше 9 минут),
`--copy-table`; предел части — 1500 с (`targets.yaml:53`). Шаг роли —
`AGENT_TIMEOUT_SEC` = 2700 с (`orchestrator/config.py:132`). Роли не вызывают
`gh`: цвет CI кодовой ветки читает ревьювер.

ТЗ несёт раздел «Уточнения по независимой проверке 25.10», которые при
расхождении с основным текстом ТЗ действуют; требования ниже записаны уже с
ними.

## Требования

1. Мутации «до». Для каждой из 22 заявок тестов этой задачи (классы `Ac3`,
   `Ac10`, `Ac4`, `Ac5`, `Ac6`, `Ac7`, `Ac8`, `Ac9`, `Ac11`, `Ac12`, `Ac13`,
   `Ac32`, `Ac33`, `Ac30` — в порядке файла) — патч к коду `orchestrator/` в
   `tasks/<id>/mutation-<nnn>.diff`, номера подряд с 001, в порядке тестов
   файла. Патч реализует ровно мутацию заявки; у заявки с несколькими
   альтернативами (через «;», «либо» или «или») — по патчу на каждую, если
   они не одинаковы по смыслу; одинаковые по смыслу альтернативы разных
   заявок — одна мутация со списком тестов. У каждой мутации в PLAN — её
   заявка, альтернатива, что меняет патч (модуль и функция по имени) и одна
   фраза обоснования независимости от случайности: какие случайные значения
   (имена, число и выбор файлов, порядок исходов, номер перепрогона, номер
   критерия, позиции строк) участвуют в проверяемом утверждении и почему
   исход «убита» от них не зависит.
2. Таблица «до»: `mutation-run <id> --ref base --tests
   tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py --copy-table
   --wait-lock 4` частями `--patches` не больше 15 патчей (гоняется весь
   долгоживущий файл, 44 теста; в зачёт идут только тесты этой задачи);
   отчёт части — повторными `mutation-run <id> --wait 5` до итоговой строки;
   вывод — в PLAN, раздел «Мутации до», дословно, с шапкой и всеми строками,
   до старта следующей части.
3. У каждой мутации «до» и «после» в PLAN — строка падения из лога прогона
   патча (файл:строка упавшего утверждения).
4. Доказательством не считается мутация, «убитая» ошибкой сбора, импорта,
   setup или фикстуры; исключением без падения утверждения; по таймауту
   pytest-timeout (`Timeout` в логе); только утверждением подготовки
   (требование 15); только тестом другой задачи — классов `Ac14`, `Ac15`,
   `Ac16`, `Ac17`, `Ac18`, `Ac26`, `Ac34`, `Ac27`, `Ac19`, `Ac20`, `Ac21`,
   `Ac22`, `Ac23`, `Ac24`, `Ac25`, `Ac31` (`Ac30`, `Ac32`, `Ac33` — классы
   этой задачи). Такой патч переписывается так, чтобы падало утверждение
   теста. Мутация, не убитая никем, — находка в PLAN.
5. Мутация убивается детерминированно при любом зерне: расхождение «убита /
   не убита» между «до», «после» и повтором — заявка или патч
   переписывается так, чтобы исход не зависел от случайных значений;
   повторы до убийства запрещены; зерно не фиксируется.
6. Исходы «итог неизвестен», «патч не применяется», «патч трогает тесты»,
   «не прогнана» — патч переписывается и прогоняется заново. Часть,
   оборванная пределом, раскладывается на меньшие части, а не прогоняется
   тем же набором.
7. Красный контроль — повтор тем же вызовом в следующем шаге; повторно
   красный — с `--workers 4` частями не больше 10 патчей (число рабочих
   процессов и диапазоны — в PLAN); и тогда красный — `escalate` с логом
   контроля, тесты и пределы не трогаются.
8. Ожидание замка — только `--wait-lock`; циклы и сценарии ожидания
   запрещены; не дождались — повтор в следующем шаге; не дождались два
   шага подряд — `escalate` с выводом `mutation-run`.
9. Временные файлы в рабочей копии не создаются. Допустимо: файл первого
   уровня каталога документов задачи с расширением не `.md` и именем не
   `test_*` и не `mutation-*` (копии `mutation-run-<n>.tsv` команды
   допустимы) либо файл в `$TMPDIR`, созданный командой `python3`. К концу
   каждого шага `git status --porcelain` рабочей копии называет только новые
   `tests/prior_outcome_sandbox.py` и `tests/test_outcome_prior_module.py`,
   изменённый `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` и
   `docs/codebase-map.md` (только вывод генератора).
10. Песочницы. Операторы верхнего уровня от `import contextlib` до `CLAIM`
    включительно (все импорты и константы), классы `Moved`, `Link`,
    `PriorSandbox`, `ReplacementSandbox`, `StrictSandbox` переносятся из
    долгоживущего файла целиком и дословно, в том же порядке, в новый модуль
    `tests/prior_outcome_sandbox.py`: тестов и заявок он не содержит,
    докстринг — новый, одной строкой назначения; строки-комментарии
    разделов можно перенести или опустить. `ast.dump` каждого оператора
    верхнего уровня, кроме нового докстринга, равен исходному — сверка в
    PLAN. Ненужные песочницам импорты и константы (`hashlib`, `unittest`,
    `CLAIM`, `TOKENS` и другие) переезжают дословно — не чистятся. Методы
    песочниц, в том числе `grant` и `passed`, не меняются.
    `tests/outcome_gate_sandbox.py`, `tests/merge_outcome_sandbox.py`,
    `tests/components_outcome_sandbox.py` не меняются.
11. Долгоживущий файл сокращается и остаётся: из него удаляются классы
    `Moved`, `Link`, `PriorSandbox`, `ReplacementSandbox`, `StrictSandbox` и
    14 тестовых классов требования 1 (со строками-комментариями их
    разделов); сразу после импорта `MergeOutcomeSandbox` добавляется один
    оператор `from tests.prior_outcome_sandbox import (Moved,
    ReplacementSandbox, StrictSandbox)`. Остальное — докстринг, импорты (в
    том числе ставшие неиспользуемыми — не чистятся), константы, функция
    `env_lines`, 15 оставшихся тестовых классов и `unittest.main()` — без
    изменений: `ast.dump` каждого оставшегося оператора верхнего уровня равен
    исходному — сверка в PLAN. `pytest --collect-only` файла — 22 теста. Под
    ролью оставшиеся 22 теста прогоняются адресно (одним вызовом pytest на
    файл); итог CI кодовой ветки читает ревьювер (роль `gh` не вызывает и
    итог CI в PLAN не пишет).
12. Свод: 22 теста требования 1 — функции нового
    `tests/test_outcome_prior_module.py` в стиле pytest, в порядке файла, без
    тестовых классов, `unittest`, `unittest.main()` и `subTest`. Источники
    импорта — явно для каждого имени: из `tests.prior_outcome_sandbox` —
    `PriorSandbox`, `Moved`, `Link` и нужные тестам и помощникам константы
    бывшего файла (`OLD`, `SIDES`, `OUTCOME_ACTION`, `PREPARE_ACTION`,
    `PASSED_ACTION`, `SKIPPED`, `PRIOR_RED`, `PRIOR_UNSTABLE`, `FLAKY`,
    `PRIOR_LINE`, `FILE_ERROR_MARK`; одноимённые константы
    `tests.outcome_gate_sandbox`, `tests.merge_outcome_sandbox`,
    `tests.components_outcome_sandbox` отсюда не импортируются, даже при
    равном значении); из `tests.outcome_gate_sandbox` — `flow`, `py_source` и
    `GATE_ACTIONS`; `_sandbox` — из `tests.fixtures`; `import pytest`; модуль
    `os` — прямым импортом, как в бывшем файле; неиспользуемые импорты не
    переносятся.
13. Докстринг нового модуля тестов — назначение; свод из прежнего файла
    (ADR-0020 п. 8: долгоживущий файл сокращён решением Оператора, свойства
    перенесённых тестов — здесь, остальные тесты сводятся задачей 2а-2в-2;
    доказательство — таблицы «до» и «после» в PLAN); описание стенда и
    стороны «прежние версии» из прежнего докстринга с новыми путями
    (`tests.prior_outcome_sandbox.PriorSandbox` поверх
    `tests.merge_outcome_sandbox.MergeOutcomeSandbox` и
    `tests.outcome_gate_sandbox.OutcomeGateSandbox`). Строки «Группа:
    долгоживущий», «Красен до реализации: …» и абзац «Провалидировано
    временным стабом реализации …» не переносятся.
14. Фикстура и помощники.
    - `box` — `yield from _sandbox(PriorSandbox)` для всех 14 бывших
      классов; фикстура только создаёт стенд и не зовёт методов с
      утверждениями непосредственно или помощником первого уровня (`setUp`
      песочницы через `_sandbox` под правило не подпадает); имя не совпадает
      с фикстурами `tests/fixtures.py`.
    - Помощники, утверждающие исход, — функции модуля с сигнатурами
      дословно: `def refusal(box, rows: list, output: str, action: str, case: str = "") -> str:`
      и `def no_gate_refusal(box, rows: list, output: str, case: str = "") -> None:`
      — по `ast.dump` равны одноимённым функциям
      `tests/test_outcome_gate_module.py`;
      `def passed(box, rows: list, output: str, case: str = "") -> str:` —
      тело метода `PriorSandbox.passed`;
      `def grant(box, t, paths=(), ids=(), covered="tests/sandbox.py:1", case: str = "") -> None:`
      — тело метода `PriorSandbox.grant`; в обоих `self` заменено на `box`,
      сообщение — по образцу `refusal`: `case + f"…" + box.explain(...)` без
      дополнительных скобок; `def conftest_case(box, extra: dict | None, conftest: str):`
      — тело метода `Ac32AddedFilesRemovedTest.conftest_case`, `self`
      заменено на `box`, вызов `self.refusal(...)` — вызовом
      `refusal(box, ...)`. Утверждения в телах помощников остаются вызовами
      `box.assertX(...)` дословно. Сверка по AST тела каждого помощника с
      исходным телом (после названных замен) — в PLAN.
15. Утверждения подготовки (падение только им — не доказательство):
    утверждения методов песочниц-предков `in_dev_task`, `artel_in_dev_task`,
    `operator_mandate`, `direct_task`, `verifying_task`, `rewrite_passed`;
    `RealGitSandbox.git` (`tests/sandbox.py:1956–1960`, проверка кода
    возврата git); функция `grant` во всех тестах этой задачи. Утверждения
    `refusal`, `no_gate_refusal`, `passed`, `conftest_case`, вложенной
    `index` и тела теста — утверждения исхода.
16. Тело каждой тестовой функции по AST равно телу исходного метода после
    замен: `self` → `box`; `self.assertX(a, b, msg)` → `assert a <op> b, msg`
    (`assertEqual` ↔ `==`, `assertTrue(x)` ↔ `assert x`, `assertFalse(x)` ↔
    `assert not x`, `assertIn` ↔ `in`, `assertNotIn` ↔ `not in`,
    `assertGreaterEqual` ↔ `>=`); `self.refusal`, `self.no_gate_refusal`,
    `self.passed`, `self.grant`, `self.conftest_case` → вызов функции модуля
    с `box` первым аргументом; все прочие обращения `self.<имя>` — методы и
    атрибуты стенда (в том числе `task`, `junit`, `developer_advance`,
    `explain`, `note`, `starting`, `case_id`, `lines_with`, `old_runs`,
    `old_files`, `third_adds`, `edited_py`, `add_path`, `junit_project`,
    `gate_rows`, `state`, `py_rel`, `py_name`, `word`, `rng`, `seed`,
    `gate_adds`, `suite_calls`) — `box.<имя>`; присваивания атрибутам стенда
    (`git_fail`, `timeout_when`, `watch_old`, `cases[…]`) — через `box`,
    дословно и тем же порядком. Ожидания и литералы — дословно; литерал
    остаётся литералом, константа — той же константой (равенство значений
    доводом не считается); совпадение нормальной формы guard не требуется.
    Текст сообщения (`self.explain(...)`, `self.note(...)`, их конкатенация с
    f-строкой) — вторым операндом `assert`; утверждение без сообщения
    остаётся без сообщения. Вложенные функции `third`, `index` и лямбды
    остаются вложенными, тело дословно, `self.` заменено на `box.`. Сверка
    AST тела каждой функции с телом метода — в PLAN.
17. Бывшие `subTest` (`test_ac9_code_only_and_new_file_no_third_checkout`,
    `test_ac9_changed_base_file_and_file_level_record_in_set`,
    `test_ac12_diff_failures_refuse_prepare`,
    `test_ac33_prior_skipped_or_missing_is_red`) — прежним циклом или прямым
    кодом в одной функции; первой строкой подслучая —
    `case = f"{label}, зерно {box.seed}: "` (у двух одиночных блоков `Ac9` —
    литерал ярлыка вместо `{label}`); `case` стоит спереди текста сообщения
    каждого прямого утверждения подслучая и передаётся параметром `case=` в
    `refusal`, `no_gate_refusal`, `passed`.
18. Локальная переменная теста, совпадающая с именем функции или фикстуры
    модуля, переименовывается (перечень — в PLAN; на a8e57874 совпадений
    нет). Дубль удаляется только если (а) каждую его мутацию по таблице «до»
    убивает и другой сохраняемый тест этой задачи и (б) каждый литерал и вид
    каждого утверждения удаляемого теста есть в утверждениях сохраняемого
    теста, убивающего те же мутации; удалённые дубли — в PLAN. Тест, чью
    мутацию не убил никто, не удаляется (заявка переписывается на мутацию,
    которую он убивает, либо находка в PLAN; если нет мутации, убиваемой при
    любом зерне, — находка в PLAN; тест не удаляется, зерно не фиксируется,
    ожидания и выбор случайных значений не меняются). У каждой функции —
    «Ловит мутацию:».
19. Таблица «после»: `mutation-run <id> --ref worktree --tests
    tests/test_outcome_prior_module.py --copy-table --wait-lock 4` теми же
    диапазонами `--patches` и тем же `--workers`, что «до»; вывод — в PLAN,
    раздел «Мутации после», дословно; перед каждой частью — пустой вывод
    `git status --porcelain -- orchestrator/`. Правила требований 3–8
    действуют и здесь.
20. Для каждой мутации, убитой «до» тестом T, «после» её убивает функция, в
    которую перенесён T, перенесённым из T утверждением (по соответствию
    требования 16); соответствие «файл:строка до → файл:строка после» и имён
    — в PLAN. Дерево `orchestrator/` ревизий обеих шапок совпадает, sha256
    каждого патча совпадает; при подтяжке main с изменением `orchestrator/`
    «до» прогоняется заново.
21. Под ролью адресно прогоняются только `tests/test_outcome_prior_module.py`
    и сокращённый долгоживущий файл (требование 11); время «до» и «после» —
    по контрольным прогонам `mutation-run`; число тестов, подслучаев и строк
    до и после — в PLAN.
22. Мандат — `answer` только на путь
    `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`; новые пути в
    мандат не вносятся. Ожидаемые находки гейта — исчезновение 22
    перенесённых методов по пути долгоживущего файла; они покрыты мандатом
    на этот путь. Если храповик даст убыль утверждений, она приписывается
    долгоживущему пути и покрыта тем же мандатом: не повод для эскалации,
    мандат не расширяется. Удаление утверждения без переноса, ослабление
    сравнения, `skip`/`xfail`, подъём пределов не разрешены.
23. Ограничение зон по смыслу: в `tests/` — новые
    `tests/prior_outcome_sandbox.py` и `tests/test_outcome_prior_module.py`,
    в `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` — только
    удаление классов и один импорт требования 11;
    `tests/outcome_gate_sandbox.py`, `tests/merge_outcome_sandbox.py`,
    `tests/components_outcome_sandbox.py`, `tests/test_outcome_gate_module.py`,
    `tests/test_merge_outcome_module.py`,
    `tests/test_outcome_components_module.py`, `tests/fixtures.py`,
    `tests/sandbox.py`, `tests/test_invariants.py` и файлы идущих
    параллельно волн не меняются; код `orchestrator/` не меняется;
    `docs/codebase-map.md` — только вывод генератора.
24. Независимая проверка (повтор `mutation-run`, сравнение утверждений и тел
    по AST, сверка `ast.dump` переноса песочниц, оставшихся операторов
    долгоживущего файла и помощников) — сессией при Операторе до approve на
    merge_gate.

## Критерии приёмки

AC-1. В каталоге документов задачи первым уровнем лежат патчи
`mutation-<nnn>.diff` с номерами подряд от 001 без пропусков, в порядке
тестов файла; каждый патч меняет только файлы под `orchestrator/`. В PLAN
каждая из 22 заявок тестов классов `Ac3`, `Ac10`, `Ac4`, `Ac5`, `Ac6`, `Ac7`,
`Ac8`, `Ac9`, `Ac11`, `Ac12`, `Ac13`, `Ac32`, `Ac33`, `Ac30` сопоставлена
мутации (по одной на каждую не одинаковую по смыслу альтернативу;
одинаковые по смыслу альтернативы разных заявок — одной мутации со списком
тестов), и у каждой мутации названы заявка, альтернатива, что меняет патч
(модуль и функция) и фраза обоснования независимости исхода от случайных
значений.

AC-2. В PLAN есть раздел «Мутации до» с выводом каждой части
`mutation-run --ref base --tests
tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py --copy-table
--wait-lock 4`, перенесённым дословно, с шапкой и всеми строками; ни одна
часть не длиннее 15 патчей (при `--workers 4` — не длиннее 10); число рабочих
процессов и диапазоны названы; в таблицах есть каждая мутация набора.

AC-3. У каждой мутации в PLAN для «до» и «после» есть строка падения из
лога прогона патча (файл:строка упавшего утверждения).

AC-4. Ни одна мутация не засчитана доказательством, если её убили только
ошибка сбора, импорта, setup или фикстуры, исключение без падения
утверждения, таймаут pytest-timeout, утверждение подготовки (`in_dev_task`,
`artel_in_dev_task`, `operator_mandate`, `direct_task`, `verifying_task`,
`rewrite_passed`, `RealGitSandbox.git`, `grant`) или тест классов `Ac14`,
`Ac15`, `Ac16`, `Ac17`, `Ac18`, `Ac26`, `Ac34`, `Ac27`, `Ac19`, `Ac20`,
`Ac21`, `Ac22`, `Ac23`, `Ac24`, `Ac25`, `Ac31`. Мутации, которые никто не
убил, и тесты без мутации, убиваемой при любом зерне, перечислены в PLAN
находками. Ни одна мутация с исходом «итог неизвестен», «патч не
применяется», «патч трогает тесты», «не прогнана» или «оборвана по пределу»
не засчитана ни убитой, ни выжившей.

AC-5. Исход каждой мутации («убита / не убита») одинаков в «до», «после» и
во всех повторах; в PLAN нет мутации, засчитанной убитой по повтору после
неубийства.

AC-6. На ветке и в каталоге документов нет временных файлов: diff ветки
против базы называет только новые `tests/prior_outcome_sandbox.py` и
`tests/test_outcome_prior_module.py`, изменённый
`tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` и
`docs/codebase-map.md`; в каталоге документов нет подкаталогов, кроме
`acceptance_tests/`, и нет файлов первого уровня с именем `test_*` или
`mutation-*`, кроме патчей `mutation-<nnn>.diff` и таблиц
`mutation-run-<n>.tsv`.

AC-7. `tests/prior_outcome_sandbox.py` не содержит тестов и заявок «Ловит
мутацию» в тестах; его докстринг — одна строка назначения; его операторы
верхнего уровня, кроме докстринга, по `ast.dump` равны в том же порядке
операторам старого файла от `import contextlib` до `CLAIM` включительно и
классам `Moved`, `Link`, `PriorSandbox`, `ReplacementSandbox`,
`StrictSandbox` (сверка в PLAN). `tests/outcome_gate_sandbox.py`,
`tests/merge_outcome_sandbox.py`, `tests/components_outcome_sandbox.py` не
изменены.

AC-8. В `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` нет
классов `Moved`, `Link`, `PriorSandbox`, `ReplacementSandbox`,
`StrictSandbox` и 14 тестовых классов требования 1; сразу после импорта
`MergeOutcomeSandbox` стоит ровно один новый оператор `from
tests.prior_outcome_sandbox import (Moved, ReplacementSandbox,
StrictSandbox)`; каждый прочий оператор верхнего уровня (докстринг, импорты,
константы, `env_lines`, 15 тестовых классов, `unittest.main()`) по
`ast.dump` равен исходному (сверка в PLAN); `pytest --collect-only` файла
собирает 22 теста.

AC-9. В `tests/test_outcome_prior_module.py` нет тестовых классов,
`subTest`, `unittest` и `unittest.main()`; `PriorSandbox`, `Moved`, `Link` и
используемые константы (`OLD`, `SIDES`, `OUTCOME_ACTION`, `PREPARE_ACTION`,
`PASSED_ACTION`, `SKIPPED`, `PRIOR_RED`, `PRIOR_UNSTABLE`, `FLAKY`,
`PRIOR_LINE`, `FILE_ERROR_MARK`) импортированы из
`tests.prior_outcome_sandbox` и ни одна из этих констант — из
`tests.outcome_gate_sandbox`, `tests.merge_outcome_sandbox` или
`tests.components_outcome_sandbox`; `flow`, `py_source`, `GATE_ACTIONS` — из
`tests.outcome_gate_sandbox`; `_sandbox` — из `tests.fixtures`; есть
`import pytest` и прямой `import os`; неиспользуемых имён в импортах нет.

AC-10. Докстринг `tests/test_outcome_prior_module.py` несёт назначение,
свод из прежнего файла со ссылкой на ADR-0020 п. 8, на сокращение
долгоживущего файла решением Оператора, на задачу 2а-2в-2 для остальных
тестов и на таблицы «до»/«после» PLAN, описание стенда и стороны «прежние
версии» с путями `tests.prior_outcome_sandbox.PriorSandbox`,
`tests.merge_outcome_sandbox.MergeOutcomeSandbox` и
`tests.outcome_gate_sandbox.OutcomeGateSandbox`; строк «Группа:
долгоживущий», «Красен до реализации» и абзаца «Провалидировано временным
стабом реализации» в нём нет.

AC-11. Фикстура `box` — `yield from _sandbox(PriorSandbox)` для всех 22
функций; она только создаёт стенд и не зовёт методов с утверждениями
непосредственно или помощником первого уровня; её имя не совпадает с
фикстурами `tests/fixtures.py`.

AC-12. В модуле есть функции с сигнатурами дословно
`def refusal(box, rows: list, output: str, action: str, case: str = "") -> str:`,
`def no_gate_refusal(box, rows: list, output: str, case: str = "") -> None:`
(обе по `ast.dump` равны одноимённым функциям
`tests/test_outcome_gate_module.py`),
`def passed(box, rows: list, output: str, case: str = "") -> str:`,
`def grant(box, t, paths=(), ids=(), covered="tests/sandbox.py:1", case: str = "") -> None:`
и `def conftest_case(box, extra: dict | None, conftest: str):`; тела
`passed`, `grant`, `conftest_case` по AST равны телам исходных методов после
замен требования 14 (сверка в PLAN); утверждения в них — вызовы
`box.assertX(...)`; сообщения `passed` и `grant` — `case + f"…" +
box.explain(...)`.

AC-13. Тело каждой из 22 тестовых функций по AST равно телу исходного
метода после замен требований 16–17 (сверка в PLAN): ожидаемые значения
дословно — литерал остался литералом, константа той же константой; ни одно
сравнение не ослаблено; форма — `assert …` по соответствию требования 16;
текст сообщения — вторым операндом `assert`, утверждение без сообщения
осталось без сообщения; помощники требования 14 вызываются голым именем с
`box` первым аргументом, методы и атрибуты стенда — через `box`;
присваивания `git_fail`, `timeout_when`, `watch_old`, `cases[…]` — через
`box` тем же порядком; вложенные `third`, `index` и лямбды остались
вложенными.

AC-14. В функциях из бывших `subTest` (`test_ac9_code_only_and_new_file_no_third_checkout`,
`test_ac9_changed_base_file_and_file_level_record_in_set`,
`test_ac12_diff_failures_refuse_prepare`,
`test_ac33_prior_skipped_or_missing_is_red`) первой строкой каждого
подслучая стоит `case = f"{label}, зерно {box.seed}: "` (у двух одиночных
блоков `Ac9` — с литералом ярлыка); `case` стоит спереди текста сообщения
каждого прямого утверждения подслучая и передан параметром `case=` в
каждый вызов `refusal`, `no_gate_refusal`, `passed` подслучая.

AC-15. У каждой перенесённой тестовой функции есть строка «Ловит
мутацию:». Локальные переменные, совпадавшие с именами функций или фикстур
модуля, переименованы, перечень — в PLAN. Каждый из 22 тестов, не
перенесённый, перечислен в PLAN удалённым дублем с выполнением условий (а)
и (б) требования 18; тест, чью мутацию не убил никто, не удалён.

AC-16. В PLAN есть раздел «Мутации после» с выводом `mutation-run --ref
worktree --tests tests/test_outcome_prior_module.py --copy-table
--wait-lock 4` теми же диапазонами `--patches` и тем же `--workers`, что
«до», перенесённым дословно, и перед каждой частью — пустой вывод
`git status --porcelain -- orchestrator/`. Дерево `orchestrator/` ревизий
обеих шапок совпадает, sha256 каждого патча в обеих шапках совпадает.

AC-17. Каждую мутацию, убитую «до» тестом T, «после» убивает функция, в
которую перенесён T, перенесённым из T утверждением; в PLAN для каждой
такой мутации есть соответствие «файл:строка до → файл:строка после» и
имён.

AC-18. В PLAN названы число тестов, подслучаев и строк до и после свода и
время «до» и «после» по контрольным прогонам `mutation-run`.

AC-19. В новых и изменённых файлах `tests/` нет `skip`/`xfail`, пределы не
выше исходных. Не изменены `tests/outcome_gate_sandbox.py`,
`tests/merge_outcome_sandbox.py`, `tests/components_outcome_sandbox.py`,
`tests/test_outcome_gate_module.py`, `tests/test_merge_outcome_module.py`,
`tests/test_outcome_components_module.py`, `tests/fixtures.py`,
`tests/sandbox.py`, `tests/test_invariants.py` и всё под `orchestrator/`;
`docs/codebase-map.md` на ветке либо не изменён, либо совпадает с выводом
`python3 scripts/codebase_map.py` на дереве ветки.

## Оценка объёма и деление

Сработавшие сигналы:
- `budget_usd` ≥ $30 — ставка $50 из ТЗ («Бюджет: $50»);
- число критериев приёмки ≥ 10 — их 19.

Прогноз диффа: 125 КиБ — оценка ТЗ (замер 25.10 на приближённой сборке),
ниже половины потолка гейта ёмкости (262 144 байт).

Деление уже выполнено Оператором в ТЗ: эта задача — первая часть волны
2а-2в (стенд `PriorSandbox`), вторая (2а-2в-2: стенды `ReplacementSandbox`
и `StrictSandbox`, удаление долгоживущего файла) заводится после мержа этой.

Обоснование монолита для этой части (материал для решения Оператора на
гейте SPEC):
- перенос песочниц, сокращение долгоживущего файла и свод 22 тестов
  неделимы: свод без сокращения оставляет полные дубли 22 тестов и два
  определения песочниц; сокращение без свода теряет покрытие; перенос
  песочниц без сокращения даёт второе определение классов — оставшиеся
  классы долгоживущего файла должны импортировать `Moved`,
  `ReplacementSandbox`, `StrictSandbox` из нового модуля в том же
  изменении; мандат на путь долгоживущего файла — один `answer`;
- доказательство сравнивает «до» и «после» одним набором патчей при
  неизменном дереве `orchestrator/`;
- дальнейшая нарезка по классам удвоила бы постоянную цену шагов при
  диффе уже вдвое ниже потолка ёмкости.

## Не входит

- Свод 22 тестов на `ReplacementSandbox` и `StrictSandbox` и удаление
  долгоживущего файла — задача 2а-2в-2, заводится после мержа этой.
- Правка докстринга долгоживущего файла (после этой задачи он временно
  описывает песочницы как определённые в нём — неточность снимается
  удалением файла в задаче 2а-2в-2).
- Правка песочниц, в том числе подмена вызова `claude --version`; правка
  `tests/outcome_gate_sandbox.py`, `tests/merge_outcome_sandbox.py`,
  `tests/components_outcome_sandbox.py`.
- Ускорение файла и закрытие строк бэклога «Время файла outcome_prior
  (G3б-2)» и «Предел полного набора 1500 с: вклад волны G».
- Изменение кода пульта: любого кода `orchestrator/`; мутации живут только
  во временной копии `mutation-run`.
- Правка `tests/test_outcome_gate_module.py`, `tests/test_merge_outcome_module.py`,
  `tests/test_outcome_components_module.py`, `tests/fixtures.py`,
  `tests/sandbox.py`, `tests/test_invariants.py`, файлов параллельных волн;
  ручная правка `docs/codebase-map.md`.
- Правка `.github/workflows/ci.yml`, `docs/backlog.md`, `docs/adr/`,
  `scripts/`, `skills/`, `conftest.py`, `pyproject.toml`, `targets.yaml` —
  только чтение.
- Итог CI кодовой ветки в PLAN — роль `gh` не вызывает; цвет CI читает
  ревьювер.
- Выдача мандата на путь долгоживущего файла — `answer` Оператора, не работа
  ролей.
- Проведение независимой проверки (требование 24) — сессия при Операторе
  перед approve мержа, не работа ролей.
- Полный зелёный набор `tests/`, зелёный CI ветки, неизменность защищённых
  путей и непревышение бюджета — их держит пульт.

## Материалы

- `docs/adr/0027-pytest-style-tests.md` (п. 8),
  `docs/adr/0020-long-lived-acceptance-tests-in-tests.md` (пп. 6, 8).
- SPEC волн 2а-2а и 2а-2б: `refs/artifacts/01M5R0DPNHZ7N8YBXMH375SMEE`,
  `refs/artifacts/01M5RH875Q1JMVRM1TXNE6HNMW` — образцы формы требований к
  своду.
- `tests/test_outcome_gate_module.py:813` (фикстура `box`), :821
  (`refusal`), :834 (`no_gate_refusal`); `tests/outcome_gate_sandbox.py:36`
  (`GATE_ACTIONS`), :258 (зерно); `tests/fixtures.py:42` (`_sandbox`);
  `tests/sandbox.py:1956–1960` (`RealGitSandbox.git`).
- `orchestrator/mutation_run.py`, `orchestrator/advance_gates/outcome_integrity.py`,
  `orchestrator/advance_gates/test_integrity.py`,
  `orchestrator/advance_gates/mandate.py`,
  `orchestrator/advance_gates/capacity.py`, `orchestrator/config.py:132`,
  :230, :578, `orchestrator/checkpoint.py:867`, `targets.yaml:53` — только
  чтение.
- `scripts/guard.py` (:1628–1629, :1902, :1926).
- Расхождения ТЗ, снятые его уточнениями 25.10 и учтённые выше: «тест другой
  задачи» — перечнем классов, `Ac30`, `Ac32`, `Ac33` — классы этой задачи;
  `import pytest` в источниках импорта; форма сообщения `passed`/`grant`;
  замена всех прочих `self.<имя>` на `box.<имя>`.
