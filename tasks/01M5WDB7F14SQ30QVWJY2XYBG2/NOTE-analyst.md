# Записка analyst

## Выяснено
- ТЗ достаточно: SPEC.md написан (9 AC, status: ready, budget 40 = рамка ТЗ, merge_after из «Порядок: после»). guard — ок.
- Номера строк в ТЗ сдвинуты: ветка строится в `orchestrator/catalog.py:918` (`_new_task_row` с :900), `fsm._spawn_division_subtasks` — `fsm.py:1037`. `gitcmd.py` — точки на :164/:341/:413/:441/:469 совпадают.
- `tests/` — общая зона (`config.COMMON_ZONES`), сигналов деления нет (порог бюджета 60).

## Не сработало
- Ничего.

## Где остановился
- SPEC сдан; QUESTIONS.md не создавался.

## Чего не хватило
- Ничего существенного.
