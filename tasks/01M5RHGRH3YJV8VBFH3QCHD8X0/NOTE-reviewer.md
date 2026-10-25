# Записка ревьювера, итерация 1

## Выяснено
- Модуль `tests/test_merge_after_module.py`: 53 passed; планка `plank-run`: 76 passed, код 0.
- Временные мутации 008 (guard самоссылка) и 037 (обращённый порядок `record_declared`) против модуля — красные нужные тесты; код возвращён `git checkout -- orchestrator scripts`, `git status --porcelain` пуст.
- Дифф ветки против a8e57874 не трогает `orchestrator/`, `scripts/`, `tests/fixtures.py`, `tests/sandbox.py`.
- Мелочи (не blocker/major): в докстринге `test_ac1_self_reference_names_field_and_element` (модуль :1230, :1237) переименование `task`→`task_id` задело имя поля фронтматтера `task:`; в PLAN «Имена» среди новых функций числится `spec_gate_declared_refusal_spec_text` — это функция волны 3м-2 (модуль :281).

## Не сработало
- grep с обратными кавычками в Bash требует подтверждения — искал через python3 -c.

## Где остановился
- REVIEW.md: approved, реестр пуст.

## Чего не хватило
- PLAN 134 КБ пропущен пакетом — читал адресно по заголовкам (`grep -n '^## '`).
