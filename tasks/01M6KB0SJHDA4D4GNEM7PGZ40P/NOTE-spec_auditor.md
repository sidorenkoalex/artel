# Записка spec_auditor — 01M6KB0SJHDA4D4GNEM7PGZ40P

## Выяснено
- Факты SPEC о коде подтверждены: fsm.py:1890/1912/1919, brief.py:76/1343, artel.py:2675, answer.py:239, auto.py:591.
- Три диффа ТЗ проходят `git apply --check` на HEAD 8fa671cc0, если добавить перевод строки в конце (в ТЗ закрывающая ``` склеена с последней строкой).
- Не названный в SPEC существующий тест: tests/test_lease_run_task_command.py:26,177-182 — `cmd_reject(PREFIX, "причина", "sess-g")` (session_id третьим позиционным) и `_cmd_reject` с `kwargs == {}` и `args[1:] == (FULL, "причина")`; пересылка `decision=None` в `_cmd_reject` ломает тест.
- Подсказка spec_gate живёт в config.AUTO_STOP (config.py:926) — вне зон; перечень дописывается в auto.py.
- Форма полей, кроме «Утверждения…», в SPEC не задана; «заглушка <…>» двусмысленна; правило сравнения строки мандата не задано.

## Не сработало
- `cd /tmp` и sed по относительным путям после cd — отклоняются; работают абсолютные пути и python из рабочего каталога.

## Где остановился
- SPEC-AUDIT.md написан, вердикт concerns; guard прогнан.

## Чего не хватило
- Долго искал, какие тесты закрепляют сигнатуру cmd_reject: ключ — grep `cmd_reject` по tests/, test_lease_run_task_command.py.
