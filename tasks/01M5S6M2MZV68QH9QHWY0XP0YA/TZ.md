---
task: 01M5S6M2MZV68QH9QHWY0XP0YA
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Vitest 4 под пультом: флаг кэша, хуки и класс ошибки в отчётчике, итоговая строка, номер повтора

# Vitest 4 под пультом: флаг кэша, хуки и класс ошибки в отчётчике, итоговая строка, номер повтора в идентификаторе


## Решения Оператора

Решение Оператора 25.10.2026 (дословно: «ок по рекомендациям») по вопросам этого ТЗ:
1. Форма идентификатора — вариант (а): у имени, которое само кончается на `#<цифры>`, номер пишется всегда, первое вхождение — `#1`; повтором гейты считают только номер от 2 (требование 4). Фраза ADR-0026 п. 3 вносится Оператором через doc-commit до `new`.
2. Упавший `afterAll`: тесты набора без собственной ошибки и не помеченные явно `skip`/`todo` записываются упавшими с хуком `afterAll`; честный провал остаётся провалом проверки, явный `skip`/`todo` — пропуском.
3. `aroundEach`/`aroundAll` — вне задачи, строкой бэклога.
4. Мандат на правку `tests/test_report_outcome_module.py::test_vitest_component_with_workdir_gets_exact_pult_argv` по перечню (строкой ANSWER на гейте SPEC).
ADR-0026 пп. 2–4, пример записи и вопрос 10 поправлены Оператором (doc-commit) до `new`.

Решение Оператора 25.10.2026 (дословно): «Да: задача Vitest 4 до канарейки, перенос записей в локальный слой — отдельной задачей до 2.1.»

Решение Оператора 22.10.2026 по вопросу 10 ADR-0026 (дословно, запись 22.10 в плане этапа 2 sled — документ ассистентской сессии вне репозитория): «failure_errors компонента frontend sled — [AssertionError, TestingLibraryElementError, JestExtendError, HtmlElementTypeError]; отчётчик pult-vitest передаёт настоящий класс ошибки (поле constructor), не обобщённое Error. Список — данные записи sled в targets.yaml (этап 2.1); правка ADR-0026 (раздел вопроса 10 и пример записи) — doc-commit на границе волны вместе с документами процесса; правка отчётчика — в задаче «Vitest 4 под пультом» (бэклог, приоритет 1).»

Отсюда граница задачи: список `failure_errors` — данные записи sled (этап 2.1, отдельно), здесь его не пишут; задача только делает так, чтобы пульт мог им пользоваться — отчётчик передаёт настоящий класс ошибки.

## Факты

Источник требований — строка бэклога «Vitest 4 под пультом…» в `docs/backlog.md` (на пине строка 407, в origin/main 9d677c82 — строка 421; приоритет 1, оценка $30–45, зоны `orchestrator/project_profile.py, orchestrator/reporters/, orchestrator/agent_log.py, orchestrator/acceptance.py, tests/`) и запись пробы 2.2 от 22.10 в том же плане (sled 7131152, Vitest 4.1.5, 306 файлов, 4301 тест, прогон около 32 с).

Сверено с пином 09ded609 (голова главной копии) и с origin/main 9d677c82. Между ними различаются, из названных ниже, `orchestrator/acceptance.py`, `docs/backlog.md`, `docs/codebase-map.md` и файлы `tests/` (волны сведения тестов): для них ссылки даны по именам функций, тестов и строк бэклога, а не по номерам строк. Тесты названы по origin/main: `tests/test_report_outcome_module.py` и `tests/report_outcome_sandbox.py` на пине ещё нет (на пине те же тесты лежат в двух прежних файлах, сведённых в origin/main в эти два). Остальные названные файлы на пине и в origin/main совпадают, номера строк в них верны.

Проверка Vitest 4.1.5 повторена 25.10 вне пульта: зависимости фронтенда sled (файл блокировки версий из клона sled на машине пульта) поставлены `npm ci --offline --ignore-scripts` из локального кэша npm во временный каталог, без обращения к сети; прогоны — на маленьком проекте с тестами каждого случая ниже (jsdom, `@testing-library/jest-dom/vitest`), с отчётчиком пульта из главной копии и с отладочным отчётчиком, печатающим поля API отчётчиков.

### (1) Флаг кэша

