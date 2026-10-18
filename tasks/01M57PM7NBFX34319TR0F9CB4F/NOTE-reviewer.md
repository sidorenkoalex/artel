## Выяснено
- Итерация 1: approved, реестр пуст. Планка 2 passed. Тесты модулей зоны и все файлы требования 11: 256 passed.
- Временные мутации (продление всех строк, глобальная голова очереди, держатель — первая строка) роняют все три теста `tests/test_merge_lock_by_project.py`.
- Карта кодовой базы свежая. Дифф `tests/` — только добавления.
- sid мьютекса и `resolve_session_id()` в продлении heartbeat совпадают в рабочем пути (CLI approve без session_id). Расходятся только при явном session_id в `cmd_approve`; записано наблюдением.

## Не сработало
- `diff <(...)` отклоняется песочницей (process substitution). Карту сверял через `git diff` после регенерации.

## Где остановился
- REVIEW.md записан со status approved.

## Чего не хватило
- Пришлось искать, откуда берётся sid approve-цикла: `fsm.cmd_approve` → `lease.run_locked` → `resolve_session_id(None)`.
