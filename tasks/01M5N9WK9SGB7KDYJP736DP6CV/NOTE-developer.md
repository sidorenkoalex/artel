# Записка developer — 01M5N9WK9SGB7KDYJP736DP6CV

## Выяснено
- Всё в `scripts/guard.py`: блок «Фикстуры pytest» перед `test_assertions` (`_pytest_aliases`/`_pytest_name`, `_FixtureDatum`, `_FixtureScope`), `_changed_fixture_names` рядом с `weakened_helpers`, вид записи в `_assertion_kind`/`_constant_roles`, `pytest_style_errors_from_files` после `lint_errors_from_files` (вызов в `long_lived_errors_from_files` под `network_addresses`).
- Запись данных фикстуры: узел — подкласс `ast.AST` `_FixtureDatum(value=<литерал>)`; ключ — кортеж (файл, фикстура, номер, dump); происхождение `None` у своей фикстуры, ("фикстура <имя>", путь) у `tests/fixtures.py`.
- `tests/fixtures.py` читается лениво (только при промахе своего файла) и только по правилу артели — лишних git-чтений в гейте у unittest-тестов нет.
- Вызывающих вне диффа гейт ищет `git grep -w` по именам `weakened_helpers` — поэтому туда идут и фикстуры, вызывающие изменённого помощника / запросившие изменённую фикстуру.
- Проверено: 89/89 долгоживущих (6 повторов), plank-run 2/2, 519 существующих тестов затронутых узлов, мутации треб. 10 и своих 5 тестов (`tests/test_guard_pytest_fixtures.py`) краснеют.

## Не сработало
- `cd ...; cmd`, `ls`, `echo $?`, циклы bash требуют подтверждения — абсолютные пути, `python3 -c`/heredoc.
- `pytest.main` в процессе отказывает сторожем conftest, пока не выставлен `sys.argv = ["pytest", <файл>]`.
- `-n 4` (xdist) в шаге падает «node down» — гонять последовательно.

## Где остановился
- Шаг завершён: PLAN.md status: ready, guard ок, карта регенерирована. Код не закоммичен — коммитит пульт.

## Чего не хватило
- Штатной команды «прогон файла tests/ с временной мутацией» — собирал через подмену модуля в памяти.
