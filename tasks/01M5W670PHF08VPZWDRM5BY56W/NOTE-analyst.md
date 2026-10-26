# Записка analyst

## Выяснено
- ТЗ достаточно; пишу SPEC с делением на 2 части (сигналы: 7 файлов зоны, рамка $70 ≥ $30).
- Часть 1: forge.py, gitlab_adapter.py, ci.py, github_adapter.py (треб. 1–3). Часть 2: doctor/misc_checks.py, doctor/cli.py, artel.py (треб. 4) — после части 1.
- `Порядок:` части деления принимает id задач (`merge_after.division_order_items`) — зависимость от А0 01M5W27CY7K7NR9347NKD8F0NX вписана в обе части.
- `tests/test_doctor.py:670 test_non_github_forge_is_skipped`: url `file:///…` — адаптер не строит адрес → `skip` с причиной (как у GitHub при сбое `gh`), тест остаётся зелёным; в «Меняемое поведение» не внесён.
- `tests/` — общая зона (`config.COMMON_ZONES`), в zones не вписана.

## Не сработало
- `ls`/`cd …;` в Bash требуют подтверждения — пользуйся Read/grep.

## Где остановился
- SPEC написан (15 AC, 10 требований, деление на 2 части: $45 + $25), `scripts/guard.py` — ок, status: ready.

## Чего не хватило
- Как пульт переносит merge_after родителя на части деления — нашёл в `orchestrator/merge_after.py::division_order`.
