---
task: 01M6Y44ZPXPQCNYDXQG6FMZPK5
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Слежение за ценой набора тестов по отчёту junit CI main: сводка, самые медленные, прирост от задачи (ADR-0032, этап 1)

# Слежение за ценой набора тестов по отчёту junit CI main: сводка, самые медленные, прирост от задачи (ADR-0032, этап 1)

## Факты

1. ADR-0032 п. 6 (принят 08.11.2026, `e4de84a0`): по отчёту junit каждого прогона CI `main` пульт пишет число тестов, сумму, время по часам, 20 самых медленных, долю каждого размера, прирост от последней смерженной задачи; `doctor` предупреждает при 75 % предела (локального и CI), алерт — при 85 %.
2. С `a8ff5c70` (08.11) задание CI «Синтаксис и тесты оркестратора» (`ci.FULL_SUITE_JOB`) выгружает отчёт junit артефактом `junit` при любом исходе прогона. Первый артефакт — прогон Actions `42503643843` (задание `128801551938`): 10 008 элементов `testcase`, сумма 5510 с, `testsuite@time` 1453 с, попытка задания (`started_at`–`completed_at`) 1469 с. Атрибут `testsuite@tests` = 18197 — pytest 9.1 считает в нём подтесты; повторов узлов нет ни при xdist, ни с подтестами. У `testcase` есть `classname` (через точки, `tests.test_x.Class`), `name`, `time`; атрибута `file` нет.
3. Чтение артефакта у GitHub: `forge` (`orchestrator/forge.py:395-457`) находит попытку задания по sha, артефакт по имени в окне попытки, скачивает архив с пределами и разбирает его (`_junit_report` `:637`, `_parse_junit` `:702`). Имя артефакта он берёт из компонента записи (`_gh_report_artifact` `:561`), а у артели компонента нет; `TestReport` (`:73`) несёт только исходы, и залоченный тест `tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py:1351` сравнивает его целиком.
4. Готовое: последний коммит ветки с исполненным заданием — `forge.green_base_commit`; предел локального полного набора — `project_profile.full_suite_limit(target)`; проверка `doctor` «suite-duration» (`orchestrator/doctor/suite_duration.py`) читает записи «прогон: время» (`acceptance.SUITE_DURATION_ACTION`, `orchestrator/acceptance.py:1653`; `duration_seconds` внутри JSON) с отбором по проекту (`_series`). Сигнал локального прогона `suite.near_limit` (`orchestrator/acceptance.py:3246`, `_signal_near_limit` `:3259`, порог 80 %) уже есть.
5. Пуш только документов в `main` задание тестов не исполняет (ADR-0016) — артефакта у такого коммита нет; прогон, оборванный пределом 40 мин (`timeout-minutes: 40`, `.github/workflows/ci.yml`), отчёта junit не оставляет.
6. Переход задачи в `done` пишет в журнал «смержено: <ветка>» (`orchestrator/fsm_merge_gate.py:1384`) без полного sha мержа; коммит мержа в `main` имеет тему `<id>: merge task/…`.
7. Новая таблица БД пульта — одним определением в `SCHEMA` и в `migrate()` (паритет «свежая БД = догнанная миграцией», `tests/test_store_schema_migration_parity.py`).

## Требуется

