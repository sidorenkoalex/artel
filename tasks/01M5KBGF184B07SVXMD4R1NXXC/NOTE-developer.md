# Записка developer — 01M5KBGF184B07SVXMD4R1NXXC

## Выяснено
- Итерация 1: правка только `orchestrator/fsm_autogate.py` (константы, `autogate_refusal_class`, ветка отказа) + карта.
- Итерация 2 (R1-F1): добавлен сторож `tests/test_fsm_autogate_env_refusal.py` (4 метода): сверка классификатора с производителями `acceptance.py` и вторая запись/строка только на отказе окружения. 33 passed по tests/test_fsm_autogate*.py; plank-run 6 passed. Мутации (литерал таймаута, сверка без «: машина занята», `or True` в ветке) красят тесты; код возвращён. R1-F1 размечен `fixed` в REVIEW.md, карта регенерирована.

## Не сработало
- `cat`/`ls`/`cp` и heredoc-правки в Bash требуют подтверждения — мутации делать через Edit.

## Где остановился
- PLAN.md status: ready; guard прогнан.

## Чего не хватило
- Ничего существенного: сценарий ветки отказа взят из `acceptance_tests/_scenario.py` планки.
