---
task: 01M563E1SH9SB63S2MW4A9B82N
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Одно наблюдение на задачи разных проектов; проект задачи в status

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–8 и 4а сопоставлены шагам 1–4.
- Шаги размера MR: по одному модулю или группе правок.
- Подход не конфликтует с архитектурой. SQL вне `store.py` не появился:
  помощник `_session_observation_with_task` собран на публичных
  `store.all_tasks` и `store.session_observations`, сторож
  `tests/test_multitarget.py` зелёный. Схема БД, `store.py`, `alerts.py`,
  `doctor/` не тронуты — это совпадает с «Влиянием на систему» и с
  diff --stat (4 файла `orchestrator/` + карта).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_validated_observation_tasks` (artel.py:1186-1190) больше не сверяет проект. Несуществующая задача отказывает через `store.get_task` до `register_observation` и до `add/remove_observation_tasks`. |
| 2 | OK | `--project P` принимается, если P ∈ {`task_target` задач набора}, иначе отказ до записи. Без флага берётся проект `raw_tasks.split(",")[0]`, а не отсортированного набора. `add/remove` поле `target` не трогают. Для задачи с NULL теперь пишется `config.DEFAULT_TARGET`, а не None. Это согласуется с `_launch_detached` (artel.py:952): он сопоставляет наблюдение по проекту с той же нормализацией. |
| 3 | OK | watch.py `_observation_events`: targets = ids ∪ проекты задач ∪ {row.target, DEFAULT_TARGET}. Функция общая для `watch --observation` и `observe events`, поэтому правило одно для обоих (AC-10 зелёный). |
| 4 | OK | Сверка `observer["target"] != target` снята. Подстрока «другой сессии» в тексте отказа сохранена. Отказы «не найдено / не активно / вне набора / свежесть» не тронуты. |
| 4а | OK | Совет `--observation <ID>` даётся только когда `matching_observation` ничего не нашёл, а задача включена в активное наблюдение сессии другого проекта. Иначе отказ прежний. Выбор наблюдения не меняется. |
| 5 | OK | Фильтр только расширен. У однопроектного наблюдения всё прежнее остаётся, добавлен только DEFAULT_TARGET. AC-5 и первая часть AC-6 зелёные. |
| 6 | OK | catalog.py: `f"{id}{label}  …"`, метка ` [p]` только при `p != DEFAULT`. NULL → артель. |
| 7 | OK | report.py: отдельный `<span class="tile-project">`. Чтение `"target" in row.keys()` работает и для `sqlite3.Row`, и для dict. Фикстуры `tests/test_report.py` не правились, тесты зелёные. |
| 8 | OK | Тесты детерминированы зерном, без сети. Смешанное наблюдение есть в каждом сценарии. |

## Замечания
- minor — orchestrator/artel.py:1081 — `store.task_target(conn, store.get_task(conn, first_task)["id"])`: обёртка `get_task(...)["id"]` нужна только для того, чтобы разрешить id (регистр или префикс). Это работает, но читается как лишний круг. Можно взять проект из уже собранного соответствия «id → проект». Последствий нет, на вкус.
- minor — orchestrator/artel.py:875-876 (`_session_observation_with_task`): сортировка идёт без `rowid` как третьего ключа, в отличие от `store.matching_observation`. Если у двух наблюдений совпадают `last_seen_at` и `created_at`, совет может назвать любое из них. Оба наблюдения валидны (сессия текущая, задача включена), так что последствие — только неоднозначный текст совета.

Обе находки minor и на вердикт не влияют, в реестр не заносятся как блокирующие.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

(Блокирующих и major-замечаний нет, реестр пуст. Minor-заметки выше — на усмотрение разработчика, закрытия не требуют.)

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py tests/test_launch_observation_refusals.py tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py tests/test_report.py tests/test_multitarget.py tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py` — 156 passed, 89 subtests passed.
- `python3 -m pytest -q` по модулям наблюдения, watch и status (`test_01m3y753…_assertion_observation`, `test_01m42nbc…_observe_extra_args`, `test_01m446x1…_watch_progress`, `test_01m44ep0…_status_show_merge_after`, `test_01m4araxf…_suite_observation`, `test_01m4c954…_observation`, `test_01m4c954…_watch`, `test_01m4nz5w…_two_sided_observation`, `test_catalog_status_log`, `test_catalog_wave_breaker_status`, `test_observation_acceptance_return`, `test_observation_edges`, `test_observation_migration_regression`, `test_observation_notification`, `test_watch`) — 138 passed, 57 subtests passed.
- `artel.py plank-run 01M563E1SH9SB63S2MW4A9B82N` — 2 passed, код выхода pytest 0.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`: кроме `built_at_sha` расхождений нет, карта свежая. Регенерацию откатил через `git checkout`.
- Временную мутацию фильтра watch (убрать `row["target"]`) песочница не пропустила: `sed -i` требует подтверждения. Заявки «Ловит мутацию» долгоживущих тестов сверены с кодом вручную: каждая ветка фильтра (id, проект задачи, проект наблюдения после remove, DEFAULT_TARGET, третий проект) держится отдельным утверждением.
- Сверка «набор не ослаблен»: diff `tests/` вне долгоживущих файлов задачи пуст, существующие ассерты не менялись.

## Предложения системе
- Приём «временная мутация» из review-checklist упирается в песочницу роли: правка кода через `sed -i` и Edit запрещена ревьюверу («Код НЕ правь»). Стоит дать штатную команду пульта для мутации с автооткатом, по аналогии с `plank-run`.