1. **Время тестов — отдельно от исходов.** `TestReport`, `_parse_junit` и `job_test_report` не меняются. Публичная функция `forge.parse_junit_times(data)` — разбор того же архива junit с теми же пределами: время каждого узла `<classname>::<name>` и `testsuite@time`; пустой или нечисловой `time` — «отчёта нет (причина)», а не ноль.
2. **Отчёт CI по sha** — публичная функция `forge.ci_suite_report(target, sha)`: попытка задания `ci.FULL_SUITE_JOB` по sha, артефакт с именем из константы `config` (`junit`), с теми же пределами и отказами, что у `job_test_report`; отдаёт время каждого теста, `suite_seconds` (`testsuite@time`), `job_seconds` (`completed_at − started_at` попытки) и причину, если отчёта нет. Попытка без артефакта (обрыв по пределу) отдаёт `job_seconds` и причину «отчёта нет».
3. **Сводка** — публичные функции `orchestrator/suite_cost.py`:
   - `size_bucket(seconds)`: `t < 1` — «до 1 с», `1 ≤ t < 10` — «1–10 с», `10 ≤ t < 60` — «10–60 с», `t ≥ 60` — «60 с и дольше»;
   - `summarize(...)`: число тестов — число элементов `testcase` (не `testsuite@tests`), сумма, `suite_seconds`, `job_seconds`, 20 самых медленных по убыванию времени (при равенстве — по имени узла), распределение по ориентирам (число и доля суммы), прирост числа и суммы против предыдущей сводки, задачи между двумя sha;
   - `merged_tasks(prev_sha, sha)`: задачи из тем коммитов `<id>: merge task/…` первой родительской линии `main` между sha (`git log --first-parent prev..sha`), где `<id>` — задача проекта в БД;
   - `limit_level(seconds, limit)`: `ok` / `warn` (≥ `config.SUITE_COST_WARN_RATIO` = 0,75) / `alert` (≥ `config.SUITE_COST_ALERT_RATIO` = 0,85).
   Предыдущая сводка — последняя записанная, sha которой — предок текущего.
4. **Запись** — одна запись на sha в новой таблице БД пульта (`SCHEMA` и `migrate()`); повтор того же sha второй записи не даёт. Запись хранит и попытку без отчёта (`job_seconds`, причина).
5. **Команда** `artel.py suite-cost` — печать последней сводки (только чтение); `--record <sha>` — запись сводки для sha; `--record-latest` — запись для последнего коммита `main` с исполненным заданием (`forge.green_base_commit`), независимо от цвета прогона. Строка справки — в докстринге команды; в перечень команд, разрешённых роли, команда не входит.
6. **Проверка doctor** «suite-cost:<target>» отдельным модулем `orchestrator/doctor/suite_cost.py`, две строки: CI — `job_seconds` последней сводки против 40 мин; локальный прогон — последняя запись «прогон: время» проекта (отбор как в `suite_duration._series`) против `project_profile.full_suite_limit`. Уровень — `limit_level`; строка называет sha и возраст сводки; нет сводки или записи — пропуск этой строки с причиной.

## Критерии приёмки

- Given архив junit с тремя тестами разного времени и подтестом, When `forge.parse_junit_times`, Then у каждого узла время, `testsuite@time`; пустой `time` — «отчёта нет»; When `forge.job_test_report` на том же архиве, Then `TestReport` равен прежнему целиком (Поверхность решения: orchestrator.forge.parse_junit_times(data) -> tuple; Размер проверки: малый);
- Given подменённые ответы `gh` для sha, When `forge.ci_suite_report`, Then время тестов, `suite_seconds`, `job_seconds`; отдельно: артефакта нет (обрыв) — `job_seconds` и причина; артефакт вне окна попытки, архив больше предела, истёкший срок — причина (Поверхность решения: orchestrator.forge.ci_suite_report(target, sha) -> SuiteReport; Размер проверки: малый);
- Given 25 тестов с известным временем (включая два с равным временем на 20-й позиции) и отчёт с `testsuite@tests` больше числа `testcase`, When `summarize`, Then число — по `testcase`, ровно 20 самых медленных по убыванию, при равенстве — по имени, распределение по четырём ориентирам с долями, прирост против предыдущей (Поверхность решения: orchestrator.suite_cost.summarize(...) -> dict; Размер проверки: малый);
- Given `size_bucket` и `limit_level` на границах (0,999; 1; 9,999; 10; 59,999; 60 с; 74,99 %; 75 %; 84,99 %; 85 %), Then ориентир и уровень по правилам требования 3 (Поверхность решения: orchestrator.suite_cost.size_bucket(seconds) -> str; orchestrator.suite_cost.limit_level(seconds, limit) -> str; Размер проверки: малый);
- Given репозиторий во временной песочнице с мержами двух задач между двумя sha и одной — раньше, When `merged_tasks`, Then ровно две задачи (Поверхность решения: orchestrator.suite_cost.merged_tasks(prev_sha, sha) -> list; Размер проверки: средний — настоящий git во временной песочнице);
- Given записанная сводка для sha, When повторная запись того же sha, Then второй записи нет; `suite-cost` без флага ничего не пишет и печатает последнюю сводку; `--record-latest` записывает сводку для коммита, который даёт подменённый `green_base_commit` (Размер проверки: средний — БД пульта во временной песочнице);
- Given сводка с `job_seconds` 31 мин и запись «прогон: время» 1300 с при пределе 1500 с, When проверка doctor, Then CI — предупреждение (77,5 %), локальный — тревога (86,7 %), обе строки с числами, sha и возрастом сводки; при 70 % — норма; без сводки — пропуск строки CI, локальная строка остаётся (Размер проверки: средний — БД пульта во временной песочнице);
- мутации «число взято из `testsuite@tests`», «порог `>` вместо `≥`», «задача вне интервала попала в прирост», «`TestReport` изменился», «повтор записывает вторую запись», «время попытки сравнивается с пределом локального прогона» — красные.

