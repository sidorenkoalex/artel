---
task: 01M5RH875Q1JMVRM1TXNE6HNMW
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/, docs/codebase-map.md
budget_usd: 40
---

# SPEC: Сведение тестов, волна 2а-2б — песочницы гейта исходов по компонентам в `tests/components_outcome_sandbox.py`, тесты `outcome_components` в `tests/test_outcome_components_module.py`, пути стенда в докстринге `outcome_prior`; стиль pytest, доказательство мутациями

## Контекст
Строка бэклога «Периодическая консолидация тестов артели» (решение Оператора
23.10.2026); ADR-0027 п. 8 и ADR-0020 п. 8: старые тесты переводятся в стиль
pytest и удаляются волнами консолидации, доказательство — множество
убиваемых мутаций, мандат Оператора по путям и независимая проверка. Порядок
волн (решение 23.10.2026): note → outcome → merge → suite-run → остальные;
мандат Оператора 23.10.2026 (дословно): «Волна сведения тестов по note;
после бери все остальные модули в работу - даю мандат»; до трёх волн
одновременно (решение 24.10.2026). Волна 2а-2а (01M5R0DPNHZ7N8YBXMH375SMEE)
смержена 25.10 (c04d747b): песочница мержа — в `tests/merge_outcome_sandbox.py`,
тесты — в `tests/test_merge_outcome_module.py`; правку докстрингов импортёров
она оставила этой семье задач.

Файлы (факты ТЗ сверены аналитиком на ad3608c6):
- `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py` — 650
  строк, 40 767 байт, 17 тестов, 17 заявок «Ловит мутацию»; долгоживущий
  файл задачи 01M5JGSAANR1NZYQD4FCSVE48Y (в `done`); импортёров нет. Константы
  `PASSED_ACTION` … `COUNTS` — :47–56, `ContextRunnerProc` — :59,
  `ComponentsOutcomeSandbox(MergeOutcomeSandbox)` — :71, тестовые классы
  `Ac16DiffComponentsTest` … `Ac13Ac14GateMandateTest` — :240–553,
  `FAIL_TO_PASS_ACTION`, `FOREIGN` — :554–555, `ForeignPlankSandbox` — :558,
  `Ac19ForeignPlankTest`, `Ac25TrainingProjectTest`,
  `Ac27OutOfBoundsForeignTest` — :579 и далее. `unittest` и `subTest` в
  файле нет; утверждений-предусловий с пометкой нет.
- Утверждения подготовки — `ComponentsOutcomeSandbox.writing_task`
  (`assertIsNone`) и `component_task` (`assertEqual` состояния `in_dev`).
  Утверждение исхода — `Ac13Ac14GateMandateTest.mandate_answer`
  (`assertIn(exc.code, (None, 0), …)`). Без утверждений —
  `Ac18ReviewLinesTest.review_section` (локальный импорт `review`) и
  `Ac13Ac14GateMandateTest.broken_consumer`.
- Случайность — зерно `OutcomeGateSandbox.setUp`
  (`tests/outcome_gate_sandbox.py:258`), новое на каждый тест: имена, числа
  тестов `backend`/`frontend`, номер критерия, выбор `broken` и `other`.
  Самый долгий тест — около 5,3 с; один прогон файла — 50,9 с.
- Заявка `test_ac19_task_out_of_bounds_still_refused` ссылается на
  `fsm_advance.py:609–613`; на ad3608c6 условие `in_outcome_bounds(profile)` —
  `orchestrator/fsm_advance.py:617`.
- `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` (44 теста) —
  докстринг :6–8, абзац «Стенд — …», называет два удалённых пути
  (`tests.test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.MergeOutcomeSandbox`,
  `tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.OutcomeGateSandbox`).

Размещение выбрано Оператором в ТЗ: песочницы — новый модуль (дописка в
`tests/merge_outcome_sandbox.py` дала бы второе определение
`PREPARE_ACTION`), тесты — новый модуль (совпадения имён `PASSED_ACTION`,
`PREPARE_ACTION`, `NOT_RUN` и фикстуры `box` с `tests/test_merge_outcome_module.py`,
другой стенд, 17 тестов вместо 36 на прогон патча).

