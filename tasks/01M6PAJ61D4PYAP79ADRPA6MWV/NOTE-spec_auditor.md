# Записка аудитора SPEC 01M6PAJ61D4PYAP79ADRPA6MWV

## Выяснено
- Третий визит: SPEC faa9184d вносит решения третьего круга 1–4; пять пунктов вердикта второго визита (94e9bb21) закрыты по содержанию.
- Новая находка: `acceptance._report_run(profile, tree, subset, timeout, …)` (acceptance.py:806) не получает id задачи, `Profile` (project_profile.py:66) его не несёт. `outcome_integrity._rerun` (:445) и `_prior_versions` (:736) — только чтение — зовут `report_run` без id, профили из `component_profiles(target, …)` (:1349). Канал id для имени проекта `artel-<id>-<прогон>` (треб. 3) и для «записи журнала» при зависшем снятии (треб. 8) не задан. `two_sided.run` (:433) — в зонах, id выводим из ветки или передаётся.
- Мелкое: предел `up` (300 с) не связан с остатком предела места — остаток для `run` может быть ≤ 0, исход не задан; учёт времени `config` в пределе места не сказан; предел `docker context inspect` не задан.
- vars(config)-перебор в тестах новые COMPOSE_* константы не ловит (observation:108 — фильтр OBSERV/HEARTBEAT).

## Не сработало
- cd + grep в Bash отклоняется; работают одиночные команды с абсолютными путями.

## Где остановился
- SPEC-AUDIT.md сдан для spec_sha faa9184d…: verdict concerns, status ready, guard ок. Два пункта: канал id задачи в `_report_run` (+ носитель записи журнала); соотношение пределов (остаток ≤ 0, время `config`, предел `context inspect`).

## Чего не хватило
- Канала id задачи в узле `_report_run` — искал по вызывающим.
