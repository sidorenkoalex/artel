## Выяснено
- Итерация 1: changes_requested, одно замечание R1-F1 (major): требования 5, 7 и передача клона из ci_rerun.py/fsm_merge_gate.py (AC-7/10/11) сторожит только разовая планка test_callers.py; временная мутация всех мест — tests/ зелёные (61 passed).
- Код ci.py по требованиям 1-4 верен; планка 4/4, 10 файлов модулей 164 passed; карта свежа; дифф tests/ — только фикстуры по ANSWER-2.

## Не сработало
- pytest -n 8 в шаге — «node down» воркеров; гонять -p no:xdist.

## Где остановился
- REVIEW.md записан. Следующей итерации: проверить новые тесты tests/ на R1-F1 той же мутацией (fsm_merge_gate `if not ci.rerun_started` → `if False`; снять **project в ci_rerun.py).

## Чего не хватило
- Нет tests/-сторожа для записи flake-rate «повтор не запущен» — искал grep "повтор не запущен\|flake-rate" tests/.
