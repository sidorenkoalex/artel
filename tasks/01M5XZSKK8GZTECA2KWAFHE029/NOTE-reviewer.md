# NOTE-reviewer (итерация 1)

## Выяснено
- Долгоживущие файлы задачи + tests/test_ci_job_full_suite.py — 55 passed локально.
- targets.hosting_registry выставляет ci.py при импорте; `import orchestrator.forge` транзитивно грузит ci — реестр есть в любом процессе с forge; без forge проверка AC-3 при загрузке пропускается (риск назван в PLAN).
- Путь артели/local: условия вынесены в _ci_result_conditions дословно.

## Не сработало

## Где остановился
- REVIEW.md итерации 1 записан: approved, замечаний нет. `full_suite: null` отказывает; планки в refs/artifacts нет (plank-run — отказ «планки нет»); мутация ci.py ловится ac8[failed_clean].

## Чего не хватило
