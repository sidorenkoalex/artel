# NOTE-reviewer (итерация 1)

## Выяснено
- Вердикт approved, реестр пуст. Планка 5 passed; долгоживущий fail_to_pass 52 passed (143 с); bans/refusal_classes/preflight/labelled_gates 58 passed.
- Правка существующего метода G2б-1 (labelled_gates::test_ac5_…) — только подготовка: опора SPEC и Popen с отчётом провала. Ассерты не тронуты, сверено с base.
- Временные мутации в guard._object_keys и record_criterion — тесты tests/test_guard_plank_bans.py ловят.
- Не ловится запретами: `it.each\`…\`(…, 5000)` (шаблонная таблица) и `suite('AC-1: …')` — вне буквы SPEC, записано в «Предложения системе».

## Не сработало
- `pytest -n 6` по файлу fail_to_pass — xdist «node down»; гонял с `-p no:xdist`.
- В Bash нет `rm` (zsh eval) — удалял через python os.remove.

## Где остановился
- REVIEW.md записан, шаг завершён.

## Чего не хватило
- Долго искал, где у приёмки ветки лежит планка (acc_tdir): `acceptance.plank_in_code_copy` в `_acceptance_run_body`, то есть внутри run_cwd.