- `orchestrator/project_profile.py:548-550` — `VITEST_VERSION_FLAGS = {4: VitestFlags("--cacheDir", True, "не подтверждено пробой (этап 2)")}`; `VitestFlags` (`:536-543`) — поля `cache_flag`, `require_assertions`, `probe`; `vitest_flags` (`:553-557`). Других главных версий в таблице нет: Vitest 3 и любая версия вне таблицы получают отказ подготовки «флаг кэша для главной версии … не подтверждён» (`orchestrator/acceptance.py`, `_vitest_head`). Это и есть нынешнее поведение «не Vitest 4», которое задача сохраняет.
- `orchestrator/acceptance.py`, `_vitest_head`: заводит каталог `_pult_dir(profile, "cache") / "vitest"` и добавляет `f"{flags.cache_flag}={cache}"` после `--expect.requireAssertions`. Каталог `cache/<компонент>/vitest` больше нигде не используется (`_pult_dir(…, "cache")` — единственный вызов).
- Vitest 4.1.5: `--cacheDir=<путь>` — `CACError: Unknown option --cacheDir`, код 1, отчёта нет (повторено). Параметр `cache` командной строки (исходник пакета `vitest@4.1.5`, описание параметров `cac`) — только признак: `--cache.dir` бросает «--cache.dir is deprecated», каталог кэша задаётся только `cacheDir` настройки Vite (то есть закрытым `vitest.config.js` проекта).
- Без флага Vitest 4 пишет файл результатов `results.json` в каталог кэша Vite внутри `node_modules` — в каталог установки пульта, который пульт подключает только для чтения (`orchestrator/acceptance.py`, `_chmod_tree`). Отказ записи Vitest молча проглатывает (прогон без флага при `node_modules` без прав записи — код 0), то есть с кэшем порядок и состав прогона зависят от того, удалась ли запись в прошлый раз. С `--no-cache` `results.json` не пишется вовсе; прогон с `--no-cache` при `node_modules` без прав записи (права как у `_chmod_tree(read_only=True)`) проходит с кодом 0 и полным отчётом пульта. Довод за `--no-cache` — воспроизводимость прогона, а не только отказ `--cacheDir`.
- ADR-0026 п. 2 (`docs/adr/0026-project-components-and-outcome-gates.md:31`) говорит «кэш Vite вне рабочей копии» — после задачи это неверно; поправка — в списке doc-commit Оператора («Не входит»).
- Тест `tests/test_report_outcome_module.py::test_vitest_component_with_workdir_gets_exact_pult_argv` требует `args[len(head)].startswith("--cacheDir=")` — закрепляет неверный для Vitest 4 флаг; без правки этого теста флаг не заменить (перечень правок ниже).
- Тест `tests/test_report_outcome_module.py::test_ac9_run_conditions_argv_env_cache_and_flags` с `--no-cache` остаётся зелёным, но его проверка «флаг кэша с путём вне клона и вне `node_modules`» становится пустой: помощник `report_arg` (`tests/report_outcome_sandbox.py`) для флага без `=` берёт значением следующий аргумент (`--reporter=…`). Проверено прототипом (ниже). Правка не обязательна; свойство «нет каталога кэша и флага с путём» закрывает новый тест требования 5.

### (2) Отчётчик `pult-vitest`

`orchestrator/reporters/pult_vitest_reporter.js` (121 строка, на пине и в origin/main одинаков):

