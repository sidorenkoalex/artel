# Записка ревьювера, итерация 1

## Выяснено
- Планки у задачи нет: `plank-run` отказывает «нет файлов test_*.py», все тесты — долгоживущие (112 зелёных вместе с `tests/test_guard_shared_readonly_rules.py`).
- R1-F1 (major): `long_lived_errors_from_files` передаёт `sandbox_sources={}` проверке стиля как есть → пустой перечень классов песочниц; вызывающие (`tests_writing.py:651`, `amend.py:313`, `:1390`, `preflight.py:261`) отдают `{}` при профиле без `size_marks`. Указание Оператора п. 1 — `{}` → `config.ROOT`. Подтверждено пробой.
- R1-F2 (minor): `import tests` + `tests.sandbox.X` не распознаётся ни `_imported_names`, ни `_SandboxRefs`.
- Временные мутации (build в `_changed_fixture_names`; `sb is not None` в `construct`) тестами ловятся.

## Не сработало
- Bash heredoc с `'...'` и `{}` отклоняется фильтром — пробу писал файлом в каталог документов и убрал `task-rm`.

## Где остановился
- REVIEW.md сдан, `changes_requested`, реестр R1-F1, R1-F2 open.

## Чего не хватило
- Указание Оператора п. 1 внутренне расходится («как для правил размера», а размер читает `{}` пустым) — записано наблюдением в REVIEW.
