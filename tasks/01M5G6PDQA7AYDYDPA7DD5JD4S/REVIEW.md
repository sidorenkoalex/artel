---
task: 01M5G6PDQA7AYDYDPA7DD5JD4S
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Неустойчивые тесты: зерно двустороннего наблюдения, select() и утечка дескрипторов БД, допуск времени kill

## Фаза A: план
- Таблица покрытия полна (требования 1–14 → шаги 1–5); блок «Итерация 2 (R1-F1)» в подходе описывает переопределение `close()`, обход переопределения во внутренних путях закрытия и новый тест — совпадает с инкрементальным diff (`orchestrator/store.py`, `tests/test_store_db_tracking.py`, `names = (`).
- «Влияние на систему» соответствует diff: код пульта — только `orchestrator/store.py`; «Риски» честно называют повторный вход в нереентерабельный `_TRACKED_LOCK` из чужого финализатора. Проверил, что в пульте такого пути нет: `grep "def __del__\|weakref.finalize" orchestrator/ scripts/` — только `store.py:297` (идёт мимо блокировки); `closing(...db())` и генераторов, держащих `db()` через `yield`, в `orchestrator/` нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Брошенные соединения закрывает просмотр учёта (без `gc`/`weakref`, эталон — замер); явно закрытые теперь выходят из учёта в `_AutoClosingConnection.close()` (`store.py:292-295`); чужепоточный `ProgrammingError` у `close()` поднимается до `pop` — открытое соединение остаётся в учёте, у `_close_abandoned` — глотается, соединение выходит из учёта |
| 2 | OK | `isinstance`, `backup`, `with conn:`, `test_store_db_connection_close.py` зелёные; повторный `close()` без ошибки (`test_closing_wrapper_does_not_grow_tracking`) |
| 3 | OK | описание называет цикл ссылок, учёт, просмотр и выход из учёта при явном `close()` |
| 4 | OK | долгоживущий `tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py` — 4 зелёных |
| 5–7 | OK | без изменений с итерации 1 (`tests/fd_wait.py`, `tests/test_fd_wait.py`, ANSWER-3) |
| 8–9 | OK | без изменений, кроме форматирования `names = (` |
| 10–13 | OK | без изменений с итерации 1; удаление `assertLessEqual(elapsed, limit, …)` — покрыто мандатом ANSWER-1 (исход рубежа в пакете) |
| 14 | OK | раздел «Доказательство неослабления» PLAN дополнен строкой `test_store_db_tracking.py` в трёхкратных прогонах |

## Замечания

Новых замечаний нет. Наблюдение без severity: при мутации учёт протекает между методами `ExplicitCloseLeavesTrackingTest` (второй метод стартовал с `before = 413`) — на зелёном коде неважно, тест сравнивает с собственным замером.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/store.py:292-295, 378-384 | явно закрытое соединение не выходило из `_TRACKED` | неограниченный рост учёта и O(n) проход на `db()` | принято: `close()` выводит соединение из учёта; `_close_abandoned`/`__del__` зовут `sqlite3.Connection.close` мимо блокировки; `tests/test_store_db_tracking.py` (оба метода) красен под мутацией «`close()` не выводит из учёта» — проверено исполнением |
| R1-F2 | accepted | tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py:710 | `names =(` | вкус | принято: `names = (` |

## Вердикт
approved — R1-F1 и R1-F2 закрыты, реестр закрыт целиком, blocker/major нет.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_store_db_tracking.py tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py tests/test_store_db_connection_close.py tests/test_fd_wait.py tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py::LocationLiteralsTest` — 14 passed, 3 subtests passed, 2,1 с (Python 3.13, Darwin).
- Временная мутация (подмена атрибута в процессе, файл не правился): `store._AutoClosingConnection.close = lambda self: sqlite3.Connection.close(self)` → `unittest` по `tests/test_store_db_tracking.py`: 2 failures (`413 not less than or equal to 0` для `closing`, `803 not less than or equal to 413` для явного `close()`) — заявка «Ловит мутацию» обоих методов подтверждена.
- `artel.py plank-run 01M5G6PDQA7AYDYDPA7DD5JD4S` — 23 passed за 153,9 с, код выхода pytest 0.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет, карта свежа (изменение откатил, `git status` чист).
- `grep` финализаторов/`closing(db())` в `orchestrator/` — пути повторного входа в `_TRACKED_LOCK` нет (основание принять риск из PLAN).

## Предложения системе
- `_TRACKED` — глобальный учёт процесса, песочница `TmpRootTest` его не сбрасывает: тесты учёта поэтому обязаны сравнивать с собственным замером, а не с нулём; стоит упомянуть в описании `TmpRootTest` (`tests/sandbox.py`), если учёт появится и у других ресурсов.
