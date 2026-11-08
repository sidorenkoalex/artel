## Выяснено
- Итерация 1: approved, два minor (R1-F1 докстринги test_suite_cost_units.py, R1-F2 деление на limit в doctor/suite_cost.py) — оба accepted.
- 130 тестов связанных файлов зелёные; карта свежая (диф только built_at_sha).

## Не сработало
- `plank-run` — «планки нет» (планка = долгоживущий файл в tests/), гонял pytest напрямую.
- pytest с `-n 4` — xdist «node down»; работает с `-p no:xdist`.

## Где остановился
- REVIEW.md записан, status approved.

## Чего не хватило
- Как гонять планку, когда она только в перечне лока `tests/` — `plank-run` её не видит.
