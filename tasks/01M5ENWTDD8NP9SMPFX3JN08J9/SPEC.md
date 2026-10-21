---
task: 01M5ENWTDD8NP9SMPFX3JN08J9
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/role_prompt.py, orchestrator/agent_log.py, orchestrator/runner.py, orchestrator/watch.py, orchestrator/report.py, orchestrator/plank_run.py, tests/
budget_usd: 30
---

# SPEC: G5б — задание test_author по правилу планки, сводки Vitest, итоговая строка plank-run, скилы приложением

## Контекст
Задача волны G по ADR-0026 («Решение» пп. 4, 5, 11; решения Оператора
19.10 и 21.10 — G5 разделена на G5а и G5б, эта задача — G5б). Сейчас
задание test_author (`orchestrator/role_prompt.py:70`, ветка
`role == "test_author"`, п. 2 на `:80`) при любом фреймворке требует
unittest с методом `test_ac<n>_...` и пометки `# AC-n: …`, хотя guard у
компонента с меткой `AC-<n>: ` (`project_profile.plank_rule`,
`guard.PlankRule.labelled_components`, `LABEL_AC`, `MARKER_SLASH`)
ждёт Vitest-планку с пометками `//`. Сводку прогона роли
(`agent_log.PYTEST_RUN_ACTION`, `pytest_summaries`, насос `OutputPump`,
`runner._spawn_and_wait` → `on_pytest_summary`; читатели — дозор
`orchestrator/watch.py` и отчёт `report._test_author_steps`) и итоговую
строку `plank-run` (`orchestrator/plank_run.py:287-291`, «итог pytest:
итоговой строки нет» у Vitest) итоговый блок Vitest не узнаёт. Скилы
`skills/test-authoring.md` и `skills/review-checklist.md` описывают
только unittest и `tests/`.

Граница задачи: новое поведение — только у задачи, компонент профиля
которой получает от правила планки метку `AC-<n>: ` (задание
test_author), и у задачи с компонентом `report: pult-vitest` (сводки и
итоговая строка); у артели, у записи `test_profile` и у
pytest-компонентов задание ролей, сводки прогонов, дозор, отчёт и вывод
`plank-run` прежние побайтно.

## Требования

1. **Задание test_author по правилу планки.** Признак — компонент
   профиля задачи входит в
   `project_profile.plank_rule(target).labelled_components()` (тот же
   источник, что у guard). При признаке в задании test_author:
   - пункт 2: «Для каждого AC-n напиши тест в
     {task_ref}/acceptance_tests/ (без подкаталогов), имя файла — по
     маскам `<последние сегменты масок tests>`; помощники —
     `_<имя>.<расширение>`. Имя теста `it`/`test` начинается с
     `AC-<n>: `, одна метка на тест, `describe` меткой не начинается —
     ТОЛЬКО из формулировки критерия. На прогоне файлы лежат в
     `<plank_layout с id задачи>`: импорты кода пиши относительно этого
     каталога.»;
   - строка запретов: «В тексте планки запрещены `.fails`, `.skipIf`,
     `.runIf`, `.only`, `vi.setConfig`, ключи `retry`/`timeout` и
     числовой литерал в аргументах `it`/`test`/`describe`/`suite`.»;
   - пункты 3–4: пометки `// AC-n: manual|skip|escalate — …` с начала
     строки в файле планки компонента;
   - пункт 2а (заметка о долгоживущих файлах,
     `_long_lived_author_note`) и пункт 5 (`_plank_run_point`) — прежние.

   Подстановки эталона пункта 2 (решение Оператора на гейте SPEC, круг 1):
   - `<последние сегменты масок tests>` — последний сегмент каждой маски
     `tests` компонента в порядке записи масок, каждый в одинарных
     обратных кавычках, через «, »;
   - `<plank_layout с id задачи>` — значение `plank_layout` компонента,
     в котором `<id>` заменён идентификатором задачи как есть (так же, как
     выкладка, `orchestrator/advance_gates/acceptance.py:254`), в
     одинарных обратных кавычках.

   Меченый компонент без `plank_layout` (решение Оператора на гейте SPEC,
   круг 1): фраза «На прогоне файлы лежат в `<plank_layout с id задачи>`:
   импорты кода пиши относительно этого каталога.» в пункте 2 опускается
   целиком; остальной текст требования 1 — тот же.

   Без признака (артель, `test_profile`, pytest-компоненты, правило не
   построено) — прежний текст задания побайтно.
