---
task: 01M5G6PDQA7AYDYDPA7DD5JD4S
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Неустойчивые тесты: зерно двустороннего наблюдения, select() и утечка дескрипторов БД, допуск времени kill

## Подход
Четыре независимые части одним MR, как задал SPEC (бюджет не переоценивается).

1. **`orchestrator/store.py` — учёт выданных соединений.** `_TRACKED`
   (`id` → соединение, сильные ссылки) под `_TRACKED_LOCK`
   (`threading.Lock`). `db()` до открытия нового соединения зовёт
   `_close_abandoned()`: соединение, у которого `sys.getrefcount(conn) - 1`
   равно его эталону `conn.abandoned_refs`, закрывается и выходит из учёта;
   `sqlite3.ProgrammingError` (чужой поток) глотается, соединение всё равно
   выходит из учёта. Эталон снимается в `db()` замером сразу после постановки
   в учёт: `sys.getrefcount(conn) - 1` (минус локальная `conn`) — в тех же
   условиях, что замер просмотра (учёт + цикл + одна локальная `conn`),
   поэтому число внутренних ссылок цикла данной версии CPython входит в
   эталон само. Без `gc`/`weakref`, без числовой константы. Любая внешняя
   ссылка (переменная, курсор, `conn.execute`, `contextlib.closing`) даёт
   +1 — такое соединение не трогается. `db_tracked_count()` — размер учёта
   под той же блокировкой. Описание `_AutoClosingConnection` переписано:
   цикл ссылок, учёт и просмотр как механизм; `__del__` прежний.
2. **Ожидание без `select.select`.** Новый модуль `tests/fd_wait.py`:
   `wait_readable(fileobj, timeout) -> bool` — вне Darwin
   `selectors.DefaultSelector`, на Darwin прежний `select.select`
   (ANSWER-3, вариант A; платформа читается в момент вызова);
   `high_fd(test, fd)` — `fcntl.fcntl(fd, fcntl.F_DUPFD, 1100)`, исходный
   закрыт, мягкий `RLIMIT_NOFILE` при нужде поднят в пределах жёсткого и
   возвращён `addCleanup`. `test_ac9_timeout_kills_group_not_green` вне
   Darwin переносит читатель канала на ≥ 1100 и ждёт/читает по нему;
   `test_ac3_timeout_kills_group_and_failure_cleanup_is_bounded` ждёт
   `wait_readable(proc.stdout, 10)`. Пределы 30 с (`CHILD_GUARD_SEC`) и 10 с
   прежние. Отдельный тест — `tests/test_fd_wait.py` (оба пути, платформа
   подменена на время метода). `tests/sandbox.py` не тронут.
3. **Зерно двустороннего наблюдения.** Модульная `location_literals(seed)`
   строит все литералы фикстуры (имена, значения, тексты файлов); сдвиг
   голого `assert` — `BARE_SHIFT = 4000`, вне сдвига `new` (1…3999).
   Помощник `check_relative_location(seed, base_sha, branch)` несёт
   `two_sided.run` и все четыре утверждения дословно; подготовка (запись
   файлов, пять `self.git`, `self.checkout`) — в теле
   `test_ac1_outcome_carries_relative_assertion_location` и нового
   `test_ac1_relative_location_on_colliding_seed` (зерно 189949286).
   Тест генерации — `LocationLiteralsTest::test_literals_never_collide`.
4. **`SilentHostingTest` без часов.** Удалено только
   `assertLessEqual(elapsed, limit, …)` (мандат ANSWER-1). Сквозной метод:
   `GH_TIMEOUT_SEC = 2`, подставной `gh` спит `GH_SILENT_SEC = 2 × 2 + 15`
   и пишет `gh_slept`; `Silence.limit = SILENCE_LIMIT_SEC = 75`;
   `Silence.expired` ставится в `serve`, только когда
   `release.wait(limit)` вернул ложь. Утверждения: прежние + флаг не поднят,
   `silence.hits == 1`, один `gh pr close` (`pr_closes`), нет `gh_slept`.
   Новый метод перехвата `test_ac6_limit_arguments_follow_gh_timeout`:
   случайный предел из 7…300 (≠ исходного 60), перехват `subprocess.run`
   (`gh` → `TimeoutExpired`, пуш удаления → ответ curl 28), сверка пар `-c`,
   `timeout=` и «не ответил за N с». `serve` вне правила молчания не менялся.

