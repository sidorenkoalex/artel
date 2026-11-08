# Записка analyst

## Выяснено
- Шаг 1: ТЗ полное, SPEC написан (7 AC, бюджет 40, монолит).
- Шаг 2 (возврат с spec_gate, 6 решений): внесены все.
- Шаг 3 (возврат второго круга, 4 решения): внесены все.
  - Р1 → требование 1: любой вызов `pytest.fixture` с `scope=` (псевдоним модуля, присваивание `x = pytest.fixture(scope=…)(f)`); `scope=None` — без отказа. AC-1 новые случаи.
  - Р2 → требование 3: класс песочницы — из `tests/sandbox.py` и `tests/*_sandbox.py` (маска `test_lint.SANDBOX_SOURCE_PATH`, :290-296), транзитивно между файлами; параметр `sandbox_sources` у `pytest_style_errors_from_files` (сейчас его нет, guard.py:4725), `None` → `config.ROOT` (как `sandbox_sources_from_dir`, :4502). AC-4 новые случаи; поверхность AC-1/2/4 с `sandbox_sources=None`.
  - Р3 → псевдонимы класса и `shared_readonly`, вызов `tests.fixtures._sandbox` (fixtures.py:42), повторное создание класса `shared_readonly`; прочие обходы — «Не входит».
  - Р4 → требование 5: регулярное выражение `^(tasks/[^/]+/)?acceptance_tests/`; ссылка на разбор фикстур — `records.trace` guard.py:2163-2177; AC-6 случай с сегментом в середине пути.
- Маска `tests/*_sandbox.py` на диске ловит и `tests/test_sandbox.py`, `tests/test_01m6prdz…_docker_config_sandbox.py` (тестовые файлы) — так же, как у `test_lint`; не противоречит решению.

## Не сработало
- `ls` в Bash не найден (PATH роли); `echo rc=$?` отклоняется.

## Где остановился
- SPEC.md status ready, guard ок.

## Чего не хватило
- —
