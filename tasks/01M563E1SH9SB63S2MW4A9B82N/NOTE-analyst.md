# Записка analyst

## Выяснено
- Отказ «другому проекту»: `orchestrator/artel.py:1150-1160` (`_validated_observation_tasks`), зовётся из register (:1045) и add/remove (:1120, с `row["target"]`).
- `register`: проект = проект первой задачи, `--project` сверяется с ним (`artel.py:1041-1044`).
- Именованное `--observation`: сверка `observer["target"] != target` в `artel.py:882` — снимается в зоне.
- Без флага: `store.matching_observation` (`store.py:223-234`, `o.target=?`) — store.py только на чтение. То же в `store.session_observations` (`store.py:237`), через неё `cycle_hint.launch_hint` (`cycle_hint.py:17-21`, вне зон).
- Фильтр алертов дозора: `watch.py:297` — `item["target"] in task_ids or item["target"] == row["target"]`; шаги идут по набору задач (`store.observation_steps_since`), проект там не участвует.

## Не сработало
- —

## Где остановился
- QUESTIONS.md записан, guard ок: (1) объём требования 4 (A — только `--observation` / B — дубль запроса в artel.py / C — расширить зоны на store.py+cycle_hint.py), дефолт A; (2) правило проекта наблюдения при register, дефолт A (`--project` = проект по умолчанию). SPEC.md не писал.
- Метку `[проект]` в status для задач не артели (без новой колонки) аналитик выбирает сам, это не вопрос.

## Чего не хватило
- Нужно было знать, что подбор наблюдения без флага живёт в store.py, а не в artel.py: из ТЗ это не видно, нашёл grep'ом `matching_observation`.
