# Записка developer

## Выяснено
- Реализация: `orchestrator/targets.py` — `SUPPORTED_PAIRS`, новые кортежи, `unsupported_reason` решает по паре, текст п. 3 через `sorted(SUPPORTED_PAIRS)`.
- Сторож А0: изменены только `GITLAB_REASON`, `TARGET_HUMAN_REASON`, ac1 (параметр gitlab+target-human, равенство трёх констант), ac7 (четвёртая запись), ac8 (параметризация по двум поддержанным парам). Новых узлов верхнего уровня нет — планка AC-5 это проверяет побайтно.
- Документ `docs/incident-external-project.md`; команды сверены с `artel.py` (`pause --now`, а не `pause-now`; локальный слой — `.artel/targets.yaml`).
- Зелено: сторож А0 + долгоживущий + 4 файла с подменой кортежей (129 passed), plank-run 19 passed, карта регенерирована.

## Не сработало
- Ничего существенного.

## Где остановился
- Всё сделано, PLAN.md status: ready, guard прогнан.

## Чего не хватило
- Ничего.
