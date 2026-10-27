# Записка analyst — 01M5XZSKK8H096FD3CPN05BQNM

## Выяснено
- ТЗ достаточно: это часть 2 деления 01M5XX9PW3K206Q3EKQCT649QF; требования 5–7 и AC-14…AC-24 SPEC родителя (`git show refs/artifacts/01M5XX9PW3K206Q3EKQCT649QF:tasks/01M5XX9PW3K206Q3EKQCT649QF/SPEC.md`) перенесены в SPEC с перенумерацией AC-1…AC-11.
- «Часть 1» из строки «Порядок» = 01M5XZSKK8GZTECA2KWAFHE029 (по `artel.py show`), в merge_after — она и 01M5WDB7JY0VJGHVKCABA2QC5T.
- Строки кода из ТЗ сверены с main: outcome_integrity.py :185/:407/:672/:739/:769/:785/:793/:813/:897/:925/:1143/:1153, reporters/outcome.py :43/:80/:106/:145 — совпадают.
- Полей `full_suite`/`ci_job` в project_profile.py на main ещё нет — их даёт часть 1 (отсюда merge_after).
- Бюджет 40 = рамка Оператора (дефолт задачи), класс «до 15 AC» дал бы 45 — вниз от дефолта только.

## Не сработало
- В шелле шага нет `ls`/`cat`; grep с `cd` в составной команде требует подтверждения — абсолютные пути работают.

## Где остановился
- SPEC.md написан, status: ready, guard прогнан.

## Чего не хватило
- id части 1 пришлось брать из `artel.py show` — в ТЗ стоит «после части 1» без id.
