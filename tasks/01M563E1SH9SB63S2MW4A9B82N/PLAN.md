---
task: 01M563E1SH9SB63S2MW4A9B82N
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Одно наблюдение на задачи разных проектов; проект задачи в status

## Подход
Правка точечная, в четырёх модулях зоны; `store.py`, схема БД и выбор
наблюдения без флага не меняются.

- `orchestrator/artel.py`:
  - `_validated_observation_tasks(conn, raw)` — больше не принимает проект и
    не сверяет его; несуществующая задача по-прежнему отказывает через
    `store.get_task` до любой записи.
  - `observe register`: проект наблюдения — `--project P`, если хотя бы одна
    задача набора из `P` (иначе отказ до `register_observation`), либо проект
    первой перечисленной задачи (`raw_tasks.split(",")[0]`, не отсортированного
    набора). `add|remove` проект наблюдения не трогают.
  - `_launch_observation`: при `--observation` снята сверка
    `observer["target"] != target`, текст отказа чужой сессии — «принадлежит
    другой сессии». Без флага, когда `store.matching_observation` ничего не
    нашёл, новый помощник `_session_observation_with_task` (публичный
    `store.session_observations` по каждому проекту задач из
    `store.all_tasks`: активное наблюдение текущей сессии любого проекта с
    включённой задачей, самое свежее по `last_seen_at`/`created_at`; SQL вне
    `store.py` запрещён сторожем `tests/test_multitarget.py::SqlOnlyInStoreTest`,
    а `store.py` вне зон) — если нашёл, отказ советует
    `--observation <ID>`; иначе прежний текст отказа. Выбор наблюдения не
    меняется: это только текст отказа (требование 4а).
- `orchestrator/watch.py::_observation_events` — общий для цикла
  `watch --observation` и `observe events`, поэтому правило одно для обоих:
  алерт выводится, если `target` ∈ {id задач набора} ∪ {проекты задач набора
  (`store.task_target`)} ∪ {проект наблюдения} ∪ {`config.DEFAULT_TARGET`}.
- `orchestrator/catalog.py::cmd_status` — метка ` [<проект>]` сразу за id,
  только если `target or DEFAULT_TARGET` не артель.
- `orchestrator/report.py::_tile_html` — отдельный `<span class="tile-project">`
  с именем проекта сразу за `tile-id`, только у внешнего проекта; проект
  читается терпимо (`"target" in row.keys()`, работает и для `sqlite3.Row`, и
  для `dict` фикстур); стиль `.tile .tile-project` в CSS отчёта.

Бюджет SPEC ($30) не переоцениваю: объём совпал с прогнозом SPEC.

## Шаги
1. `artel.py`: register/add/remove, `_launch_observation`, совет 4а.
2. `watch.py`: фильтр алертов `_observation_events`.
3. `catalog.py`/`report.py`: метка проекта в `status` и на плитке.
4. Карта `docs/codebase-map.md` регенерирована; прогон долгоживущих тестов
   задачи, планки (`plank-run`, 2 passed), затронутых модулей и полного
   набора (`suite-run` №1: 5641 прошло, 1 новый красный —
   `test_multitarget.py::test_no_sql_outside_store` на первой версии
   помощника с SQL; исправлено, тест и файлы задачи зелёные отдельным
   прогоном; повтор `suite-run --failed` отказан замком машины — идёт гейт
   задачи 01M55VDVVDVWW2MTJ01F88N5FM).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 2 |
| 4 | 1 |
| 4а | 1 |
| 5 | 1, 2 (AC-5, AC-6 первая часть — тесты test_author, зелёные и до правки) |
| 6 | 3 |
| 7 | 3 |
| 8 | 4 (тесты test_author детерминированы по зерну, без сети) |

Собственных тестов в `tests/` не добавлял: все свойства требований 1–7 и 4а
покрыты долгоживущими файлами задачи
(`tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`,
`tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`) и планкой
`acceptance_tests/test_ac9_tile_without_target.py`.

## Влияние на систему
- Снимаются две сверки проекта (register/add/remove и `--observation`) — это
  требование SPEC, не ослабление гейта: проверки существования задачи,
  сессии, активности, членства в наборе и свежести связи остаются
  (`tests/test_launch_observation_refusals.py`,
  `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py` зелёные без правки).
- Фильтр алертов расширяется только добавочно: всё, что выводилось раньше
  (id задачи набора, проект наблюдения), выводится и сейчас; добавлены
  проекты задач набора и проект артели. Наблюдение артели видит то же, что
  раньше (артель = проект наблюдения).
- Строка `status` задачи артели и плитка задачи артели побайтно прежние;
  тесты `startswith(task_id)` не затронуты, так как метка идёт после id.
- Схема БД, `store.py`, `alerts.py`, `doctor/`, `cycle_hint.py`,
  автоподбор наблюдения не меняются.
- Откат — revert merge-коммита задачи.

## Риски
- `watch` теперь на каждой итерации делает по запросу `task_target` на задачу
  набора — наборы малые (единицы задач), нагрузка пренебрежима.

## Предложения системе
- Песочница роли не даёт `ls`/`cat` и отклоняет `$VAR`/подстановки в
  командах Bash — перечень файлов приходится собирать отдельными вызовами
  (класс «инструментарий шага натирает», отмечено и test_author в записке).
