---
task: 01M3SF7DPFGEZ7VYEGGXGTX49E
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

1. Конфликт подтяжки main — механический. В `orchestrator/artel.py` единственный конфликт — строки справки «Команды:» про `run`/`auto`/`stop`/`approve`. Ветка задачи добавила к `approve` флаг `[--fixes-main "<основание>"]`; main (задача 01M3SX69E8P64D77J1XTHMHE40, наблюдение) переписал строки `run`/`auto`/`stop` и добавил `observe …` и `hook-migrate …`. Разрешение: взять версию main целиком и в строке `approve` добавить `[--fixes-main "<основание>"]` после `[--accept-red "<основание>"]`. Остальной код обеих сторон без изменений.
2. `docs/codebase-map.md` не править руками — перегенерировать после разрешения (`python3 scripts/codebase_map.py`).
3. После разрешения прогнать адресные тесты задачи; других правок не делать. PLAN.md — `status: ready`.
