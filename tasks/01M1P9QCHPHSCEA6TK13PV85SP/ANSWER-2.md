---
task: 01M1P9QCHPHSCEA6TK13PV85SP
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Повторная эскалация по AC-3 снята: тест AC-3
(`test_ac3_zones_extension_with_operator_mandate.py`) написан по
ANSWER-1, устаревшую пометку `# AC-3: escalate` в
`test_ac3_ac7_markers.py` Оператор убрал мостом. Новых вопросов нет,
ответ ANSWER-1 в силе (вариант b: раздел `## Расширение зон` в PLAN,
маркер `Расширение зон разрешено:` в ANSWER, колонка
`tasks.zones_extension`). test_author: проверить маркеры красноты по
каждому файлу и завершить шаг; прогоны — только в переднем плане с
таймаутом, по одному файлу.
