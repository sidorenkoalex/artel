# Записка spec_auditor

## Выяснено
- Круг 2 (spec_sha 008324d5): решения Оператора 1–6 внесены в SPEC полностью; факты amend.py:222-232/386-397/1011-1016/1106-1116/1372-1378 верны.
- Новые находки: (1) обход требования 1 — `seeded = pytest.fixture(scope="module")(f)` присваиванием: pytest строит один раз на модуль (опыт в tmp: 2 passed, второй тест видит тот же объект), `_fixture_decorator` (guard.py:1985) смотрит только декораторы; (2) классы песочниц живут и в `tests/*_sandbox.py` (ReportSandbox(RealGitSandbox), OutcomeGateSandbox…, test_lint.SANDBOX_SOURCE_PATH, guard.sandbox_sources_from_dir), а определение решения 3 — только `tests/sandbox.py`; импорт `tests.*` долгоживущим разрешён; (3) создание песочницы не вызовом класса (`cls = RealGitSandbox; cls()`, `tests.fixtures._sandbox(RealGitSandbox)`) мимо правила «вызов-создание»; (4) «содержит /acceptance_tests/» снимет размер с долгоживущего файла внешнего проекта с сегментом `<dir>/` = acceptance_tests (is_long_lived_test_path); (5) ссылка решения 3 на guard.py:2127-2153 — это `requested` теста, а разбор фикстур, берущих фикстуры, — `records.trace` :2163-2177, одним уровнем.
- Существующие тесты не ломаются: `shared_readonly(`/`scope=` только в строках образцов.

## Не сработало
- Bash с несколькими командами и `$var` отклоняется — по одной команде.

## Где остановился
- SPEC-AUDIT.md сдан, verdict concerns.

## Чего не хватило
- Перечня модулей песочниц (`tests/*_sandbox.py`) в SPEC/карте — нашёлся через test_lint.SANDBOX_SOURCE_PATH.