2. **Сводка прогона Vitest.** Блок — три строки после удаления ANSI и
   крайних пробелов: `Test Files  <сч> (<n>)`; сразу за ней
   `Tests  <сч> (<n>)`, где `<сч>` — `<число> (failed|passed|skipped|todo)`
   через ` | ` либо `no tests`; в пределах следующих четырёх строк
   `Duration  <число>(ms|s)`. Действие журнала —
   `VITEST_RUN_ACTION = "прогон vitest"` (в `orchestrator/agent_log.py`),
   деталь — «<сч Tests> (<n>) in <секунды>s»; секунды — всегда два знака
   после точки и для `ms` (перевод в секунды), и для `s` (`523ms` →
   `0.52s`, `1.5s` → `1.50s`).
3. Насос (`agent_log.OutputPump`) получает новый параметр
   `on_vitest_summary`; `runner._spawn_and_wait` передаёт его, только если
   `decide(target).profile.report == project_profile.REPORT_VITEST`.
   Профиль не определён (`decide(target).profile is None`: пропуск, отказ,
   сбой чтения записи) — прежнее поведение побайтно везде: насос без
   `on_vitest_summary`, прежние строки `plank-run`, прежнее задание
   test_author.
4. Дозор (`orchestrator/watch.py`) относит запись «прогон vitest» к
   классу `pytest` с общим бюджетом строк (сравнение действия —
   принадлежность паре `PYTEST_RUN_ACTION`, `VITEST_RUN_ACTION`). Отчёт:
   `report._test_author_steps` считает секунды обоих действий.
5. `PYTEST_RUN_ACTION`, разбор pytest и их читатели у прочих задач —
   прежние побайтно.
6. **Итоговая строка `plank-run`.** У компонента `pult-vitest` (признак —
   тот же, что у `runner`:
   `decide(target).profile.report == project_profile.REPORT_VITEST`) обе
   строки итога — `orchestrator/plank_run.py:289` (прогон оборван) и
   `:291` — пишут «итог vitest: <деталь>» по разбору требования 2 (нет
   блока — «итоговой строки нет») и «код выхода vitest»; у прочих, в том
   числе при неопределённом профиле (требование 3), — обе строки прежние
   побайтно.
7. **Скилы приложением к PLAN.** Новый раздел в конце
   `skills/test-authoring.md` «Компонент с меткой `AC-<n>: ` (Vitest)»:
   в начале сказано, что разделы о unittest выше относятся к
   Python-компоненту и артели; содержание — метка, запреты, каталог
   планки и импорты относительно выкладки, пометки `//`, долгоживущий
   файл по шаблону `long_lived`, прогон `plank-run`; существующие строки
   не меняются. В `skills/review-checklist.md` — дописка к правилам `:39`
   («Долгоживущие свойства — в `tests/`») и `:102` («Дифф tests/ —
   только импорты и пути патчей»): у компонента с отчётом `pult-vitest`
   «каталог долгоживущих тестов компонента» вместо `tests/`; сверка
   изменённых утверждений — по строкам гейта исходов пакета ревьювера.
   Дописка у компонента `pult-vitest` обязана назвать раздел пакета
   ревьювера «Изменённые утверждения тестов» и строки гейта исходов в нём
   как источник сверки изменённых утверждений; одной замены `tests/` на
   каталог компонента мало (решение Оператора на гейте SPEC, круг 1).
   Правка — приложением к PLAN (защищённые пути), проверка — гейт
   применимости приложений PLAN (`orchestrator/advance_gates/plan_appendix.py`).
8. Тесты детерминированы, без сети и без Node. Существующие тесты, в том
   числе `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`, — без
   правок.

## Критерии приёмки

AC-1. Задание test_author у задачи артели, у записи `test_profile` и у
компонента `junit-xml` с командой pytest побайтно совпадает с эталоном,
снятым с кода пина (до изменения).

