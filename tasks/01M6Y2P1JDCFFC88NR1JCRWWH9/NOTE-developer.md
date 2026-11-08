# Записка developer

## Выяснено
- Долгоживущие тесты: tests/test_01m6y2p1jdcffc88nr1jcrwwh9_shared_state_rules.py (статика, 107) и …_construct_failure.py (подпроцесс, 2) — все 109 зелёные.
- Сделано: tests/sandbox.py `_SharedModuleState.construct` (sb=None до try); scripts/guard.py — `_shared_readonly_calls`, `_Fixture.shared`, `_fixture_table`, `_FixtureScope.records` (без параметров build), `_changed_fixture_names`, `_shared_state_violations`, `_SandboxRefs`, `_sandbox_class_names`, `sandbox_sources` у `pytest_style_errors_from_files`, поле `_StyleViolation.statements` (освобождение lint_base требует присваивание в базе), `_size_rules_apply` + `PLANK_LABEL_RE`.
- Свой тест: tests/test_guard_shared_readonly_rules.py (3 теста, мутации проверены — краснеют).
- Затронутые существующие тесты (guard-фикстуры, assertion_changes, size rules, preflight, tests_writing, network, test_lint и др.) — зелёные.
- Приложения 1–2 в PLAN.md: `git apply --check` — 0; guard PLAN.md — ок.

## Не сработало
- `pytest -n 4` по списку файлов — сторож роли считает это полным прогоном; без `-n` пачками по ~10 файлов проходит.

## Где остановился
- Шаг завершён, PLAN.md status: ready.

## Чего не хватило
- —
