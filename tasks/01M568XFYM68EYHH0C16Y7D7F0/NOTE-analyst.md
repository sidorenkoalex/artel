# Записка analyst

## Выяснено
- ТЗ достаточно, SPEC.md написан (7 требований, AC-1..AC-7), status: ready, guard ок.
- Текст с `config.MAIN_BRANCH` в kill — `orchestrator/cleanup.py:211` (cleanup_killed_task) и `:81-82` (drop_task_dir, сверка с ROOT артели); `:177-178` уже зовёт `_merged_base(repo)`. База проекта — `_base_of(repo)` (`cleanup.py:105`).
- `docs/codebase-map.md` и `tests/` — в COMMON_ZONES.

## Не сработало
- Первый прогон guard: сигнал «число файлов» — guard считает все пути, упомянутые в тексте SPEC (включая только-чтение). Закрыто секцией «Оценка объёма» с монолитом и «Прогноз диффа: 20 КиБ».

## Где остановился
- SPEC сдан, ждёт гейта SPEC (монолит утверждает Оператор).

## Чего не хватило
- Ничего существенного.
