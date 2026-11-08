# Записка analyst

## Выяснено
- ТЗ полное: адреса сверены с кодом — `scripts/guard.py` `_style_violations:4618`, `_fixture_decorator:1985`, `_fixture_table:2036`, `_FixtureScope:2091`, `_fixture_helper_calls:2228`, `_changed_fixture_names:2349`, `assertion_changes:2873`, `long_lived_errors_from_files:4399`, `pytest_style_errors_from_files:4725`, `long_lived_plank_errors:4967`; `tests/sandbox.py` `_SharedModuleState.construct:2534`, `sb = self.sandbox_cls()` вне `try` на `:2539`, `shared_readonly:2568`.
- Тесты с «нет метки размера» (`tests/test_01m6xhjh6ej8d0br5prngzay8c_size_rules.py`, `..._size_gate_paths.py`) меток `acceptance_tests/` не используют — п. 5 ТЗ их ожидания не меняет (по grep).
- В `tests/` вне `sandbox.py` фикстур `scope="module"` нет (grep).
- SPEC написан: 7 AC, бюджет 40, монолит с обоснованием (сигнал budget ≥ 30).

## Не сработало
- —

## Где остановился
- SPEC.md ready, guard прогнан.

## Чего не хватило
- —
