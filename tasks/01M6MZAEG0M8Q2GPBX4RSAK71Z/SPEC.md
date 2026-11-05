---
task: 01M6MZAEG0M8Q2GPBX4RSAK71Z
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/reporters/outcome.py, docs/codebase-map.md, tests/test_01m6mzaeg0m8q2gpbx4rsak71z_*.py
budget_usd: 25
---

# SPEC: Отчёт JUnit: путь теста в каталоге, имя которого начинается с точки

## Контекст
pytest в формате xunit2 (по умолчанию) не пишет атрибут `file`, и путь
теста восстанавливается из `classname` — точечного пути модуля. Каталог
планки внешнего проекта обязан начинаться с точки
(`orchestrator/plank_layout.py:151`, `LAYOUT_PARENT_NOT_HIDDEN`), поэтому
`classname` несёт две точки подряд: `tests..artel-plank.<id>.test_x`.
`_junit_location` (`orchestrator/reporters/outcome.py:106-133`, деление —
`:117`) и `_forge_location` (`orchestrator/reporters/outcome.py:256-268`,
деление — `:263`) делят `classname` по каждой точке: сегмент
`.artel-plank` теряет точку, файл не находится, путём записи становится
всё точечное имя (`:123-124`). Гейт сопоставляет записи с файлами планки
точным путём (`orchestrator/advance_gates/acceptance.py:251-257`,
`:335-348`), и «честный FAIL_TO_PASS» отказывает тестам планки, которые на
деле исполнены (случай 05.11; обход — `report_args` с
`-o junit_family=xunit1` в локальном слое проекта). Тесты пульта подают
поддельный отчёт с атрибутом `file`
(`tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py:392`), поэтому
этот разбор не проверен.

## Требования

1. `_junit_location` и `_forge_location` делят `classname` по точкам так,
   что пустой сегмент (точка в начале `classname` или точка сразу после
   другой точки) не разделитель: точка присоединяется к следующему
   сегменту как начало имени каталога:
   `tests..artel-plank.<id>.test_x` → `tests/.artel-plank/<id>/test_x.py`,
   `.artel-plank.<id>.test_x` → `.artel-plank/<id>/test_x.py`. Имя
   каталога из двух и более точек в начале (`..x`) разбирается тем же
   правилом последовательно. Прочие `classname` (без пустых сегментов)
   разбираются как сейчас.
2. Путь записи при наличии атрибута `file` определяется как сейчас.

## Критерии приёмки

AC-1. Отчёт настоящего pytest (xunit2, без атрибута `file`) для файла
`tests/.artel-plank/<id>/test_x.py` во временной песочнице разобран
`_junit_location`: запись получает путь `tests/.artel-plank/<id>/test_x.py`
и имя — `name` отчёта без префикса модуля (`test_ok`); гейт FAIL_TO_PASS
сопоставляет её с файлом планки (`plank_layout` внешнего проекта в
песочнице).

AC-2. То же для `_forge_location`: запись отчёта задания CI с тем же
`classname` при дереве файлов, содержащем путь
`tests/.artel-plank/<id>/test_x.py`, получает путь
`tests/.artel-plank/<id>/test_x.py` и имя `test_ok`.

AC-3. Для файла `.artel-plank/<id>/test_x.py` в корне песочницы
(`classname` начинается с точки) и `_junit_location` (отчёт настоящего
pytest), и `_forge_location` дают путь `.artel-plank/<id>/test_x.py` и
имя `name` отчёта без префикса модуля.

AC-4. Для теста в классе `TestK` того же файла (`classname`
`tests..artel-plank.<id>.test_x.TestK`, отчёт настоящего pytest) и
`_junit_location`, и `_forge_location` дают путь
`tests/.artel-plank/<id>/test_x.py` и имя `TestK::test_…`.

AC-5. Прежний разбор сохранён: отчёт xunit1 (с атрибутом `file`) того же
файла, включая тест в классе, даёт путь из `file` и имя `TestK::test_…`;
`classname` без пустых сегментов — с классом теста (`tests.test_m.TestK`)
и с путём через `/` — даёт прежние путь и имя в `_junit_location` и
`_forge_location`.

## Не входит

- Снятие обхода `junit_family=xunit1` в локальном слое проекта — делает
  Оператор после мержа.
- Прочие форматы отчётов.
- Прочие разборщики `classname` (`_junit_node` и `_junit_file_times` в
  `orchestrator/acceptance.py`) — каталог на точку уже обрабатывают.
- Правка `orchestrator/plank_layout.py`, `orchestrator/acceptance.py`,
  `orchestrator/advance_gates/acceptance.py`,
  `orchestrator/advance_gates/tests_writing.py`,
  `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py` — только чтение.
- Зелёный набор существующих тестов `tests/` без их правки (критерий ТЗ
  «прежние тесты разбора отчётов зелёные без правки») — её держит пульт;
  покраснение существующего теста — эскалация с именем теста, без правки.

## Материалы

- Безопасность тестов (из ТЗ): временная песочница пульта, настоящий
  pytest только во временном каталоге с минимальным файлом; без сети; без
  настоящих клонов проектов и локального слоя.
- Бюджет: рамка ТЗ $20 ниже планки $25 (`config.BUDGET_CALIBRATION_FLOOR_USD`)
  — стоит планка; 5 критериев и 3 элемента зоны — нижний класс калибровки.
