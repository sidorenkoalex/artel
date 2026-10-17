# Записка spec_auditor

## Выяснено
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок.
- Факты SPEC против кода верны, кроме watch.py:297 (на деле :299).
- Пробелы AC: алерт с target = id задачи набора и ветка «проект наблюдения» в фильтре watch.py:299 ни одним AC не держатся.
- Существующие тесты ищут строку status по startswith(task_id) (zone_lock_projects.py:68, wave_breaker_projects.py:184,190) — метка проекта должна стоять после id.
- tests/test_report.py:44-46 — фикстуры плитки без ключа target; row["target"] даст KeyError.
- ANSWER-1 п.2 = вариант A из QUESTIONS.md (коммит 59ba0cb9 ссылки документов): без --project — проект первой задачи; SPEC совпадает.

## Не сработало
- ls в окружении шага нет (command not found); sed -i требует подтверждения.

## Где остановился
- Аудит завершён.

## Чего не хватило
- Текст варианта A из ANSWER-1 пришлось доставать из истории ссылки документов (QUESTIONS.md удалён аналитиком).
