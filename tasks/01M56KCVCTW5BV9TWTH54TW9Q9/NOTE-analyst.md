# Записка analyst — 01M56KCVCTW5BV9TWTH54TW9Q9

## Выяснено
- Второй возврат из spec_gate 18.10 (по второму аудиту) — внесены все три решения, итерация 3; 7 AC, budget 35, status ready, guard ок.
- (1) Требование 3 / AC-5 — только pytest-own; у pult-pytest FileNotFoundError доходит до вызывающего (tests/test_acceptance_pycache.py:73-98: run, collect, run_full_suite). Добавлено в «Не входит».
- (2) Каталог прогона — необязательный параметр _place_env/_own_env; two_sided._run_side (two_sided.py:242, вне зон, не правится) его не передаёт → для относительного command[0] с `/` шаг (б) пропускается; записано в треб. 1 и AC-3.
- (3) AC-7: os.environ + PYTHONUNBUFFERED (_run_full_suite_to_log, acceptance.py:1592) + PYTHONPATH/REPORT_ENV (two_sided) + наличие ключа PYTHONPYCACHEPREFIX.
- Ранее: каналы отказа по местам — run/collect `(False, текст)`, run_repeat `RedTest`, run_plank `REFUSED_EXIT_CODE`, полный прогон `FULL_SUITE_NOT_STARTED` (не кешируется).

## Не сработало
- `ls` в Bash недоступен (command not found) — пользоваться Read/sed.

## Где остановился
- SPEC сдан, guard ок.

## Чего не хватило
- Ничего.
