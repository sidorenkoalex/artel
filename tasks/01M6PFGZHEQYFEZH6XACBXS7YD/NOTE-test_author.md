# Записка test_author

## Выяснено
- Все AC-1–AC-9 — в одном долгоживущем файле `tests/test_01m6pfgzheqyfezh6xacbxs7yd_decision_equals_form.py`; каталог acceptance_tests/ планки пуст.
- `_cmd_reject` — закрытое имя, в долгоживущем файле запрещено: AC-4–AC-7 зовут `artel.main()` с argv `reject …` под фикстурой `tmp_root` (снимает признак роли), `fsm.cmd_reject` подменён, вызов сверяется через `inspect.signature(...).bind`.
- AC-8/AC-9 — `ComponentsOutcomeSandbox` по образцу `tests/test_01m6kb0sjhda4d4gnem7pgz40p_decision_reject.py` (new_task/cli скопированы).
- Стаб (`isascii() and isdigit()` в parse; разбор ключей в `_cmd_reject`: повтор → «ключ --decision повторён», затем пустое/`--` значение → «без значения», затем позиционная причина) — все 18 зелёные, плюс существующие тесты решения зелёные; стаб откатан.
- До реализации зелёные AC-3 и AC-7 (держат прежнее поведение).

## Не сработало
- `ls`/цепочки через `;` в Bash недоступны.

## Где остановился
Тесты написаны и провалидированы, preflight пройдена целиком. `plank-run` отказывает «планки нет» (в acceptance_tests/ нет test_*.py) — долгоживущий файл прогнан pytest напрямую: 16 красных, 2 зелёных (AC-3, AC-7).

## Чего не хватило
Правило «закрытое имя» для `_cmd_reject` из SPEC — пришлось идти через `artel.main()`.
