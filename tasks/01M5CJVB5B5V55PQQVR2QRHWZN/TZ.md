---
task: 01M5CJVB5B5V55PQQVR2QRHWZN
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: G3а-1а: гейт неослабления по исходам на выходе из `in_dev` — `PASS_TO_PASS`, нестабильность, сравнение отчётов

# G3а-1а: гейт неослабления по исходам на выходе из `in_dev` — `PASS_TO_PASS`, нестабильность, сравнение отчётов

## Факты

Первая часть G3а волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`, «Решение» п. 6 — гейт неослабления по исходам; переход в ADR назван `in_dev → review`, после ADR-0015 гейт неослабления стоит на `in_dev -> verifying`). Решения Оператора 20.10: G3а делится на G3а-1а (эта задача), G3а-1б (мандат по идентификатору теста: новый маркер, запись ответа, матрица неослабления, независимая проверка) и G3а-2 (гейт мержа по исходам, двусторонний прогон по имени ошибки, пакет ревьювера, ошибки уровня файла, запрет плагинов повторов pytest, записи по тестам в кэше итога).

**Граница задачи одной фразой:** новый гейт исполняется только у профиля, для которого `in_outcome_bounds` истинно (компонент записи `components:` с полем `report`); у артели, у записи `test_profile` и у записи из нескольких компонентов (до G3б её отклоняет `decide`) — прежнее поведение побайтно.

- Переход `in_dev -> verifying` — `orchestrator/fsm_advance.py:732` (`in_dev`); гейт неослабления по тексту (слой python-ast) — `orchestrator/fsm_advance.py:804` (`_test_integrity_gate_refuses`), следом — `orchestrator/fsm_advance.py:806` (`_review_rework_gate_refuses`).
- Тело гейта по тексту — `orchestrator/advance_gates/test_integrity.py:1722` (`_test_integrity_gate`); методы тестов берутся только из Python-текста — тесты Vitest сегодня не проверяет ни один гейт неослабления.
- Профиль проекта — `orchestrator/project_profile.py:184` (`decide`); граница по исходам — `orchestrator/advance_gates/acceptance.py:213` (`in_outcome_bounds`).
- Полный набор с записями по каждому тесту — `orchestrator/acceptance.py:3425` (`components_full_suite`), результат — `orchestrator/acceptance.py:2401` (`FullSuiteRun`, поле `tests` — записи `CaseResult`); итог из кэша записей не несёт, нужен `fresh=True`. Исходы: «нет тестов» — `orchestrator/acceptance.py:2309` (`FULL_SUITE_NO_TESTS`), «неизвестно» и «не начат» — одна константа `orchestrator/acceptance.py:2315` (`FULL_SUITE_NOT_STARTED`).
- Прогон отдельных файлов по отчёту — `orchestrator/acceptance.py:793` (`_report_run`), образец — `orchestrator/advance_gates/two_sided.py:336` (`_run_side_report`); у `junit-xml` пути идут после команды, у `pult-vitest` — через `select` (`orchestrator/acceptance.py:688`, `_subset_args`; без `select` — отказ).
- База сравнения — `orchestrator/gitcmd.py:533` (`diff_base`, merge-base с origin/main); выписки базы и головы — образец `orchestrator/advance_gates/two_sided.py:411` (`run`).
- Записи отчёта — `orchestrator/reporters/outcome.py` (`CaseResult`: исход, `retries`, у `pult-vitest` — `mode`, `fails`; `todo` у Vitest приходит как пропуск); идентификатор — `orchestrator/project_profile.py:440` (`test_id`).
- Мандат на ослабление по файлу: маркер «Ослабление тестов разрешено:», сбор по всем `ANSWER-n.md` с отбраковкой автокоммита шага роли — `orchestrator/advance_gates/test_integrity.py:1074` (`_answer_mandate`), покрытие — `orchestrator/advance_gates/test_integrity.py:1040` (`_covering_source`).
- Классы отказов — `orchestrator/advance_gates/refusal_classes.py`; гейт по тексту — «чинит Оператор» (`orchestrator/advance_gates/test_integrity.py:77`).
- У sled сегодня запись `test_profile` с `report: junit-xml` — `in_outcome_bounds` ложно, гейт заработает на живых задачах после перевода записи на `components:` (этап 2 плана sled).

## Требуется

1. **Новый гейт исходов** на переходе `in_dev -> verifying` — сразу после гейта по тексту и до гейта переделки ревью; новый модуль `orchestrator/advance_gates/outcome_integrity.py`. Профиль — `decide(target).profile`; отказ или пропуск решения, ложное `in_outcome_bounds` — гейт не создаётся, без прогона и записи журнала. Компонент — единственный компонент профиля (выбор по диффу — G3б).
2. **Прогоны.** Полный набор компонента на базе (`diff_base`) и на голове кодовой ветки в отдельных выписках, `components_full_suite(..., fresh=True)`. Исход стороны «неизвестно/не начат» или таймаут — отказ подготовки с причиной и стороной, без сравнения. «Нет тестов» на базе — набор `PASS_TO_PASS` пуст; на ветке — все тесты базы исчезли (п. 4).
3. **`PASS_TO_PASS`.** В набор входят тесты, прошедшие на базе без повторов. Красный на ветке — `failed`, `error` или `passed` с `retries > 0`; `skipped` — не красный, это п. 4. Красный тест перепрогоняется ещё дважды на ветке и дважды на базе — только его файлы, через `_report_run`, предел — `full_suite_timeout_sec` компонента; компонент `pult-vitest` без `select` — отказ подготовки. Перепрогон с исходом не «зелёный» и не «красный» — отказ подготовки; тест, пропавший из отчёта перепрогона, — красный этого прогона. Итог по тесту:
   - красный на ветке все три раза при трижды зелёной базе — находка «сломан правкой»;
   - красный хотя бы раз и зелёный хотя бы раз на ветке при трижды зелёной базе — находка «нестабилен после правки»;
   - база хотя бы раз красная — не находка, строка журнала «нестабилен и на базе: <идентификатор>».
4. **Сравнение отчётов** — отдельной функцией над двумя списками `CaseResult`: у теста базы — идентификатор исчез на ветке; «прошёл → пропущен»; на ветке `todo` или `fails` у прежнего идентификатора. Новый идентификатор (нет на базе) с исходом пропуск, `todo` или `fails` — находка на этот идентификатор. Рост числа пропусков компонента — итоговая строка отказа, не отдельная находка. Один идентификатор — одна находка, по старшинству п. 6.
5. **Мандат.** Находка покрыта, если путь её файла — элемент прежнего маркера «Ослабление тестов разрешено:», собранного тем же правилом, что `_answer_mandate` (с отбраковкой ANSWER, закоммиченного автокоммитом шага роли). Для Python-компонента элемент `путь::имя` прежнего маркера покрывает находку исходов с тем же путём и полным именем. Мандат по идентификатору теста — G3а-1б.
6. **Отказ и журнал.** Непокрытые находки — одним отказом в порядке: исчезнувшие → «сломан правкой» → «нестабилен после правки» → прочие находки сравнения; внутри вида — по идентификатору; каждая строкой с идентификатором и исходами по прогонам. Действия журнала (решение Оператора 20.10): если среди непокрытых находок есть хоть одна, кроме «сломан правкой», — «переход отклонён: гейт неослабления по исходам», класс «чинит Оператор», в отказе все находки; если непокрытые находки — только «сломан правкой», — «переход отклонён: гейт неослабления по исходам — сломан правкой», класс «чинит роль» (developer чинит код или эскалирует за мандатом); отказ подготовки — «переход отклонён: гейт неослабления по исходам — подготовка», класс «чинит Оператор». Все три — в `REFUSAL_CLASSES` (`tests/test_refusal_classes.py` дополняется); критерий — `auto` возвращает шаг developer на «сломан правкой» и останавливается на остальных. Пройденный гейт — запись журнала с числом тестов базы и ветки, перепрогонов и покрытых мандатом находок.
7. Тесты детерминированы, без сети и без Node: функция сравнения п. 4 — на записях `pult-vitest` (`mode=todo`, `fails=True`, пропуск) и `junit-xml`; сквозной сценарий — учебный проект с компонентом `junit-xml` на подменённом раннере, отдающем заранее заданные отчёты по номеру прогона: каждая находка п. 3, порядок п. 6, перепрогон только нужных файлов, «нестабилен и на базе», тест с повтором на базе вне набора, отказ подготовки по каждому исходу стороны и перепрогона, мандат на файл и на `путь::имя`, ANSWER от автокоммита роли не снимает находку. У артели и у записи `test_profile` — гейт не создан, прогона нет; `tests/test_fsm_advance_gate_smoke.py` без правок и зелёный.

Зоны: orchestrator/advance_gates/outcome_integrity.py, orchestrator/fsm_advance.py, orchestrator/advance_gates/refusal_classes.py, tests/

Только чтение: docs/adr/0026-project-components-and-outcome-gates.md, orchestrator/acceptance.py, orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/test_integrity.py, orchestrator/advance_gates/zones.py, orchestrator/advance_gates/two_sided.py, orchestrator/advance_gates/mandate.py, orchestrator/project_profile.py, orchestrator/gitcmd.py, orchestrator/reporters/outcome.py. Вызывающие `in_dev`, `in_outcome_bounds`, `diff_base` (orchestrator/fsm.py, orchestrator/schema.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/__init__.py, orchestrator/advance_gates/capacity.py, orchestrator/advance_gates/plan_appendix.py, orchestrator/advance_gates/review.py, orchestrator/checkpoint.py, orchestrator/plank_helper.py, orchestrator/fsm_merge_gate.py, orchestrator/amend.py, orchestrator/review.py, orchestrator/runner.py, orchestrator/suite_run.py, orchestrator/answer.py — в том числе вызывающие `decide`, `components_full_suite`, `_answer_mandate`) — только чтение: подписи не меняются.

Не входит: мандат по идентификатору теста — новый маркер, запись ответа, матрица неослабления, независимая проверка, `spec_audit` (G3а-1б); выбор компонентов по диффу (G3б); гейт мержа по исходам, двусторонний прогон по имени ошибки, пакет ревьювера, ошибки уровня файла, запрет плагинов повторов pytest, записи по тестам в кэше итога (G3а-2) — до неё повторный прогон базы на каждом входе в переход — принятая цена; прежние версии тестов на коде ветки, строгий режим, исключения в коде, заменяемые тесты (G3б); документы `docs/operator-gates.md` о мандате (G5).

Бюджет: $45–55.
