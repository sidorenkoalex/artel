# Записка developer

## Выяснено
- Итерация 2 (ревью R1-F1): `_AutoClosingConnection.close()` теперь убирает соединение из `_TRACKED`
  (после `super().close()`, под `_TRACKED_LOCK`); `_close_abandoned` и `__del__` зовут
  `sqlite3.Connection.close` напрямую — иначе повторное взятие нереентерабельного Lock.
- Новый тест `tests/test_store_db_tracking.py` (2 метода), мутация (pass вместо pop) краснит оба: учёт 393 → 972.
- R1-F2 (`names = (`) исправлен. Реестр REVIEW.md размечен fixed.
- Планка 23/23 зелёная после правки; затронутые файлы (store fds, connection_close, lease, two_sided) зелёные.

## Не сработало
- Bash: составные команды (`for …; done`, `|| true`) требуют одобрения; pytest с тем же файлом трижды в одной команде дедуплицирует.

## Где остановился
- suite-run №2 оборван пределом 1500 с: 6391 passed, 3 упавших без сводки (spec_audit_flow::test_ac9,
  profile_callers::test_ac10 ×2); повтор упавших №3 — 3 passed. guard по PLAN.md — ок; PLAN.md status: ready. Шаг завершён.

## Чего не хватило
- Ничего существенного.
