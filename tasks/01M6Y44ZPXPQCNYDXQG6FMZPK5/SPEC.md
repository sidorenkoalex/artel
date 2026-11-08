---
task: 01M6Y44ZPXPQCNYDXQG6FMZPK5
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/forge.py, orchestrator/suite_cost.py, orchestrator/artel.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/config.py, orchestrator/doctor/cli.py, orchestrator/doctor/__init__.py, orchestrator/doctor/suite_cost.py, docs/codebase-map.md, tests/
budget_usd: 85
---

# SPEC: Слежение за ценой набора тестов по отчёту junit CI main: сводка, самые медленные, прирост от задачи (ADR-0032, этап 1)

## Контекст
ADR-0032 п. 6 (принят 08.11.2026, `e4de84a0`) требует: по отчёту junit
каждого прогона CI `main` пульт пишет число тестов, сумму, время по часам,
20 самых медленных, долю каждого размера и прирост от последней смерженной
задачи; `doctor` предупреждает при 75 % предела (локального и CI), тревога —
при 85 %. С `a8ff5c70` задание CI `ci.FULL_SUITE_JOB` («Синтаксис и тесты
оркестратора», `orchestrator/ci.py:39`) выгружает отчёт junit артефактом
`junit` при любом исходе прогона. Сейчас `forge` (`orchestrator/forge.py`)
читает из отчёта только исходы (`TestReport`, `:73`; `_parse_junit`, `:702`;
`job_test_report`, `:800`), имя артефакта берёт из компонента записи
(`_gh_report_artifact`, `:561`), которого у артели нет; времени тестов,
сводки, её записи и проверки `doctor` по ней нет.

Факты из ТЗ, на которые опираются требования: у `testcase` есть
`classname` (через точки), `name`, `time`, атрибута `file` нет;
`testsuite@tests` у pytest 9.1 считает подтесты и больше числа элементов
`testcase`; пуш только документов в `main` задание тестов не исполняет
(ADR-0016); прогон, оборванный пределом 40 мин (`timeout-minutes: 40`,
`.github/workflows/ci.yml`), отчёта junit не оставляет; коммит мержа задачи
в `main` имеет тему `<id>: merge task/…`.

## Требования

1. **Время тестов — отдельно от исходов.** `TestReport`, `_parse_junit` и
   `job_test_report` (`orchestrator/forge.py`) не меняются. Новая публичная
   функция `forge.parse_junit_times(data)` разбирает тот же архив junit с
   теми же пределами и отдаёт время каждого узла `<classname>::<name>` и
   `testsuite@time`. Пустой или нечисловой `time` — исход «отчёта нет»
   с причиной, а не ноль.
2. **Отчёт CI по sha.** Новая публичная функция
   `forge.ci_suite_report(target, sha)`: находит попытку задания
   `ci.FULL_SUITE_JOB` по sha и артефакт с именем из новой константы
   `config` (значение `junit`), с теми же пределами и отказами, что у
   `job_test_report`; отдаёт время каждого теста, `suite_seconds`
   (`testsuite@time`), `job_seconds` (`completed_at − started_at` попытки)
   и причину, если отчёта нет. Попытка без артефакта (обрыв по пределу)
   отдаёт `job_seconds` и причину «отчёта нет».
3. **Сводка** — публичные функции нового модуля `orchestrator/suite_cost.py`:
   - `size_bucket(seconds)`: `t < 1` — «до 1 с», `1 ≤ t < 10` — «1–10 с»,
     `10 ≤ t < 60` — «10–60 с», `t ≥ 60` — «60 с и дольше»;
   - `summarize(...)`: число тестов — число элементов `testcase` (не
     `testsuite@tests`), сумма времени, `suite_seconds`, `job_seconds`,
     20 самых медленных по убыванию времени (при равенстве времени — по
     имени узла), распределение по четырём ориентирам `size_bucket` (число
     тестов и доля суммы), прирост числа и суммы против предыдущей сводки,
     задачи между двумя sha;
   - `merged_tasks(prev_sha, sha)`: задачи из тем коммитов
     `<id>: merge task/…` первой родительской линии `main` между sha
     (`git log --first-parent prev..sha`), где `<id>` — задача проекта
     в БД пульта;
   - `limit_level(seconds, limit)`: `ok`; `warn` при доле
     `≥ config.SUITE_COST_WARN_RATIO` (= 0,75); `alert` при доле
     `≥ config.SUITE_COST_ALERT_RATIO` (= 0,85).
   Предыдущая сводка — последняя записанная сводка, sha которой — предок
   текущего sha.
4. **Запись.** Одна запись на sha в новой таблице БД пульта, определённой
   одним определением в `SCHEMA` и в `migrate()`; повторная запись того же
   sha второй записи не даёт. Запись хранит и попытку без отчёта
   (`job_seconds`, причина).
