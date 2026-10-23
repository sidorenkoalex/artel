# Записка analyst — 01M5KP57JXWKKKCJKY47HT21W8

## Выяснено
- ТЗ достаточно — пишу SPEC, без QUESTIONS.
- Место утверждений о скиле/образце (ТЗ, требование 5) выбрано: тест в `tests/`. Основание: приложения PLAN накладывают CI ветки (`scripts/plan_appendix_ci.py`, docs/operator-session.md:400), рубеж in_dev→verifying, автогейт, approve и `suite-run` (`orchestrator/appendix_tree.py::suite_tree`, вызовы fsm_autogate.py:417, fsm.py:1404, suite_run.py:677, advance_gates/acceptance.py:598) и ворота мержа (fsm_merge_gate.py:1168). Правило скила spec-authoring «сторож внутри приложения» опирается на «CI ветки идёт без приложений» — это устарело с SPEC 01M443HV9SJYVYQTHJSQ87QV68.
- Правка `test_ac7_external_reviewer_mission_keeps_suite_run` — смена вида утверждения (assertIn → assertNotIn + новые), в «Меняемое поведение» не годится; нужен мандат «Ослабление тестов разрешено:» в ANSWER с матрицей (docs/operator-gates.md:85). ТЗ: мандат дан, строку Оператор передаёт через `answer` на эскалации роли — эскалирует разработчик.
- Бюджет: ТЗ $20, пол калибровки `config.BUDGET_CALIBRATION_FLOOR_USD` = 25 → поставлен 25.

## Не сработало
- `sed` по относительному пути после `cd` — отказ разрешений; использовать Read/grep с абсолютным путём.

## Где остановился
- SPEC.md написан (status: ready, 9 AC), guard ок. Сигнал деления «число модулей» ложный (guard считает все упомянутые пути orchestrator/*.py) — секция заполнена обоснованием монолита, прогноз диффа 12 КиБ.

## Чего не хватило
- Какие гейты сейчас гоняют набор с приложениями PLAN — нашёл через grep `suite_tree` по orchestrator/.
