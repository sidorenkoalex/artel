# NOTE analyst — 01M6HGH8ZH5SQ5Z5X709Z69KYV

## Выяснено
- Требования 1–2 ТЗ уже в main задачей 01M5MVSP9YW0DYA4YQ1KSG0AHF (merge dd2dc628c + приложение 56aa10663, 23.10 22:28):
  `orchestrator/test_lint.py` (`findings`, `top_level_functions`); `tests/test_invariants.py:43,2443-2453` зовёт модуль;
  `scripts/guard.py::lint_errors_from_files` (:4509) вызывается из `long_lived_errors_from_files` (:4469) →
  `orchestrator/advance_gates/tests_writing.py::_tests_writing_test_groups_gate` (:483, :518) и `_tests_writing_long_lived_gate` (:643);
  действия «переход отклонён: группы приёмочных тестов» / «…долгоживущие файлы tests/» — ROLE_FIXES (`refusal_classes.py:116-117`).
- Канарейка 6e19ccb8 (23.10 00:24) — предок мержа dd2dc628c, т.е. краснела ДО появления гейта.
- Проверено руками: `guard.lint_errors_from_files` даёт «tests/test_x.py::T::test_a: строка 4: цикл до срока…» и «…путь к живому файлу репозитория…».
- Оговорка: линт идёт только при `network_addresses` (артель); для чужого проекта (в т.ч., возможно, пула канарейки) — нет.

## Не сработало
- —

## Где остановился
- Написан QUESTIONS.md (задача — дубль сделанного), SPEC не трогал.

## Чего не хватило
- В ТЗ нет ссылки на 01M5MVSP9YW0DYA4YQ1KSG0AHF; дубль нашёлся только по карте (`orchestrator/test_lint.py` уже в ней).
