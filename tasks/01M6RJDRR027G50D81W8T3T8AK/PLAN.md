---
task: 01M6RJDRR027G50D81W8T3T8AK
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Шаблон заголовка MR задачи внешнего проекта: policy.mr_title_template

## Подход
По образцу `branch_template`/`commit_template`:
- `orchestrator/targets.py`: поле `mr_title_template` в `LOCAL_FIELDS["policy"]`
  (необязательное) и в `DELIVERY_POLICY_FIELDS` (так оно попадает в плоскую
  запись через `_flatten`); константы `DEFAULT_MR_TITLE_TEMPLATE = "{id}: {title}"`
  и `MR_TITLE_PLACEHOLDERS = ("{id}", "{ref}", "{title}")`; проверка в
  `_check_delivery` — непустая строка, только перечисленные подстановки,
  `{ref}` только при `policy.ref_required`; отказ через `refuse(...)` —
  текст `поле 'policy.mr_title_template'`.
- `orchestrator/github_adapter.py`: одна функция `_mr_title(conn, task_id, t,
  entry)` сборки заголовка, вызываемая в обоих местах (`ensure_draft_mr` —
  `gh pr create`, `open_forge_mr` — `forge.open_mr`). Ссылки задачи читаются
  только при `{ref}` в шаблоне; ключ — первой в порядке записи
  (`store.external_refs`) ссылки системы `ref_required` (правило
  `pull.commit_title`). Подстановка по порядку `{id}` → `{ref}` → `{title}`.
  Нет ссылки — заголовок по умолчанию и запись журнала
  `шаблон заголовка MR не применён` / `нет ссылки системы <ref_required>`.
- `target-set` (`projects.py`) берёт допустимые имена из `LOCAL_FIELDS` и
  проверяет запись загрузкой — правки не нужны.
- Регенерация `docs/codebase-map.md`.

## Шаги
1. Поле, константы и проверка в `orchestrator/targets.py`.
2. Сборка заголовка `_mr_title` и её вызов в двух местах
   `orchestrator/github_adapter.py`.
3. Сторож `tests/test_mr_title_template_units.py` на свойство, не покрытое
   долгоживущими файлами: шаблон без `{ref}` не читает ссылки задачи
   (проверен мутациями «ссылки читаются безусловно» и «`{title}` первым» —
   красный). Прогон долгоживущих тестов задачи и тестов затронутых модулей
   (18 файлов: 443 passed), регенерация карты, guard.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 1 (target-set проверяет загрузкой) |

## Влияние на систему
- Запись без поля даёт прежний заголовок побайтно (умолчание `{id}: {title}`,
  при пустом названии — id), к ссылкам задачи обращения нет.
- `gitlab_adapter` (префикс `Draft: `, снятие, `_title_refusal`), `forge`,
  `projects`, `store`, `pull` не меняются. Гейты, лимиты, тесты не
  ослабляются; существующие тесты не правятся.
- Откат — revert merge-коммита задачи.

## Риски
- Поле в `DELIVERY_POLICY_FIELDS` попадает в плоскую запись: другие
  читатели этого кортежа — только `_flatten` (grep), риска нет.

## Предложения системе
- `_check_delivery` не требует `ref_required` для `{ref}` в `commit_template`
  (в отличие от `branch_template`/`mr_title_template`) — `{ref}` молча
  подставится пустым; кандидат в отдельную задачу.
