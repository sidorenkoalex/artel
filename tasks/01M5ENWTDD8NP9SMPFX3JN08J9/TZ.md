---
task: 01M5ENWTDD8NP9SMPFX3JN08J9
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: G5б: задание test_author по правилу планки, сводки Vitest, итоговая строка plank-run, скилы приложением

# G5б: задание test_author по правилу планки, сводки прогонов Vitest, итоговая строка plank-run, скилы приложением

## Факты

Задача волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`, «Решение» п. 4 — сводки прогонов и итоговая строка узнают команды компонентов; п. 5 — требования к планке с меткой `AC-<n>: `, «импорты — относительно выкладки»; п. 11 — задание test_author и скилы по фреймворку компонента). Решения Оператора 19.10 (вынос из G2б в G5: задание test_author по фреймворку и `skills/test-authoring.md`) и 21.10 (G5 делится на G5а и G5б — эта задача; обе параллельно с G3а-2б-1).

**Граница задачи одной фразой:** новое поведение — только у задачи, компонент профиля которой получает от правила планки метку `AC-<n>: ` (задание test_author), и у задачи с компонентом `report: pult-vitest` (сводки и итоговая строка); у артели, у записи `test_profile` и у pytest-компонентов задание ролей, сводки прогонов, дозор, отчёт и вывод `plank-run` прежние побайтно.

- Задание test_author — `orchestrator/role_prompt.py:70` (ветка `role == "test_author"`): «Для каждого AC-n напиши unittest в {task_ref}/acceptance_tests/test_*.py, метод test_ac<n>_...» (`orchestrator/role_prompt.py:80`) при любом фреймворке; пометки пунктов 3–4 — `# AC-n: manual|skip|escalate`; заметка о долгоживущих файлах — `orchestrator/role_prompt.py:201` (`_long_lived_author_note`, уже по шаблону `long_lived`; дословно закреплена `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py:177`); прогон планки — `orchestrator/role_prompt.py:237` (`_plank_run_point`).
- Метку `AC-<n>: ` и пометки `//` guard ставит по правилу планки, а не по `report`: `orchestrator/project_profile.py:470` (`plank_rule`; компонент с масками `tests` и командой не pytest), `scripts/guard.py:2880` (`labelled_components`), `scripts/guard.py:2777` (`LABEL_AC`), `scripts/guard.py:2779` (`MARKER_SLASH`); запреты текста планки — `scripts/guard.py:494` (`plank_ban_errors`:  `.fails`, `.skipIf`, `.runIf`, `.only`, `vi.setConfig`, ключи `retry`/`timeout`, числовой литерал в аргументах первого уровня `it`/`test`/`describe`/`suite`, две метки в имени, `describe` с меткой в начале). Пометка `# AC-n` в `.jsx` пометкой не считается (`tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py:453`).
- Сводка прогона роли: `orchestrator/agent_log.py:221` (`PYTEST_RUN_ACTION = "прогон pytest"`), разбор — `orchestrator/agent_log.py:239` (`pytest_summaries`); насос — `orchestrator/agent_log.py:354` (`OutputPump`), запись в журнал — `orchestrator/runner.py:1710` (`on_pytest_summary` в `_spawn_and_wait`, `orchestrator/runner.py:1619`); читатели — дозор `orchestrator/watch.py:221`, `:288`, `:446` (класс `pytest`, бюджет строк) и отчёт: функция `_test_author_steps` (`orchestrator/report.py:947`), сверка действия — `orchestrator/report.py:969`; секунды — `orchestrator/report.py:99`, `_PYTEST_SECONDS_RE`. Итоговый блок Vitest не узнаёт никто.
- Итоговая строка `plank-run` — `orchestrator/plank_run.py:287-291`: «итог pytest: <строка>» по `acceptance.run_summary_line`; у Vitest — «итог pytest: итоговой строки нет».
- Скилы: `skills/test-authoring.md:23-28` («unittest в tasks/<id>/acceptance_tests/test_*.py»), `skills/review-checklist.md:39` («Долгоживущие свойства — в `tests/`»), `skills/review-checklist.md:102` («Дифф tests/ — только импорты и пути патчей»).
- Файлы скилов — защищённые пути (перечень защищённых путей в `orchestrator/config.py`): правка — приложением к PLAN, гейт применимости приложений — `orchestrator/advance_gates/plan_appendix.py`.

## Требуется

1. **Задание test_author по правилу планки.** Признак — компонент профиля задачи входит в `project_profile.plank_rule(target).labelled_components()` (тот же источник, что у guard). Тогда:
   - пункт 2: «Для каждого AC-n напиши тест в {task_ref}/acceptance_tests/ (без подкаталогов), имя файла — по маскам `<последние сегменты масок tests>`; помощники — `_<имя>.<расширение>`. Имя теста `it`/`test` начинается с `AC-<n>: `, одна метка на тест, `describe` меткой не начинается — ТОЛЬКО из формулировки критерия. На прогоне файлы лежат в `<plank_layout с id задачи>`: импорты кода пиши относительно этого каталога.»;
   - строка запретов: «В тексте планки запрещены `.fails`, `.skipIf`, `.runIf`, `.only`, `vi.setConfig`, ключи `retry`/`timeout` и числовой литерал в аргументах `it`/`test`/`describe`/`suite`.»;
   - пункты 3–4: пометки `// AC-n: manual|skip|escalate — …` с начала строки в файле планки компонента;
   - пункт 2а и пункт 5 — прежние.

   Иначе (артель, `test_profile`, pytest-компоненты, правило не построено) — прежний текст побайтно.
