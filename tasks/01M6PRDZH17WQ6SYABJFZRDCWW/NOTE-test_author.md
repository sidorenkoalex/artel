# Записка test_author

## Выяснено
- Все AC-1…AC-5 — долгоживущие: один файл `tests/test_01m6prdzh17wq6syabjfzrdcww_docker_config_sandbox.py`, `acceptance_tests/` пуст (plank-run говорит «планки нет» — ожидаемо, preflight пройдена целиком).
- Guard запрещает в долгоживущем файле только id СВОЕЙ задачи; импорт `from tests import test_01m6paj61d4pyap79adrpa6mwv_compose_docker as compose_docker` законен.
- Функция берётся через атрибут модуля (`compose_docker.docker_config_sandbox`) — в красной фазе каждый тест падает AttributeError, а не весь файл на сборке.
- AC-5 разбирает `Path(compose_docker.__file__)` через ast: ищет `<имя> = docker_config_sandbox()`, `setenv("DOCKER_CONFIG", str(<имя>))`, `setenv("HOME", str(<имя>.parent))`, `real_git.addCleanup(shutil.rmtree, <имя>, …)`, отсутствие `mkdtemp`.
- Валидация стабом (helper + замена строки :314) — 7 passed; мутации «HOME до помощника» и «HOME не от результата» — красно. Стаб откатан, исходный файл не тронут.

## Не сработало
- heredoc python в Bash отклонён фильтром (кавычки в фигурных скобках) — использовал временный файл и task-rm.

## Где остановился
- Шаг завершён: тесты красны по правильной причине, preflight пройдена.

## Чего не хватило
- Ничего существенного.
