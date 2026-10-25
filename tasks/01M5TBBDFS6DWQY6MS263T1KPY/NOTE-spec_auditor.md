# Записка spec_auditor — 01M5TBBDFS6DWQY6MS263T1KPY (визит 2, spec_sha c48a541e…)

## Выяснено
- SPEC c48a541e учла решения гейта 26.10 пп. 1–12; остаточные находки:
  - AC-9/треб. 2: полный id эпика (E+26 = 27 знаков) не проходит `idgen.is_task_id_form` (`orchestrator/idgen.py:59`) → `merge_after.check` отдаёт причину формы `guard.merge_after_form_errors` (`scripts/guard.py:5636`) без « — », а не `_reason`.
  - `cmd_status` (`orchestrator/catalog.py:991`) печатает все задачи подряд по id, «блоков проекта» нет — треб. 13/AC-28 опираются на несуществующую структуру.
  - Миграция с записью журнала: `store.db()` зовёт `migrate` на КАЖДОМ открытии (`store.py:409`); БД без `steps` (tests/test_agent_failure.py:355) уронит INSERT.
  - `lease.acquire` пишет «lease взят» в steps (`lease.py:144`) → AC-13 (снимок steps) требует отказа `--as-epic` до `run_locked`.
  - Заголовок группы (треб. 13) не называет эпик, а AC-25 ждёт смены названия в `status`.
  - Членство родителя в эпике при `--as-epic` не задано.
  - Мандата в ANSWER-n на правку test_multitarget.py:288-289 нет.
- Вердикт: concerns.

## Не сработало
- `ls`/`cat` недоступны в Bash; составные команды с awk требуют подтверждения.

## Где остановился
- SPEC-AUDIT.md написан, guard прогнан.

## Чего не хватило
- Нет карточки «migrate идёт на каждом store.db(), steps может отсутствовать» — нашёл по комментарию schema.py:391.