2. **Сводка прогона Vitest.** Блок — три строки после удаления ANSI и крайних пробелов: `Test Files  <сч> (<n>)`; сразу за ней `Tests  <сч> (<n>)`, где `<сч>` — `<число> (failed|passed|skipped|todo)` через ` | ` либо `no tests`; в пределах следующих четырёх строк `Duration  <число>(ms|s)`. Действие журнала — `VITEST_RUN_ACTION = "прогон vitest"`, деталь — «<сч Tests> (<n>) in <секунды>s»; `ms` переводятся в секунды с двумя знаками. Насос получает новый параметр `on_vitest_summary`; `runner._spawn_and_wait` передаёт его, только если `decide(target).profile.report == project_profile.REPORT_VITEST`. Дозор: класс `pytest`, общий бюджет строк (сравнение действия — принадлежность паре `PYTEST_RUN_ACTION`, `VITEST_RUN_ACTION`). Отчёт: `_test_author_steps` считает секунды обоих действий. `PYTEST_RUN_ACTION`, разбор pytest и их читатели у прочих задач — прежние побайтно.
3. **Итоговая строка `plank-run`.** У компонента `pult-vitest` (признак — тот же, что у `runner`: `decide(target).profile.report == project_profile.REPORT_VITEST`) обе строки итога — `orchestrator/plank_run.py:289` (прогон оборван) и `:291` — пишут «итог vitest: <деталь>» по разбору п. 2 (нет блока — «итоговой строки нет») и «код выхода vitest»; у прочих — обе строки прежние побайтно.
4. **Скилы приложением к PLAN.** Новый раздел в конце `skills/test-authoring.md` «Компонент с меткой `AC-<n>: ` (Vitest)»: в начале сказано, что разделы о unittest выше относятся к Python-компоненту и артели; содержание — метка, запреты, каталог планки и импорты относительно выкладки, пометки `//`, долгоживущий файл по шаблону `long_lived`, прогон `plank-run`; существующие строки не меняются. В `skills/review-checklist.md` — дописка к правилам `:39` и `:102`: у компонента с отчётом `pult-vitest` «каталог долгоживущих тестов компонента» вместо `tests/`; сверка изменённых утверждений — по строкам гейта исходов пакета ревьювера. Проверка — гейт применимости приложений PLAN.
5. Тесты детерминированы, без сети и без Node: эталон задания test_author, снятый с кода пина, у артели, `test_profile` и `junit-xml` с pytest — побайтно; задание у компонента `pult-vitest` и у `junit-xml` с командой не pytest и масками `tests` — текст п. 1; разбор блока Vitest (успех, падения, `todo`/`skipped`, `no tests`, `ms` и `s`, блок без `Duration`, строка «Tests» в листинге кода, ANSI) — по фикстурам; у задачи артели насос создаётся без `on_vitest_summary`, и записей «прогон vitest» нет даже при блоке Vitest в выводе инструмента; дозор и отчёт с записью «прогон vitest»; итоговая строка `plank-run` у `pult-vitest` и прежняя у прочих. Существующие тесты (в том числе `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`) без правок и зелёные. Настоящая форма блока Vitest подтверждается пробой на sled (этап 2 плана).

Зоны: orchestrator/role_prompt.py, orchestrator/agent_log.py, orchestrator/runner.py, orchestrator/watch.py, orchestrator/report.py, orchestrator/plank_run.py, tests/

Только чтение: docs/adr/0026-project-components-and-outcome-gates.md, orchestrator/project_profile.py, scripts/guard.py, orchestrator/acceptance.py, orchestrator/targets.py, orchestrator/store.py, orchestrator/config.py, orchestrator/advance_gates/plan_appendix.py, skills/test-authoring.md, skills/review-checklist.md (правка — приложением к PLAN). Вызывающие функций зон из других модулей (orchestrator/doctor/preflight.py, orchestrator/providers/claude.py — запуск шага; orchestrator/artel.py — классы дозора; orchestrator/brief.py — бриф test_author, зона G5а; вызывающие `run_summary_line` — orchestrator/amend.py, orchestrator/suite_run.py, orchestrator/reporters/outcome.py; вызывающие `plank_rule` и `labelled_components` — orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/tests_writing.py, orchestrator/amend.py, orchestrator/checkpoint.py, orchestrator/dry_run.py, orchestrator/fsm.py, orchestrator/fsm_autogate.py, orchestrator/fsm_merge_gate.py, orchestrator/preflight.py) — только чтение: подписи не меняются.

Не входит: документы `knowledge` в брифе (G5а); сводки Vitest и задание у записи из нескольких компонентов (sled) — после G3б; карта кода внешнего проекта; гейты планки и неослабления (G3а-2б-1, G3а-2б-2, G3б).

Бюджет: $25–30.
