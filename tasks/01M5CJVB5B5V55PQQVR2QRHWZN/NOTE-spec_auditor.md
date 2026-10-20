# Записка spec_auditor

## Выяснено
- Повторный аудит, SPEC 41977a42: все 9 решений гейта SPEC №1 внесены (Е1, В1, В5, Д1, Е2, В2, Е6, А1, Д2) — построчно в SPEC-AUDIT «ТЗ и SPEC».
- Новое: А3 — «todo/fails на ветке у прежнего идентификатора» не требует перемены от базы; давний неизменный it.todo/it.fails → находка в каждой задаче (outcome.py:43, 218).
- В7 (слабое): «число перепрогонов» в журнале пройденного гейта не определено.
- refusal_class — точное совпадение ключа (refusal_classes.py:137–140); multi-component → отказ decide (repo_context.py:162), до нового гейта не доходит.
- _report_run: timed_out / refusal / state (acceptance.py:833–851).

## Не сработало
- `cd … && …` в Bash отклоняется — guard звать абсолютным путём.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, guard ок.

## Чего не хватило
- Нет.