## Шаги
1. `orchestrator/store.py`: учёт, просмотр, `db_tracked_count`, описание.
2. `tests/fd_wait.py`, `tests/test_fd_wait.py`, правка report_outcome и
   timeout_integrations.
3. `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py`.
4. `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`.
5. `python3 scripts/codebase_map.py`; планка; трёхкратные прогоны; замеры.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 (долгоживущий `tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py`) |
| 5 | 2 |
| 6 | 2 |
| 7 | 2 |
| 8 | 3 |
| 9 | 3 |
| 10 | 4 |
| 11 | 4 |
| 12 | 4 |
| 13 | 4 |
| 14 | 5 (раздел «Доказательство неослабления») |

## Доказательство неослабления

Учёт гейтом (`guard.test_assertions` + `guard.changed_test_assertions`
против базы ветки), по методам — база → голова:

- `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py::OutcomeLocationTest::test_ac1_outcome_carries_relative_assertion_location`:
  9 → 9, `LOST` нет. Прежние утверждения — `self.assertEqual(outcome.refusals, [...], context)`,
  `self.assertEqual(outcome.results, {...}, context)`,
  `self.assertTrue(location_found(extra, rel, line, text, foreign), note(...))`,
  `self.assertEqual(absolute, [], note(...))` — дословно в помощнике
  `check_relative_location` (первый уровень); пять `self.git` (`assertEqual(res.returncode, 0, …)`
  в `RealGitSandbox.git`) — в теле метода. Новый `test_ac1_relative_location_on_colliding_seed`: 0 → 9.
- `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac9_timeout_kills_group_not_green`:
  3 → 3, `LOST` нет. `self.assertFalse(run.green, …)`, `self.assertTrue(case["fake"].runs(), …)`,
  `self.assertTrue(gone, …)` — на прежних местах; заменены только
  `select.select([reader], [], [], CHILD_GUARD_SEC)` → `wait_readable(reader, CHILD_GUARD_SEC)` и перенос `reader`.
- `tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py::SeparateSuiteScenarios::test_ac3_timeout_kills_group_and_failure_cleanup_is_bounded`:
  21 → 21, `LOST` нет. `self.assertTrue(ready, "ребёнок не подал сигнал готовности")` и прочие — на месте;
  `ready, _, _ = select.select([proc.stdout], [], [], 10)` → `ready = wait_readable(proc.stdout, 10)`.
- `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py::SilentHostingTest::test_ac6_silent_gh_and_origin_bounded_and_noted`:
  7 → 10, `LOST` ровно одна — `self.assertLessEqual(elapsed, limit, self.why(…))` (мандат ANSWER-1).
  `self.assertEqual(self.state(self.ext), "killed", …)`, `self.assertGreaterEqual(self.silence.hits, 1, …)`,
  `self.assertIn(SILENT, self.left_reason(self.ext, PR_PREFIX))`,
  `self.assertIn(SILENT, self.left_reason(self.ext, BRANCH_PREFIX))` — дословно в методе.
  Добавлены: `assertFalse(self.silence.expired, …)`, `assertEqual(self.silence.hits, 1, …)`,
  `assertEqual(len(self.pr_closes(self.branch)), 1, …)`, отсутствие `gh_slept`.
  Новый `test_ac6_limit_arguments_follow_gh_timeout`: 0 → 9.

Таблица мутаций строки «Ловит мутацию» (`SilentHostingTest`, без урезания
срока молчания; «до правки» — тест базы ветки, «после правки» — тест головы,
мутация — текстовая правка `orchestrator/cleanup.py` во временной копии):

