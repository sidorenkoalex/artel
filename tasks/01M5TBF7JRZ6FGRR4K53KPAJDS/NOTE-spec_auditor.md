# NOTE spec_auditor

## Выяснено
- Визит 4 (SPEC sha 73a8dbf1…). Рабочий каталог (HEAD 761b646) старше Э1 — сверка по `git show origin/main:<файл>` (main 7f37c6dd7). Э2а на main нет.
- Находки визита 3 закрыты SPEC (alert-ack убран, epic retry, зона watch.py, session_id, аварийный выход).
- Новое: `_cmd_stop` (artel.py:1429) → `store.disable_task_observation` выключает задачу во ВСЕХ наблюдениях; observation_tasks/observation_steps_since видят только enabled=1.
- Задачи эпика попадают в набор только перед запуском дочернего — события надзора до первого запуска (самозавершение AC-27..29) не доставятся; AC-30 предзаполняет набор и это не ловит.
- Отказ лимита пульта в дочернем (runner.py:219, auto.py:966) = остановка не на гейте → гонка подсчёта по lease застревает задачу.
- Отказные записи команд: amend.py:161 и др. «amend-tests отклонён», ci_rerun.py:68.
- _launch_observation отказывает через sys.exit и при неактивном/без связи наблюдении (artel.py:955-969).

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready, guard ок.

## Чего не хватило
- Шелл шага: `ls`, `echo ====`, `$VAR`, `cd … && grep относительного пути` отказывают — абсолютные пути и Edit вместо python-правки.