- `failedHook` (`:48-56`) ищет в `task.result.hooks` значение `"fail"`. Vitest 4.1.5 (исходник пакета `@vitest/runner@4.1.5`, функция `callSuiteHook`) ставит хуку `"run"` перед вызовом и `"pass"` после успешного; брошенное исключение оставляет `"run"`, значения `"fail"` нет вовсе. Наблюдение: упавший `beforeEach` — `{"beforeEach": "run"}`, прошедшие — `{"beforeEach": "pass", "afterEach": "pass"}`, хук с таймаутом — `"run"` и ошибка «Hook timed out». Итог: `hook` всегда `null`; `expect` в `beforeEach` даёт запись `fail` с `AssertionError` без хука — `orchestrator/reporters/outcome.py:186-206` (`_vitest_case`) засчитывает её провалом проверки.
- `beforeAll`/`afterAll` — состояние хука и ошибка лежат на наборе (`TestSuite.task.result.hooks`, `TestSuite.errors()`), а у хуков верхнего уровня файла — на модуле (`TestModule.task.result.hooks`, `TestModule.errors()`). Тесты под упавшим `beforeAll` — `skipped` без ошибки; при упавшем `afterAll` тесты — `passed`. Отчётчик ошибок набора не читает (`record`, `:58-79`); ошибку модуля читает только как ошибку уровня файла (`moduleErrorRecord`, `:81-95`), то есть упавший `beforeAll` верхнего уровня сейчас даёт запись `<ошибка уровня файла>` и пропущенные тесты.
- Класс ошибки: `error_name: first.name` (`:74`, `:92`). Сериализация ошибок Vitest (пакет `@vitest/utils@4.1.5`, `serializeValue`: функция — строка `Function<имя>`, свойства собираются обходом прототипов) несёт собственное поле `constructor` строкой `Function<Имя>`. Наблюдение: матчер jest-dom `toHaveTextContent` — `name: "Error"`, `constructor: "Function<JestExtendError>"`; `toBeInTheDocument` на не-элементе — `name: "Error"`, `constructor: "Function<HtmlElementTypeError>"`; `getByText` — `name: "TestingLibraryElementError"`, `constructor: "Function<Error>"`; `expect(1).toBe(2)` — `name: "AssertionError"`, собственного `constructor` нет; `TypeError` — оба поля `TypeError`. Значит, ни одно поле в одиночку не даёт класса: по `name` пропадают `JestExtendError` и `HtmlElementTypeError`, по `constructor` — `TestingLibraryElementError` и `AssertionError`.
- `mode`: Vitest 4 разворачивает `.only` в `"run"` до отчёта (`@vitest/runner`, `interpretTaskModes`), `test.options.mode` и `task.mode` у теста с `.only` — `"run"`. При `--allowOnly=false` (базовый argv пульта) Vitest вешает ошибку `[Vitest] Unexpected .only modifier…` (`checkAllowOnly`): у `it.only` — на сам тест (`fail`, `Error`), у `describe.only` — на набор (`TestSuite.errors()`), а тесты набора — `skipped` без ошибки. Отчётчик пишет `mode: "run"`, у `describe.only` — пропуск.
- Ошибки набора без упавшего хука (например, бросила функция уборки, которую вернул `beforeAll`) правилами требования 2 не разбираются: записи тестов остаются как есть, прогон с кодом 1 даёт итог «неизвестно» (`orchestrator/reporters/outcome.py`, `verdict`) — это безопасно (не зелёный и не провал проверки); разбор — строкой бэклога («Не входит»).
- `aroundEach`/`aroundAll` (новые хуки Vitest 4.1) состояния хука не ставят: `expect` в `aroundEach` неотличим от провала проверки теста, ошибка `aroundAll` — на наборе, тесты `skipped`. В sled (клон 0027c23) `aroundEach`/`aroundAll`, `beforeAll`/`afterAll` не используются (поиск по исходникам фронтенда).
- Ни один тест `tests/` не исполняет `pult_vitest_reporter.js`: все тесты `pult-vitest` подменяют раннер и пишут JSON отчёта сами. `node` есть на машине пульта (nvm, 18–22; первым в `PATH` — 20.15.1) и в образе `ubuntu-latest` CI (`.github/workflows/ci.yml`, версия Node не закреплена). Файл отчётчика — модуль ES с расширением `.js`, а `package.json` с `"type": "module"` в `orchestrator/reporters/` нет: импорт по пути файла на Node 20.15.1 падает (проверено 25.10), на 22.23.3 проходит; копия файла с расширением `.mjs` импортируется и на Node 18.2.0.

### (3) Итоговая строка Vitest

- `orchestrator/agent_log.py:259-260` — `_VITEST_COUNTS` знает только `failed|passed|skipped|todo`. Vitest 4.1.5 печатает «expected fail» (пакет `vitest@4.1.5`, `getStateString`; порядок — failed, passed, expected fail, skipped, todo): строка `Tests  6 failed | 2 passed | 1 expected fail | 1 skipped | 1 todo (11)` не разбирается, `vitest_summaries` (`:267-289`) возвращает `[]` (повторено). Пропадают сводка шага роли в журнале (`orchestrator/runner.py:1720`) и итоговая строка `plank-run` (`orchestrator/plank_run.py:295`, вместо неё `NO_SUMMARY_LINE`); читатели журнала — `orchestrator/watch.py:57`, `orchestrator/report.py:970` — берут из детали только секунды.
- Строка «Test Files» «expected fail» не несёт (считаются только тесты, `i.type === "test"`).

### (4) Номер повтора в идентификаторе

