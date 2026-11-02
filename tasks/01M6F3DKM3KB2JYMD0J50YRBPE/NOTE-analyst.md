# NOTE analyst

## Выяснено
- Итерация 2 (возврат из spec_gate): Оператор решил 6 пунктов аудита (Е1, Г1/Е2, А2, В2, В1, А1) — см. «Причина возврата» брифа.
- `auto`: опрос `verifying` — `orchestrator/auto.py:1080-1100`; надзор эпика — `_epic_view` `auto.py:1280`, статус «ждёт Оператора» `_WAITING` для `EPIC_GATE_STATES`/`escalated` (`:1308`), `_NOT_HOLDING_STOP_STATES` `:1170`.
- `CountersNeverResetTest.COUNTERS` — `tests/test_invariants.py:1613`; `review_iters` — `schema.py:184`.
- Факты итерации 1: `fsm_advance.verifying` `:442`, `LIMIT_REVIEW_ITERS` `config.py:330`, `board.waiting_on` `board.py:27`.

## Не сработало
- `ls` в Bash нет; составные команды требуют подтверждения — только grep/Read с абсолютными путями.

## Где остановился
- SPEC итерации 2 записан (17 AC, status: ready, зоны + auto.py, budget 40, merge_after 01M6BMG29KZV1RX21HFAXZG3CM, раздел «Матрица неослабления»); guard — ок. Шаг завершён.
- Толкование п. 5 возврата при двух проверках: журнальная запись «ждёт проверки» — одна на голову (первая неотмеченная), предусловие verify-ok — наличие такой записи по текущей голове для любого имени профиля; строка `status` после отметки `a` называет `b` (AC-10).

## Чего не хватило
- Б1 аудита (поле `verify` в плоской записи артели, `_flatten`) Оператор не решал — оставлено формулировкой ТЗ.
