# Записка spec_auditor

## Выяснено
- Визит 2 (SPEC sha 7229a8be…): SPEC-AUDIT.md сдан, status ready, verdict concerns, guard ок. Отклонения C1–C6; D1–D5 Оператора перенесены в SPEC.
- C1: weakening_scope артели — tests/**/*.py (targets.yaml:49): единое правило треб.6 у артели прослеживает импорт из любого модуля tests/ и ломает AC-10(в); признак режима не назван; импортированная метка у артели без AC.
- C2: orchestrator/fsm.py:1053-1060 — второй потребитель guard.TestModules/method_literal_keys (сверка «Меняемого поведения»), вне зон, в SPEC не назван.
- C3: исхода «доказано» в коде нет — two_sided.PASSED = "пройден" (two_sided.py:44).
- Путь profile/workdir внутри зоны есть: _evaluate(conn, task_id, …) test_integrity.py:1074, project_profile.for_task.

## Не сработало
- Bash: `$W`-переменные, `cd X && …`, `;`/`|` с head — требуют подтверждения; одна команда, абсолютные пути.

## Где остановился
- Шаг закончен.

## Чего не хватило
- Искал, есть ли вне зон потребители guard.TestModules — нашёлся fsm.py:1053; в карте «Импортируется» это не видно по имени класса.
