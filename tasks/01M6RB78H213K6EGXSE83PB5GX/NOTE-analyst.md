# Записка analyst — 01M6RB78H213K6EGXSE83PB5GX

## Выяснено
- Факты ТЗ сверены: `orchestrator/cleanup.py:258-262` `_bounded` (пары `-c http.lowSpeed*`), `:265-281` `_delete_origin_branch`, `:329` вызов из kill, `:390` тот же `_delete_origin_branch(head=…)` из уборки смерженной задачи; `:357` `_origin_branch_head` — ls-remote через `_bounded` (не входит). `orchestrator/gitcmd.py:975-990` `_whitelist_refusal`: перед push только `-C`.
- `targets.push_whitelisted` (`targets.py:610`): белый список действует при `merge_gate != operator`.
- Долгоживущие тесты требуют пары `-c` в пуше удаления: `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py::test_ac6_limit_arguments_follow_gh_timeout` (стр. 673-676) и `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py::DeletedTest::test_ac1_…` (стр. 373-377). Оба — на проекте `merge_gate: operator` (вне белого списка), т.е. с требованием 3 ТЗ не конфликтуют: для проектов вне списка форма с `-c` остаётся.
- Для `target-human` с записью отправки (`_server_left_to_project_people`) kill сервер не трогает — сценарий AC-1 требует задачу без записи отправки.

## Не сработало
—

## Где остановился
SPEC.md написан (4 требования, AC-1…AC-4, budget 25), status ready; guard — ок.

## Чего не хватило
Дольше всего искал, какие существующие тесты держат `-c`-пары и на каком merge_gate их песочница.
