---
task: 01M5G6PDQA7AYDYDPA7DD5JD4S
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Неустойчивые тесты: зерно двустороннего наблюдения, select() и утечка дескрипторов БД, допуск времени kill

## Фаза A: план
- Таблица покрытия полна (требования 1–14 → шаги 1–5), шаги размера MR, подход согласован с SPEC и ANSWER-1…3.
- «Влияние на систему» соответствует diff: код пульта тронут только в `orchestrator/store.py`; `tests/sandbox.py`, `tests/test_store_db_connection_close.py`, `conftest.py` не тронуты; карта `docs/codebase-map.md` свежа (проверено перегенерацией). Откат — revert. Но раздел «Влияние» и «Риски» не называют рост учёта на явно закрытых соединениях (см. R1-F1).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | реализовано не полностью | Брошенные соединения закрываются (AC-1 зелёный, без `gc`/`weakref`, эталон — замер). Но явно закрытые соединения никогда не выходят из учёта — R1-F1 |
| 2 | OK | `isinstance`, `backup`, `with conn:`, `test_store_db_connection_close.py` зелёные |
| 3 | OK | описание `_AutoClosingConnection` называет цикл ссылок, учёт и `_close_abandoned` |
| 4 | OK | `tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py` — 4 теста зелёные |
| 5 | OK | `tests/fd_wait.py::wait_readable`, оба файла импортируют; пределы 30 с / 10 с; Darwin — `select.select` по ANSWER-3 |
| 6 | OK | `high_fd`: `F_DUPFD 1100`, исходный закрыт, rlimit возвращается `addCleanup` (порядок LIFO: сначала закрытие дескриптора, затем возврат предела) |
| 7 | OK | `tests/test_fd_wait.py`, оба пути с подменой `sys.platform` |
| 8 | OK | `location_literals(seed)`, `BARE_SHIFT = 4000`; помощник `check_relative_location(seed, base_sha, branch)`; подготовка с пятью `self.git` в теле обоих методов |
| 9 | OK | `LocationLiteralsTest::test_literals_never_collide`, `test_ac1_relative_location_on_colliding_seed` |
| 10 | OK | `test_ac6_limit_arguments_follow_gh_timeout`: случайный предел 7…300 ≠ исходного, перехват `subprocess.run`, пары `-c`, `timeout=`, «за N с» |
| 11 | OK | `GH_SILENT_SEC = 2*2+15`, `SILENCE_LIMIT_SEC = 75` ∈ [60,120), флаг `expired` ставится только при `release.wait` → False, событие `gh_slept` |
| 12 | OK | `silence.hits == 1` дополнительно к прежнему `>= 1`, один `gh pr close` по журналу; `serve` вне правила молчания не менялся |
| 13 | OK | удалено только `assertLessEqual(elapsed, limit, …)` (мандат ANSWER-1, исход рубежа — «покрыто мандатом»); описание переформулировано, три мутации сохранены |
| 14 | OK | раздел «Доказательство неослабления» PLAN: утверждения по местам, таблица мутаций, трёхкратные прогоны, замер дескрипторов 310 → 16 |

## Замечания