- `orchestrator/project_profile.py:610-616` (`test_id`) дописывает `#<n>` только при `n`; `orchestrator/reporters/outcome.py:88-103` (`_Ids`) даёт номер `n ≥ 2` второму и следующим повторам одного имени в файле, первое вхождение — без номера (ADR-0026 п. 3: `[#<порядковый номер при повторе>]`).
- `parse_test_id` (`project_profile.py:619-631`) отрезает последний `#<цифры>` всегда: `parse_test_id("frontend:src/a.test.js::kinds > name #12")` → `("frontend", "src/a.test.js", "kinds > name ", 12)` (повторено). Номер из разбора проверяют гейты: `orchestrator/advance_gates/acceptance.py:344-349` (`not_passed_kind`: `where[3] is not None` — «повтор имени теста в файле») и `orchestrator/advance_gates/tests_writing.py:1185-1188` (сбор `repeats` — то же условие). Имя из разбора берут `orchestrator/advance_gates/two_sided.py:369` (узел `путь::имя` двустороннего прогона; два теста «x #12» и «x #13» дают один узел «x »), `orchestrator/mutation_run.py:407` (`_node`), `orchestrator/advance_gates/acceptance.py:305-311` (`record_location`). Мандаты сверяют идентификатор целиком (`orchestrator/advance_gates/mandate.py:574-577`), путь и компонент разбор не портит.
- Тесты разбора: `tests/test_01m58fnwbv25ff26e7az9q9912_components.py::TestIdTest::test_ac7_test_id_literal_and_round_trip` (случайные имена из букв, `n` из `None` и 1–49, в том числе явный `n=1`), `tests/test_project_components.py::TestIdTest::test_hash_without_number_stays_in_name` (`t[x#y]`, `t#²`), `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py::…::test_ac2_guard_and_parse_test_id_agree`; `scripts/guard.py:5804-5810` (`is_test_id_form`) номер не разбирает.

### Прототип и проверка совместимости

25.10 во временной выписке origin/main (тогда 2bf85f62) собран прототип требований 1, 3 и 4 (`VitestFlags("--no-cache", …)` без каталога; «expected fail» в `_VITEST_COUNTS`; `test_id` с `#1` у имени, кончающегося на `#<цифры>`) и требования 2 (отчётчик вне репозитория). Прогон Vitest 4.1.5 с прототипом отчётчика дал по каждому случаю ожидаемую запись (таблица требования 2). Файл `tests/test_report_outcome_module.py` целиком: 40 из 41 зелёные, красный — только `test_vitest_component_with_workdir_gets_exact_pult_argv`. Затем одним процессом прогнаны все 45 файлов `tests/`, где встречаются `pult-vitest`, `REPORT_VITEST`, `VITEST_VERSION_FLAGS`, `parse_test_id`, `test_id(`, `vitest_summaries`, `plank_run` или `_Ids`: 681 тест зелёный, 1 красный — тот же `test_vitest_component_with_workdir_gets_exact_pult_argv` (26 мин 39 с). Других правок существующих тестов прототип не потребовал. Прототип не включал правок гейтов требования 4 (`n ≥ 2`) и уточнений С1–С3 независимой проверки ТЗ.

### Вопросы Оператору до `new`

1. Форма идентификатора для имени, которое само кончается на `#<цифры>` (требование 4). Рекомендация (а): у такого имени номер пишется всегда, первое вхождение — `#1` (`…::name #12#1`, повтор — `…::name #12#2`); повтором гейты считают только номер от 2 (`not_passed_kind` и сбор `repeats` — `n is not None and n >= 2`), иначе одиночный тест `x #12` даёт ложную находку «повтор имени»; разбор однозначен, у прочих имён идентификаторы прежние, существующие тесты не правятся; нужна поправка ADR-0026 п. 3 фразой «`#1` — у первого вхождения имени на `#<цифры>`; повтором считается номер от 2» — doc-commit Оператора вместе с правкой вопроса 10. Вариант (б): формат не трогать, а потребители имени (`two_sided`, `mutation_run`, `record_location`) берут полное имя целиком из текста после `::`, номер повтора — только из `_Ids`; разбор `parse_test_id` остаётся неоднозначным для мандатов, набранных человеком.
2. Падение `afterAll` (требование 2в). Рекомендация: тесты набора без собственной ошибки (`pass` или `skip` от Vitest) и с `options.mode` не `skip`/`todo` записываются упавшими с хуком `afterAll`; тест с собственным честным провалом (например, `AssertionError`) остаётся провалом проверки, явный `it.skip`/`it.todo` — пропуском. Довод: иначе прогон с кодом 1 при одних зелёных записях даёт «неизвестно» без причины. Вариант — не трогать записи при `afterAll` (итог «неизвестно», безопасно, но без причины).
3. `aroundEach`/`aroundAll`: рекомендация — вне задачи; строка бэклога «запрет `aroundEach`/`aroundAll` в тексте планки (guard) либо распознавание по стеку», пока sled их не использует.

## Требования

1. **Флаг кэша Vitest 4.**
   - Запись таблицы: `VITEST_VERSION_FLAGS[4]` — `VitestFlags("--no-cache", True, "<проба 2.2 sled 7131152, 22.10; повторено 25.10 на 4.1.5>")`. Формы записи (`VitestFlags`, имена и порядок полей `cache_flag`, `require_assertions`, `probe`) и `vitest_flags` не меняются; строки документации `VitestFlags` и комментарий таблицы говорят: `cache_flag` — готовый аргумент пульта для кэша Vitest; каталога кэша пульт не заводит.
   - `_vitest_head`: после `--expect.requireAssertions` добавляется ровно `flags.cache_flag` одним аргументом, без `=<каталог>`; каталог `_pult_dir(profile, "cache") / "vitest"` не создаётся.
   - Неизменно: отказ для версии вне таблицы и для версии без `--expect.requireAssertions` (тексты прежние); проверка `command` против `VITEST_BASE_ARGV`; получение версии (`_vitest_version`); порядок остальных аргументов.
2. **Отчётчик `pult-vitest`** (`orchestrator/reporters/pult_vitest_reporter.js`). Форма JSON и имена полей прежние (`file`, `name`, `state`, `mode`, `fails`, `retry_count`, `error_name`, `timeout`, `hook`, `duration_ms`; у записи уровня файла — `file_level`, `error_name`, `error_message`); новых полей нет.
   - а) **Хук теста.** Упавшим считается `beforeEach`/`afterEach`, у которого в `task.result.hooks` значение `"fail"` (прежняя форма) или `"run"` (Vitest 4: хук начат и не завершён); `"pass"` — не упавший. Порядок поиска — `beforeEach`, затем `afterEach`.
   - б) **Хук набора и модуля.** Правило касается только теста без собственной ошибки (состояние Vitest `passed` или `skipped`), у которого `options.mode` не `skip` и не `todo`, и без упавшего хука своего уровня. Ищется первый вверх по цепочке предков до модуля включительно предок, у которого упал `beforeAll` или `afterAll` по правилу а) и `errors()` непуст; если он есть, тест записывается `state: "fail"`, `hook: "<имя хука>"`, `error_name` — класс первой ошибки этого предка (правило г), `timeout` — по сообщениям ошибок этого предка. Тест с собственной ошибкой (честный провал, ошибка тела) записывается по своим ошибкам, как без правила б); явный `it.skip`/`it.todo` остаётся пропуском.
   - в) **`afterAll`.** То же правило б) действует и для `afterAll` (тест без собственной ошибки, прошедший до упавшего `afterAll`, записывается упавшим с хуком `afterAll`) — если Оператор не решит иначе (вопрос 2).
   - г) **Класс ошибки.** `error_name` — имя `Имя` из собственного поля `constructor` вида `Function<Имя>`, если оно не `Error` и не `anonymous`; иначе — `name` ошибки; иначе `null`. Правило одно для записи теста, записи хука и записи уровня файла. Ошибка без поля `constructor` (прежняя форма) — по `name`, как сейчас.
   - д) **`.only`.** Тест, у которого среди собственных ошибок или ошибок первого вверх по цепочке до модуля набора-предка с такой ошибкой есть сообщение, начинающееся с `[Vitest] Unexpected .only modifier`, записывается `mode: "only"` и `state: "fail"`, `error_name` — класс этой ошибки, `hook: null`. Соседние тесты, пропущенные Vitest из-за `.only` (без ошибки и не под набором с ошибкой `.only`), — прежние `skip` с `mode: "skip"`.
   - е) **Ошибка модуля.** Запись уровня файла (`file_level: true`) — как сейчас при ошибке сбора; если у модуля упал `beforeAll`/`afterAll` верхнего уровня (правило а) и в модуле есть тесты, его ошибки идут в записи тестов по правилу б), записи уровня файла нет.
   - е2) **Поле `hook`** заполняется только у записи `state: "fail"`; у `pass`, `skip`, `todo` — `null` (например, `ctx.skip()` в `beforeEach` оставляет хуку `"run"`, а запись — `skip` без хука).
   - ж) Прочее неизменно: полное имя, путь от `cwd`, `retry_count`, `duration_ms`, `fails`, состояния `pass`/`skip`/`todo`, путь вывода (`PULT_VITEST_REPORT`, `outputFile`), отсутствие записи при отсутствии пути.
   - з) Строка заголовка файла говорит, что форма API сверена с Vitest 4.1.5 пробой 25.10, и перечисляет правила а)–е) коротко.

   Ожидаемые записи на Vitest 4.1.5 (по ним же строятся поддельные объекты тестов требования 5; прототипом 25.10 проверены все строки, кроме трёх строк сразу после «`afterEach` бросил», — они следуют из правил б) и е2) после независимой проверки ТЗ):

   | Случай | state | mode | hook | error_name |
   |---|---|---|---|---|
   | `expect(1).toBe(2)` | fail | run | null | AssertionError |
   | jest-dom `toHaveTextContent` не то | fail | run | null | JestExtendError |
   | jest-dom `toBeInTheDocument` на `{}` | fail | run | null | HtmlElementTypeError |
   | `getByText` нет элемента | fail | run | null | TestingLibraryElementError |
   | `null.x` | fail | run | null | TypeError |
   | `expect` в `beforeEach` | fail | run | beforeEach | AssertionError |
   | `afterEach` бросил | fail | run | afterEach | Error |
   | тело упало `expect`, затем бросил `afterEach` | fail | run | afterEach | AssertionError (разборщик — `ERROR` «падение хука afterEach») |
   | честный провал `expect` в наборе с упавшим `afterAll` | fail | run | null | AssertionError (провал проверки остаётся) |
   | `it.skip` в наборе с упавшим `beforeAll` | skip | skip | null | null |
   | `beforeAll` набора бросил `TypeError` | fail | run | beforeAll | TypeError |
   | `afterAll` набора бросил | fail | run | afterAll | Error |
   | `beforeAll` верхнего уровня файла | fail | run | beforeAll | TypeError (записи уровня файла нет) |
   | `beforeAll` внешнего набора, тест во вложенном | fail | run | beforeAll | TypeError |
   | хук с таймаутом | fail | run | beforeEach | Error, `timeout: true` |
   | `it.only` при `--allowOnly=false` | fail | only | null | Error |
   | тест в `describe.only` | fail | only | null | Error |
   | `ctx.skip()` в `beforeEach` | skip | run | null | null |
   | `it.fails`, тело упало | pass | run | null | null (`fails: true`) |
   | ошибка в теле `describe` (сбор) | запись уровня файла, `RangeError` | | | |

