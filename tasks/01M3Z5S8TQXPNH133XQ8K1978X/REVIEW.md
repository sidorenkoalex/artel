---
task: 01M3Z5S8TQXPNH133XQ8K1978X
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Допуск набора сверяет роли вне набора с боевыми моделями

## Фаза A: план
- Покрытие: все 5 требований SPEC есть в таблице PLAN, у каждого названы шаги.
- Шаги размером с MR: одно условие в коде с документацией и отдельно тесты с проверкой. Микроопераций нет.
- Архитектура: сверка идёт через уже существующий `_combat_model` (`orchestrator/models.py:1230`). Пути «только чтение» из SPEC не тронуты: в diff только `orchestrator/models.py`, `tests/test_model_sets.py`, `docs/stack.md` и карта.
- «Влияние на систему» совпадает с diff. Схема БД и формат сводки не менялись, путь отката (revert) описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/models.py:1271-1275`. Каждая роль набора обязана совпасть со сводкой: `summary.get(role) == model`, поэтому роль набора, которой нет в сводке, даёт `None` и отказ. Каждая роль сводки вне набора сравнивается с `_combat_model(role)`. Если боевая модель не разрешилась (`None`) или в сводке записано `не разрешена` (`canary.py::_plan_summary`), прогон не засчитывается. Формат модели в сводке — `resolved.model` из `canary.py::_roles_in_clone`, то есть та же строка, которую отдаёт `resolve_role(role).model` в `_combat_model`, так что сравнение корректно. |
| 2 | OK | При допуске пояснение называет `run_stamp` (строка 1276). Текст отказа совпадает с SPEC дословно (1278-1279). |
| 3 | OK | Цикл проверки пар, фильтры `verdict`/класса шаблона и порядок проверок не изменились. AC-5 зелёный. |
| 4 | OK | Долгоживущий тест задачи покрывает AC-1…AC-5. Плюс `SetAdmittedUnknownOutsideRoleTest` — это другое свойство (роль без разрешимой боевой модели), а не повтор долгоживущего. В `git diff a6904801 -- tests/` нет удалённых строк, существующие тесты не тронуты. |
| 5 | OK | `docs/stack.md:849`. AC-6 планки зелёный. |

## Замечания

Замечаний уровня blocker/major/minor нет. Наблюдение не для исправления: `_combat_model` → `resolve_role` → `load_local()` перечитывает слой для каждой роли вне набора в каждой трудной зелёной строке. На нынешнем размере `canary_runs` это незаметно; если таблица вырастет, слои можно один раз прочитать до цикла.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q` на долгоживущем тесте задачи, `tests/test_model_sets.py`, `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`, `tests/test_task_model_set_units.py`, `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`, `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`, `tests/test_pair_suspension_units.py` и планке `tasks/01M3Z5S8TQXPNH133XQ8K1978X/acceptance_tests` — 74 passed.
- Временная мутация `and all(True or model == _combat_model(role) …)`, то есть роли вне набора не сверяются. Красные: `test_ac1_foreign_models_outside_set_not_counted`, `test_ac3_both_runs_names_the_combat_one`, `SetAdmittedUnknownOutsideRoleTest::test_unknown_outside_role_does_not_confirm_set` (3 failed, 14 passed). Код возвращён через `git checkout -- orchestrator/models.py`, `git status` чистый.
- sha256 долгоживущего теста `11f262f2…ee40` совпадает с `acceptance_tests/long_lived.sha256.txt`.
- `git diff a6904801 -- tests/ | grep '^-'` — удалённых строк в тестах нет, только заголовки файлов.
- `python3 scripts/codebase_map.py`: после регенерации карта отличается от ветки только строкой `built_at_sha`, то есть свежая. Регенерация откачена.

## Предложения системе
