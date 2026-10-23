# Записка ревьювера, итерация 2

## Выяснено
- R1-F1 закрыто: `tests/test_fsm_autogate_env_refusal.py` (4 метода) — сторож классификатора и ветки отказа; мутации M1–M3 красят заявленные методы.
- Тесты: 35 passed (test_fsm_autogate*, test_canary_acceptance_reason); планка 6 passed; карта свежа.

## Не сработало
- Мутация правкой файла (cp/python write) — требует подтверждения. Сработало: `python3 -c` с `mock.patch.object(fsm_autogate, ...)` и запуском unittest модуля теста.

## Где остановился
- REVIEW.md итерация 2: approved, реестр R1-F1 accepted.

## Чего не хватило
- Ничего существенного.
