# Записка spec_auditor

## Выяснено
- Аудит SPEC bb0e13b1: вердикт concerns, одно отклонение. Факты SPEC верны: notes.py:266-282, config.py:509, repo_context.is_artel (172-173), resolve (82-96), store.task_target (701-707).
- Отклонение: колонка tasks.target nullable (schema.py:115); resolve("")/resolve(None) -> None, а is_artel пустую колонку считает артелью. Буквальное «resolve по target = None -> неизвестный» поменяет текст удержания у артели с пустым target; AC-3 этого не ловит. Прочтение: is_artel первым.
- Все стенды окна в tests/ заводят задачу с DEFAULT_TARGET/ARTEL — ожидания не меняются; config.TARGETS патчится песочницей (tests/sandbox.py:91).
- docs/codebase-map.md в COMMON_ZONES (config.py:803).

## Не сработало
- Bash с `cd ... &&`/переменной в составной команде требует подтверждения — использовать абсолютные пути.

## Где остановился
- SPEC-AUDIT.md сдан, guard прогнан.

## Чего не хватило
- Нет.
