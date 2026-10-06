---
task: 01M484RNV3QBDY3B0M16J916ZP
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Этап 3 ADR-0021, часть 3 из 3: прочие развилки, сторож и сквозной тест внешнего потока

## Фаза A — план

- Таблица покрытия PLAN полна: требования 1–8 → шаги 1–5. Шаги — проверяемые единицы, без микроопераций.
- Подход (фильтр «тот же проект» вместо «только артель», единый признак `repo_context.is_artel`, `fsm._origin_main_source` через `repo_context.resolve`) не спорит с архитектурой этапов 1–2 ADR-0021.
- Разбивка требования 8 сверена: `grep -rn DEFAULT_TARGET orchestrator/ | wc -l` = 67, как в PLAN. В модулях, которые тронул diff, остались только умолчания и константы (zone_lock:287/316, runner:366, catalog:229/511/663, store:229/231/537/538, fsm:247) — категории из PLAN.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Строки 1–6: `zone_lock._project`, `forecast_overlaps(target=)`, `blocking_conflict`/`queue_position` отбирают задачи того же проекта; в `catalog` отсечки для чужого проекта сняты. Строки 7–11: фильтры по проекту в alerts/runner/catalog сняты, дедуп идёт по источнику, алерт по-прежнему заводится на `DEFAULT_TARGET`. Строки 12–13: развилки в `_dirty_refuses` и `_tests_writing_ac_state` сняты. Строка 14: паспорт ведётся у любого проекта, `send_pending` ушёл (коммит паспорта шлёт ссылку сам). Строка 15: одна запись `target/sha/чисто/код/артефакты`, `код=` берётся из `default_code_sha`, который через `workspace.task_repo` работает у любого проекта. Строка 17: дубль удалён, импорт `targets` из fsm убран. Строки 20, 22, 23, 26, 27 сняты, поведение совпадает с колонкой «Общее поведение». Оставленные строки 16, 18, 19, 21, 24, 25, 28, 29 зовут `is_artel`. |
| 2 | OK | `repo_context.is_artel` принимает контекст, имя, строку задачи (dict/sqlite3.Row) и путь. Путь сравнивается с `clone_path(DEFAULT_TARGET)` — это та же функция, что `workspace.repo`, так что прежняя семантика `ci._repo_kwargs` не изменилась. |
| 3 | OK | Сторож — долгоживущий `tests/test_01m484rnv3qbdy3b0m16j916zp_gate_target_guard.py`, зелёный. Развилка в `advance_gates/review.py` удалена. |
| 4 | OK | `..._external_flow.py::ExternalWithProfileTest` (а–д): зелёный. |
| 5 | OK | `ExternalWithoutProfileTest`: зелёный. |
| 6 | OK | Первые строки докстрингов `repo_context` и `advance_gates/__init__` названы. Планка AC-17 зелёная. Перегенерация `scripts/codebase_map.py` меняет только строку `built_at_sha`, то есть карта свежая. |
| 7 | OK | Свой тест есть только на формы субъекта `is_artel` (`IsArtelSubjectsTest`); свойство долгоживущих тестов он не повторяет — те подменяют признак, а не проверяют его. Смена ожиданий 15 методов сверена с ANSWER-1, см. ниже. |
| 8 | OK | Разбивка в PLAN, число строк сходится. |

### Сверка изменённых утверждений с ANSWER-1

- Все 9 методов из раздела пакета «Изменённые утверждения тестов» и 4 метода `test_step_refixation` + 2 метода `test_git_fixation` входят в перечень мандата. Число утверждений не уменьшилось. У KillDocsRef и DivisionParentCleanup их стало больше: проверяется точная цепочка родителей плюс `diff --name-only` == только `PASSPORT.md`, проверки «является предком» нет (условие 2 выполнено). Докстринги трёх тестов стоп-крана переписаны под новую мутацию (условие 3). Перечень «было → стало» в PLAN есть (условие 4).
- Вне мандата меняются только обвязки: `test_doctor.py::BranchFreshnessCheckTest.setUp` (успешный `in_repo`, лямбды принимают `base=`) и `test_fsm_map_conflict_autoresolve.py.setUp` (паспорт заглушён). Утверждения не тронуты. Сужения данных я не нашёл: ни одна задача из сценариев не выпадает, и `fetch` у артели теперь просто нужен по строке 27.
- `test_step_refixation`: `entry_sha` теперь равен `self.head()` после `enter_tests_writing()`. Это смена вычисления ожидаемого значения в пределах мандата, сами утверждения те же.

## Замечания

Блокирующих и major нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved. Ниже — наблюдения уровня вкуса, в реестр их не заношу. Их можно закрыть попутно в следующей задаче по этому коду:
- `orchestrator/fixation.py:69` `external_code_sha` больше не вызывается: его единственный потребитель `store.record_fixation` перешёл на `default_code_sha`. При этом докстринг `default_code_sha` (fixation.py:87) всё ещё говорит «self/артели», хотя функция теперь общая.
- `orchestrator/artifact_branch.py:207–210` разбирает и текстовый `stdout` у `hash-object`, хотя вызов идёт с `text=False`. Эта защита рассчитана на моки subprocess в песочницах и не отражает реальное поведение git; поведение безопасное (пусто → "").

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M484RNV3QBDY3B0M16J916ZP`: 2 passed, код выхода 0.
- `python3 -m pytest -q -p no:xdist` по долгоживущим `tests/test_01m484rnv3qbdy3b0m16j916zp_*.py` (6 файлов) и затронутым модулям: test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation, test_alerts_wave_breaker, test_artifact_ref_sync, test_catalog_wave_breaker_status, test_division_parent_cleanup, test_doctor, test_fsm_map_conflict_autoresolve, test_git_fixation, test_repo_context, test_review_package, test_runner_wave_breaker, test_split_assessment_merge_gate, test_step_refixation, test_catalog_zone_overlap. Итог: 441 passed, 31 subtests passed за 178 с. С `-n 6` xdist в окружении роли не стартует (node down), поэтому гонял последовательно.
- `guard.test_functions_without_mutation_claim(base, head)` по всем 19 файлам `tests/`, изменённым против 4d6f5b77: находок нет.
- `grep -rn DEFAULT_TARGET orchestrator/ | wc -l` → 67, сходится с PLAN.
- `python3 scripts/codebase_map.py` + `git diff --stat docs/codebase-map.md`: меняется 1 строка (`built_at_sha`), содержимое свежее; изменение откатил.
- Временную мутацию `is_artel` (пустой `target` строки → не артель) для проверки `IsArtelSubjectsTest` прогнать не удалось: составную команду отклонил запрос прав. Заявка теста сверена с кодом глазами: подтест `{"target": None}` ждёт `True`, а такая мутация вернёт `False`.
- CI коммита 49d84b25 зелёный (16 проверок, из пакета).

## Предложения системе

- В окружении роли `pytest -n N` (xdist) падает со «node down: Not properly terminated». Прогон затронутых модулей в шаге ревью приходится вести последовательно, это ~3 минуты на 440 тестов. Стоит проверить, что воркерам xdist не хватает в PATH роли (та же копилка 05.10, где в PATH нет /bin).
