# Записка аналитика

## Выяснено
- ТЗ достаточно — пишу SPEC (без QUESTIONS).
- Э0 (01M5TB6VDVV6AM8DWPGVQE8CDW) на ветке ещё нет: `fsm.STATES`, `fsm.TERMINAL_STATES`, `closed_as` не найдены grep'ом в orchestrator/ (есть только `cleanup.TERMINAL_STATES`, `watch._TERMINAL_STATES`). SPEC опирается на имена Э0; merge_after = Э0.
- Прямая краснота: `tests/test_multitarget.py:289` — `assertEqual(sorted(config.PROJECT_DIRS), ["knowledge","logs","tasks","worktrees"])`; добавление `epics` её краснит. Литерал — список, в «Меняемое поведение» не входит (только скаляры); оформлено отдельным разделом с матрицей по мандату ТЗ 25.10.
- Прочие тесты схемы (`test_observation_edges.py:25` issubset и т.п.) новой таблицей не краснеют.
- CLI в `orchestrator/artel.py` — ручной разбор (`_cmd_new(rest)` ~2266), флагов `--epic/--after/--as-epic` нет.
- Сигналы деления: 8 файлов зоны (без общих), >10 AC, бюджет 75 ≥ 60. Решение в SPEC — монолит (материал Оператору), бюджет = Рамка ТЗ $75 (рекомендация таблицы $85).

## Не сработало
- Составные bash-команды с `cd`/пайпами отказываются песочницей — только одиночные команды с абсолютными путями.

## Где остановился
- SPEC.md написан, status: ready, 18 AC, guard: ок. Класс красного теста — `TargetInitTest`.

## Чего не хватило
- Нет быстрого способа узнать, что Э0 ещё не в main и какие его имена появятся: искал `fsm.STATES`/`closed_as` grep'ом.
