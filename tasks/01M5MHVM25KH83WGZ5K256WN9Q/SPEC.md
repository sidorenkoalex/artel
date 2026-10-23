---
task: 01M5MHVM25KH83WGZ5K256WN9Q
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/watch.py, orchestrator/artel.py, docs/codebase-map.md, tests/
budget_usd: 25
---

# SPEC: Свежесть связи наблюдения — одна функция вместо трёх копий

## Контекст
Находка ревизии кода 22.10 CR-2026-10-22-15 (`docs/audits/code-revision-2026-10-22.md`).
Проверка «возраст связи наблюдения против `config.OBSERVATION_STALE_SECONDS`»
(порог 90 с) написана трижды с одинаковым ядром
`(datetime.now(timezone.utc) - datetime.fromisoformat(row["last_seen_at"])).total_seconds()`:
в `orchestrator/artel.py::_launch_observation` (блок свежести после выбора
наблюдателя, сейчас строки ~950–958), в `orchestrator/artel.py::_observation_fresh`
(~1066–1071) и в `orchestrator/watch.py::observation_process_state`, ветка
`row["pid"] is None` (~320–326). Семантика порога у всех трёх одна: свежая при
`age <= порог`. Задача — свести три копии к двум функциям модуля `watch` без
смены поведения, кроме намеренного устранения падения на пустой строке
`last_seen_at` в `artel.py`.

## Требования

1. В `orchestrator/watch.py` появляются две функции:
   - `observation_age(row) -> float | None` — возраст связи в секундах от
     `row["last_seen_at"]` до текущего времени UTC; `None`, если `last_seen_at`
     пусто (`None` или пустая строка);
   - `observation_link_fresh(row) -> bool` — `observation_age(row)` не `None`
     и не больше `config.OBSERVATION_STALE_SECONDS`.
   Текущее время берётся одним вызовом `datetime.now(timezone.utc)` внутри
   `observation_age` через имя `datetime` модуля `watch`, чтобы тест мог
   зафиксировать его подменой `mock.patch.object(watch, "datetime", <подкласс datetime>)`.
2. Три копии заменяются вызовами этих функций с сохранением поведения:
   - в функции выбора наблюдения при запуске (`artel.py::_launch_observation`) —
     `age = watch.observation_age(observer)`; `None` → прежний отказ «связи с
     watch ещё нет …»; `age > config.OBSERVATION_STALE_SECONDS` → прежний отказ
     с тем же текстом и `age:.0f`; решение принимается по уже полученному `age`,
     второй раз текущее время не берётся;
   - `artel.py::_observation_fresh` — проверка `state != "active"` остаётся,
     свежесть — `watch.observation_link_fresh(row)`;
   - `watch.py::observation_process_state` — `"unstarted"`, `"fresh"`,
     `"stale"` при тех же условиях, что сейчас.
   Пустая строка в `last_seen_at` в `artel.py` обрабатывается как `None`: при
   запуске — отказ «связи с watch ещё нет …», в `_observation_fresh` — `False`;
   прежнее падение `datetime.fromisoformat("")` с `ValueError` устраняется
   намеренно. Остальные тексты отказов, коды выхода и порядок проверок не
   меняются.
3. После правки выражение `datetime.fromisoformat(... "last_seen_at" ...)`
   встречается в `orchestrator/` только внутри `watch.observation_age`.
4. Новый файл теста в `tests/`:
   (а) `observation_age` — `None` при `last_seen_at` `None` и `""`; для
   значения «сейчас минус 30 с» в формате `isoformat()` — около 30 (допуск 2 с);
   (б) `observation_link_fresh` — истина при возрасте ровно
   `OBSERVATION_STALE_SECONDS` (текущее время зафиксировано подменой), ложь
   при пороге плюс 1 с и при пустом `last_seen_at`;
   (в) разбор AST всех модулей `orchestrator/`: вызовы `fromisoformat`
   (атрибут `fromisoformat` у любого имени), в поддереве аргумента которых есть
   строковая константа `"last_seen_at"`, — ровно один, внутри функции
   `observation_age` модуля `watch`; проверка (в) — линтер требования 3, в её
   докстринге — «Ловит мутацию: в `artel.py` или `watch.py` возвращена своя
   копия разбора `last_seen_at`».
   На текущем коде (а) и (б) красные (функций нет), (в) красный (три места).
