## Выяснено
- Факты SPEC о коде сверены: advance_origin :56-70, push :63-64, проверки :65-66/:67-69, тесты :87-111/:116-138/:143-174, _fetched_base orchestrator/workspace.py:176-184.
- Ловушка: у bare origin нет user.name/email (tests/sandbox.py:1160-1166); identity песочницы только в локальном конфиге root (sandbox.py:1532-1533); CI не задаёт git identity → commit-tree в bare без -c user.* упадёт на раннере.
- Гейт неослабления отбрасывает msg утверждений (scripts/guard.py:1619-1634) — смена текста :68-69 безопасна.

## Не сработало
- cat/ls в Bash недоступны (command not found) — читать через Read/grep.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, 3 мелких пункта; guard прогнан.

## Чего не хватило
- Явного места, где в CI задаётся git identity (его нет) — искал в .github/workflows и sandbox.