3. **Итоговая строка Vitest.** `_VITEST_COUNTS` в `orchestrator/agent_log.py` принимает счётчик `expected fail` в любой позиции ряда наравне с `failed|passed|skipped|todo`; формат детали `vitest_summaries` («<счётчики Tests> (<n>) in <секунды>s») прежний. Блок без «expected fail» разбирается как сейчас; строка «Tests» без строки «Test Files» перед ней по-прежнему итогом не является.
4. **Номер повтора** (по решению Оператора на вопрос 1; ниже — вариант (а)).
   - `test_id(component, path, name, n=None)`: если `n is None` и `name` кончается на `#<ASCII-цифры>` с непустой частью перед `#` (то же условие, что в `parse_test_id`), дописывается `#1`. В остальных случаях результат прежний, явный `n` — как сейчас.
   - Поведение `parse_test_id` не меняется (он может звать общий с `test_id` помощник условия); `test_id` и `parse_test_id` — взаимно обратны для любого имени: `parse_test_id(test_id(c, p, name))` возвращает `name` целиком.
   - `_Ids` не меняется (первое вхождение получает `#1` через `test_id`, повторы — `#2…`).
   - Повтором считается `n ≥ 2`: `not_passed_kind` (`orchestrator/advance_gates/acceptance.py`) и сбор `repeats` (`orchestrator/advance_gates/tests_writing.py`) проверяют `n is not None and n >= 2` — через один общий помощник в `orchestrator/advance_gates/acceptance.py`; `#1` повтором не является. Тексты находок прежние.
   - Строка документации `test_id` называет правило.
