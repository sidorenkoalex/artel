# NOTE-reviewer (итерация 2)

## Выяснено
- R1-F1, R1-F2 приняты: пять временных мутаций (ключ `tools`, `declared`, `base`, `decide` без `with_tools`, `_top_level` без `in_class`) — каждая краснит свой тест в tests/test_component_checks.py.
- R2-F1 (новое, major): вызов `with_tools` в `acceptance._task_own_profile` (acceptance.py:2464) без сторожа в tests/ — мутация «убрать вызов» не краснит 22 файла tests/ (240 passed, ~5 мин).
- Планка 4 passed; три файла задачи — 33 passed.

## Не сработало
- Shell шага отклоняет `$(...)`/функции в bash — мутации делать python-скриптом через heredoc.

## Где остановился
- REVIEW.md итерации 2 записан, changes_requested (R2-F1 open).

## Чего не хватило
- В tests/ нет ни одного обращения к `_task_own_profile` — пришлось гонять мутацию по широкому набору, чтобы это доказать.
