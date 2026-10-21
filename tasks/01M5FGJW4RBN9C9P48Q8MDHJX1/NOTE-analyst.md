# Записка analyst — 01M5FGJW4RBN9C9P48Q8MDHJX1

## Выяснено
- ТЗ полное: SPEC написан (status: ready, 9 AC, budget_usd 25, zones из ТЗ), guard — ок.
- Адреса ТЗ сверены по коду ветки: `_push_merged_main` fsm_merge_gate.py:1284, `_cleanup_merged_task` :1352, вызов :1529 (после `_finalize_done_state`, до `_await_main_ci` :1530); cleanup.py `_left_reason` :229, `_delete_origin_branch` :253 (lowSpeed-предел :256), `cleanup_project_remote` :266.
- tests/test_merge_gate_ci_wait.py:415 подменяет `_cleanup_merged_task` через `lambda *a, **k: None` — добавление параметра `final_sha` её не ломает.
- Раздел «Меняемое поведение» не нужен: ТЗ требует существующие тесты без правок.

## Не сработало
- Первый прогон guard: сигнал «число файлов» (guard считает все пути, упомянутые в тексте SPEC) + «прогноз диффа не дан»; и docs/backlog.md не классифицирован. Закрыто разделом «Оценка объёма» (монолит, прогноз 30 КиБ) и строкой в «Не входит».

## Где остановился
- SPEC готов, шаг завершён.

## Чего не хватило
- Что guard считает «файлами зоны» по всем упомянутым в тексте путям, а не по полю zones — узнал только из отказа (scripts/guard.py::split_signal_names).
