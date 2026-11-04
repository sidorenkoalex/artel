# Записка spec_auditor

## Выяснено
- Утверждения SPEC о коде подтвердились: runner.py:83 spawn_agent, :1805 вызов, :2086 «agent run finished»; liveness.py:118/:157. Но :2094 — это ОПРЕДЕЛЕНИЕ close_pump; вызов — runner.py:1876 (в `_spawn_and_wait`, раньше `_finish_ok`).
- Дифф приложения ложится: blob skills/test-authoring.md на HEAD = 5757841ad, контекст строк 364–369 совпадает.
- alerts.KINDS (alerts.py:73) хватает для тревоги требования 3, alerts.py не нужен.
- Подмены spawn_agent в тестах (sandbox.claude_only_popen, FakeProc) — pid не int, поэтому новое снятие группы их не заденет.
- Вердикт: concerns (8 отклонений, все решаемы на гейте).

## Не сработало
- grep с `cd` и пайпами отклоняется правилами — нужны абсолютные пути и простые команды.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Значение resource.RLIM_INFINITY на Linux (-1) на macOS не проверить — вывод сделан по документации CPython.