5. **Команда** `artel.py suite-cost`: без флагов — печать последней сводки,
   только чтение; `--record <sha>` — запись сводки для sha;
   `--record-latest` — запись сводки для последнего коммита `main`
   с исполненным заданием (`forge.green_base_commit`), независимо от цвета
   прогона. Строка справки — в докстринге команды; в перечень команд,
   разрешённых роли, команда не входит.
6. **Проверка doctor** «suite-cost:<target>» — отдельным модулем
   `orchestrator/doctor/suite_cost.py`, две строки: CI — `job_seconds`
   последней сводки против 40 мин; локальный прогон — последняя запись
   «прогон: время» (`acceptance.SUITE_DURATION_ACTION`) проекта, отбор как
   в `suite_duration._series`, против `project_profile.full_suite_limit`.
   Уровень строки — `limit_level`; строка называет числа, sha и возраст
   сводки; нет сводки или записи — пропуск этой строки с причиной.

## Критерии приёмки

AC-1. Given архив junit с тремя тестами разного времени и подтестом, When
`forge.parse_junit_times`, Then у каждого узла `<classname>::<name>` — его
время, отдано `testsuite@time`; архив с пустым `time` — исход «отчёта нет»
с причиной, не ноль; When `forge.job_test_report` на том же архиве, Then
`TestReport` равен прежнему целиком. (Поверхность решения:
`orchestrator.forge.parse_junit_times(data) -> tuple`; размер проверки:
малый.)

AC-2. Given подменённые ответы `gh` для sha, When `forge.ci_suite_report`,
Then отданы время тестов, `suite_seconds`, `job_seconds`; отдельно:
артефакта нет (обрыв) — `job_seconds` и причина «отчёта нет»; артефакт вне
окна попытки, архив больше предела, истёкший срок артефакта — причина.
(Поверхность решения: `orchestrator.forge.ci_suite_report(target, sha) ->
SuiteReport`; размер проверки: малый.)

AC-3. Given 25 тестов с известным временем (включая два с равным временем
на 20-й позиции) и отчёт с `testsuite@tests` больше числа `testcase`, When
`summarize`, Then число тестов — по `testcase`; ровно 20 самых медленных по
убыванию времени, при равенстве — по имени узла; распределение по четырём
ориентирам с долями суммы; прирост числа и суммы против предыдущей сводки.
(Поверхность решения: `orchestrator.suite_cost.summarize(...) -> dict`;
размер проверки: малый.)

AC-4. Given `size_bucket` и `limit_level` на границах (0,999; 1; 9,999; 10;
59,999; 60 с; 74,99 %; 75 %; 84,99 %; 85 %), Then ориентир и уровень — по
правилам требования 3. (Поверхность решения:
`orchestrator.suite_cost.size_bucket(seconds) -> str`;
`orchestrator.suite_cost.limit_level(seconds, limit) -> str`; размер
проверки: малый.)

AC-5. Given репозиторий во временной песочнице с мержами двух задач между
двумя sha и одной — раньше, When `merged_tasks`, Then ровно две задачи.
(Поверхность решения: `orchestrator.suite_cost.merged_tasks(prev_sha, sha)
-> list`; размер проверки: средний — настоящий git во временной песочнице.)

AC-6. Given записанная сводка для sha, When повторная запись того же sha,
Then второй записи нет; `suite-cost` без флага ничего не пишет и печатает
последнюю сводку; `--record-latest` записывает сводку для коммита, который
даёт подменённый `green_base_commit`. (Размер проверки: средний — БД пульта
во временной песочнице.)

AC-7. Given сводка с `job_seconds` 31 мин и запись «прогон: время» 1300 с
при пределе 1500 с, When проверка doctor «suite-cost:<target>», Then строка
CI — предупреждение (77,5 %), строка локального прогона — тревога (86,7 %),
обе строки с числами, sha и возрастом сводки; при 70 % — норма; без сводки —
строка CI пропущена с причиной, строка локального прогона остаётся.
(Размер проверки: средний — БД пульта во временной песочнице.)

AC-8. Мутации «число тестов взято из `testsuite@tests`», «порог `>` вместо
`≥`», «задача вне интервала попала в прирост», «`TestReport` изменился»,
«повтор записывает вторую запись», «время попытки сравнивается с пределом
локального прогона» — красные на тестах AC-1…AC-7.

