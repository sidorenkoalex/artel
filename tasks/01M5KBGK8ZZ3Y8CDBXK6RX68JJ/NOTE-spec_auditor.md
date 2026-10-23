# Записка spec_auditor 01M5KBGK8ZZ3Y8CDBXK6RX68JJ

## Выяснено
- Факты SPEC о коде подтверждены: tests/test_suite_run.py:333-346, orchestrator/acceptance.py:37-67, :2578-2579, orchestrator/stack.py:587-626, test_integrity.py:1074.
- Сценарий требования 2 статически красный на прежнем теле: под подменой subprocess.run ответ git «1 passed…» даёт _main_copy_root = рабочая копия, venv там нет → /fake/bin/python; ожидание вне подмены — <главный>/.artel/venv/bin/python3.
- config.VENV_DIR песочница TmpRootTest не подменяет (tests/sandbox.py:90-99) — внешняя подмена VENV_DIR доживает до внутреннего теста.
- recommended_budget_usd(7 AC, 1 зона) = $40 (config.py:644-650), не $25; calibration_warning сработает (25 < 40·2/3).
- Гейт зон пропускает config.COMMON_ZONES (config.py:814: orchestrator/config.py, tests/) — утверждение SPEC:124 про config.py и tests/sandbox.py неверно.
- answer в spec_gate принимает мандат тестов (orchestrator/answer.py:428-437).

## Не сработало
- Живой прогон сценария через python -c — запрос подтверждения, не выполнен.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Нет быстрого способа прогнать одноразовый скрипт в шаге без записи в рабочий каталог.
