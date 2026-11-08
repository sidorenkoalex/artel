# Записка analyst

## Выяснено
- Шаг 1: ТЗ полное, SPEC написан (7 AC, бюджет 40, монолит). Адреса: `scripts/guard.py` `_style_violations:4618`, `_fixture_decorator:1985`, `_fixture_table:2036`, `_fixture_helper_calls:2228`, `long_lived_errors_from_files:4399`, `long_lived_plank_errors:4967`; `tests/sandbox.py` `construct:2534`, `shared_readonly:2568`.
- Шаг 2 (возврат с spec_gate, 6 решений): внесены все.
  - Р1 → требование 6: в `amend-tests` правила только на долгоживущих файлах; планка там — только линт детерминизма (amend.py:222-232 и др.), «Не входит» и копилка — оба пути.
  - Р2 → требование 2: одна форма присваивания, шесть форм импорта, отказ «иной вызов shared_readonly …»; AC-2 по случаю на форму.
  - Р3 → требование 3: транзитивные обёртки над фикстурами tests/fixtures.py, вызов `RealGitSandbox()`, наследование через локальные классы; класс песочницы = транзитивно от `TmpDirTest` (sandbox.py:711) / `TmpRootTest` (:1609); FakeProc не песочница. AC-4 новые случаи.
  - Р4 → «вторая общая фикстура в модуле», AC-4.
  - Р5 → AC-3 случай с помощником build, мутация в AC-7.
  - Р6 → метка `acceptance_tests/…` или содержит `/acceptance_tests/`; строка матрицы; текст отказа для не литерала scope.
- `orchestrator/amend.py` упомянут — добавлен в «только чтение» (guard требовал классификации).

## Не сработало
- `echo rc=$?` в Bash отклоняется разборщиком (simple_expansion).

## Где остановился
- SPEC.md status ready, guard ок.

## Чего не хватило
- —
