# Записка developer

## Выяснено
- Возврат из verifying: `tests/test_multitarget.py::SqlOnlyInStoreTest` — SQL в notes.py
  запрещён. Закрыто: держатель мьютекса читается `store.task_exists` + `store.get_task`
  (exists первым — get_task делает sys.exit на отсутствии и разрешает префикс; при
  точном существующем id resolve_task_id возвращает его же). store.py не тронут.
- Правка — `orchestrator/notes.py::_silence_window_reason` + помощник `_task_project`
  (is_artel первым, resolve только для не-артели). Внешний триггер пропускается.
- tests/test_notes.py + долгоживущий файл + SqlOnlyInStoreTest: 53 зелёные. Карта регенерирована.

## Не сработало
- suite-run: занят чужим прогоном (задача 01M563E1SH9SB63S2MW4A9B82N) — полный набор не прогнан.
- plank-run: планки в acceptance_tests нет.

## Где остановился
- PLAN ready, guard ок.

## Чего не хватило
- В прошлом шаге не знал про инвариант «SQL только в store.py» (tests/test_multitarget.py) —
  его стоит проверять при любой правке orchestrator/ вне store.py.
