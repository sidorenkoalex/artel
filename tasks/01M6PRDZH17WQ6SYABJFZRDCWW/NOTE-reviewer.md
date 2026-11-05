## Выяснено
- Итерация 1: approved, реестр пуст. Diff — помощник `docker_config_sandbox` + одна строка в test_ac17; finally/skipif/утверждения не тронуты.
- CI=1: 12 passed, 1 skipped по двум файлам задачи. Мутации copytree / `in os.environ` / HOME до помощника — красные.

## Не сработало
- `plank-run` — отказ «планки нет» (в refs/artifacts нет test_*.py); критерии в долгоживущем tests/.
- bash с `${...}`/многокомандными строками отклоняется песочницей — мутации делал одним python-heredoc.

## Где остановился
REVIEW.md записан, approved.

## Чего не хватило
Ничего существенного.
