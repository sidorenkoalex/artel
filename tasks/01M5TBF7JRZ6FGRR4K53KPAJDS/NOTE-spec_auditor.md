# NOTE spec_auditor

## Выяснено
- Визит 2 (SPEC sha 32d21c89…, после возврата с гейта 26.10). Рабочий каталог старше Э1 — сверял по origin/main через `git show origin/main:<файл>` (Bash с `$VAR`/пайпами требует подтверждения — писать пути литералом, по одной команде).
- Э2а на origin/main ещё нет (grep start_after пуст) — треб. 10 SPEC это учитывает.
- auto пишет свои записи актором "operator" (auto.py:582,1008,183,228,854,649; artel.py:1027 detached launch); session_id общий через файл .artel/session-id (session.py) — «действие Оператора» (треб. 4) механически не отличимо.
- _cmd_stop (artel.py:1396) сам журнал не пишет, только SIGTERM + disable_task_observation; add_observation_tasks (store.py:82) включает задачу обратно.
- matching_observation (store.py:225) требует задачу в наборе — для эпика правило «как у auto <id>» буквально неприменимо; SPEC пересказал его без этого условия.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready; guard прогнан.

## Чего не хватило
- Как отличить запись журнала «командой Оператора» от записи цикла auto — правила в коде нет.