| Мутация | До правки | После правки |
|---|---|---|
| пуш без пар `-c http.lowSpeedLimit=1 -c http.lowSpeedTime=…` | красный: `test_ac6_silent…` (elapsed > 14 с), 23,8 с | красный: `test_ac6_silent…` (флаг `expired`) и `test_ac6_limit_arguments…` (нет пар), 82,4 с |
| предел пуша числом 60 вместо `config.GH_TIMEOUT_SEC` | красный: `test_ac6_silent…` (elapsed > 14 с), 23,7 с | красный: `test_ac6_limit_arguments…` (`http.lowSpeedTime=60` ≠ случайного), 70,0 с |
| срабатывание предела как «отказ» (`if False:` в `_left_reason`) | красный: `test_ac6_silent…` (заметка без «не ответил»), 9,3 с | красный: оба метода (заметки без «не ответил»), 11,7 с |

Планка с урезанием срока молчания до 8 с (`test_kill_silent.py`, 12 тестов,
в том числе мутации `gh_timeout_number`, `note_limit_number`, `push_twice`,
`gh_twice`) — зелёная.

Прогон каждого изменённого файла трижды подряд (`python3 -m pytest <файл>
-p no:cacheprovider -p timeout -o timeout=120`), все три прогона зелёные:

| Файл | Прогон 1 | Прогон 2 | Прогон 3 |
|---|---|---|---|
| test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py | 23 passed, 90 с | 23 passed, 90 с | 23 passed, 90 с |
| test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py | 26 passed, 30 с | 26 passed, 30 с | 26 passed, 29 с |
| test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py | 3 passed, 10 с | 3 passed, 10 с | 3 passed, 10 с |
| test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py | 12 passed, 34 с | 12 passed, 34 с | 12 passed, 34 с |
| test_fd_wait.py | 2 passed | 2 passed | 2 passed |
| test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py | 4 passed | 4 passed | 4 passed |
| test_store_db_connection_close.py | 5 passed | 5 passed | 5 passed |

Замер дескрипторов процесса pytest после файла report_outcome при выключенной сборке мусора (`gc.disable()` плагином до сбора, `/dev/fd` в `pytest_sessionfinish`): до починки 4 на старте → 310 в конце; после починки 4 на старте → 16 в конце.

## Влияние на систему
- `store.db()` зовут почти все команды пульта. Поведение для вызывающих
  прежнее: тот же класс `_AutoClosingConnection` (подкласс
  `sqlite3.Connection`, `isinstance`, `backup`, `with conn:` работают),
  WAL, схема, `row_factory`, `__del__`. Новое — закрытие брошенных
  соединений на следующем `db()`; соединение с любой живой ссылкой не
  закрывается (обоснование — SPEC, требование 1; держит долгоживущий
  `tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py`). Цена — проход
  по учёту на каждый `db()` (размер учёта — число живых соединений).
- Тесты: утверждения не ослаблены, кроме одного по мандату ANSWER-1;
  `tests/sandbox.py`, `tests/test_store_db_connection_close.py`,
  `conftest.py`, код пульта вне `store.py` не тронуты.
- Откат — revert коммита ветки; схема БД и форматы не меняются.

## Риски
- Код, держащий соединение только через объект, ссылка которого не
  учитывается счётчиком (C-уровневые заимствованные ссылки), мог бы
  потерять соединение; в пульте таких мест не найдено — внешние держатели
  (переменная, курсор, связанный метод, `closing`) покрыты тестом.
- Сквозной `SilentHostingTest` без урезания срока не ловит «предел пуша
  числом 60» флагом (60 с < 75 с срока молчания) — эту мутацию держит
  сценарий перехвата; описание метода говорит именно так.

## Предложения системе
- Сторож `conftest.py` отвергает `pytest.main([...файл])` внутри процесса как «полный прогон» — замер в одном процессе пришлось делать плагином через `python -m pytest`; полезна команда пульта «прогон файла с замером ресурсов».
- В шаге роли не работают `ls`/`cat`/`sleep`/`sed -i` и составные команды (нет в PATH либо требуют одобрения) — разведка только `find`/`grep`/`git`/`python3`.