5. **Тесты.** Новый файл `tests/test_<id>_vitest4.py` в стиле pytest (ADR-0027): функции модуля, простой `assert`, варианты — `@pytest.mark.parametrize` литералами, подготовка — фикстурами самого файла или `tests/fixtures.py`, без утверждений в фикстурах. В документации каждой функции — «Ловит мутацию:».
   - Отчётчик исполняется настоящим `node`: тест копирует `orchestrator/reporters/pult_vitest_reporter.js` во временный каталог с расширением `.mjs` и пишет рядом модуль-обвязку `.mjs`, который импортирует эту копию (прямой импорт `.js` без `package.json` с `"type": "module"` падает на Node < 22.7; копия работает на Node ≥ 18), строит поддельные `TestModule`/`TestSuite`/`TestCase` формы Vitest 4.1.5 (`type`, `name`, `parent`, `module.moduleId`, `options.mode`/`fails`, `task.result.hooks`, `result()` с `state` и сериализованными `errors`, `diagnostic()`, `errors()` у набора и модуля, `children.allTests()`), вызывает `onInit`/`onTestRunEnd` и пишет отчёт по `PULT_VITEST_REPORT`. `node` ищется в `PATH`; нет `node` — тест падает с текстом причины (не пропуск). Каждый вызов `node` — с пределом времени.
   - а) Классы ошибок: варианты таблицы требования 2 (AssertionError без `constructor`; `name: "Error"` + `Function<JestExtendError>`; `name: "Error"` + `Function<HtmlElementTypeError>`; `name: "TestingLibraryElementError"` + `Function<Error>`; `TypeError` в обоих полях; `Function<anonymous>` + `name: "Error"`) → ожидаемое `error_name`. Ловит мутацию: класс только из `name`; класс только из `constructor`; обобщённый `Error` из `constructor` перекрывает `name`.
   - б) Хук теста: `{"beforeEach": "run"}` с `AssertionError` → `hook: "beforeEach"`; `{"beforeEach": "pass", "afterEach": "run"}` → `afterEach`; `{"beforeEach": "fail"}` (прежняя форма) → `beforeEach`; `{"beforeEach": "pass", "afterEach": "pass"}` при упавшем теле → `hook: null`. Ловит мутацию: признак падения только `"fail"`; `"pass"` считается падением.
   - в) Хук набора и модуля: набор с `{"beforeAll": "run"}` и ошибкой `TypeError`, тест `skipped` без ошибок → `fail`/`beforeAll`/`TypeError`; вложенный набор под таким набором — так же; модуль с `{"beforeAll": "run"}` и ошибкой — записи тестов с хуком и без записи уровня файла; модуль с ошибкой сбора без хуков — прежняя запись уровня файла; набор с `{"beforeAll": "run"}` без ошибок (поддельный случай: хук не завершён, ошибки нет) — тест остаётся `skip`; `it.skip` (`options.mode: "skip"`) под упавшим `beforeAll` — остаётся `skip`; `ctx.skip()` в `beforeEach` (`{"beforeEach": "run"}`, `skipped`) — `skip`, `hook: null`. Ловит мутацию: ошибки набора не читаются; хук модуля превращается в ошибку уровня файла; хук без ошибок засчитан падением; правило б) перекрывает явный пропуск; хук пишется в запись пропуска.
   - г) `afterAll` набора (по решению на вопрос 2): прошедший тест → `fail`/`afterAll`; тест с собственным `AssertionError` в том же наборе → `fail`, `hook: null`, `AssertionError` (через разборщик — `FAILED`); `it.skip` в том же наборе → `skip`. Ловит мутацию: `afterAll` не учтён — запись `pass`; правило б) перекрывает честный провал теста ошибкой хука; явный пропуск становится провалом.
   - д) `.only`: тест с собственной ошибкой `.only` → `mode: "only"`, `fail`; тест набора с ошибкой `.only` (сам `skipped`) → `mode: "only"`, `fail`; сосед, пропущенный из-за `.only`, → `skip`/`skip`; тест во вложенном наборе внутри набора с ошибкой `.only` (у вложенного набора ошибок нет) → `mode: "only"`, `fail`. Ловит мутацию: `mode` берётся только из `options.mode`; все пропущенные засчитаны `only`; смотрится только непосредственный родитель.
   - е) Неизменное: зелёный тест, `todo`, `skip`, `it.fails` с прошедшим и упавшим телом, `retry_count`, путь отчёта из `outputFile` без `PULT_VITEST_REPORT` — записи как до задачи (литералы ожидаемых записей в тесте). Ловит мутацию: правило хуков или `.only` задевает обычные состояния.
   - ж) Конец в конец с разборщиком: отчёт обвязки по таблице требования 2 → `orchestrator.reporters.outcome.parse_vitest(..., failure_errors=("AssertionError", "TestingLibraryElementError", "JestExtendError", "HtmlElementTypeError"))`: провал проверки (`FAILED`) — у AssertionError, JestExtendError, HtmlElementTypeError и TestingLibraryElementError без хука; `ERROR` — у хуков, `.only`, `TypeError`, таймаута. Ловит мутацию: класс ошибки или хук теряются между отчётчиком и разборщиком.
   - з) Флаг кэша: компонент `pult-vitest` с версией 4 (песочница и поддельный раннер — как в `tests/report_outcome_sandbox.py`) запускается с аргументом `--no-cache` сразу после `--expect.requireAssertions`; в argv нет аргумента, начинающегося с `--cacheDir`, и нет аргумента со значением-каталогом кэша; каталог кэша пульта компонента (`_pult_dir(profile, "cache") / "vitest"`) не создан. Версия вне таблицы и версия без `--expect.requireAssertions` — прежние отказы. Ловит мутацию: флаг склеивается с каталогом (`--no-cache=<путь>`); каталог кэша по-прежнему заводится; флаг пропал.
   - и) Итоговая строка: блок с `6 failed | 2 passed | 1 expected fail | 1 skipped | 1 todo (11)` и `Duration  1.94s (…)` → деталь `6 failed | 2 passed | 1 expected fail | 1 skipped | 1 todo (11) in 1.94s`; `expected fail` в начале и в конце ряда; прежний блок без него — прежняя деталь; «Tests … expected fail» без «Test Files» перед ней — не итог; блок со строкой `Tests  1 failed | 2 bogus (3)` — не итог. Ловит мутацию: «expected fail» не принят; принят любой текст между `|`.
   - к) Идентификатор: `test_id` для имён `x #12`, `a > b#3`, `t#0` → суффикс `#1`, и `parse_test_id` возвращает имя целиком; для `t`, `t[x#y]`, `t#²`, `t#`, `#12` (пустая часть перед `#`) — без суффикса; явный `n` — прежний литерал; `_Ids` на отчёте с двумя тестами `x #12` и тестом `x` даёт `…::x #12#1`, `…::x #12#2`, `…::x`. Гейты: `not_passed_kind` на прошедшей записи `…::x #12#1` — пусто, на `…::x #12#2` — «повтор имени теста в файле»; на прошедшей записи `…::x#2` — повтор, как сейчас; гейт планки (песочница по образцу `tests/outcome_gate_sandbox.py`) на файле с одиночным `x #12` — находки «повтор» нет, с двумя `x #12` — находка у `…::x #12#2`. Ловит мутацию: `#1` дописывается всем именам; условие `test_id` расходится с условием `parse_test_id` (например, без `isascii`); гейт считает повтором любой номер, в том числе `#1`.
