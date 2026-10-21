# Записка developer — 01M5FRYVP4NF81VT00FYPHPWJH (итерация 2)

## Выяснено
- R1-F1 закрыт: новые `tests/test_report_argv_rerun_ban.py`, `tests/test_gate_owner_marker.py`, `tests/test_mandate_file_path_token.py` (требования 1, 2, 5, 6, 8). Код не менялся.
- 12 временных мутаций кода (флаги argv, поле ключа, условие from_components, fullmatch/search, `:\d+`, префиксы выписок, порядок маркера канарейки, prune никогда/всегда, маркер в `_gate`/`two_sided.run`) — все красят новые тесты.
- Правило `*.py` в ячейке мандата живёт в `mandate._covered`, не в `_component_covered` — тест зовёт `_covered(cell, profile, True)`.
- Карта регенерирована; REVIEW R1-F1 размечен `fixed`.

## Не сработало
- `pytest -n` со списком файлов роняет воркеры — гонять с `-p no:xdist`.

## Где остановился
- guard и PLAN status: ready.

## Чего не хватило
- Ничего существенного.
