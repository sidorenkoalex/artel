---
task: 01M6Y44ZPXPQCNYDXQG6FMZPK5
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/forge.py, orchestrator/suite_cost.py, orchestrator/artel.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/config.py, orchestrator/doctor/cli.py, orchestrator/doctor/__init__.py, orchestrator/doctor/suite_cost.py, docs/triggers.md, docs/codebase-map.md, tests/
budget_usd: 85
---

# SPEC: Слежение за ценой набора тестов по отчёту junit CI main: сводка, самые медленные, прирост от задачи (ADR-0032, этап 1)

## Контекст
ADR-0032 п. 6 (принят 08.11.2026, `e4de84a0`) требует: по отчёту junit
каждого прогона CI `main` пульт пишет число тестов, сумму, время по часам,
20 самых медленных, долю каждого размера и прирост от последней смерженной
задачи; `doctor` предупреждает при 75 % предела (локального и CI), алерт —
при 85 %. С `a8ff5c70` задание CI `ci.FULL_SUITE_JOB` («Синтаксис и тесты
оркестратора», `orchestrator/ci.py:39`) выгружает отчёт junit артефактом
`junit` при любом исходе прогона. Сейчас `forge` (`orchestrator/forge.py`)
читает из отчёта только исходы (`TestReport` `:73`, `_parse_junit` `:702`,
`job_test_report` `:800`), имя артефакта берёт из компонента записи
(`_gh_report_artifact` `:561`), которого у артели нет; времени тестов,
сводки, её записи и проверки `doctor` по ней нет.

Факты из ТЗ, на которые опираются требования: у `testcase` есть
`classname` (через точки), `name`, `time`, атрибута `file` нет;
`testsuite@tests` у pytest 9.1 считает подтесты и больше числа элементов
`testcase`; пуш только документов в `main` задание тестов не исполняет
(ADR-0016), и тогда `forge._gh_attempt` отдаёт пропущенную попытку
(`orchestrator/forge.py:541-543`); прогон, оборванный пределом 40 мин
(`timeout-minutes: 40`, `.github/workflows/ci.yml:216`), отчёта junit не
оставляет; коммит мержа задачи в `main` имеет тему `<id>: merge task/…`
(`orchestrator/fsm_merge_gate.py:860`). Решения Оператора по батчу
вопросов — `ANSWER-1.md` (ответы 1–9), ссылки на них ниже — «ответ N».

## Требования

1. **Время тестов — отдельно от исходов.** `TestReport`, `_parse_junit` и
   `job_test_report` (`orchestrator/forge.py`) не меняются: состав полей
   `TestReport` остаётся (`outcomes`, `reason`). Новая публичная функция
   `forge.parse_junit_times(data)` — `data` это байты архива артефакта
   junit — разбирает архив с теми же пределами и отказами, что
   `_junit_report` (пути элементов, предел распаковки, ровно один `*.xml`,
   отказ DTD, повтор ключа), и отдаёт кортеж `(times, suite_seconds,
   reason)`: `times` — словарь «`<classname>::<name>` → время в секундах
   (float)» по каждому элементу `testcase`, `suite_seconds` —
   `testsuite@time` (float), `reason` — пустая строка. Отчёта нет — `(None,
   None, reason)` с непустой причиной; пустой или нечисловой атрибут
   `time` у `testcase` или у `testsuite` — такой исход, а не ноль.
