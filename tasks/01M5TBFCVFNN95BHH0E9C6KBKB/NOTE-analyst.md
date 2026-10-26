# Записка аналитика

## Выяснено
- Итерация 2 (возврат с гейта SPEC 26.10, шесть решений Оператора) внесена в SPEC:
  (1) `approve --as-epic` — в «Не входит» + фраза в требовании 11; (2) требование 17 + AC-20 (черновики `draft` мешают `ready_to_close` — `board.py:117` — и `epic close`, `epics.py:183` на main); (3)(4) требование 12 переписано: своя область `deferred_sends` на каждую команду, журнал под id эпика с `target` проекта (`artifact_branch._journal_push_outcome` `:416` пишет под task_id), AC-21; (5) AC-15…AC-18; (6) требование 6 + AC-19, зона `orchestrator/budget.py` (`apply_division_frame` `:201`, источник `operator`).
- Зоны дополнены `orchestrator/budget.py`, `orchestrator/board.py` (15 файлов вне общих), критериев 21, бюджет оставлен по рамке ТЗ $65 (калибровка ~$85, отмечено в «Оценке объёма»).
- Прежнее: места перебора `refs/artifacts/*` — см. требование 15 и «Материалы» SPEC; Э1 смержен в origin/main, читать `git show origin/main:orchestrator/epics.py`.

## Не сработало
- `ls` в песочнице недоступен; `git show origin/main:<путь>` работает.

## Где остановился
- SPEC.md обновлён, status ready, `scripts/guard.py` — ок.

## Чего не хватило
- Где вычисляется «готов к закрытию» — нашёл grep'ом `ready_to_close` (board.py), в ТЗ модуль не назван.
