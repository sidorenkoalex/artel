## Выяснено
- Итерация 1: approved, реестр пуст. Код: `targets.py` (виды runner/mapping, правило pytest-own, `secret_env_names()` с ленивым импортом), `project_profile.py` (поля Profile, env — MappingProxyType, hash=False).
- Затронутые тесты зелёные с PYTHONUNBUFFERED=1; карта свежа (только built_at_sha).

## Не сработало
- `plank-run` — отказ «планки нет»: у задачи нет test_*.py в планке, всё в долгоживущих tests/.

## Где остановился
- REVIEW.md записан, шаг завершён.

## Чего не хватило
- Тестов targets с именем `tests/test_targets*.py` нет — искать по `grep -rl targets.check tests`.