2. **Отчёт CI по sha.** Новая публичная функция
   `forge.ci_suite_report(target, sha)` отдаёт кортеж `(times,
   suite_seconds, job_seconds, reason)`. Она находит попытку задания
   `ci.FULL_SUITE_JOB` по sha тем же правилом, что `job_test_report`, и
   артефакт с именем `targets.CI_REPORT_ARTIFACT_DEFAULT` (ответ 9: новой
   константы имени нет), с теми же пределами и отказами, что у
   `job_test_report` (окно `started_at`–`completed_at` попытки, ровно один
   годный артефакт, срок хранения, предел размера архива, предел
   скачивания); архив разбирает `parse_junit_times`. `job_seconds` —
   `completed_at − started_at` завершённой попытки в секундах.
   Исходы:
   - отчёт прочитан — `times` и `suite_seconds` из `parse_junit_times`,
     `job_seconds`, `reason` пустая;
   - попытка завершена, отчёта нет (годного артефакта нет — обрыв по
     пределу; срок истёк; архив больше предела; архив не разобран) —
     `(None, None, job_seconds, reason)`, причина непустая;
   - задание не исполнялось (у попытки заключение `skipped`) — `(None,
     None, None, reason)`, причина содержит «задание не исполнялось»;
   - попытка не найдена, не завершена или ответ `gh` не прочитан —
     `(None, None, None, reason)` с непустой причиной.
   Хостинг проекта не GitHub — `(None, None, None, reason)` без обращения
   к сети.
3. **Последний исполненный коммит ветки.** Новая публичная функция
   `forge.last_executed_commit(target, branch, job_name)` (ответ 1)
   отдаёт кортеж `(sha, reason)`: sha последнего прогона Actions ветки
   `branch`, у которого задание `job_name` завершено с любым заключением,
   кроме `skipped` (`success`, `failure`, `timed_out`, `cancelled`);
   незавершённые прогоны пропускаются; не найден — `(None, причина)`.
   `forge.green_base_commit` не меняется.
4. **Сводка** — публичные функции нового модуля `orchestrator/suite_cost.py`:
   - `size_bucket(seconds)`: `t < 1` — «до 1 с», `1 ≤ t < 10` — «1–10 с»,
     `10 ≤ t < 60` — «10–60 с», `t ≥ 60` — «60 с и дольше»;
   - `summarize(times, suite_seconds, job_seconds, previous=None,
     tasks=())` отдаёт словарь с ключами: `tests` — число тестов, то есть
     число ключей `times` (число элементов `testcase`, не
     `testsuite@tests`); `total_seconds` — сумма времени `times`;
     `suite_seconds`; `job_seconds`; `slowest` — список пар `[узел,
     секунды]` из 20 самых медленных по убыванию времени, при равенстве
     времени — по имени узла по возрастанию; `buckets` — словарь «ориентир
     `size_bucket` → `{"count": число тестов, "share": доля суммы времени
     (0…1)}`» по всем четырём ориентирам, включая пустые; `delta_tests` и
     `delta_seconds` — прирост `tests` и `total_seconds` против `previous`
     (словаря того же вида), `None` без `previous`; `tasks` — список
     задач из аргумента `tasks`. При `times = None` (отчёта нет) `tests`,
     `total_seconds`, `slowest`, `buckets`, `delta_tests`, `delta_seconds`
     — `None`, `job_seconds` сохраняется;
   - `merged_tasks(prev_sha, sha)`: список id задач из тем коммитов
     `<id>: merge task/…` первой родительской линии `main` между sha
     (`git log --first-parent prev_sha..sha`, репозиторий пульта), где
     `<id>` — задача проекта артели в БД пульта; темы с `<id>`, которого
     в БД нет, в список не входят;
   - `limit_level(seconds, limit)`: `ok`; `warn` при доле
     `seconds / limit ≥ config.SUITE_COST_WARN_RATIO` (= 0,75); `alert` при
     доле `≥ config.SUITE_COST_ALERT_RATIO` (= 0,85).
   Предыдущая сводка для sha (ответ 4) — запись того же проекта,
   ближайшая к sha по первой родительской линии `main` среди его предков,
   у которой есть отчёт (`tests` не `None`); записи без отчёта для
   прироста пропускаются. Нет предыдущей — прирост `None`, задачи — пустой
   список.
5. **Запись.** Новая таблица БД пульта — одним определением в `SCHEMA`
   и в `migrate()`: `migrate()` на БД пульта без этой таблицы её создаёт.
   Запись несёт проект (ответ 6), sha, время записи, вывод `summarize` и
   причину отсутствия отчёта. Одна запись на пару «проект, sha»: повторная
   запись того же sha второй записи не даёт и первую не меняет. Попытка
   без отчёта (`job_seconds` есть, `times` нет) записывается вместе с
   `job_seconds` и причиной. Последняя сводка проекта — его запись,
   сделанная позже всех по времени записи.