Тесты импортируют `orchestrator.suite_cost` внутри тела теста, а не на уровне модуля: модуля до кода нет, сухой сбор не должен падать.

Безопасность тестов: ответы GitHub — подмена вызова `gh` в процессе теста, без сети; архивы junit — во временном каталоге; БД пульта и репозиторий — во временной песочнице (`tests.sandbox`); служебный каталог пульта, настоящая запись проектов и каталоги задач не читаются и не пишутся.

Заметка: время подготовки класса при xdist попадает первому тесту класса на каждом рабочем процессе — в списке самых медленных возможен шум; так и оставить.

Матрица неослабления:

| Свойство | Где держится | После | Чем покрыто |
|---|---|---|---|
| Исходы `job_test_report` для гейтов исходов (ADR-0026) | `orchestrator/forge.py:395-457`, `_parse_junit` | без изменений | залоченные тесты `github_ci_report`, критерий 1 |
| Равенство `TestReport` | `orchestrator/forge.py:73` | класс не меняется | критерий 1, мутация |
| Сигнал `suite.near_limit`, проверка `suite-duration`, пределы | `orchestrator/acceptance.py:3259`, `orchestrator/doctor/suite_duration.py` | без изменений | «Не входит» |
| Паритет схемы БД | `tests/test_store_schema_migration_parity.py` | таблица одним определением | существующий тест паритета |

Существующие тесты: правка не должна сделать красным ни один существующий тест; если краснеет тест, сверяющий состав `TestReport`, перечень проверок `doctor` или схему БД, — эскалация с именем теста, без правки.

Зоны: orchestrator/forge.py, orchestrator/suite_cost.py, orchestrator/artel.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/config.py, orchestrator/doctor/cli.py, orchestrator/doctor/__init__.py, orchestrator/doctor/suite_cost.py, docs/codebase-map.md, tests/

Только чтение: `docs/adr/0032-test-cost-and-growth.md`, `docs/adr/0031-test-runs-strategy.md`, `orchestrator/acceptance.py`, `orchestrator/ci.py`, `orchestrator/targets.py`, `orchestrator/project_profile.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/gitlab_adapter.py`, `orchestrator/doctor/suite_duration.py`, `.github/workflows/ci.yml`, `tests/sandbox.py`.

Не входит:
- перевод артели на компонент записи с `full_suite: ci` (этап 4б ADR-0031);
- изменение `TestReport`, триггера `suite.near_limit`, проверки `suite-duration` и пределов;
- реестр размеров по каждому тесту (время каждого теста отдельной таблицей) — следующий шаг этапа 1 по данным первых сводок;
- автоматическая запись сводки после мержа — командой `--record-latest` (Оператор или `doctor`-обход позже);
- выбор тестов на шаге роли (этап 7).

Приоритет 1.

Рамка: $85. Набор моделей — по умолчанию.
