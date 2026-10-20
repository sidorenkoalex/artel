# Записка reviewer (итерация 1)

## Выяснено
- test_id = `комп:путь::имя[#n]`; `covering` берёт `rest = cid.partition(":")[2]` — корректно.
- Исходы полного набора: GREEN/RED/TIMEOUT/NO_TESTS/NOT_STARTED; «неизвестно» мапится в NOT_STARTED (`acceptance._full_suite_outcome`) — гейт отказывает подготовкой, fail-open нет.
- Запись из нескольких компонентов: `decide` даёт refusal (PROFILE_UNREAD multi) — гейт не создаётся.
- Юниты 12 passed; долгоживущий сквозной файл 23 passed (205 с); plank-run 3 passed; карта свежая.
- Временные мутации compare (две находки у id) и covering (без сверки символа) ловятся юнит-тестами.

## Не сработало
- Ничего.

## Где остановился
- REVIEW.md итерации 1 записан: approved, реестр пуст (guard.registry_errors — []).

## Чего не хватило
- Дольше всего искал, какие исходы может вернуть `acceptance.full_suite` (acceptance.py:2306-2440) — нужно, чтобы исключить fail-open гейта.
