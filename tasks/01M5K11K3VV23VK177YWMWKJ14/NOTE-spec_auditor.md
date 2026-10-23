# Записка spec_auditor — 01M5K11K3VV23VK177YWMWKJ14 (круг 2)

## Выяснено
- Решения гейта №1 (5 пунктов) перенесены в SPEC полностью; ссылки на код сходятся, кроме `_approve_during_canary_kwargs`: def на artel.py:1877, не :1882.
- lease.run_locked (lease.py:334) возвращает body(sid) — возврат `_cmd_kill` дойдёт до `cmd_kill`.
- Возврат cmd_kill никто в tests/ не использует; мок cmd_kill в test_01m3xtf…_role_refusal.py:47/:186 даёт truthy MagicMock — подсказка напечатается, тест вывод не сверяет.
- Отклонения (concerns): нет AC на отсутствие подсказки при --reason с записанным переходом; AC-7 не покрывает причину из одних "\n"/"\t" (мутация strip(" ") → деталь «kill switch: »).

## Не сработало
- `ls`/`cat` в Bash недоступны (command not found) — git show HEAD: и sed работают.

## Где остановился
- SPEC-AUDIT.md записан, verdict concerns, guard зелёный.

## Чего не хватило
- Ничего существенного.
