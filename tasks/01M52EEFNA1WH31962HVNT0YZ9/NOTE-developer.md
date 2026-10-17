# Записка developer — 01M52EEFNA1WH31962HVNT0YZ9

## Выяснено
- Канал профиля: `command=<Profile>` у run/collect/run_repeat/run_full_suite/full_suite/suite_result_key; `profile=` у run_plank и two_sided.run (-> `_run_side`).
- Путь артели (pult-pytest) зафиксирован частью 1 вплоть до формы вызова (`subprocess.run` против `Popen`) — pytest-own идёт отдельной веткой (`acceptance._run_in_session`: Popen + start_new_session + killpg); pult — прежний код через `_head(command)`.
- Помощники в acceptance.py: `_own`, `_head`, `_place_command`, `_place_env`, `_own_env`, `_own_cwd`, `_own_target`, `_run_in_session`, `_run_pytest`, `_own_suite_result_key`, `_task_own_profile`.
- Отказ workdir в полном наборе — текст с префиксом `FULL_SUITE_NOT_STARTED: ` -> существующая ветка full_suite (без лога/итога).
- `acceptance_suite`: на пустой in-memory БД `store.task_target` бросает sqlite3.Error -> target артели -> прежняя форма вызова.

## Не сработало
- Ничего существенного: долгоживущий файл задачи зелёный с первой реализации.

## Где остановился
- Готово: код, свой тест tests/test_acceptance_suite_profile.py (мутация проверена), карта, PLAN ready. Полный набор suite-run №1 зелёный (5538/0). Планка 3 passed.

## Чего не хватило
- Имени параметра профиля для мест без `command` в SPEC нет — взял `profile` (его первым пробует долгоживущий тест).