6. **Команда** `artel.py suite-cost` работает с проектом артели
   (`config.DEFAULT_TARGET`; задание `ci.FULL_SUITE_JOB` — задание CI
   артели):
   - без флагов — печатает последнюю сводку (sha, время записи и все
     значения вывода `summarize`, причину, если отчёта нет); ничего не
     пишет; сводок нет — сообщает об этом;
   - `--record <sha>` — `ci_suite_report` для sha, предыдущая сводка по
     требованию 4, `merged_tasks(предыдущий sha, sha)`, `summarize`,
     запись; задание не исполнялось (ответ 3) или `job_seconds` нет
     (попытка не найдена, не завершена, не прочитана) — записи нет, отказ
     с причиной `ci_suite_report`, код выхода ненулевой;
   - `--record-latest` — то же, что `--record`, для sha, который отдаёт
     `forge.last_executed_commit(<артель>, "main", ci.FULL_SUITE_JOB)`;
     не найден — записи нет, отказ с причиной, код выхода ненулевой.
   Строка справки команды — в блоке «Команды:» докстринга модуля
   `orchestrator/artel.py`; в перечень команд, разрешённых роли
   (`_ROLE_ALLOWED_COMMANDS`, `orchestrator/artel.py:2595`), команда не
   входит.
7. **Проверка doctor** «suite-cost:<target>» — отдельным модулем
   `orchestrator/doctor/suite_cost.py`, подключённым в `doctor.all_checks`.
   Строится для каждого проекта, у которого есть сводка или запись
   «прогон: время» (`acceptance.SUITE_DURATION_ACTION`) задачи проекта в
   БД (ответ 6). Две строки с именем `suite-cost:<target>`:
   - строка CI (текст начинается с «CI:») — `job_seconds` последней
     сводки проекта против `config.SUITE_COST_CI_LIMIT_SEC` (= 2400 с, 40
     мин; ответ 8); называет секунды, предел, долю в процентах, sha и
     возраст сводки, у сводки без отчёта — и её причину; сводки нет —
     пропуск строки с причиной;
   - строка локального прогона (текст начинается с «локальный прогон:») —
     `duration_seconds` последней по времени записи «прогон: время» задач
     проекта (только отбор по проекту, без сброса по подтверждению алерта
     `suite.duration`; ответ 5) против значения
     `project_profile.full_suite_limit(target)`; называет секунды, предел,
     его источник, долю в процентах и возраст записи; записи нет — пропуск
     с причиной; `targets.TargetsError` из `full_suite_limit` — пропуск с
     причиной из исключения (ответ 7).
   Уровень строки — `limit_level` (ответ 2): `ok` — статус `ok`; `warn` —
   статус `warn`, текст называет «предупреждение»; `alert` — статус
   `warn`, текст называет «тревога», и `alerts.raise_alert(conn, target,
   "trigger", "suite.cost", <сообщение>)` с сообщением, не зависящим от
   чисел, sha и строки, — так дедуп `raise_alert` держит один открытый
   алерт `suite.cost` на проект. Статус `fail` проверка не выдаёт.
   `docs/triggers.md` получает одну новую строку реестра для источника
   `suite.cost` (условие — доля `≥ config.SUITE_COST_ALERT_RATIO` предела
   CI или локального; носитель — алерт kind=trigger); прочие строки
   реестра не меняются.
8. **Предел CI сверен с CI.** Тест задачи сверяет
   `config.SUITE_COST_CI_LIMIT_SEC` с `timeout-minutes` задания с именем
   `ci.FULL_SUITE_JOB` в `.github/workflows/ci.yml` (минуты × 60); чтение
   файла — по правилам линта детерминизма тестов
   (`orchestrator/test_lint.py`).

## Критерии приёмки

