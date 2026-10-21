## Выяснено
- Код cleanup.py/fsm_merge_gate.py соответствует SPEC по требованиям 1–7; планка 13/13 зелёная, долгоживущий файл + kill-тесты 24 passed; карта свежа (diff только built_at_sha).
- Временная мутация: удалил строку `cleanup.cleanup_merged_remote(...)` в `_cleanup_merged_task` — все 12 файлов tests/ про гейт мержа (84 теста) зелёные. Проводку гейта держит только разовая планка → R1-F1 major.

## Не сработало
- `pytest -n 8` в этом окружении падает (node down) — гонял с `-p no:xdist`.

## Где остановился
- REVIEW.md итерации 1: changes_requested, R1-F1 open.

## Чего не хватило
- Нет.
