## Выяснено
- ТЗ — часть 2 нарезки родителя 01M56P60XS9AP4BH01YK35220D; AC взяты дословно из SPEC родителя
  (`git show refs/artifacts/01M56P60XS9AP4BH01YK35220D:tasks/01M56P60XS9AP4BH01YK35220D/SPEC.md`):
  AC-1…AC-8 → AC-1…AC-8, AC-15 → AC-9.
- Часть 1 = 01M56TNTY7HEC85MC940KZR1ZJ (помощники), уже done и в main (merge 4b0efef0).
  Поставлен в merge_after с разделом обоснования (строка «Порядок: после части 1» id не несёт —
  заявлено ли что-то в БД, не проверял).
- budget_usd 25 = рамка Оператора. Раздел «Меняемое поведение» не нужен: тестов, ждущих, что async не считается, не нашёл (`grep TEST_METHOD`).
- Потребители TEST_METHOD: guard.py:533, orchestrator/dry_run.py:70, orchestrator/acceptance.py:2245.

## Не сработало
- `grep --include` в zsh-оболочке пульта — глоб не раскрывается; `$?` в команде блокирует sandbox.

## Где остановился
- SPEC.md написан, status: ready, guard ок.

## Чего не хватило
- Как пульт пишет merge_after подзадачам деления при «Порядок: после части N» (catalog.spawn_subtask) — не досмотрел.
