# Записка developer — 01M5JPEHY8HY70R5T5AQ0EDSH1

## Выяснено
- zone_lock: `_waiting_dependency(conn, t, own)` теперь обходит `_ancestors` (транзитивно),
  пропускает done/killed/чужой проект, возвращает (путь, id, состояние). `_start_conflict`
  зовёт её после `_occupier` (порядок прежний), `_holds_queue` — тоже. `_reason` вида
  «зависимость» несёт « (<состояние>)».
- `_ancestors` падал на id, которого нет в БД (`store.get_task` → SystemExit), в т.ч. в
  `queue_order`; теперь такой id не раскрывается (`store.task_exists`).
- doctor `check_zone_waits`: взаимная блокировка = `blocking_conflict` называет X и id ждущей
  ∈ `_ancestors(X)`; выходы в той же детали. Логика инлайн — SPEC ограничил зону одной функцией.
- Зелёные: долгоживущий файл задачи, test_zone_lock, zone_queue_start, тесты doctor/status/
  auto (298), plank-run (AC-8). Карта регенерирована.

## Не сработало
- `pytest -n 4` в этом окружении падает (node down) — гонять с `-p no:xdist`.
- Bash-скрипт с `{"` в тексте требует подтверждения — мутации заново не прогонял
  (test_author проверил все 6 своим стабом).

## Где остановился
- PLAN.md status: ready. Код в worktree незакоммичен — коммитит пульт.

## Чего не хватило
- Ничего существенного.
