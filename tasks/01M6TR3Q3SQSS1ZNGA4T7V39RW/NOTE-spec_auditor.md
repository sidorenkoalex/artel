# Записка spec_auditor — 01M6TR3Q3SQSS1ZNGA4T7V39RW (аудит, spec_sha bd7b21ff)

## Выяснено
- sha SPEC на диске = bd7b21ff4eb08ad6fc2ee3e56f3f75fab32fa2b7. Дифф к прошлой проверенной версии 30570dd6 — `git diff c4b0634b5 ca95d86e5 -- tasks/<id>/SPEC.md` (ссылка refs/artifacts/<id>).
- Решения гейта №4.1–4.3 внесены: треб. 13 (ожидание TEARDOWN+запас, затем всегда docker ps + down без -v, до `_account_step` runner.py:1762), треб. 1/7 по компоненту, AC-20/22/26, формы AC-3/AC-15, записка про pause/kill.
- `_compose_teardown` (acceptance.py:1306-1327): kill+down вместе в одном пределе TEARDOWN — запас исполнителя сверх него корректен.
- Компонент задачи один (project_profile.py:384-385: несколько — отказ), выбор — for_task_target; plank_run (:210) и suite_run._component_command (:623-640) уже его зовут.
- Раннеров `pytest` нет: PROFILE_RUNNERS = pult-pytest, pytest-own, compose (targets.py:98-102). У pult-pytest pytest — интерпретатор venv пульта (acceptance._pytest_command), подмена PATH его не ловит.
- Опыт: SIGINT ребёнку process_group=0 — finally идёт, rc -2, та же сессия.
- Не снято с прошлого аудита: В3 (ветка «прогон не прерван» без AC; `plank-run --wait` без запроса не задан).

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready.

## Чего не хватило
- Ничего существенного; дифф версий по артефактной ссылке сэкономил время.