5. Формат хранения времени в таблице `observations` не меняется, данные не
   мигрируются. Существующие тесты не правятся (в том числе
   `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`,
   `tests/test_observation_edges.py`,
   `tests/test_observation_acceptance_return.py::test_doctor_warns_for_dead_pid_and_stale_link`,
   `tests/test_cycle_hint.py`).

## Критерии приёмки

AC-1. `watch.observation_age(row)` возвращает `None` при `row["last_seen_at"]`,
равном `None`, и при `""`; при значении `(datetime.now(timezone.utc) - 30 с).isoformat()`
возвращает число в пределах 30 ± 2.

AC-2. `watch.observation_link_fresh(row)` при текущем времени, зафиксированном
подменой `mock.patch.object(watch, "datetime", <подкласс datetime>)`, возвращает
`True` при возрасте связи ровно `config.OBSERVATION_STALE_SECONDS`, `False` при
возрасте `OBSERVATION_STALE_SECONDS + 1` с и `False` при пустом `last_seen_at`
(`None` и `""`).

AC-3. Разбор AST всех модулей `orchestrator/` находит ровно один вызов
`<имя>.fromisoformat(...)`, в поддереве аргумента которого есть строковая
константа `"last_seen_at"`, и этот вызов лежит внутри функции `observation_age`
модуля `orchestrator/watch.py`. Докстринг проверки содержит «Ловит мутацию: в
`artel.py` или `watch.py` возвращена своя копия разбора `last_seen_at`».

AC-4. Выбор наблюдения при запуске (`artel.py::_launch_observation`) с
наблюдателем, у которого `last_seen_at` равно `None` или `""`, отказывает
прежним текстом «связи с watch ещё нет …» (пустая строка не роняет
`ValueError`); с возрастом связи больше порога — прежним отказом «связь
устарела на {age:.0f} с (порог … с)»; с возрастом ровно порог — отказа по
свежести нет. Текущее время в этом блоке берётся один раз (через
`watch.observation_age`).

AC-5. `artel.py::_observation_fresh(row)` возвращает `False` при
`state != "active"`, при `last_seen_at` `None` и `""` (без `ValueError`), и
`watch.observation_link_fresh(row)` в остальных случаях.

AC-6. `watch.observation_process_state(row)` при `row["pid"] is None` возвращает
`"unstarted"` при пустом `last_seen_at`, `"fresh"` при возрасте не больше
порога и `"stale"` при большем.

AC-7. Формат записи `last_seen_at`, `started_at`, `created_at` в таблице
`observations` и код записи в `orchestrator/store.py` не меняются; файлы
`tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`, `tests/test_observation_edges.py`,
`tests/test_observation_acceptance_return.py`, `tests/test_cycle_hint.py` на
ветке совпадают с main.

## Не входит

- Единый формат времени в таблице `observations` и миграция строк — риск для
  работающих дозоров (`started_at` сравнивается на равенство в
  `store.claim_observation`/`store.touch_claimed_observation`), отдельное решение.
- Сортировка списка наблюдений в `artel.py` (`rows.sort` по `last_seen_at`).
- Правки `orchestrator/artel.py` вне блока свежести `_launch_observation` и
  `_observation_fresh`; правки `orchestrator/watch.py` вне новых функций и
  ветки `pid is None` в `observation_process_state`.
- Правки `orchestrator/store.py` и `orchestrator/config.py` (только чтение).
- Зелёный полный набор `tests/` и неизменность существующих тестов как
  проверка набора — её держит пульт.

Только чтение: orchestrator/store.py, orchestrator/config.py, orchestrator/ (каталог обхода AST в тесте; меняются только файлы зон).

## Материалы

- `docs/audits/code-revision-2026-10-22.md`, находка CR-2026-10-22-15.
- `orchestrator/config.py` — `OBSERVATION_STALE_SECONDS`.
