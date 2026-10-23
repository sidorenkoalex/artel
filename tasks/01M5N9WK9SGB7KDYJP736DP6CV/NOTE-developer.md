# Записка developer — 01M5N9WK9SGB7KDYJP736DP6CV

## Выяснено
- Всё в `scripts/guard.py`: блок «Фикстуры pytest» перед `test_assertions` (`_pytest_aliases`/`_pytest_name`, `_FixtureDatum`, `_FixtureScope`, `_fixture_helper_calls`), `_changed_fixture_names` рядом с `weakened_helpers`, вид записи в `_assertion_kind`/`_constant_roles`, `pytest_style_errors_from_files` (вызов в `long_lived_errors_from_files` под `network_addresses`).
- Итерация 2 (R1-F1): у артели `_HelperScope.function` по импорту видит только `tests/sandbox.py`; для фикстур добавлен `_fixture_helper_calls` — функция любого модуля `tests/` по импорту, происхождение записи — файл помощника. `weakened_helpers` теперь называет функции модуля с иной последовательностью литералов (не всё тело — чтобы правки sandbox без данных не расширяли поиск).
- Поиск вызывающих вне диффа в `test_integrity.py` — один шаг по имени (+ цепочка наследников классов); цепочка «помощник → общая фикстура вне диффа → тест» не ловится, записано в «Рисках» PLAN.
- Проверено: 325 тестов (задача + затронутые узлы) зелёные, plank-run 2/2, обе новые заявки мутации краснеют.

## Не сработало
- `cat`, `ls`, `cd ...; cmd` в шелле недоступны/требуют подтверждения — Write/Edit и `python3 -c`.
- `-n 4` (xdist) в шаге падает «node down» — гонять последовательно.

## Где остановился
- Итерация 2 сдана: PLAN.md status: ready, R1-F1 размечен fixed в REVIEW.md, карта регенерирована. Код не закоммичен — коммитит пульт.

## Чего не хватило
- Штатной команды «прогон файла tests/ с временной мутацией» — мутировал правкой guard.py и возвращал.
