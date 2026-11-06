# Записка spec_auditor

## Выяснено
- Факты SPEC о коде подтвердились: github_adapter.py:186/:441, targets.py:377/391/417-419/424, projects.py:780, catalog._branch_ref_key :642.
- Ключ {ref} у задачи может быть не один (catalog.cmd_link, new без {ref} в ветке); образец выбора — pull.commit_title (pull.py:926-939, первая по порядку записи).
- target-set: значение `{ref}: {title}` проходит разбор и пишется в кавычках (проверено _argument_value/_literal); копия — в config.LOGS, не рядом.
- tests/test_github_adapter.py EnsureDraftMrTest: conn=mock.Mock() — чтение ссылок без {ref} сломает тесты.

## Не сработало
- —

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Нет одного места, где описано, какие пути ensure_draft_mr делают git push (пришлось читать github_adapter.py:130-200).