AC-2. Задание test_author у компонента `pult-vitest` и у компонента
`junit-xml` с командой не pytest и масками `tests` содержит текст
требования 1: пункт 2 (каталог `acceptance_tests/` без подкаталогов, имя
файла по последним сегментам масок `tests`, помощники `_<имя>.<расширение>`,
метка `AC-<n>: ` в имени `it`/`test`, одна метка, `describe` без метки,
каталог `plank_layout` с id задачи и импорты относительно него), строку
запретов, пометки `// AC-n: manual|skip|escalate — …` в пунктах 3–4;
пункты 2а и 5 — те же, что у прежнего текста. Подстановки — по
требованию 1: последние сегменты масок `tests` в порядке записи, каждый в
обратных кавычках, через «, »; `plank_layout` с `<id>`, заменённым
идентификатором задачи как есть, в обратных кавычках. У компонента с
масками `tests`, командой не pytest и без `plank_layout` задание не
содержит фразы о каталоге выкладки и импортах, остальной текст тот же;
`tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py` остаётся без
правок и проходит.

AC-3. Разбор блока Vitest по фикстурам даёт деталь
«<сч Tests> (<n>) in <секунды>s» для успешного прогона, прогона с
падениями, с `todo`/`skipped`, с `no tests`, с `Duration` в `ms`
и в `s` (секунды всегда с двумя знаками после точки: `523ms` → `0.52s`,
`1.5s` → `1.50s`), а также для вывода с
ANSI-последовательностями; блок без строки `Duration` в пределах
четырёх строк и строка «Tests» внутри листинга кода (без строки
`Test Files` непосредственно перед ней) сводкой не считаются.

AC-4. Насос с переданным `on_vitest_summary` при блоке Vitest в выводе
вызывает его, и в журнал попадает запись с действием
`VITEST_RUN_ACTION == "прогон vitest"` и деталью по разбору AC-3.

AC-5. У задачи артели (и у любой задачи, чей `decide(target).profile.report`
не `pult-vitest`) насос создаётся без `on_vitest_summary`, и записей
«прогон vitest» в журнале нет, даже если блок Vitest присутствует в
выводе инструмента; то же у задачи с неопределённым профилем
(`decide(target).profile is None`: пропуск, отказ, сбой чтения записи) —
без исключения, насос без `on_vitest_summary`, и задание test_author у
такой задачи — прежнее побайтно; у задачи с `report: pult-vitest`
`runner._spawn_and_wait` передаёт насосу `on_vitest_summary`.

AC-6. `PYTEST_RUN_ACTION` равно прежнему значению `"прогон pytest"`, а
разбор pytest и запись «прогон pytest» на прежнем выводе pytest дают
прежние детали побайтно.

AC-7. Дозор показывает запись «прогон vitest» в классе `pytest` с общим
бюджетом строк пары `PYTEST_RUN_ACTION`/`VITEST_RUN_ACTION`; отчёт
(`report._test_author_steps`) суммирует секунды записей обоих действий.

AC-8. `plank-run` у задачи с компонентом `pult-vitest` печатает итог
«итог vitest: <деталь>; код выхода vitest: <код>», а при оборванном по
таймауту прогоне — «итог vitest: <деталь>; прогон превысил …с и
оборван»; без блока Vitest в выводе деталь — «итоговой строки нет».

AC-9. `plank-run` у задачи артели, у pytest-компонента и у задачи с
неопределённым профилем (`decide(target).profile is None`) печатает обе
строки итога («итог pytest: …; код выхода pytest: …» и строку
оборванного прогона) прежними побайтно.

AC-10. PLAN несёт приложение к `skills/test-authoring.md` (новый раздел
в конце «Компонент с меткой `AC-<n>: ` (Vitest)» с вводной фразой об
отнесении разделов о unittest к Python-компоненту и артели и
содержанием из требования 7, существующие строки не меняются) и к
`skills/review-checklist.md` (дописки к правилам `:39` и `:102` по
требованию 7); текст приложения к `skills/review-checklist.md` содержит
название раздела пакета ревьювера «Изменённые утверждения тестов»; оба
приложения проходят гейт применимости приложений PLAN.

## Оценка объёма и деление

