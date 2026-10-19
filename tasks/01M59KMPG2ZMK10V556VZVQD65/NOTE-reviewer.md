# NOTE-reviewer (итерация 1)

## Выяснено
- Планка (`plank-run`): 25 passed. Долгоживущий файл, `tests/test_guard_plank_rule_parsing.py` и сторож предпроверки: 40 passed. Сторож не тронут.
- Временные мутации (якорь `TEST_CALL_HEAD`, пропуск строк в `_closing_paren`) тесты поймали. Код возвращён.
- `conftest.py`/`PASSPORT.md` посторонние и по regex main (`guard.py:2484`), поэтому `DEFAULT_PLANK_RULE.component_of` не меняет поведение артели.
- Не замечание: `_closing_paren` не пропускает комментарии. Апостроф в `//` внутри таблицы `.each` даёт ложное «нет теста» — ошибка fail-closed, кандидат в G2б.

## Не сработало
- Ничего.

## Где остановился
- REVIEW.md итерации 1 заполнен: approved, реестр пуст.

## Чего не хватило
- Чтобы закрыть сомнение про `conftest.py` в чекпоинте артели, пришлось искать regex `ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL` — в пакете его не было.