6. **Существующие тесты** остаются зелёными. Правится только тест из перечня ниже и только по мандату. Покраснел любой другой тест — эскалация с его именем и причиной, а не правка.

### Перечень правок существующих тестов, требующих мандата Оператора

1. `tests/test_report_outcome_module.py`, `test_vitest_component_with_workdir_gets_exact_pult_argv`:
   - строку `assert args[len(head)].startswith("--cacheDir="), box.note(str(args))` заменить на `assert args[len(head)] == "--no-cache", box.note(str(args))`;
   - остальное (базовый argv, `--expect.requireAssertions`, число и вид хвостовых аргументов) не трогать.
   - Без правки требование 1 не исполнимо: тест закрепляет флаг, которого Vitest 4 не знает. Свойство теста («ровно базовый argv, флаги пульта, `report_args`») не ослабляется: проверка становится строже — равенство вместо префикса.

Других правок не нужно: прочие тесты берут из таблицы только версию с `require_assertions` (`tests/outcome_gate_sandbox.py`, `tests/test_outcome_gate_module.py`, `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`, `tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py`, `tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py`, `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py`) либо форму записи через `entry_values`/`flipped`/`cache_flag` (`tests/report_outcome_sandbox.py`), а разбор идентификаторов — на именах без `#<цифры>` в конце.