AC-1. Given архив junit (zip во временном каталоге) с тремя тестами
разного времени и подтестом, When `forge.parse_junit_times(data)`, Then
`times` несёт каждый узел `<classname>::<name>` с его временем,
`suite_seconds` равно `testsuite@time`, `reason` пустая; архив с пустым
`time` у одного `testcase` — `(None, None, <непустая причина>)`, не ноль;
When `forge.job_test_report` на том же архиве (подменённые ответы `gh`),
Then `TestReport` равен прежнему целиком, а имена полей
`dataclasses.fields(forge.TestReport)` — ровно `("outcomes", "reason")`.
(Поверхность решения: `orchestrator.forge.parse_junit_times(data) ->
tuple`; размер проверки: малый.)

AC-2. Given подменённые ответы `gh` для sha (в процессе теста, без сети),
When `forge.ci_suite_report(target, sha)`, Then: годный артефакт —
`times`, `suite_seconds` и `job_seconds` (`completed_at − started_at`),
причина пустая; годного артефакта нет (обрыв) — `(None, None,
job_seconds, <причина>)`; артефакт вне окна попытки, архив больше предела,
истёкший срок — `times` `None` и причина; все попытки `skipped` —
`job_seconds` `None` и причина содержит «задание не исполнялось».
(Поверхность решения: `orchestrator.forge.ci_suite_report(target, sha) ->
tuple`; размер проверки: малый.)

AC-3. Given подменённые ответы `gh` со списком прогонов ветки `main`
(новые первыми): незавершённый, с заданием `skipped`, оборванный
(`timed_out`), красный, зелёный, When `forge.last_executed_commit(target,
"main", ci.FULL_SUITE_JOB)`, Then sha оборванного прогона; без оборванного
— красного; без оборванного и красного — зелёного; только незавершённые и
`skipped` — `(None, <причина>)`. (Поверхность решения:
`orchestrator.forge.last_executed_commit(target, branch, job_name) ->
tuple`; размер проверки: малый.)

AC-4. Given архив junit с 25 тестами известного времени (включая два с
равным временем на 20-й позиции) и `testsuite@tests` больше числа
`testcase`, When `parse_junit_times`, затем `summarize(times,
suite_seconds, job_seconds, previous, tasks)` с предыдущей сводкой, Then
`tests` = 25; `slowest` — ровно 20 пар по убыванию времени, из двух равных
на 20-й позиции — меньшая по имени узла; `buckets` — четыре ориентира с
числом и долей суммы; `delta_tests` и `delta_seconds` против `previous`;
`tasks` — переданный список; без `previous` прирост `None`.
(Поверхность решения: `orchestrator.suite_cost.summarize(times,
suite_seconds, job_seconds, previous=None, tasks=()) -> dict`; размер
проверки: малый.)

AC-5. Given `size_bucket` и `limit_level` на границах (0,999; 1; 9,999;
10; 59,999; 60 с; 74,99 %; 75 %; 84,99 %; 85 % предела), Then ориентир и
уровень — по правилам требования 4. (Поверхность решения:
`orchestrator.suite_cost.size_bucket(seconds) -> str`;
`orchestrator.suite_cost.limit_level(seconds, limit) -> str`; размер
проверки: малый.)

AC-6. Given репозиторий и БД пульта во временной песочнице: на первой
родительской линии `main` мержи двух задач проекта между двумя sha, мерж
третьей задачи — раньше первого sha, мерж с темой `<x>: merge task/…`
между sha, где `<x>` в БД нет, When `merged_tasks(prev_sha, sha)`, Then
ровно две задачи. (Поверхность решения:
`orchestrator.suite_cost.merged_tasks(prev_sha, sha) -> list`; размер
проверки: средний — настоящий git и БД пульта во временной песочнице.)

AC-7. Given в песочнице записи сводок проекта для трёх коммитов: предок
текущего sha с отчётом, более близкий предок без отчёта и коммит вне линии
предков, записанный позже всех, When `suite-cost --record <sha>` (с
подменёнными ответами `gh`), Then прирост записанной сводки посчитан
против предка с отчётом, а задачи — `merged_tasks` от его sha.
(Поверхность решения: нет — правило выбора наблюдается через команду
записи, отдельной публичной функции выбора требование не задаёт; размер
проверки: средний — git и БД пульта во временной песочнице.)

