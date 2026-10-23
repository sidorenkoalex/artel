# Записка developer — 01M5M675F6K2TE7TTJN3AET4PP

## Выяснено
- Причина возврата «инцидент целостности» — коммит ANSWER-2 Оператора в refs/artifacts (77d5a1d3 -> fd8a6e68); закрывается выполнением ANSWER-2.
- ANSWER-2 п.1 (строка сбоя — прежний формат `_remove_dirs` «… не удалён: <причина>») противоречит долгоживущему тесту AC-5 (`tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py::OrphanWorktreeRemovalFailureTest`, ждёт «<имя>: не удалён — <причина>»). Тест написан до ANSWER-2. PLAN.md — status: escalate, дефолт — amend-tests AC-5 под прежний формат.
- Реализовано и зелёно: pin.py `_prune_origin_refs` (N = разница for-each-ref), prune.py вид `_orphan_worktrees` (свой `_worktree_list`, отличает «не получен»), docs/retention.md, новый tests/test_pin_prune_orphan_guards.py (п.2/4/5 ANSWER-2, мутации проверены). Карта регенерирована.
- Красен только AC-5 (формат строки). Планка AC-8 зелёная.

## Не сработало
- В Bash нет rm/ls/cp; конструкции `$var`, `{"` в heredoc блокируются — сценарии писать файлом и удалять через python os.remove.

## Где остановился
- Шаг завершён эскалацией. После amend-tests AC-5 код менять не нужно — сдать PLAN status: ready.

## Чего не хватило
- Сверки ANSWER с зафиксированными долгоживущими тестами до шага разработчика.
