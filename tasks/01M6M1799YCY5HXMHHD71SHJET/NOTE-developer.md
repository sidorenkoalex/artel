# Записка developer

## Выяснено
- Реализация: forge.py (github_call + _github_form_allowed, _GitHub.mr_status/open_mr/undraft_mr/assign_mr, MergeRequest.already_exists, ASSIGNEE_BY_NAME, assignee_by_name), github_adapter.py (mr_assignee(policy, target), ASSIGNEE_NOT_NAME, ссылка при iid с причиной), fsm_merge_gate.py (_deliver_mr: ветвь MR_PARTIAL_DETAIL, эскалация по already_exists; _ready_existing_mr передаёт target).
- GH_CALLS: удалены 4 ключа по мандату. Код закоммичен ролью (57735472f) — планка AC-17 читает git show HEAD.
- Долгоживущие 96 passed, AC-17 passed, соседние модули зелёные.

## Не сработало
- `pytest -n 4` в шаге роли: сторож conftest роняет воркеры — гонять без -n.
- test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py::test_ac18_watch_notifies_once_on_outcome_change упал на git fetch под нагрузкой, отдельно зелёный.

## Где остановился
PLAN.md status: ready. Карта перегенерирована (после коммита изменилась только строка built_at_sha — оставлена незакоммиченной).

## Чего не хватило
Ничего существенного.
