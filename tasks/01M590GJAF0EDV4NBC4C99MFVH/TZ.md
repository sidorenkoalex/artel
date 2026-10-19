---
task: 01M590GJAF0EDV4NBC4C99MFVH
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: G1б: итог тестов компонента из отчёта — JUnit, отчётчик пульта для Vitest, окружение и установка пультом

# G1б: итог тестов компонента из отчёта — JUnit, отчётчик пульта для Vitest, окружение и установка пультом

## Факты

Вторая задача волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`, принят 19.10.2026; «Решение» п. 4, 7 (в редакции — пп. 4, 8–10, 12), «Порядок исполнения» — строка G1б). Опирается на схему компонентов задач G1а (01M58FNWBV25FF26E7AZ9Q9912, функции `project_profile.components`, `select_components`, `test_id`/`parse_test_id`; запись с несколькими компонентами — `profile_of` UNREAD с признаком «несколько компонентов») и G1а-2 (01M58PG72PG64GS790XM2EWS61, `Profile.tools`, проверки doctor, ключ кэша): поля `report`, `report_args`, `failure_errors`, `select`, `env`, `install`, `tools`, `checks_local`, выбор компонентов по путям.

- Итог прогона сегодня — код возврата и текст pytest: `orchestrator/acceptance.py:374` (`run_summary_line`), `:1512` (`_full_suite_outcome`), `:1946` (`failed_entries`); прогоны — `acceptance.run` (`:713`), `collect` (`:868`), `run_plank` (`:1325`), `full_suite` (`:2222`); команда — `_own`/`_head`/`_place_command` (`:121-150`). `orchestrator/suite_run.py:262` (`_is_pytest` отказывает не-pytest команде), `:349` (`parse` по итоговой строке pytest), `:743` (`cmd_suite_run`). Полный прогон гейта мержа — `orchestrator/fsm_merge_gate.py:818-850` (`_full_suite_command`, один профиль), `:953-985`. Прогоны через `_place_command` также в `advance_gates/two_sided.py:282-289` и сухой сбор — `advance_gates/tests_writing.py:569-575`; предел полного набора — `full_suite_limit` (`notes.py:1048`, `doctor/cli.py:16`).
- JUnit уже читается ради времени и повтора красных: `acceptance.py:799-821`, `:992-1075` (`_junit_node`, `_junit_red_tests`, `run_repeat`).
- JUnit Vitest не различает провал проверки и ошибку (любое падение — `<failure type="<имя ошибки>">`; `skip` и `todo` одинаково `<skipped/>`; `it.fails` — зелёный; повторов не видно); Vitest ищет `vitest.config.ts`/`.mts` раньше `.js`. Поэтому для Vitest — свой отчётчик пульта (ADR п. 4).
- Сторож зависших тестов узнаёт только `pytest`/`unittest`: `doctor/hung_test_watchdog.py:20`.
- Инварианта «неизвестный местный итог тестов не зелёный» нет; инвариант 19 (`docs/invariants.md:49`) — про CI перед мержем.
- `install` профиля описан, но пультом не исполняется (`targets.py:61-63`).

## Требуется

1. Для компонента с `report: junit-xml` пульт добавляет `report_args` (подстановка `{path}` — файл отчёта вне рабочей копии), запускает команду компонента в его `workdir` с чистым окружением компонента, своей группой процессов и таймаутом и читает итог **только из отчёта**: по каждому тесту — идентификатор компонента (ADR п. 3), исход (passed / failed / error / skipped), вид падения, причина пропуска, время. Код возврата без разборчивого отчёта или отчёт без тестов при ненулевом коде — исход «неизвестно», не зелёный.
2. Для компонента с `report: pult-vitest` — отчётчик пульта: файл в репозитории пульта (новый каталог `orchestrator/reporters/`), подключаемый `--reporter=<путь>`; JSON по каждому тесту: идентификатор, состояние, имя ошибки, признак таймаута, падение хука (какого), `mode` (`run`/`skip`/`todo`/`only`), признак `fails`, число повторов. «Провал проверки» — имя ошибки из `failure_errors` компонента; иное падение — ошибка. Окружение Vitest задаёт пульт: `CI=true`; запуск `node_modules/.bin/vitest run --config vitest.config.js --allowOnly=false --update=false --retry=0` и `--expect.requireAssertions`, если флаг принимается версией Vitest (иначе — отказ подготовки с текстом); кэш Vite вне рабочей копии.
3. Итог по отчёту — во всех местах прогона по профилю проекта: прогон планки, сухой сбор, `plank-run`, `amend-tests`, `suite-run` (без `_is_pytest`-отказа для компонентов с отчётом; без флагов xdist у не-pytest), двусторонний прогон (вызов), полный прогон на гейте мержа — **по каждому затронутому компоненту** (выбор G1а), итог гейта — зелёный, только если зелёны все. Предел полного набора — по компоненту.
4. Установка зависимостей — пульт: команда `install` компонента исполняется пультом один раз на версию файла блокировки (для npm — `npm ci --ignore-scripts`), каталог зависимостей (`node_modules`) и кэш принадлежат пульту и подключаются к рабочей копии задачи только для чтения (символьная ссылка на каталог пульта с правами только чтения или эквивалент); прогоны гейтов используют тот же каталог. Сбой установки — отказ прогона с текстом, не зелёный.
5. `checks_local` компонента исполняются пультом на гейтах приёмки и мержа вместе с полным прогоном; ненулевой код — красный с выводом проверки.
5а. Пробел, оставленный G1а-2 (01M58PG72PG64GS790XM2EWS61): `suite_run._profile_command` (`orchestrator/suite_run.py:294`) строит профиль без `tools`, а ключ базы итога полного набора от `tools` не зависит. Профиль `suite-run` получает `tools` тем же помощником `project_profile`, что `decide` и `_task_own_profile`; ключ базы включает `tools` компонента — одинаково у гейта мержа и у `suite-run` (AC через оба входа).
6. Сторож зависших тестов узнаёт команды компонентов проекта (по `command` записи), а не только `pytest`/`unittest`.
7. **У артели (`pult-pytest`) и у записей с `test_profile` без `report` разбор итога, тексты и исходы прежние** — аналитик перечисляет в SPEC тексты, которые закрепляются тестами до правки. Компонент с `report: junit-xml` у pytest-own (sled backend сегодня с `report: junit-xml`) — переходит на итог из отчёта; тексты сводок для него — сверить и перечислить в SPEC.
8. Новый инвариант 41 «неизвестный или неразобранный местный итог тестов не зелёный; повторы внутри прогона компонентов с отчётом пульта запрещены» — строка `docs/invariants.md` и проверка `tests/test_invariants.py` приложением к PLAN (защищённые пути; применяет пульт по приложению, коммит — по правилам приложений).
9. Тесты детерминированы, без сети и без настоящего Node: учебный проект с компонентами `junit-xml` (pytest) и `pult-vitest` (подменённый раннер, пишущий заранее заданный JSON отчётчика); сценарии: зелёный, провал проверки, ошибка, таймаут, падение хука, `skip`/`todo`/`only`/`fails`, отчёта нет, отчёт не разобран, сбой установки.

Критерии приёмки:
- компонент `junit-xml`: зелёный, красный по провалу, «неизвестно» без отчёта — по отчёту, независимо от текста вывода;
- компонент `pult-vitest`: `TypeError` — ошибка, `AssertionError` — провал проверки, `it.fails` и `todo` различимы, повтор виден; окружение прогона содержит `CI=true` и флаги п. 2;
- полный прогон гейта мержа проекта с двумя компонентами гоняет оба затронутых и красен, если красен любой;
- установка исполняется один раз на версию файла блокировки; рабочая копия роли не может изменить каталог зависимостей;
- у артели исходы и перечисленные тексты прежние;
- инвариант 41 в приложении PLAN и проверка в `tests/test_invariants.py`.

Зоны: `orchestrator/acceptance.py`, `orchestrator/suite_run.py`, `orchestrator/plank_run.py`, `orchestrator/amend.py`, `orchestrator/fsm_advance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/pull.py`, `orchestrator/preflight.py`, `orchestrator/notes.py`, `orchestrator/project_profile.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/two_sided.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/doctor/cli.py`, `orchestrator/doctor/hung_test_watchdog.py`, `orchestrator/reporters/` (новый), `tests/`.

Приложением: `docs/invariants.md`, `tests/test_invariants.py`.

Только чтение: `targets.yaml`, `orchestrator/targets.py`, `orchestrator/repo_context.py`, `docs/adr/0026-project-components-and-outcome-gates.md`, `scripts/guard.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/advance_gates/mandate.py`, `docs/backlog.md`. Правка вне зон — эскалация до SPEC.

Не входит: планка и долгоживущие файлы по компоненту, честный `FAIL_TO_PASS` (G2а, G2б); гейт неослабления по исходам (G3а, G3б); бриф и сводки роли (G5); перевод записи sled (этап 2 плана); контейнерная среда.

Рамка: $60. Набор моделей — по умолчанию.
