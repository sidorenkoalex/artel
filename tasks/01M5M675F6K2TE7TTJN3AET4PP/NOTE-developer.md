# Записка developer — 01M5M675F6K2TE7TTJN3AET4PP

## Выяснено
- ANSWER-3 (вариант а): Оператор поправил долгоживущий тест AC-5 через amend-tests (b69e06ee) под прежний формат `_remove_dirs` «… не удалён: <причина>». Код не менялся.
- Прогон 23.10 после ANSWER-3: test_prune, test_pin, оба долгоживущих файла, test_pin_prune_orphan_guards — 31 passed, 11 subtests; планка AC-8 — 1 passed; guard на PLAN — ок.
- Реализация (прошлый шаг): pin.py `_prune_origin_refs`, prune.py вид `_orphan_worktrees` (свой `_worktree_list`), docs/retention.md, tests/test_pin_prune_orphan_guards.py. Карта регенерирована.

## Не сработало
- В Bash нет rm/ls/cp; сценарии писать файлом.

## Где остановился
- PLAN.md — status: ready, раздел «Эскалация» снят. Шаг завершён.

## Чего не хватило
- —