AC-8. Given БД пульта во временной песочнице, When запись сводки sha
дважды, Then запись одна и первая не изменилась; When запись попытки без
отчёта (обрыв), Then запись хранит `job_seconds` и причину; Given БД, на
которой таблицы сводок нет, When `migrate()`, Then таблица есть и запись
в неё проходит. (Поверхность решения: нет — свойство наблюдается через
команду `suite-cost --record` и `orchestrator.schema.migrate(conn)`;
размер проверки: средний — БД пульта во временной песочнице.)

AC-9. Given БД пульта во временной песочнице и подменённые ответы `gh`,
When `artel.py suite-cost` без флагов, Then в БД ничего не записано, а
вывод несёт sha и значения последней сводки — те же, что вывод
`summarize` на том же входе (`tests`, `total_seconds`, `suite_seconds`,
`job_seconds`, 20 узлов `slowest`, четыре ориентира, прирост, задачи);
When `--record <sha>`, Then сводка этого sha записана; When `--record
<sha>` для попытки `skipped`, Then записи нет, вывод называет «задание не
исполнялось», код выхода ненулевой; When `--record-latest`, Then записана
сводка для sha, который отдаёт подменённый
`forge.last_executed_commit`; `suite-cost` нет в
`_ROLE_ALLOWED_COMMANDS` и есть в блоке «Команды:» докстринга
`orchestrator.artel`. (Поверхность решения: нет — подключение команды,
вход — командная строка `artel.py suite-cost …` (`orchestrator.artel.main()`
по `sys.argv`); размер проверки: средний — БД
пульта во временной песочнице.)

AC-10. Given в песочнице сводка проекта с `job_seconds` 1860 с (31 мин) и
запись «прогон: время» задачи проекта 1300 с при пределе профиля 1500 с,
When `doctor.all_checks`, Then строка «CI:» `suite-cost:<target>` —
статус `warn`, «предупреждение», 77,5 %, sha и возраст сводки; строка
«локальный прогон:» — статус `warn`, «тревога», 86,7 %, и в таблице
`alerts` один открытый алерт kind=trigger, источник `suite.cost`, этого
проекта; повторный `doctor` с другими числами уровня `alert` второго
открытого алерта не даёт; при 70 % обеих — статус `ok`, алерта нет;
сводка без отчёта с `job_seconds` 2400 с — строка «CI:» «тревога» с
причиной отсутствия отчёта; без сводки — строка «CI:» пропущена с
причиной, строка локального прогона остаётся; `full_suite_limit` бросает
`targets.TargetsError` — строка локального прогона пропущена с причиной
исключения, `all_checks` не падает; статуса `fail` у строк нет.
(Поверхность решения: нет — подключение проверки, вход —
`orchestrator.doctor.all_checks(conn)`; размер проверки: средний — БД
пульта во временной песочнице.)

AC-11. Given `.github/workflows/ci.yml` репозитория, When тест читает
`timeout-minutes` задания с именем `ci.FULL_SUITE_JOB`, Then значение × 60
равно `config.SUITE_COST_CI_LIMIT_SEC`; в `docs/triggers.md` есть строка
реестра, называющая источник `suite.cost` и константу
`SUITE_COST_ALERT_RATIO`. (Поверхность решения: нет — сверка константы с
файлами репозитория; размер проверки: малый.)

AC-12. Мутации «число тестов взято из `testsuite@tests`» (AC-4), «порог
`>` вместо `≥`» (AC-5), «задача вне интервала попала в прирост» (AC-6),
«`TestReport` изменился, в том числе полем со значением по умолчанию»
(AC-1), «повтор записывает вторую запись» (AC-8), «время попытки
сравнивается с пределом локального прогона» (AC-10), «предыдущая сводка —
последняя по времени записи без проверки предка» (AC-7), «`skipped`
попытка записана» (AC-9), «`--record-latest` берёт только зелёные
прогоны» (AC-3), «таблица только в `SCHEMA`, без `migrate()`» (AC-8) —
красные на названных критериях. (Поверхность решения: нет — перечень
мутаций к критериям выше; размер проверки: малый — мутации прогоняются на
тестах AC-1…AC-11.)

