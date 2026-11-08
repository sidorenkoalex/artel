# Записка developer 01M6XHJH6EJ8D0BR5PRNGZAY8C

## Выяснено
- Вызывающие guard: tests_writing `_tests_writing_long_lived_gate` (дерево — голова кодовой ветки через git, `project_profile.sandbox_sources_at`), preflight `_long_lived`/`_groups` (диск рабочей копии), amend `_long_lived_errors` и `_labelled_long_lived_errors` (рабочая копия — диск + lint_base голова ветки; --from-branch — git головы + `_locked_long_lived_texts`; помощник `amend._sandbox_sources`).
- Корни песочниц входят в перечень, только если определены в `sandbox_sources` (тест AC-6: проект без tests/sandbox.py — отказа нет).
- `pytestmark` с аннотацией распознаётся только правилами размера (`annotated=True`), разбор guard прежний.
- Приложения 1–3 из SPEC проходят `git apply --check` на ветке; с приложением 2 профиль артели читается с `size_marks: required`.

## Не сработало
- `pytest -n 8` в шаге роли: все воркеры «node down» — гонял пачками последовательно.

## Где остановился
- Готово: PLAN ready, guard ок. Долгоживущие файлы задачи 75+9 зелёные, тесты затронутых модулей зелёные (amend*, preflight*, labelled_gates, long_lived_imports, long_lived_transitions, project_profile*, docs_dir_layout, test_invariants, targets-тесты). Карта регенерирована.

## Чего не хватило
- Где взять дерево модулей песочниц на каждом пути (git головы vs диск рабочей копии) — пришлось читать amend целиком.
