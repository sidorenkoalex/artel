---
task: 01M6MZAEG0M8Q2GPBX4RSAK71Z
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Отчёт JUnit: путь теста в каталоге, имя которого начинается с точки

# Отчёт JUnit: путь теста в каталоге, имя которого начинается с точки

## Факты

1. pytest в формате xunit2 (по умолчанию) не пишет атрибут `file`; путь теста восстанавливается из `classname` — путь модуля, где `/` заменены точками. Каталог планки внешнего проекта обязан начинаться с точки (`orchestrator/plank_layout.py:151`, `LAYOUT_PARENT_NOT_HIDDEN`), поэтому `classname` несёт две точки подряд: `tests..artel-plank.<id>.test_x`.
2. `orchestrator/reporters/outcome.py:106-134` (`_junit_location`) делит `classname` по каждой точке (`:117`): сегмент `.artel-plank` теряет точку, файл не находится, и путём записи становится всё точечное имя (`:123-124`). Тот же разбор — `_forge_location` (`orchestrator/reporters/outcome.py:256-268`, `:263`).
3. Гейт сопоставляет записи с файлами планки точным путём (`orchestrator/advance_gates/acceptance.py:251-257`, `:335-348`): тесты планки внешнего проекта с `plank_layout` в каталоге на точку для гейта «нет в отчёте» — «честный FAIL_TO_PASS» отказывает, хотя тесты исполнены (случай 05.11 на внешнем проекте с планкой; обход — `report_args` с `-o junit_family=xunit1` в записи проекта локального слоя).
4. Тесты пульта подают поддельный отчёт с атрибутом `file` (`tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py:392`), поэтому разбор `classname` с каталогом на точку не проверен.

## Требуется

1. `_junit_location` и `_forge_location` делят `classname` по точкам так, что пустой сегмент (точка в начале `classname` или точка сразу после другой точки) не разделитель: точка присоединяется к следующему сегменту как начало имени каталога: `tests..artel-plank.<id>.test_x` → `tests/.artel-plank/<id>/test_x.py`, `.artel-plank.<id>.test_x` → `.artel-plank/<id>/test_x.py`. Имя каталога из двух и более точек в начале (`..x`) разбирается тем же правилом последовательно. Прочие `classname` (без пустых сегментов) разбираются как сейчас.
2. Путь с атрибутом `file` — как сейчас.

Критерии приёмки:
- отчёт настоящего pytest (xunit2, без `file`) для файла `tests/.artel-plank/<id>/test_x.py` во временной песочнице: запись получает путь `tests/.artel-plank/<id>/test_x.py` и имя — `name` отчёта без префикса модуля (`test_ok`); гейт FAIL_TO_PASS сопоставляет её с файлом планки (`plank_layout` внешнего проекта в песочнице);
- то же для `_forge_location` (отчёт задания CI с тем же `classname`, дерево файлов с этим путём);
- то же для файла `.artel-plank/<id>/test_x.py` в корне песочницы (`classname` начинается с точки) — для `_junit_location` и `_forge_location`;
- отчёт настоящего pytest для теста в классе `TestK` того же файла (`classname` `tests..artel-plank.<id>.test_x.TestK`): путь `tests/.artel-plank/<id>/test_x.py`, имя `TestK::test_…`; то же для `_forge_location`;
- отчёт xunit1 (с атрибутом `file`) того же файла, включая тест в классе: путь — из `file`, имя `TestK::test_…`, как сейчас;
- `classname` без пустых сегментов, с классом теста (`tests.test_m.TestK`) и с путём через `/` — прежние путь и имя;
- прежние тесты разбора отчётов зелёные без правки.

Безопасность тестов: временная песочница пульта, настоящий pytest только во временном каталоге с минимальным файлом; без сети; без настоящих клонов проектов и локального слоя.

Существующие тесты: правка не должна сделать красным ни один существующий тест; если краснеет — эскалация с именем теста, без правки.

Зоны: `orchestrator/reporters/outcome.py` (`_junit_location`, `_forge_location`), `docs/codebase-map.md`, `tests/` (долгоживущие файлы задачи).

Прочие разборщики `classname` (`_junit_node` и `_junit_file_times` в `orchestrator/acceptance.py`) каталог на точку уже обрабатывают — вне зоны.

Только чтение: `orchestrator/plank_layout.py`, `orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`.

Не входит:
- снятие обхода `junit_family=xunit1` в локальном слое проекта — Оператором после мержа;
- прочие форматы отчётов.

Приоритет 1.

Рамка: $20. Набор моделей — по умолчанию.