Условия тестов (из ТЗ): тесты импортируют `orchestrator.suite_cost` внутри
тела теста, а не на уровне модуля — модуля до кода нет, сухой сбор не
должен падать. Ответы GitHub — подмена вызова `gh` в процессе теста, без
сети; архивы junit — во временном каталоге; БД пульта и репозиторий — во
временной песочнице (`tests.sandbox`); служебный каталог пульта, настоящая
запись проектов и каталоги задач не читаются и не пишутся.

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны вне общих зон — 10 (`forge.py`,
`suite_cost.py`, `artel.py`, `store.py`, `schema.py`, `config.py`,
`doctor/cli.py`, `doctor/__init__.py`, `doctor/suite_cost.py`,
`docs/triggers.md`; порог 5); критериев приёмки 12 (порог 10);
`budget_usd` = 85.

Материал Оператору для решения «монолит» (сам текст «монолит принят» —
решение Оператора):
- Единственный шов по зонам — `orchestrator/forge.py` (требования 1–3,
  AC-1–AC-3). Отдельно он мержим с зелёной планкой (новые публичные
  функции, исходы не меняются), но без потребителя: форма выходов
  `parse_junit_times`/`ci_suite_report` — входной контракт `summarize`,
  записи и `doctor` (требования 4–7), и, зафиксированная без них, она
  утверждается вслепую — расхождение вскроется во второй части и потребует
  правки уже смерженного `forge`.
- Требования 4–8 (`suite_cost.py`, схема/store, команда, doctor, реестр
  триггеров) делят одну запись сводки: команда пишет её, doctor читает,
  выбор предыдущей сводки идёт по ней же — резать их поперёк нельзя.
- Деление на две части дало бы два цикла аналитика, аудита и гейта SPEC
  против рамки $85 ТЗ на всю задачу.
- Мутация «`TestReport` изменился» сторожит обе части сразу: в монолите
  она проверяется на том же диффе, что и новый разбор времени.

## Не входит

- Перевод артели на компонент записи с `full_suite: ci` (этап 4б ADR-0031).
- Изменение `TestReport`, `_parse_junit`, `job_test_report`,
  `green_base_commit`, триггера `suite.near_limit`
  (`orchestrator/acceptance.py:3259`), проверки `doctor` «suite-duration»
  (`orchestrator/doctor/suite_duration.py`) и пределов.
- Прочие строки `docs/triggers.md`, кроме одной новой строки `suite.cost`
  (мандат ANSWER-1).
- Реестр размеров по каждому тесту (время каждого теста отдельной
  таблицей) — следующий шаг этапа 1 по данным первых сводок.
- Автоматическая запись сводки после мержа — только командой
  `--record-latest` (Оператор или обход `doctor` позже).
- Выбор проекта у команды `suite-cost` — она работает с артелью.
- Выбор тестов на шаге роли (этап 7 ADR-0032).
- Шум «время подготовки класса при xdist попадает первому тесту класса» в
  списке самых медленных — так и оставить (заметка ТЗ).
- Правка файлов только для чтения из ТЗ: `docs/adr/0032-test-cost-and-growth.md`,
  `docs/adr/0031-test-runs-strategy.md`, `orchestrator/acceptance.py`,
  `orchestrator/ci.py`, `orchestrator/targets.py`,
  `orchestrator/project_profile.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/gitlab_adapter.py`, `orchestrator/doctor/suite_duration.py`,
  `.github/workflows/ci.yml`, `tests/sandbox.py`; правка линта
  детерминизма `orchestrator/test_lint.py` (тест AC-11 следует его
  правилам, не меняет их).
- Зелёный полный набор существующих `tests/` — его держит пульт. Если
  краснеет существующий тест, сверяющий состав `TestReport`, перечень
  проверок `doctor` или схему БД (`tests/test_store_schema_migration_parity.py`,
  `tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py`), —
  эскалация с именем теста, без его правки (условие ТЗ).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| `forge.py`: новые `parse_junit_times`, `ci_suite_report` | исходы `job_test_report` для гейтов ADR-0026 — `orchestrator/forge.py:395-457`, `:702`; равенство `TestReport` — `:73`, `tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py:1351` | да: функции не меняются | залоченные тесты `github_ci_report`; AC-1 (равенство и состав полей), AC-12 | ок |
