# Записка developer (итерация 2)

## Выяснено
- R1-F1: `scripts/guard.py::long_lived_errors_from_files` теперь передаёт проверке стиля `sandbox_sources or None` (`{}` вызывающих = «правила размера выключены» → классы песочниц из `config.ROOT`). Прямой `pytest_style_errors_from_files(…, {})` — пустой перечень, как требует AC-4.
- R1-F2: `_imported_names` понимает `import tests[.x]` без псевдонима и `import tests as p`; `_SandboxRefs.packages` — то же для классов песочниц.
- Новые тесты в tests/test_guard_shared_readonly_rules.py (5 всего), мутации проверены — краснеют. Долгоживущие файлы задачи + затронутые модули зелёные. Карта регенерирована.
- Реестр REVIEW.md: R1-F1, R1-F2 → fixed с описанием; PLAN.md шаг 6, status: ready; guard ок.

## Не сработало
- Bash с heredoc/`cp`/`$?` в одной команде отклоняется фильтром — мутации делал через Edit.

## Где остановился
- Шаг завершён.

## Чего не хватило
- —
