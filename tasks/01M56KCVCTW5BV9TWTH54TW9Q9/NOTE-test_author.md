## Выяснено
- Все 7 AC — свойства кода: планка целиком из долгоживущих файлов tests/test_01m56kcvctw5bv9twth54tw9q9_*.py; acceptance_tests/ пуст (plank-run отвечает «планки нет» — штатно).
  - own_run_path: AC-1 (настоящий прогон, PATH = только каталог интерпретатора), AC-2, AC-3 (PATH из env подменённого subprocess по 8 местам).
  - summary_deselected: AC-4 (чистые функции).
  - missing_command: AC-5 (8 мест, абсолютный путь и голое имя; pult-pytest FNF наружу; нет каталога лога), AC-6 (full_suite: NOT_STARTED, кеш пуст, потом обёртка появилась → прогон заново, третий — из кеша).
  - pult_pytest_unchanged: AC-7, зелёный с рождения.
- Валидация стабом в orchestrator/acceptance.py: 11 passed, 97 subtests; стаб откачен (git checkout). preflight — всё «пройдена».
- Ожидаемый текст отказа — литерал «команда профиля <command[0]> не найдена» без кавычек вокруг имени.
- Хвост PATH сверяется через realpath(join(cwd вызова, элемент)): относительный элемент, разрешаемый от workdir, тоже засчитан.

## Не сработало
- Bash шага: голые ls/cat недоступны (PATH роли), `$VAR` в команде требует подтверждения — только python3/grep/sed/git.

## Где остановился
- Шаг завершён: 4 файла в tests/, записка обновлена.

## Чего не хватило
- Образец мест PLACES нашёлся сразу (tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py); карту кода не регенерировал — правка docs/ вне tests/ откатилась бы.
