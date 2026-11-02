# Записка analyst

## Выяснено
- ТЗ достаточно, SPEC.md написан (status: ready, 12 требований, AC-1..AC-15), guard ок.
- merge_after: 01M6EZXVFGXC6WBDA9QJESAZRW («часть 1» — так показывает `artel.py show`).
- budget_usd 40 = рамка ТЗ. Сигналы объёма: AC ≥ 10, бюджет ≥ $30; в SPEC дан материал к решению «монолит», решение — за Оператором.
- Клона подмодулей в orchestrator/ сейчас нет вовсе (grep "submodule" пуст); `ensure_clone` — workspace.py:95-123, `set_clone_hooks` — :68-75.
- Токен слота: gitcmd.hosting_token (:125), hosting_env (:149). scripts/git-hooks/ не защищённый путь.

## Не сработало
- TZ части 1 (tasks/01M6EZXVFGXC6WBDA9QJESAZRW) читать запрещено правами шага.

## Где остановился
- Шаг завершён: SPEC сдан.

## Чего не хватило
- Не смог прочитать ТЗ части 1, чтобы понять, вводит ли она клон подмодулей/слот токена, на которые опирается требование 9.
