# Записка test_author — 01M5KNXGEMBAC1QRNHY3KC14JR

## Выяснено
- AC-1..AC-8 — долгоживущий `tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py` (класс `PoolLeakSignsTest`, 10 методов, `random` с печатью зерна); AC-9 — разовый `acceptance_tests/test_ac9_tree_guard.py` (`git grep -E` по CODE_ROOT из `_pult`).
- Тесты подменяют `doctor.runner.in_role_environment` (side_effect от `self.role_env`), `Path.home` → временный каталог, `config.ROOT/DB/LOGS`.
- Метки шаблонов в фикстуре: `<!-- canary-guid: G -->` или строка `canary-guid: G` (выбор случайный); алерт 1в в тестах опознаётся по источнику `doctor.canary-pool-leak`, текст 1в проверяется только на «нет GUID, есть имя каталога».
- Стаб корректной реализации (регексы 1а/1б/1г + сбор меток `canary-guid:[ \t]*(\S*)`) зеленил все 11 тестов на 6 случайных зёрнах и не ломал `tests/test_doctor_canary_pool.py`; стаб откатан (`git checkout`).
- На текущем коде долгоживущий файл красен (AC-4 зелёна: прежняя голая подстрока её ловит); AC-9 зелёна с рождения.
- Bash песочницы отвергает `$` и циклы в командах — `git grep` с `$HOME` гонять через python3.

## Не сработало
- —

## Где остановился
- plank-run: 1 passed; preflight: все проверки пройдены. Шаг завершён.

## Чего не хватило
- —
