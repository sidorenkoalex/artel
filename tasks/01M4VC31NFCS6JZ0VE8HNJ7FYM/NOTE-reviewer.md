## Выяснено
- Итерация 1: changes_requested, одно major — R1-F1: связку `_run_one_task` → колонка `escalation_roles` держит только разовая планка. Мутация `escalation_roles=None` в `canary.py:2633` выжила в 6 файлах tests/ (172 passed).
- Логика `escalation_roles`, `_escalation_roles_of`/`_excess_escalation_role`, миграция — без замечаний; планка 3 passed; карта свежая.

## Не сработало
- `pytest tests/ -k …` блокирует сторож роли как полный прогон — нужно перечислять файлы.

## Где остановился
- REVIEW.md записан. Следующей итерации: проверить новый тест в tests/ той же мутацией.

## Чего не хватило
- Ничего существенного.
