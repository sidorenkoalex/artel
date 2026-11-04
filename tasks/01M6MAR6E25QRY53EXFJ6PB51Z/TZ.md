---
task: 01M6MAR6E25QRY53EXFJ6PB51Z
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Отчёт JUnit: путь теста в каталоге на точку (планка внешнего проекта)

# Отчёт JUnit: путь теста в каталоге, имя которого начинается с точки

## Факты

1. pytest в формате xunit2 (по умолчанию) не пишет атрибут `file`; путь теста восстанавливается из `classname` — путь модуля, где `/` заменены точками. Каталог планки внешнего проекта обязан начинаться с точки (`orchestrator/plank_layout.py:151`, `LAYOUT_PARENT_NOT_HIDDEN`), поэтому `classname` несёт две точки подряд: `tests..artel-plank.<id>.test_x`.
2. `orchestrator/reporters/outcome.py:106-134` (`_junit_location`) делит `classname` по каждой точке (`:117`): сегмент `.artel-plank` теряет точку, файл не находится, и путём записи становится всё точечное имя (`:123-124`). Тот же разбор — `_forge_location` (`orchestrator/reporters/outcome.py:256-268`, `:262`).
3. Гейт сопоставляет записи с файлами планки точным путём (`orchestrator/advance_gates/acceptance.py:251-257`, `:335-348`): тесты планки внешнего проекта с `plank_layout` в каталоге на точку для гейта «нет в отчёте» — «честный FAIL_TO_PASS» отказывает, хотя тесты исполнены (случай 05.11, задача sled 01M6M84AT1R5T058NGV0JD0CCJ; обход — `report_args` с `-o junit_family=xunit1` в локальном слое).
4. Тесты пульта подают поддельный отчёт с атрибутом `file` (`tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py:392`), поэтому разбор `classname` с каталогом на точку не проверен.

## Требуется

1. `_junit_location` и `_forge_location` делят `classname` так, что точка сразу после другой точки — начало имени каталога, а не разделитель: `tests..artel-plank.<id>.test_x` → `tests/.artel-plank/<id>/test_x.py`. Прочие `classname` (без двух точек подряд) разбираются как сейчас.
2. Путь с атрибутом `file` — как сейчас.

Критерии приёмки:
- отчёт настоящего pytest (xunit2, без `file`) для файла `tests/.artel-plank/<id>/test_x.py` во временной песочнице: запись получает путь `tests/.artel-plank/<id>/test_x.py` и имя `test_…`; гейт FAIL_TO_PASS сопоставляет её с файлом планки (`plank_layout` внешнего проекта в песочнице);
- то же для `_forge_location` (отчёт задания CI с тем же `classname`, дерево файлов с этим путём);
- `classname` без двух точек подряд, с классом теста (`tests.test_m.TestK`) и с путём через `/` — прежние путь и имя;
- прежние тесты разбора отчётов зелёные без правки.

Безопасность тестов: временная песочница пульта, настоящий pytest только во временном каталоге с минимальным файлом; без сети; без настоящих клонов проектов и локального слоя.

Существующие тесты: правка не должна сделать красным ни один существующий тест; если краснеет — эскалация с именем теста, без правки.

Зоны: `orchestrator/reporters/outcome.py` (`_junit_location`, `_forge_location`), `docs/codebase-map.md`, `tests/` (долгоживущие файлы задачи).

Только чтение: `orchestrator/plank_layout.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`.

Не входит:
- снятие обхода `junit_family=xunit1` в локальном слое проекта — Оператором после мержа;
- прочие форматы отчётов.

Приоритет 1.

Рамка: $20. Набор моделей — по умолчанию.