Зоны: orchestrator/project_profile.py, orchestrator/acceptance.py, orchestrator/reporters/pult_vitest_reporter.js, orchestrator/agent_log.py, orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/tests_writing.py, tests/

Ограничение зон по смыслу:
- в `orchestrator/project_profile.py` — запись `VITEST_VERSION_FLAGS[4]`, строки документации `VitestFlags` и комментарий таблицы, `test_id` (и помощник условия номера рядом с ним, общий для `test_id` и `parse_test_id`);
- в `orchestrator/acceptance.py` — только `_vitest_head` (флаг кэша без каталога);
- в `orchestrator/reporters/pult_vitest_reporter.js` — правила требования 2 и заголовок файла;
- в `orchestrator/agent_log.py` — только `_VITEST_COUNTS` и комментарий над ним;
- в `orchestrator/advance_gates/acceptance.py` — только условие повтора в `not_passed_kind` и общий помощник «номер повтора от 2» рядом с `record_location`;
- в `orchestrator/advance_gates/tests_writing.py` — только условие сбора `repeats` (вызов того же помощника);
- в `tests/` — новый файл и правка из перечня по мандату.

Только чтение: docs/backlog.md, docs/adr/0026-project-components-and-outcome-gates.md, docs/adr/0027-pytest-style-tests.md, .github/workflows/ci.yml, orchestrator/reporters/outcome.py, orchestrator/advance_gates/two_sided.py, orchestrator/advance_gates/mandate.py, orchestrator/fsm_merge_gate.py, orchestrator/mutation_run.py, orchestrator/plank_run.py, orchestrator/runner.py, orchestrator/watch.py, orchestrator/report.py, orchestrator/targets.py, scripts/guard.py, tests/report_outcome_sandbox.py, tests/outcome_gate_sandbox.py, tests/sandbox.py, tests/fixtures.py, tests/test_outcome_gate_module.py, tests/test_01m58fnwbv25ff26e7az9q9912_components.py, tests/test_project_components.py, tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py, tests/test_vitest_summary_pump.py, tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py, tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py, tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py, tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py, tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py, tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py, tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py.

Не входит:
- прочие файлы orchestrator/reporters/ вне названных в зонах и «Только чтение»;
- список `failure_errors` записи sled и сама запись (`targets.yaml`, этап 2.1) и перенос записей внешних проектов в локальный слой (отдельная задача по решению 25.10);
- правка ADR-0026 — doc-commit Оператора: вопрос 10 и пример записи (`failure_errors`); п. 3 — «`#1` — у первого вхождения имени на `#<цифры>`; повтором считается номер от 2»; п. 2 (строка 31) — «кэш результатов выключен (`--no-cache`); каталог кэша Vite — только из `vitest.config.js` проекта»;
- записи таблицы для Vitest 3 и других главных версий (не подтверждены пробой; отказ для них остаётся);
- распознавание `aroundEach`/`aroundAll` (вопрос 3);
- правка разборщика `orchestrator/reporters/outcome.py` и прочих мест гейтов: они уже переводят хук в ошибку и сверяют `error_name` с `failure_errors`;
- ошибки набора без упавшего хука (уборка, возвращённая `beforeAll`, и подобные): итог остаётся «неизвестно», что безопасно; разбор — строкой бэклога «отчётчик pult-vitest: ошибки набора без упавшего хука»;
- `docs/codebase-map.md`: карту перестраивает шаг мержа (`_map_step` в `orchestrator/fsm_merge_gate.py`);
- правка `tests/test_report_outcome_module.py::test_ac9_run_conditions_argv_env_cache_and_flags` (остаётся зелёным; пустую проверку пути кэша закрывает тест 5з);
- тесты без утверждений в sled (`stage5-sections.test.jsx`, `LifecycleGraph.test.jsx`) — задача фронтенда sled;
- прогон настоящего Vitest в тестах пульта (установки Vitest в CI нет).

Бюджет: $55.
