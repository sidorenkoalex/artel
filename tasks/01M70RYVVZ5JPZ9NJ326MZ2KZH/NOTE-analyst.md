## Выяснено
- Факты ТЗ сверены с кодом: `orphans.py:62-83` (`continue` при cwd None на :76-77), `hung_test_watchdog.py:68-81` (`_process_cwd`), вызов сторожа `:172`. `doctor/__init__.py:177` реэкспортирует `_process_cwd` — файл только для чтения, имя `_process_cwd` должно остаться.
- `_temp_owner_alive` (orphans.py:115-118) вызывается и сторожем зависших (hung_test_watchdog.py ~:177) — fail-closed в `_live_suite_run_in` действует и там.
- `prune.py::_run_pid_alive` повторяет разбор run.json — вне зон.
- SPEC: AC-1..AC-5; AC-6 ТЗ (существующий тест зелёный) перенесён в «Не входит» как «держит пульт». AC-5 несёт поверхность `orchestrator.doctor.hung_test_watchdog.process_cwd(pid, executable)` (новое публичное имя). guard ок.

## Не сработало
- git grep по refs/artifacts с подстановкой команд отклонён песочницей.

## Где остановился
- SPEC.md написан, status: ready, guard пройден.

## Чего не хватило
- Образца формы маски тестов в zones у прежних SPEC — взял `tests/test_01m70ryvvz5jpz9nj326mz2kzh_*.py`.