| `forge.py`: новая `last_executed_commit` (ответ 1) | `green_base_commit` (`orchestrator/forge.py:460-492`) — последний зелёный коммит для проверки базы `doctor` (`orchestrator/doctor/project_checks.py:580`) | да: `green_base_commit` и его потребитель не меняются | не покрыто тестами `tests/`; AC-3 — новая функция | ок при условии: `green_base_commit` не меняется (сверка ревью диффа) |
| `schema.py`/`store.py`: новая таблица | паритет «свежая БД = догнанная» — `tests/test_store_schema_migration_parity.py:28-46`, только колонки `tasks` | для новой таблицы — AC-8 | AC-8 (`migrate()` на БД без таблицы её создаёт) | ок |
| Алерт `suite.cost` и строка `docs/triggers.md` (ответ 2) | дедуп `raise_alert` — `orchestrator/alerts.py:93-105` | да: прежние источники и дедуп не меняются | tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py, tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py; AC-10, AC-11 | ок |
| Строки `doctor` уровня `warn` вместо `fail` (ответ 2) | `fail` делает выход `doctor` ненулевым — `orchestrator/doctor/cli.py:361-364` | да: коды выхода прежних проверок не меняются | tests/test_doctor.py; AC-10 | ок |
| `doctor/cli.py`: новая проверка в `all_checks` | тесты, зовущие `doctor.all_checks` с записями «прогон: время» — `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py:59,136` | да: проверка не бросает исключений (`TargetsError` перехвачен) | AC-10 | ок |
| `artel.py`: новая команда | справка ↔ реестр — `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py:75-117`; белый список роли — `orchestrator/artel.py:2595-2598` | да | тест справки; AC-9 | ок |
| Константа `config.SUITE_COST_CI_LIMIT_SEC` (ответ 8) | предел задания CI — `timeout-minutes: 40`, `.github/workflows/ci.yml:216` | да: файл CI не меняется | AC-11 | ок |
| `suite.near_limit`, `suite-duration`, пределы | `orchestrator/acceptance.py:3259`, `orchestrator/doctor/suite_duration.py` | без изменений | `tests/test_suite_duration.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py` | ок |

## Материалы

- ADR-0032 п. 6 (`docs/adr/0032-test-cost-and-growth.md`), ADR-0016
  (классы пуша CI), ADR-0026 (гейты исходов); `ANSWER-1.md` — ответы
  Оператора 1–9 и мандат на `docs/triggers.md`.
- Первый артефакт `junit`: прогон Actions `42503643843`, задание
  `128801551938` — 10 008 `testcase`, сумма 5510 с, `testsuite@time`
  1453 с, попытка 1469 с, `testsuite@tests` = 18197.
- Опоры в коде: `forge._gh_attempt` (`orchestrator/forge.py:527`),
  `forge.green_base_commit` (`:460`, образец обхода прогонов ветки),
  `targets.CI_REPORT_ARTIFACT_DEFAULT` (`orchestrator/targets.py:175`),
  `project_profile.full_suite_limit` (`orchestrator/project_profile.py:431`,
  бросает `TargetsError` `:435`), `acceptance.SUITE_DURATION_ACTION`
  (`orchestrator/acceptance.py:1653`), `alerts.raise_alert`
  (`orchestrator/alerts.py:93`, образец вызова —
  `orchestrator/doctor/suite_duration.py:67`), регистрация проверок
  `doctor` (`orchestrator/doctor/cli.py:281`,
  `orchestrator/doctor/__init__.py:213`), строка реестра-образец
  `suite.near_limit` — `docs/triggers.md`, №32; `gitcmd.merges_between`
  (`orchestrator/gitcmd.py:1591`, образец `--first-parent`); git — только
  через `gitcmd` (`tests/test_invariants.py`,
  `CarpentryGitCallsGoThroughGitcmdTest`).
