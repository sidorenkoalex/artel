# Записка spec_auditor

## Выяснено
- Вердикт concerns, D1–D5 в SPEC-AUDIT.md. Главное: абзац review.py:965-975 называет и исключение tasks/<id>/, и карту; SPEC не требует сохранить фразу о tasks/ у внешней задачи (D1). snapshot_exclude (review.py:298) исключает docs/codebase-map.md для любого проекта — утверждение SPEC «не исключает» неверно (D2). Оформление компонента конвенций (render, границы run_id) в SPEC не задано (D3).
- Тесты пакета (test_review_package_map.py, test_review_package.py) идут по задаче артели (task_target без строки = DEFAULT_TARGET, store.py:701) — ослабления не видно.
- docs/codebase-map.md в config.COMMON_ZONES (config.py:803) — регенерация карты в зонах.

## Не сработало
- grep с `cd ...;` и xargs требуют подтверждения — только одиночные команды с абсолютными путями.

## Где остановился
- SPEC-AUDIT.md записан, status: ready; guard прогнан.

## Чего не хватило
- Нет: всё нашлось в review.py/brief.py.
