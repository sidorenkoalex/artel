# Записка analyst — 01M56KCVCTW5BV9TWTH54TW9Q9

## Выяснено
- Возврат из spec_gate 18.10: Оператор принял все 5 предложений SPEC-AUDIT. SPEC переписан (итерация 2): 7 AC, budget 35 (рамка ТЗ), zones прежние, status ready, guard ок.
- (1) Отказ «команда профиля <имя> не найдена» — каналом отказа workdir каждого места: run/collect `(False, текст)`, run_repeat `RedTest`, run_plank `REFUSED_EXIT_CODE`, 3 пути полного прогона — префикс `FULL_SUITE_NOT_STARTED` (не кешируется, acceptance.py:2028 до save_suite_result :2038). Отдельный AC-6 про некеширование.
- (2) AC-2 и AC-5 — по каждому из 8 мест PLACES (tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py:62-65); two_sided — свой текст «pytest не запустился: …».
- (3) command[0]: не найден — (б) пропускается без падения; относительный с `/` — от workdir (AC-3).
- (4) Формулировка: одинаково наличие каталогов (б)/(в), не PATH целиком.
- (5) AC-7 (артель pult-pytest): ожидание — литералы argv/cwd и os.environ + PYTHONPYCACHEPREFIX, не через _pytest_env/_place_env.

## Не сработало
- —

## Где остановился
- SPEC сдан, guard ок.

## Чего не хватило
- Ничего.