guard прослеживает помощника с утверждениями только при вызове
`self.<метод>` по цепочке классов или голым именем функции своего модуля
либо `tests/sandbox.py` (`scripts/guard.py:1902–1924`, :1926–1948); текст
сообщения `assert` нормализатор отбрасывает (:1628–1634). Гейт ёмкости
диффа — 262 144 байта; оценка ТЗ — 80–90 КБ. `mutation-run` несёт
`--workers <n>`, `--wait-lock <минуты>` (сумма с `--wait` — не больше 9
минут), `--copy-table`; предел части — 1500 с (`targets.yaml:53`). Шаг роли
— `AGENT_TIMEOUT_SEC` = 2700 с (`orchestrator/config.py:132`). Роли не
вызывают `gh`: цвет CI кодовой ветки читает ревьювер.

ТЗ несёт раздел «Уточнения по независимой проверке 25.10», которые при
расхождении с основным текстом ТЗ действуют; требования ниже записаны уже с
ними.

## Требования

1. Мутации «до». Для каждой из 17 заявок — патч к коду `orchestrator/` в
   `tasks/<id>/mutation-<nnn>.diff`, номера подряд с 001, в порядке тестов
   файла. Патч реализует ровно мутацию заявки; у заявки с несколькими
   альтернативами (через «;» или «либо») — по патчу на каждую, если они не
   одинаковы по смыслу; одинаковые по смыслу альтернативы разных заявок —
   одна мутация со списком тестов. У каждой мутации в PLAN — её заявка,
   альтернатива, что меняет патч (модуль и функция по имени) и одна фраза
   обоснования независимости от случайности: какие случайные значения
   (имена, числа тестов, `broken`, `other`) участвуют в проверяемом
   утверждении и почему исход «убита» от них не зависит.
2. Таблица «до»: `mutation-run <id> --ref base --tests
   tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py --copy-table
   --wait-lock 4` частями `--patches` не больше 15 патчей; отчёт части —
   повторными `mutation-run <id> --wait 5` до итоговой строки; вывод — в
   PLAN, раздел «Мутации до», дословно, с шапкой и всеми строками, до
   старта следующей части.
3. У каждой мутации «до» и «после» в PLAN — строка падения из лога прогона
   патча (файл:строка упавшего утверждения).
4. Доказательством не считается мутация, «убитая» ошибкой сбора, импорта,
   setup или фикстуры; исключением без падения утверждения; по таймауту
   pytest-timeout (`Timeout` в логе); только утверждением методов подготовки
   (`writing_task`, `component_task`, методов песочниц-предков —
   `in_dev_task`, `artel_in_dev_task`, `operator_mandate`, `direct_task`,
   `verifying_task`, `rewrite_passed` — или `RealGitSandbox.git` из
   `tests/sandbox.py`, проверки кода возврата git); непрошедшим предусловием
   сценария: патч переписывается так, чтобы падало утверждение теста. Все
   утверждения тела теста, включая проверку состояния задачи, — утверждения
   теста. Утверждение `mandate_answer` — утверждение исхода и
   доказательством считается. Мутация, не убитая никем, — находка в PLAN.
5. Мутация убивается детерминированно при любом зерне: расхождение «убита /
   не убита» между «до», «после» и повтором — заявка или патч
   переписывается так, чтобы исход не зависел от случайных значений;
   повторы до убийства запрещены. Если для теста нет мутации, убиваемой при
   любом зерне, — находка в PLAN; тест не удаляется, зерно не фиксируется,
   ожидания и выбор `broken`/`other` не меняются.
6. Исходы «итог неизвестен», «патч не применяется», «патч трогает тесты»,
   «не прогнана» — патч переписывается и прогоняется заново. Часть,
   оборванная пределом, раскладывается на меньшие части, а не прогоняется
   тем же набором.