Сработавшие сигналы (`guard.split_signal_names`):
- число файлов зоны ≥ 5 — шесть модулей `orchestrator/` плюс `tests/`;
- число критериев приёмки — 10 (порог `SPLIT_SIGNAL_AC_COUNT`);
- затронут инвариантный механизм — зоны задачи упомянуты в
  `docs/invariants.md`; по существу задет журнал шагов (инвариант 11,
  `docs/invariants.md:41`) через `agent_log`/`runner`;
- прогноз диффа не дан — закрыт строкой ниже.

Прогноз диффа: 45 КиБ

Оценка прогноза: код шести модулей `orchestrator/` — ~10 КиБ (задание
test_author, разбор блока Vitest и его вызов в насосе, признак в
`runner`/`plank_run`, пара действий в дозоре и отчёте); тесты `tests/` с
фикстурами вывода Vitest и эталоном задания — ~35 КиБ. Порог сигнала —
половина потолка гейта ёмкости (128 КиБ); приложения к скилам едут в
PLAN, не в дифф ветки.

**Монолит** (решение Оператора на гейте SPEC, круг 1, 21.10): задача уже
выделена из G5 (рамка $30), монолит принят. Сигнал «затронут
инвариантный механизм» снимается тем, что журнал шагов (инвариант 11)
получает только новое действие «прогон vitest», а прежние записи
(в том числе «прогон pytest») и их читатели не меняются (требование 5,
AC-6); `tests/test_invariants.py` задача не трогает.

## Не входит

- Документы `knowledge` в брифе — G5а.
- Сводки Vitest и задание у записи из нескольких компонентов (sled) —
  после G3б.
- Карта кода внешнего проекта.
- Гейты планки и неослабления (G3а-2б-1, G3а-2б-2, G3б).
- Изменение подписей функций модулей «только чтение» и их вызывающих
  (`project_profile.plank_rule`, `guard.PlankRule.labelled_components`,
  `acceptance.run_summary_line`, `orchestrator/brief.py`,
  `orchestrator/doctor/preflight.py`, `orchestrator/providers/claude.py`,
  `orchestrator/artel.py` и прочие перечисленные в ТЗ) — только чтение.
- Проба настоящей формы блока Vitest на sled — этап 2 плана, не тест
  ветки.
- Зелёный полный набор `tests/` — её держит пульт.

- Приложением к PLAN, не правкой ветки: `skills/test-authoring.md`,
  `skills/review-checklist.md`.
- Только чтение: `docs/adr/0026-project-components-and-outcome-gates.md`,
  `orchestrator/project_profile.py`, `scripts/guard.py`,
  `orchestrator/acceptance.py`, `orchestrator/targets.py`,
  `orchestrator/store.py`, `orchestrator/config.py`,
  `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/brief.py`,
  `orchestrator/doctor/preflight.py`, `orchestrator/providers/claude.py`,
  `orchestrator/artel.py`, `orchestrator/amend.py`,
  `orchestrator/suite_run.py`, `orchestrator/reporters/outcome.py`,
  `orchestrator/advance_gates/acceptance.py`,
  `orchestrator/advance_gates/tests_writing.py`,
  `orchestrator/checkpoint.py`, `orchestrator/dry_run.py`,
  `orchestrator/fsm.py`, `orchestrator/fsm_autogate.py`,
  `orchestrator/fsm_merge_gate.py`, `orchestrator/preflight.py`.

## Материалы

- `tasks/01M5ENWTDD8NP9SMPFX3JN08J9/TZ.md`
- `docs/adr/0026-project-components-and-outcome-gates.md`, «Решение»
  пп. 4, 5, 11.
- `orchestrator/role_prompt.py:70-95` (`_long_lived_author_note` `:201`,
  `_plank_run_point` `:237`); `orchestrator/project_profile.py:328`
  (`REPORT_VITEST`), `:470` (`plank_rule`); `scripts/guard.py:494`
  (`plank_ban_errors`), `:2777-2779`, `:2880`;
  `orchestrator/agent_log.py:221`, `:239`, `:354`;
  `orchestrator/runner.py:1619`, `:1710`; `orchestrator/watch.py:221`,
  `:288`, `:446`; `orchestrator/report.py:99`, `:947`, `:969`;
  `orchestrator/plank_run.py:287-291`.
- `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py:177`,
  `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py:453`.
