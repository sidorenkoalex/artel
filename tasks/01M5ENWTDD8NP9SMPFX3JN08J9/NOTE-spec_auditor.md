# Записка spec_auditor — 01M5ENWTDD8NP9SMPFX3JN08J9

## Выяснено
- Все места кода, названные в SPEC, сошлись с рабочим каталогом (role_prompt.py:70/80/201/237, project_profile.py:328/470, guard.py:494/2777-2779/2880, agent_log.py:221/239/354, runner.py:1619/1710, watch.py:221/288/446, report.py:99/947/969, plank_run.py:287-291, skills test-authoring:25-28, review-checklist:39/102).
- Существующие тесты не закрепляют прежний пункт 2 задания test_author у pult-vitest и «итог pytest» plank-run у vitest; тесты шаблона (template_hints.py:54-61) заводят pult-vitest БЕЗ plank_layout, и их задание test_author должно собираться.
- plank_rule даёт метку AC-<n>: любому компоненту с tests и командой не pytest, независимо от report и plank_layout (project_profile.py:497-503); выкладка по plank_layout только у компонента с report и plank_layout (acceptance.py:1328-1333, 1400-1406).
- Сигналы деления по guard.split_signal_names: + «затронут инвариантный механизм», «прогноз диффа не дан» — в SPEC не названы.

## Где остановился
Вердикт: concerns. Отклонения — в разделе «Вердикт» SPEC-AUDIT.md.

## Чего не хватило
Искал дольше всего, откуда берётся текст пункта 2 при пустом plank_layout: SPEC этого не определяет.
