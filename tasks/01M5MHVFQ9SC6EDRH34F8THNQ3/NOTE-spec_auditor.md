## Выяснено
- Пять копий `?mode=ro` подтверждены: store.py:337, knowledge_cards.py:767, suite_run.py:179, preflight.py:84, scripts/test_rule_stats.py:72 (+ connect на :74). Других строк `?mode=ro` в orchestrator/scripts нет (докстринги пишут `mode=ro` без `?`).
- Существующие шпионы (canary AC-11, knowledge AC-5, developer suite-run AC-1, rule_stats AC-9) патчат атрибут `sqlite3.connect` глобально — вызов из store их не ломает.
- scripts/test_rule_stats.py сейчас не импортирует store (:41-44) — понадобится новый импорт, а SPEC «Не входит» разрешает лишь строку открытия и импорт sqlite3.
- Импорт sqlite3 остаётся нужен во всех четырёх вызывающих (except/аннотации).

## Не сработало
- grep с `cd … ;` и переменными в Bash требует подтверждения — только абсолютные пути.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns.

## Чего не хватило
- Ничего существенного.