7. Красный контроль — повтор тем же вызовом в следующем шаге; повторно
   красный — с `--workers 4` частями не больше 15 патчей (число рабочих
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
   `tests/components_outcome_sandbox.py` и
   `tests/test_outcome_components_module.py`, изменённый
   `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, удаление
   `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py` и
   `docs/codebase-map.md` (только вывод генератора).
10. Песочницы. Импорты и константы от `import contextlib` до `COUNTS`
    включительно, классы `ContextRunnerProc` и `ComponentsOutcomeSandbox`,
    константы `FAIL_TO_PASS_ACTION`, `FOREIGN` и класс `ForeignPlankSandbox`
    переносятся из `outcome_components` целиком и дословно, в том же
    порядке, в новый модуль `tests/components_outcome_sandbox.py`: тестов и
    заявок он не содержит, докстринг — новый, одной строкой назначения.
    `ast.dump` каждого оператора верхнего уровня, кроме нового докстринга,
    равен исходному — сверка в PLAN. Ненужные песочницам импорты
    (`contextlib`, `io`, `answer`, `mandate`, `outcome_integrity`,
    `MATRIX_HEADERS`) переезжают дословно. Методы песочниц, в том числе с
    утверждениями подготовки, не меняются. `tests/merge_outcome_sandbox.py`
    и `tests/outcome_gate_sandbox.py` не меняются.
11. Импортёр `outcome_prior`: в абзаце докстринга «Стенд — …» меняются
    только два пути —
    `tests.test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.MergeOutcomeSandbox`
    на `tests.merge_outcome_sandbox.MergeOutcomeSandbox` и
    `tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.OutcomeGateSandbox`
    на `tests.outcome_gate_sandbox.OutcomeGateSandbox`; разбивка строк,
    остальной текст докстринга и весь код не меняются (`ast.dump` модуля
    без докстринга равен исходному — сверка в PLAN). Файл проходит гейт
    неослабления без мандата; находка гейта по нему — эскалация, не обход.
    Под ролью для `outcome_prior` — только `pytest --collect-only` (44
    теста); его зелень — по CI кодовой ветки, которую читает ревьювер (роль
    `gh` не вызывает и итог CI в PLAN не пишет).
12. Свод: 17 тестов — функции нового `tests/test_outcome_components_module.py`
    в стиле pytest, без тестовых классов, `unittest` и `subTest`.
    Источники импорта — явно для каждого имени: из
    `tests.components_outcome_sandbox` — `ComponentsOutcomeSandbox`,
    `ForeignPlankSandbox` и нужные тестам константы бывшего файла
    (`PASSED_ACTION`, `OUTCOME_ACTION`, `BROKEN_ACTION`, `PREPARE_ACTION`,
    `SKIP_RECORD`, `OUT_OF_BOUNDS`, `NOT_RUN`, `COUNTS`, `FOREIGN`;
    одноимённые константы `tests.merge_outcome_sandbox` и
    `tests.outcome_gate_sandbox` не импортируются, даже при равном
    значении); из `tests.outcome_gate_sandbox` — `MATRIX_HEADERS`; `_sandbox`
    — из `tests.fixtures`; модули пульта (`answer`, `project_profile`,
    `mandate`, `outcome_integrity`) — прямым импортом тем же способом, что в
    бывшем файле; из стандартной библиотеки — только `contextlib` и `io`
    (плюс `pytest`); неиспользуемые импорты не переносятся.
13. Докстринг нового модуля — назначение, свод из прежнего файла (ADR-0020
    п. 8: долгоживущий файл удалён решением Оператора, его свойства
    перенесены сюда, доказательство — таблицы «до» и «после» в PLAN),
    описание стенда из прежнего докстринга с новыми путями
    (`tests.components_outcome_sandbox.ComponentsOutcomeSandbox` поверх
    `tests.merge_outcome_sandbox.MergeOutcomeSandbox`); строки «Группа:
    долгоживущий» и «Красен до реализации» не переносятся.
14. Фикстуры только создают стенд и не зовут методов с утверждениями: `box`
    — `yield from _sandbox(ComponentsOutcomeSandbox)` для бывших классов
    `Ac16`, `Ac17`, `Ac18`, `Ac22`, `Ac13Ac14`; `foreign_box` — `yield from
    _sandbox(ForeignPlankSandbox)` для бывших `Ac19`, `Ac25`, `Ac27`; имена
    фикстур не совпадают с фикстурами `tests/fixtures.py`.
15. Методы тестовых классов — функции модуля с сигнатурами дословно:
    `def mandate_answer(box, t, marker: str, element: str, matrix_element: str, covered: str) -> None:`,
    `def review_section(box, t) -> str:`, `def broken_consumer(box):`; тело
    дословно, `self.` заменено именем параметра; утверждение исхода
    `mandate_answer` остаётся вызовом `box.assertIn(...)` дословно; параметр
    `case` не вводится; локальный импорт `review` остаётся внутри тела
    `review_section`. Тест зовёт их голым именем. Сверка по AST тела каждой
    функции с телом метода (с заменой `self` на имя параметра) — в PLAN.
16. Методы песочниц тест зовёт через стенд; методы песочниц не меняются.
    Присваивания атрибутам стенда (`no_marker`, `git_fail`, `cases[…]`) —
    через имя фикстуры, дословно и тем же порядком.
17. Утверждения и проверяемые свойства не меняются: соответствие
    `assertEqual(a, b)` ↔ `assert a == b`, `assertTrue(x)` ↔ `assert x`,
    `assertIn(a, b)` ↔ `assert a in b`, `assertNotIn(a, b)` ↔
    `assert a not in b`; `self.<помощник>` ↔ функция модуля; `self` ↔ имя
    фикстуры; ожидания и литералы дословно; литерал остаётся литералом,
    константа — той же константой (равенство значений доводом не
    считается); совпадение нормальной формы guard не требуется. Текст
    сообщения (`self.note(...)`, `self.explain(...)`, их конкатенация) —
    вторым операндом `assert`; утверждение без сообщения остаётся без
    сообщения. Локальная переменная теста, совпадающая с именем функции или
    фикстуры модуля, переименовывается (перечень — в PLAN).
18. Дубль удаляется только если (а) каждую его мутацию по таблице «до»
    убивает и другой сохраняемый тест того же исходного файла и (б) каждый
    литерал и вид каждого утверждения удаляемого теста есть в утверждениях
    сохраняемого теста, убивающего те же мутации; удалённые дубли — в PLAN.
    Тест, чью мутацию не убил никто, не удаляется (заявка переписывается на
    мутацию, которую он убивает, либо находка в PLAN). У каждой функции —
    «Ловит мутацию:».
19. В заявке `test_ac19_task_out_of_bounds_still_refused` устаревшая ссылка
    на строки `fsm_advance.py` заменяется на «гейт FAIL_TO_PASS добавляется
    только по профилю задачи в границе (`fsm_advance.tests_writing`,
    условие `in_outcome_bounds(profile)`)».
20. Таблица «после»: `mutation-run <id> --ref worktree --tests
    tests/test_outcome_components_module.py --copy-table --wait-lock 4` теми
    же диапазонами `--patches` и тем же `--workers`, что «до»; вывод — в
    PLAN, раздел «Мутации после», дословно; перед каждой частью — пустой
    вывод `git status --porcelain -- orchestrator/`. Правила требований 3–8
    действуют и здесь.
21. Для каждой мутации, убитой «до» тестом T, «после» её убивает функция, в
    которую перенесён T, перенесённым из T утверждением (по соответствию
    требования 17); соответствие «файл:строка до → файл:строка после» и
    имён — в PLAN. Дерево `orchestrator/` ревизий обеих шапок совпадает,
    sha256 каждого патча совпадает; при подтяжке main с изменением
    `orchestrator/` «до» прогоняется заново.
22. Под ролью адресно прогоняется только
    `tests/test_outcome_components_module.py` (и `--collect-only`
    `outcome_prior` по требованию 11); время «до» и «после» — по контрольным
    прогонам `mutation-run`; число тестов и строк до и после — в PLAN.
23. `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py` удаляется
    (мандат — `answer` только на этот путь; распознанное git переименование
    удаляемого файла в новый модуль покрывается тем же мандатом по старому
    пути, новые пути в мандат не вносятся; `outcome_prior` проходит гейт
    без мандата). Удаление утверждения без переноса, ослабление сравнения,
    `skip`/`xfail`, подъём пределов не разрешены. Ожидаемая находка
    храповика — в новом модуле прослеживается меньше утверждений (методы
    песочниц зовутся через стенд): убыль приписывается удаляемому пути и
    покрыта мандатом на него — не повод для эскалации, мандат не
    расширяется.
24. Ограничение зон по смыслу: в `tests/` — новые
    `tests/components_outcome_sandbox.py` и
    `tests/test_outcome_components_module.py`, в
    `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` — только два
    пути в докстринге (требование 11), удаление файла требования 23;
    `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`,
    `tests/test_merge_outcome_module.py`, `tests/test_outcome_gate_module.py`,
    `tests/fixtures.py`, `tests/sandbox.py`, `tests/test_invariants.py` и
    файлы идущих параллельно волн не меняются; код `orchestrator/` не
    меняется; `docs/codebase-map.md` — только вывод генератора.
25. Независимая проверка (повтор `mutation-run`, сравнение утверждений по
    AST, сверка `ast.dump` переноса песочниц, функций из методов тестовых
    классов и модуля `outcome_prior` без докстринга) — сессией при
    Операторе до approve на merge_gate.

## Критерии приёмки

AC-1. В каталоге документов задачи первым уровнем лежат патчи
`mutation-<nnn>.diff` с номерами подряд от 001 без пропусков, в порядке
тестов файла; каждый патч меняет только файлы под `orchestrator/`. В PLAN
каждая из 17 заявок сопоставлена мутации (по одной на каждую не одинаковую
по смыслу альтернативу; одинаковые по смыслу альтернативы разных заявок —
одной мутации со списком тестов), и у каждой мутации названы заявка,
альтернатива, что меняет патч (модуль и функция) и фраза обоснования
независимости исхода от случайных значений.

AC-2. В PLAN есть раздел «Мутации до» с выводом каждой части
`mutation-run --ref base --tests
tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py --copy-table
--wait-lock 4`, перенесённым дословно, с шапкой и всеми строками; ни одна
часть не длиннее 15 патчей; число рабочих процессов и диапазоны названы; в
таблицах есть каждая мутация набора.

AC-3. У каждой мутации в PLAN для «до» и «после» есть строка падения из
лога прогона патча (файл:строка упавшего утверждения).

AC-4. Ни одна мутация не засчитана доказательством, если её убили только
ошибка сбора, импорта, setup или фикстуры, исключение без падения
утверждения, таймаут pytest-timeout, утверждение методов подготовки
(`writing_task`, `component_task`, `in_dev_task`, `artel_in_dev_task`,
`operator_mandate`, `direct_task`, `verifying_task`, `rewrite_passed`,
`RealGitSandbox.git`) или непрошедшее предусловие сценария. Мутации,
которые никто не убил, и тесты без мутации, убиваемой при любом зерне,
перечислены в PLAN находками. Ни одна мутация с исходом «итог неизвестен»,
«патч не применяется», «патч трогает тесты», «не прогнана» или «оборвана по
пределу» не засчитана ни убитой, ни выжившей.

AC-5. Исход каждой мутации («убита / не убита») одинаков в «до», «после» и
во всех повторах; в PLAN нет мутации, засчитанной убитой по повтору после
неубийства.

AC-6. На ветке и в каталоге документов нет временных файлов: diff ветки
против базы называет только новые `tests/components_outcome_sandbox.py` и
`tests/test_outcome_components_module.py`, изменённый
`tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, удаление
`tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py` и
`docs/codebase-map.md`; в каталоге документов нет подкаталогов, кроме
`acceptance_tests/`, и нет файлов первого уровня с именем `test_*` или
`mutation-*`, кроме патчей `mutation-<nnn>.diff` и таблиц
`mutation-run-<n>.tsv`.

AC-7. `tests/components_outcome_sandbox.py` не содержит тестов и заявок
«Ловит мутацию»; его докстринг — одна строка назначения; его операторы
верхнего уровня, кроме докстринга, по `ast.dump` равны в том же порядке
операторам старого файла от `import contextlib` до `COUNTS`, классам
`ContextRunnerProc`, `ComponentsOutcomeSandbox`, константам
`FAIL_TO_PASS_ACTION`, `FOREIGN` и классу `ForeignPlankSandbox` (сверка в
PLAN). `tests/merge_outcome_sandbox.py` и `tests/outcome_gate_sandbox.py` не
изменены.

AC-8. В `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` по
сравнению с базой изменены только два пути в абзаце докстринга «Стенд — …»
(на `tests.merge_outcome_sandbox.MergeOutcomeSandbox` и
`tests.outcome_gate_sandbox.OutcomeGateSandbox`), разбивка строк та же;
`ast.dump` модуля без докстринга равен исходному (сверка в PLAN); `pytest
--collect-only` файла собирает 44 теста.

AC-9. В `tests/test_outcome_components_module.py` нет тестовых классов,
`subTest`, `unittest` и `unittest.main()`; `ComponentsOutcomeSandbox`,
`ForeignPlankSandbox` и константы `PASSED_ACTION`, `OUTCOME_ACTION`,
`BROKEN_ACTION`, `PREPARE_ACTION`, `SKIP_RECORD`, `OUT_OF_BOUNDS`,
`NOT_RUN`, `COUNTS`, `FOREIGN` импортированы из
`tests.components_outcome_sandbox` и ни одна из них — из
`tests.merge_outcome_sandbox` или `tests.outcome_gate_sandbox`;
`MATRIX_HEADERS` — из `tests.outcome_gate_sandbox`; `_sandbox` — из
`tests.fixtures`; из стандартной библиотеки импортированы только
`contextlib` и `io` (плюс `pytest`); неиспользуемых имён в импортах нет.

AC-10. Докстринг `tests/test_outcome_components_module.py` несёт
назначение, свод из прежнего файла со ссылкой на ADR-0020 п. 8 и таблицы
«до»/«после» PLAN и описание стенда с путями
`tests.components_outcome_sandbox.ComponentsOutcomeSandbox` и
`tests.merge_outcome_sandbox.MergeOutcomeSandbox`; строк «Группа:
долгоживущий» и «Красен до реализации» в нём нет.

AC-11. Фикстуры `box` (`yield from _sandbox(ComponentsOutcomeSandbox)`, для
бывших `Ac16`, `Ac17`, `Ac18`, `Ac22`, `Ac13Ac14`) и `foreign_box`
(`yield from _sandbox(ForeignPlankSandbox)`, для бывших `Ac19`, `Ac25`,
`Ac27`) только создают стенд и не зовут методов с утверждениями; их имена
не совпадают с фикстурами `tests/fixtures.py`.

AC-12. В модуле есть функции
`def mandate_answer(box, t, marker: str, element: str, matrix_element: str, covered: str) -> None:`,
`def review_section(box, t) -> str:` и `def broken_consumer(box):`, тело
каждой по AST равно телу исходного метода с заменой `self` на имя параметра
(сверка в PLAN); утверждение `mandate_answer` — вызов `box.assertIn(...)`;
локальный импорт `review` — внутри тела `review_section`; тесты зовут эти
функции голым именем, методы песочниц — через стенд; присваивания
`no_marker`, `git_fail`, `cases[…]` идут через имя фикстуры тем же порядком;
методы песочниц не изменены.

AC-13. Ожидаемые значения перенесённых тестов совпадают с исходными
дословно: литерал остался литералом, константа — той же константой; ни одно
сравнение не ослаблено; форма — `assert …` по соответствию требования 17;
текст сообщения (`self.note(...)`, `self.explain(...)`, их конкатенация) —
вторым операндом `assert`, утверждение без сообщения осталось без
сообщения; локальные переменные, совпадавшие с именами функций или фикстур
модуля, переименованы, перечень — в PLAN.

AC-14. У каждой перенесённой тестовой функции есть строка «Ловит
мутацию:»; в заявке `test_ac19_task_out_of_bounds_still_refused` нет ссылки
на строки `fsm_advance.py`, вместо неё — «гейт FAIL_TO_PASS добавляется
только по профилю задачи в границе (`fsm_advance.tests_writing`, условие
`in_outcome_bounds(profile)`)». Каждый из 17 тестов, не перенесённый,
перечислен в PLAN удалённым дублем с выполнением условий (а) и (б)
требования 18; тест, чью мутацию не убил никто, не удалён.

AC-15. В PLAN есть раздел «Мутации после» с выводом `mutation-run --ref
worktree --tests tests/test_outcome_components_module.py --copy-table
--wait-lock 4` теми же диапазонами `--patches` и тем же `--workers`, что
«до», перенесённым дословно, и перед каждой частью — пустой вывод
`git status --porcelain -- orchestrator/`. Дерево `orchestrator/` ревизий
обеих шапок совпадает, sha256 каждого патча в обеих шапках совпадает.

AC-16. Каждую мутацию, убитую «до» тестом T, «после» убивает функция, в
которую перенесён T, перенесённым из T утверждением; в PLAN для каждой
такой мутации есть соответствие «файл:строка до → файл:строка после» и
имён.

AC-17. В PLAN названы число тестов и строк до и после свода и время «до» и
«после» по контрольным прогонам `mutation-run`.

AC-18. На ветке нет `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`.
В новых и изменённых файлах `tests/` нет `skip`/`xfail`, пределы не выше
исходных. Не изменены `tests/merge_outcome_sandbox.py`,
`tests/outcome_gate_sandbox.py`, `tests/test_merge_outcome_module.py`,
`tests/test_outcome_gate_module.py`, `tests/fixtures.py`, `tests/sandbox.py`,
`tests/test_invariants.py` и всё под `orchestrator/`; `docs/codebase-map.md`
на ветке либо не изменён, либо совпадает с выводом
`python3 scripts/codebase_map.py` на дереве ветки.

## Оценка объёма и деление

Сработавшие сигналы:
- `budget_usd` ≥ $30 — ставка $40 из ТЗ («Бюджет: $40»);
- число критериев приёмки ≥ 10 — их 18;
- число файлов зоны ≥ 5 — четыре файла `tests/` и `docs/codebase-map.md`.

Прогноз диффа по оценке ТЗ — 80–90 КБ, ниже половины потолка гейта ёмкости
(262 144 байт).

Обоснование монолита (материал для решения Оператора на гейте SPEC).
Части задачи сцеплены:
- перенос песочниц, свод тестов и удаление старого файла неделимы: свод
  без удаления оставляет полные дубли и два определения песочниц, удаление
  без свода теряет покрытие; мандат на удаление — один `answer`;
- доказательство сравнивает «до» и «после» одним набором патчей при
  неизменном дереве `orchestrator/`;
- правка двух путей в докстринге `outcome_prior` — меньше 1 КБ; отдельная
  задача удвоила бы постоянную цену шагов (аналитик, автор тестов, ревью)
  ради правки докстринга, а следующая волна `outcome_prior` по ТЗ
  заводится только после мержа этой.

## Не входит

- Сведение `outcome_prior` (113 КБ, 44 теста — следующая отдельная волна,
  заводится после мержа этой); правка кода и иного текста `outcome_prior`,
  кроме двух путей докстринга.
- Правка песочниц, в том числе подмена вызова `claude --version`; правка
  `tests/merge_outcome_sandbox.py`, `tests/outcome_gate_sandbox.py`.
- Замена поддельного раннера на `sh` (M3 не делается).
- Изменение кода пульта: любого кода `orchestrator/`; мутации живут только во
  временной копии `mutation-run`.
- Правка `tests/test_merge_outcome_module.py`, `tests/test_outcome_gate_module.py`
  (упоминания удалённых путей в их докстрингах — история свода),
  `tests/fixtures.py`, `tests/sandbox.py`, `tests/test_invariants.py`, файлов
  параллельных волн; ручная правка `docs/codebase-map.md`.
- Правка `docs/backlog.md`, `docs/adr/`, `scripts/`, `skills/`,
  `conftest.py`, `pyproject.toml`, `targets.yaml` — только чтение.
- Итог CI кодовой ветки в PLAN — роль `gh` не вызывает; цвет CI читает
  ревьювер.
- Выдача мандата на удаление файла — `answer` Оператора, не работа ролей.
- Проведение независимой проверки (требование 25) — сессия при Операторе
  перед approve мержа, не работа ролей.
- Полный зелёный набор `tests/`, зелёный CI ветки, неизменность защищённых
  путей и непревышение бюджета — их держит пульт.

## Материалы

- `docs/adr/0027-pytest-style-tests.md` (п. 8),
  `docs/adr/0020-long-lived-acceptance-tests-in-tests.md` (пп. 6, 8).
- SPEC волны 2а-2а: `refs/artifacts/01M5R0DPNHZ7N8YBXMH375SMEE` — образец
  формы требований к своду.
- `orchestrator/mutation_run.py`, `orchestrator/advance_gates/outcome_integrity.py`,
  `orchestrator/advance_gates/test_integrity.py`,
  `orchestrator/advance_gates/mandate.py`,
  `orchestrator/advance_gates/capacity.py`, `orchestrator/fsm_advance.py:617`,
  `orchestrator/advance_gates/tests_writing.py:1090`,
  `orchestrator/checkpoint.py:867` — только чтение.
- `scripts/guard.py` (:1628–1634, :1902–1924, :1926–1948), `tests/fixtures.py`
  (`_sandbox(cls)`), `tests/outcome_gate_sandbox.py:258`, `targets.yaml:53`,
  `orchestrator/config.py:132`.
- Расхождения ТЗ, снятые его уточнениями 25.10: части при `--workers 4` — до
  15 патчей (основной текст — до 5); стандартная библиотека нового модуля —
  только `contextlib` и `io` (основной текст — «тем же способом, что в
  бывшем файле»).
