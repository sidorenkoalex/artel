# Записка test_author — 01M5KBGF184B07SVXMD4R1NXXC

## Выяснено
- Критерии требуют закрытых имён (`_maybe_autogate_acceptance`, подмена `_autogate_conditions`, `acceptance._full_suite_timeout_note`/`_not_started_note`/`_db_in_tree_note`, `canary._acceptance_from_steps`). Статика долгоживущего файла tests/ их запрещает, поэтому вся планка лежит в acceptance_tests/ с «Группа: разовый»; долгоживущих файлов tests/ нет.
- Файлы: `_scenario.py` (песочница SchemaConnTmpRootTest, задача T001 в acceptance, подмены по треб. 5, вывод через redirect_stdout); `test_env_refusal_record.py` (AC-1, AC-2: красные, второй записи нет); `test_refusal_preserved.py` (AC-3, AC-4, AC-5: зелёные с рождения); `test_refusal_class_producers.py` (AC-6: красный, функции нет; держатели замка и предел берутся из random, зерно печатается).
- Проверка временным стабом (константы + функция + ветка в `_maybe_autogate_acceptance`): 6 passed; стаб снят через `git checkout`, дерево чистое.
- Без стаба plank-run: 26 failed (AC-1, AC-2, подтесты AC-6), 4 passed. preflight: все проверки пройдены.

## Не сработало
- Составные bash-команды (cp && python, for, xargs) песочница не пропускает: стаб ставил через Edit, снимал через `git checkout`.

## Где остановился
- Шаг завершён: планка готова, preflight зелёный.

## Чего не хватило
- Правило «в долгоживущем файле только публичные имена» не стыкуется с SPEC, который разрешает подменять закрытые имена (треб. 5) и при этом рассчитывает на долгоживущие тесты («Не входит»).
