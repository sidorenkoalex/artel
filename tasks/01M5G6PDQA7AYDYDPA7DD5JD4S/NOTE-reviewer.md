## Выяснено
- Итерация 2: approved. R1-F1 исправлен: `_AutoClosingConnection.close()` выводит соединение из `_TRACKED`; мутация (close без pop) краснит оба теста `tests/test_store_db_tracking.py`. R1-F2 исправлен.
- Затронутые тесты 14 passed, планка 23 passed (154 с), карта свежа.
- Риск повторного входа в `_TRACKED_LOCK` из чужого финализатора: в `orchestrator/` других `__del__`/`closing(db())` нет.

## Не сработало
- heredoc в Bash отклоняется — python гонять через `python3 -c "..."`.

## Где остановился
- REVIEW.md (iteration 2, approved) записан, реестр закрыт целиком.

## Чего не хватило
- Ничего существенного.
