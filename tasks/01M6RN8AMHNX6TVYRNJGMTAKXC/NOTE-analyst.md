# NOTE-analyst

## Выяснено
- Факты ТЗ сверены с кодом: `PULT_ACTOR_TRAILER` gitcmd.py:544, `pult_message` :585-593, `LOCAL_FIELDS` targets.py:391-411, `_check_delivery` :664, `co_author` :721-727, `_flatten` :849-859.
- `target-set` generic по `LOCAL_FIELDS`; `_argument_value` отказывает пустому значению (projects.py вне зон).
- Возврат с гейта SPEC (3 решения) закрыт: AC-1 — загрузка через локальный слой (targets.load), пропуск в `_flatten` краснит; AC-2 — случай без co_author (нет пустого завершающего абзаца); AC-4 + требования 1-2 — ключ `[A-Za-z0-9-]+`, непустое значение, отказ числу/списку/`Key_x: v`/`"Key: "`.
- Опыт: yamlmini.mapping читает `42` как int, `[x, y]` как list, `"Key: "` строкой; блочный список `- x` не разбирается вовсе.

## Не сработало
- Bash с несколькими командами (ls; cat) отклоняется правами — читать через Read.

## Где остановился
- SPEC.md status: ready, guard ок. budget_usd 25.

## Чего не хватило
- Ничего.
