## Выяснено
- ТЗ достаточно, SPEC.md написан (status: ready, 5 AC, budget 25, zones: orchestrator/config.py, tests/). Guard: ок.
- Факты ТЗ сверены с кодом: `orchestrator/config.py:1007` `CORE_REFERENCE_MAX_BYTES = 32_768`; предел читают `brief.py:1143` (`_core_reference_part`) и `projects.py:112`; `brief.CORE_REFERENCE_LABEL` — `brief.py:117`.
- Существующие тесты предел берут из config и подменяют его (`mock.patch.object(config, "CORE_REFERENCE_MAX_BYTES", ...)`), литерала 32768 в утверждениях нет, есть только в докстринге (`test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py:582`). Раздел «Меняемое поведение» не нужен.

## Не сработало
- Первый прогон guard отказал: сработал сигнал числа файлов. Его дали пути только для чтения из «Не входит». Добавил «Оценку объёма» с обоснованием монолита и строкой «Прогноз диффа: 12 КиБ».

## Где остановился
- Шаг закончен.

## Чего не хватило
- Не проверял, нет ли в tests/test_reference_command.py и tests/test_merge_reference_step.py скрытой опоры на фиксированный размер справочника больше 16 КиБ без подмены предела: grep этих файлов требовал подтверждения.
