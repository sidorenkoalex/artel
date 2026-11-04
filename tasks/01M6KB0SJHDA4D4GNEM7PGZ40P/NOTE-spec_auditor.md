# Записка spec_auditor — 01M6KB0SJHDA4D4GNEM7PGZ40P (аудит 4, spec_sha 5f6d5673)

## Выяснено
- Решение №3 (F1, C1–C3, C5, B1, A1) закрыто текстом SPEC. Факты SPEC сверены с кодом на 8fa671cc0, расхождений нет. Бриф аналитика берёт полный detail через _return_context (brief.py:1527); store не режет detail.
- Обвязка: лямбда с условным выражением из двух _cmd_reject(conn, tid, …) проходит оба AST-линтера; keyword-only decision_file проходит test_ac6.
- Базы диффов: blob skills/spec-audit.md = 93bab317b, skills/spec-authoring.md = b63133cf4 — совпадают с index диффов.
- Вердикт concerns, одно отклонение — C1: форма «файл:строка» и «перечень путей» не определена, AC-4 не ловит разбор вида «любое двоеточие».
- Замечания: --decision в awaiting_human (fsm.py:1865 срабатывает раньше); метка поля в начале строки; tests/test_auto_cycle.py:345–363 не в перечне SPEC; круговой импорт brief→gitcmd→fsm.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, guard ок.

## Чего не хватило
- Поиск тестов с текстом справки reject — их нет; искать пришлось grep по tests/ и scripts/.