- major — `orchestrator/store.py:351-370` (`_close_abandoned`, `db`) — соединение, которое вызывающий код закрыл явно (`conn.close()`, `contextlib.closing(store.db())`), навсегда остаётся в `_TRACKED`: `close()` разрывает внутренний цикл (кэш выражений), число ссылок падает НИЖЕ эталона (замер на 3.13: эталон 4, после `close()` — 2), условие `!= conn.abandoned_refs` не срабатывает никогда. Проверено исполнением: 500 × `x = store.db(); x.close()` → `db_tracked_count()` 1 → 501; ещё 500 × `with closing(store.db())` → 1001. Сценарий последствий: места пульта, закрывающие соединение явно (`orchestrator/suite_lock.py:280-287`, `orchestrator/knowledge_cards.py:821-826`), и десятки тестов с `addCleanup(conn.close)` (`tests/test_acceptance.py`, `tests/test_canary_sets.py`, `tests/test_steps_task_id_index.py`, `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py` и др.) монотонно растят учёт в долгоживущем процессе (пульт, исполнитель xdist): объекты `Connection` не освобождаются никогда (раньше их освобождала сборка циклов), а каждый `db()` проходит весь учёт `sys.getrefcount` — O(n) на вызов, O(n²) на процесс. Это та же утечка, которую задача чинит, только сменившая ресурс (память и время вместо дескрипторов), и `db_tracked_count()` перестаёт быть «числом соединений в учёте» в смысле живых. Предложение: выводить соединение из учёта при явном `close()` (переопределить `close` в `_AutoClosingConnection`: под `_TRACKED_LOCK` `_TRACKED.pop(id(self), None)`, затем `super().close()` — аккуратно с повторным входом из `_close_abandoned`, где блокировка уже взята) либо в `_close_abandoned` выводить из учёта и соединения с числом ссылок ниже эталона, не трогая те, что выше. Долгоживущий тест в `tests/` (в новом файле разработчика, долгоживущий файл задачи залочен): N × явный `close()` (и `closing`) → `db_tracked_count()` не растёт; заявка «Ловит мутацию: закрытое соединение не выходит из учёта — учёт растёт на N».
- minor — `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py:710` — `names =(` без пробела после `=`; при правке R1-F1 заодно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/store.py:351-370 | явно закрытое соединение (`close()`/`closing`) не выходит из `_TRACKED`: после `close()` число ссылок ниже эталона, `!=` не срабатывает | неограниченный рост учёта и памяти в долгоживущем процессе, O(n) проход на каждый `db()`; 500 закрытий → учёт 501 | выводить из учёта при явном `close()` (или при числе ссылок ниже эталона) + долгоживущий тест в `tests/` с заявкой «Ловит мутацию» |
| R1-F2 | open | tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py:710 | `names =(` — форматирование | вкус | `names = (` |

## Вердикт
changes_requested — исправить R1-F1 (выход явно закрытого соединения из учёта + тест в `tests/`); R1-F2 — попутно. Остальные части (fd_wait, зерно, `SilentHostingTest` без часов) замечаний не имеют.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py tests/test_fd_wait.py tests/test_store_db_connection_close.py tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py …report_outcome.py::VitestReporterTest::test_ac9_timeout_kills_group_not_green …project_kill_cleanup.py::SilentHostingTest …two_sided_observation.py::LocationLiteralsTest …two_sided_observation.py::OutcomeLocationTest` — 20 passed, 27 subtests passed, 27,7 с (Python 3.13.12, Darwin).
- `artel.py plank-run 01M5G6PDQA7AYDYDPA7DD5JD4S` — 23 passed за 138 с, код выхода 0.
- Временная мутация `BARE_SHIFT = 7` (подменой атрибута модуля, файл не правился): `test_ac1_relative_location_on_colliding_seed` красный (лишний отказ `test_bare: старая версия на ветке: зелёная`), `test_literals_never_collide` красный (8 зёрен, в том числе 12, 9694, 11783, 189949286) — заявки обоих тестов подтверждены.
- Скрипт на `store.db()` во временном каталоге: эталон 4, после `close()` число ссылок 2; 500 × `db().close()` → `db_tracked_count()` 501; ещё 500 × `with closing(db())` → 1001 (основание R1-F1).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождение только в `built_at_sha`, карта свежа (изменение откатил).

## Предложения системе
- Класс «учёт ресурса без пути выхода при штатном освобождении»: SPEC требования 1 описал выход из учёта только для брошенных и чужепоточных соединений, про явно закрытые — лишь «повторное `close()` без ошибки»; аналитику (skills analyst) стоит спрашивать «как запись покидает учёт в каждом исходе жизни объекта».
