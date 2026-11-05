# Записка developer

## Выяснено
- Реализация (прошлый шаг, коммиты 57735472f, 79d518ea6): forge.py (github_call + _github_form_allowed, четыре функции _GitHub, MergeRequest.already_exists, ASSIGNEE_BY_NAME, assignee_by_name), github_adapter.py (mr_assignee(policy, target), ASSIGNEE_NOT_NAME, ссылка при iid с причиной), fsm_merge_gate.py (_deliver_mr: ветвь MR_PARTIAL_DETAIL, эскалация по already_exists).
- Шаг по ANSWER-2: гейт неослабления ложно отнёс правку GH_CALLS к test_ac3_no_token_no_request/test_ac18_network_down_reason (они параметризованы GL_CALL_NAMES). Условия мандата выполнены без правок: diff файла против main — только удаление четырёх ключей GH_CALLS. Код не менялся; gitlab_forge + github_mr_units — 262 passed.

## Не сработало
- `pytest -n 4` в шаге роли: сторож conftest роняет воркеры — гонять без -n.

## Где остановился
PLAN.md дополнен абзацем про ANSWER-2, status: ready, guard ок. Карта: после регенерации меняется только built_at_sha (оставлено незакоммиченным, пульт закоммитит).

## Чего не хватило
Ничего.
