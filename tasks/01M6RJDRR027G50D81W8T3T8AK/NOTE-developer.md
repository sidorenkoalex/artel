# Записка developer

## Выяснено
- Реализация: `orchestrator/targets.py` — поле `mr_title_template` в `LOCAL_FIELDS["policy"]` и `DELIVERY_POLICY_FIELDS` (так попадает в плоскую запись `_flatten`), константы `DEFAULT_MR_TITLE_TEMPLATE`/`MR_TITLE_PLACEHOLDERS`, проверка в `_check_delivery`.
- `orchestrator/github_adapter.py` — `_mr_title(conn, task_id, t, entry)` + `MR_TITLE_NOT_APPLIED_ACTION`; вызов в `ensure_draft_mr` (gh) и `open_forge_mr` (forge).
- `target-set` правок не потребовал (имена из `LOCAL_FIELDS`, проверка загрузкой).
- Свой сторож: `tests/test_mr_title_template_units.py` (без `{ref}` ссылки не читаются; порядок подстановки), проверен мутациями.
- Долгоживущие файлы задачи + 16 соседних файлов: 443 passed. Карта регенерирована.

## Не сработало
- Составные bash-команды с heredoc требуют подтверждения — мутации делал правками Edit.

## Где остановился
- Готово: PLAN.md status: ready, guard ок.
- Шаг 2 (после ANSWER-1): сдвиг строк `projects.py` сверен (`:991-1000`, `:786-788`), код не меняется; PLAN дополнен шагом 4, 28 passed.

## Чего не хватило
- Ничего существенного.
