---
task: 01M5MHVM25KH83WGZ5K256WN9Q
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Свежесть связи наблюдения — одна функция вместо трёх копий

# Свежесть связи наблюдения — одна функция вместо трёх копий

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-15 (`docs/audits/code-revision-2026-10-22.md`, раздел «Находки»). Сверено с `origin/main` edbbc059 (код `orchestrator/` совпадает с пином 870aa7e9); номера строк `orchestrator/artel.py` сдвинулись против отчёта, места названы функциями.

Проверка «возраст связи наблюдения против `config.OBSERVATION_STALE_SECONDS`» (порог 90 с, `config.py:82–83`) написана трижды с одинаковым ядром `age = (datetime.now(timezone.utc) - datetime.fromisoformat(row["last_seen_at"])).total_seconds()`:

1. `orchestrator/artel.py`, функция выбора наблюдения при запуске (`_launch_observation`, блок после `chosen = observer["id"]`): `last_seen_at is None` → отказ «связи с watch ещё нет»; `age > порог` → отказ «связь устарела на {age:.0f} с (порог … с)»; ровно порог — свежая.
2. `orchestrator/artel.py`, `_observation_fresh(row)`: `state != "active"` или `last_seen_at is None` → `False`; иначе `age <= порог`.
3. `orchestrator/watch.py`, `observation_process_state(row)`, ветка `row["pid"] is None`: пустой `last_seen_at` (проверка `not`) → `"unstarted"`; иначе `"fresh"` при `age <= порог`, `"stale"` при большем.

Семантика порога у всех трёх одна: свежая при `age <= порог`. `orchestrator/artel.py` уже обращается к модулю `watch` (`watch.observation_process_state`, `watch.cmd_watch`).

Формат времени: `last_seen_at` и `started_at` пишутся `datetime.now(timezone.utc).isoformat()` (`store.touch_observation`, `store.touch_claimed_observation`, `watch.py` при старте), `created_at` — журнальным `store.now()` (`%Y-%m-%d %H:%M:%SZ`). В живой БД (24 строки) каждая колонка однородна; колонки между собой нигде не сравниваются, сортировка по `last_seen_at` верна. `started_at` сравнивается на равенство при захвате и освобождении наблюдения (`store.claim_observation`, `store.touch_claimed_observation`), поэтому смена его формата у работающих дозоров меняет ключ.

Тесты свежести и выбора наблюдения пишут `last_seen_at` через `isoformat()` и не правятся: `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py` (ac2, ac4, ac5, ac6, ac8), `tests/test_observation_edges.py`, `tests/test_observation_acceptance_return.py::test_doctor_warns_for_dead_pid_and_stale_link`, `tests/test_cycle_hint.py`.

## Требования

1. В `orchestrator/watch.py` появляются две функции:
   - `observation_age(row) -> float | None` — возраст связи в секундах от `row["last_seen_at"]` до текущего времени UTC; `None`, если `last_seen_at` пусто (`None` или пустая строка);
   - `observation_link_fresh(row) -> bool` — `observation_age(row)` не `None` и не больше `config.OBSERVATION_STALE_SECONDS`.
   Текущее время берётся одним вызовом `datetime.now(timezone.utc)` внутри `observation_age` через имя `datetime` модуля `watch`, чтобы тест мог зафиксировать его подменой `mock.patch.object(watch, "datetime", <подкласс datetime>)`.
2. Три копии таблицы заменяются вызовами этих функций с сохранением поведения:
   - в функции выбора наблюдения `artel.py` — `age = watch.observation_age(observer)`; `None` → прежний отказ «связи с watch ещё нет …»; не свежая → прежний отказ с тем же текстом и `age:.0f`;
   - `_observation_fresh` — проверка `state` остаётся, свежесть — `watch.observation_link_fresh(row)`;
   - `observation_process_state` — `"unstarted"`, `"fresh"`, `"stale"` при тех же условиях.
   В функции выбора наблюдения решение принимается по уже полученному `age`: `age > config.OBSERVATION_STALE_SECONDS` → прежний отказ; второй раз текущее время не берётся. Пустая строка в `last_seen_at` в `artel.py` обрабатывается как `None` (при запуске — отказ «связи с watch ещё нет …», в `_observation_fresh` — `False`); прежнее падение `fromisoformat("")` с `ValueError` устраняется намеренно. Остальные тексты отказов, коды выхода и порядок проверок не меняются.
3. После правки выражение `datetime.fromisoformat(... "last_seen_at" ...)` встречается в `orchestrator/` только внутри `watch.observation_age`.
4. Тест (новый файл в `tests/`): (а) `observation_age` — `None` при `last_seen_at` `None` и `""`; для значения «сейчас минус 30 с» в формате `isoformat()` — около 30 (допуск 2 с); (б) `observation_link_fresh` — истина при возрасте ровно `OBSERVATION_STALE_SECONDS` (текущее время зафиксировано подменой), ложь при пороге плюс 1 с и при пустом `last_seen_at`; (в) разбор AST всех модулей `orchestrator/`: вызовы `fromisoformat` (атрибут `fromisoformat` у любого имени), в поддереве аргумента которых есть строковая константа `"last_seen_at"`, — ровно один, внутри функции `observation_age` модуля `watch`; проверка (в) — линтер требования 3, в её докстринге — «Ловит мутацию: в `artel.py` или `watch.py` возвращена своя копия разбора `last_seen_at`». На текущем коде (а) и (б) красные (функций нет), (в) красный (три места).
5. Формат хранения времени в таблице `observations` не меняется, данные не мигрируются. Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/watch.py, orchestrator/artel.py, docs/codebase-map.md, tests/

Ограничение зон по смыслу: в `orchestrator/artel.py` — только функция выбора наблюдения при запуске (блок свежести) и `_observation_fresh`; в `orchestrator/watch.py` — новые функции и ветка `pid is None` в `observation_process_state`.

Только чтение: orchestrator/store.py (запись `last_seen_at`, `started_at` — не меняется), orchestrator/config.py (`OBSERVATION_STALE_SECONDS`), orchestrator/ (каталог обхода AST в тесте; меняются только файлы Зон).

Не входит: единый формат времени в таблице `observations` и миграция строк — риск для работающих дозоров (`started_at` сравнивается на равенство), отдельное решение; сортировка списка наблюдений в `artel.py` (`rows.sort` по `last_seen_at`).

Бюджет: $25.