Условия тестов (из ТЗ): тесты импортируют `orchestrator.suite_cost` внутри
тела теста, а не на уровне модуля — модуля до кода нет, сухой сбор не
должен падать. Ответы GitHub — подмена вызова `gh` в процессе теста, без
сети; архивы junit — во временном каталоге; БД пульта и репозиторий — во
временной песочнице (`tests.sandbox`); служебный каталог пульта, настоящая
запись проектов и каталоги задач не читаются и не пишутся.

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны вне общих зон — 8 (`forge.py`,
`suite_cost.py`, `artel.py`, `store.py`, `schema.py`, `doctor/cli.py`,
`doctor/__init__.py`, `doctor/suite_cost.py`; порог
`SPLIT_SIGNAL_ZONE_FILES` = 5); `budget_usd` = 85 ≥
`SPLIT_SIGNAL_BUDGET_USD` = 60. Критериев приёмки 8 — ниже порога 10.

Материал Оператору для решения «монолит» (сам текст «монолит принят» —
решение Оператора):
- Технически единственный шов по зонам — `orchestrator/forge.py` (+
  константа имени артефакта в `config`): требования 1–2, AC-1–AC-2.
  Отдельно он мержим с зелёной планкой (новые публичные функции, исходы не
  меняются), но без потребителя: форма `SuiteReport` — входной контракт
  `summarize`, записи и `doctor` (требования 3–6), и, зафиксированная без
  них, она утверждается вслепую — расхождение вскроется только во второй
  части и потребует правки уже смерженного `forge`.
- Требования 3–6 (`suite_cost.py`, схема/store, команда, doctor) делят одну
  запись сводки: команда пишет её, doctor читает, `summarize` ищет
  предыдущую по ней же — резать их поперёк нельзя, это одна часть.
- Деление на две части (forge → остальное) дало бы две подзадачи
  ~$25 + ~$45–85 с двумя циклами аналитика и гейта SPEC против рамки $85
  ТЗ на всю задачу.
- Мутация «`TestReport` изменился» (AC-8) сторожит обе части сразу:
  в монолите она проверяется на том же диффе, что и новый разбор времени.

## Не входит

- Перевод артели на компонент записи с `full_suite: ci` (этап 4б ADR-0031).
- Изменение `TestReport`, триггера `suite.near_limit`
  (`orchestrator/acceptance.py:3259`), проверки `doctor` «suite-duration»
  (`orchestrator/doctor/suite_duration.py`) и пределов.
- Реестр размеров по каждому тесту (время каждого теста отдельной
  таблицей) — следующий шаг этапа 1 по данным первых сводок.
- Автоматическая запись сводки после мержа — только командой
  `--record-latest` (Оператор или обход `doctor` позже).
- Выбор тестов на шаге роли (этап 7 ADR-0032).
- Шум «время подготовки класса при xdist попадает первому тесту класса» в
  списке самых медленных — так и оставить (заметка ТЗ).
- Правка файлов только для чтения из ТЗ: `docs/adr/0032-test-cost-and-growth.md`,
  `docs/adr/0031-test-runs-strategy.md`, `orchestrator/acceptance.py`,
  `orchestrator/ci.py`, `orchestrator/targets.py`,
  `orchestrator/project_profile.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/gitlab_adapter.py`, `orchestrator/doctor/suite_duration.py`,
  `.github/workflows/ci.yml`, `tests/sandbox.py`.
- Зелёный полный набор существующих `tests/` — его держит пульт. Если
  краснеет существующий тест, сверяющий состав `TestReport`, перечень
  проверок `doctor` или схему БД (`tests/test_store_schema_migration_parity.py`,
  `tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py`), —
  эскалация с именем теста, без его правки (условие ТЗ).

## Материалы

- ADR-0032 п. 6 (`docs/adr/0032-test-cost-and-growth.md`), ADR-0016
  (классы пуша CI), ADR-0026 (гейты исходов).
- Первый артефакт `junit`: прогон Actions `42503643843`, задание
  `128801551938` — 10 008 `testcase`, сумма 5510 с, `testsuite@time`
  1453 с, попытка 1469 с, `testsuite@tests` = 18197.
- Готовые опоры: `forge.green_base_commit` (`orchestrator/forge.py:805`),
  `project_profile.full_suite_limit` (`orchestrator/project_profile.py:431`),
  `acceptance.SUITE_DURATION_ACTION` (`orchestrator/acceptance.py:1653`),
  `suite_duration._series` (`orchestrator/doctor/suite_duration.py:20`),
  регистрация проверок `doctor` (`orchestrator/doctor/cli.py:281`,
  `orchestrator/doctor/__init__.py:213`).
- Матрица неослабления ТЗ: исходы `job_test_report` и равенство
  `TestReport` — без изменений (AC-1, AC-8); `suite.near_limit`,
  `suite-duration`, пределы — без изменений («Не входит»); паритет схемы БД —
  существующий тест паритета.
