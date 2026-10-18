# Записка analyst — 01M57PMBHWK5EGQ8HPA5TQX72H

## Выяснено
- report.py:544 `_tile_html` УЖЕ показывает проект (`<span class="tile-project">sled</span>`, без скобок; тестов на `tile-project` в tests/ нет). Без проекта: `_gate_queue_html` (597), `_closed_tasks_html` (612), `_tokens_by_task` (756), `_friction_html` (805), `_alerts_html` (642, target алерта не выводится вовсе). Итоги по всем проектам вместе: `_metrics_html` (693: $/задачу done, total_spent, total_estimate; доля acceptance), разрез ролей. total_spent/total_estimate = SUM по tasks (store.py:681/687) — делится по проекту из строк tasks в report.py, без store.
- watch.py:303 дозор наблюдения УЖЕ показывает алерты target=DEFAULT_TARGET любому наблюдению; теряются алерты с target NULL (token_rate_divergence alerts.py:177, budget.py:359, amend.py:881, doctor live_smoke/hung_test/orphans.temp/canary_pool:240) — `None in targets` ложно. Позиция «оповещено» уже на наблюдение (store.advance_notified, notified_alert_id).
- Алерты уровня пульта заводятся и на NULL, и на DEFAULT_TARGET (wave breaker alerts.py:238, doctor/orphans.py:185); алерты проекта артели тоже на DEFAULT_TARGET (map_growth, recovery, suite_duration и т.п.) — различить нельзя без правки вне зон.
- status (catalog.py:937): метка проекта, зоны по проекту, стоп-кран — помечены осознанно (01M484RNV3); merge-wait — глобальный мьютекс (не входит по ТЗ); триггеры с `[target or '-']`. Смешения в status не нашёл.

## Где остановился
QUESTIONS.md — батч из 4 вопросов (класс алерта пульта / зоны, объём итогов report, форма метки, вид строки NULL-алерта в watch). SPEC не писала. guard на QUESTIONS.md — ок. После ANSWER: писать SPEC, удалить QUESTIONS.md; находки в зоне report.py (метка проекта у очереди гейтов, закрытых задач, разреза задач, трения; target в панели алертов) — в требования без вопроса.

## Чего не хватило
Определения «алерт уровня пульта» в коде: нет ни константы, ни поля — только target NULL или DEFAULT_TARGET вперемешку с алертами проекта артели.
