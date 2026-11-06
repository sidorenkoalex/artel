# NOTE-reviewer (итерация 2)

## Выяснено
- R1-F1 исправлен: `_drop_group(proc)` — SIGKILL → wait → пробы; опыт `{'gone': 1}`.
- R1-F2 исправлен: `tests/test_doctor_compose_stands.py`, мутация `-v` в `down` его красит.
- plank-run 30 passed; 5 файлов тестов задачи/doctor — 149 passed; карта свежая.

## Не сработало
- Составные bash-команды с `sed -i`/`cp` отклоняются — временную мутацию делал через Edit.

## Где остановился
- REVIEW.md итерации 2: approved, R1-F1 и R1-F2 — accepted.

## Чего не хватило
- Ничего существенного.
