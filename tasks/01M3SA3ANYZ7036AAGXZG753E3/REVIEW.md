---
task: 01M3SA3ANYZ7036AAGXZG753E3
type: review
author_role: reviewer
status: approved     # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Команда models показывает фактическую модель роли

## Фаза A: план
- Таблица покрытия полна: требования 1–9 привязаны к шагам 1–3; шаги —
  единицы размера MR (код команды, пункт документа, тесты + карта).
- Подход не конфликтует с архитектурой: `resolve_role` не меняется, только
  вызывается с уже прочитанными слоями (`catalog`, `local`) — ровно тот
  режим, который описан в его докстринге (orchestrator/models.py:603–607).
- «Влияние на систему» совпадает с diff: `docs/stack.md`,
  `orchestrator/models.py`, `tests/test_models.py` (+ сгенерированная
  карта); гейты/лимиты/инварианты не тронуты. Откат — revert merge.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_role_resolutions` зовёт `resolve_role(role, catalog, local)`; модель столбца — только `resolved.model`; прежние `_roles_by_tier`/`tier_of_model` удалены, второй копии правила нет. |
| 2 | OK | `_role_source` — `role_models` либо `resolved.tier`; ячейка «`<источник>: роли`». Подпись читается из `local.role_models` отдельно, но это подпись, не выбор модели (заявлено в рисках PLAN). |
| 3 | OK | Роль кладётся только к `resolved.model`; ярус в обход разрешения не читается. |
| 4 | OK | Заголовок «роли»; строка-причина тоже переименована в «роли показаны не полностью». |
| 5 | OK | `  роль → модель → провайдер (role_models | ярус X)` под таблицей; модель/провайдер — из `Resolution`. Порядок звеньев как у `role-providers` `doctor` (без яруса — SPEC требует «роль, затем модель, затем провайдер»). |
| 6 | OK | Перехват `ModelsError` на уровне роли (`RoleTierError` — тоже `ResolutionError`, orchestrator/models.py:620–623, так что прежний перехват `roles.RolesError` не потерян); строка `роль → не разрешено: <текст>`, плюс строка-причина над таблицей. |
| 7 | OK | Вызовы — `roles.load`, `resolve_role` на переданных слоях; записей нет (AC-4 проверяет файлы и журнал). Строки-причины слоя и карты сохранены. |
| 8 | OK | `docs/stack.md:617–626` описывает столбец с источником и итоговые строки. |
| 9 | OK | Долгоживущий `tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py` (AC-1…AC-5) + `test_refused_role_is_named_above_the_table` в `tests/test_models.py`. |

## Замечания
Нет blocker/major/minor.

Наблюдения без замечания:
- `tests/test_models.py` — изменён только ожидаемый заголовок столбца
  («роли по ярусам» → «роли») в тесте и его докстринге; это явно допущено
  SPEC («Не входит»). Ассерты не удалены и не ослаблены.
- Новый тест разработчика не повторяет долгоживущий: долгоживущий AC-4
  проверяет причину нечитаемой карты, а тест разработчика — строку-причину
  над таблицей при отказе разрешения одной роли (свойство R1-F5, в AC-3
  планки не проверяется).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний нет, реестр пуст.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_models.py
  tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py tests/test_stack.py
  tests/test_models_doctor.py` — 89 passed, 20 subtests passed.
- Временная мутация в памяти (`mock.patch.object`, код на диске не
  менялся), прогон `tests.test_01m3sa3anyz7036aagxzg753e3_models_roles` +
  `tests.test_models`:
  - `_role_source` → всегда `resolved.tier` (источник записи печатается
    ярусом) — красный `test_ac1_roles_column_follows_role_models_with_source`;
  - `_role_resolutions` возвращает причину `None` (отказ гасится только в
    итоговой строке) — красные `test_refused_role_is_named_above_the_table`,
    `test_ac4_…`, `test_unreadable_roles_map_is_named_above_the_table`,
    `test_unreadable_tier_is_named_above_the_table`. Заявка теста
    разработчика подтверждена.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` —
  расходится только строка `built_at_sha`, карта свежая по содержимому;
  рабочее дерево возвращено (`git checkout -- docs/codebase-map.md`).
- Прочитан `orchestrator/models.py::resolve_role` (597–644) — чтобы
  проверить, что отказ яруса роли (`roles.RolesError`) приходит как
  `RoleTierError ⊂ ModelsError` и перехват `_role_resolutions` его ловит.

## Предложения системе
- Шелл шага ревью отклоняет запись во `/tmp` (heredoc в файл вне рабочего
  каталога ждёт подтверждения) — временную мутацию удобнее делать
  `python3 - <<EOF` с `mock.patch.object` в памяти: код на диске не
  трогается, и возвращать нечего. Стоит упомянуть приём в
  `skills/review-checklist.md` рядом с «временной мутацией».
