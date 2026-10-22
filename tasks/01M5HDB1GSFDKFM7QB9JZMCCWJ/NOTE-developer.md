# Записка developer

## Выяснено
- Отказ developer — `suite_run._refuse_developer_full_run`, вызывается в `cmd_suite_run` до `_db()`/`deliver_journal`; id — `store.get_task` на `_readonly_db()` (mode=ro). `_running` проверяется до отказа (AC-3).
- Подсказки под маркером: `_developer_hint`; развилки в `_wait` (прогона нет, оборван) и в ветке `--failed`.
- Миссия: `role_prompt.suite_run_note` переписана; `MissionTest::test_ac25` зелёный (подстрока `suite-run <id>` есть в форме `--failed`).
- `ROLES` в readonly_db — без developer (мандат ANSWER-1).

## Не сработало
- `pytest -n 4` в рабочем каталоге: воркеры xdist падают «node down» — гонял последовательно.
- `plank-run`: AC-8 красен локально — читает PLAN.md из ссылки документов, до автокоммита шага его там нет. Матрицу сверил той же логикой вручную — проходит.

## Где остановился
- Шаг завершён: долгоживущий файл, readonly_db, suite_run/suite_lock/appendix/step_suite_dirs, тесты миссий зелёные; карта регенерирована; PLAN ready.

## Чего не хватило
- Что планка AC-8 читает PLAN из ссылки, а не с диска каталога документов.
