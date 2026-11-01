# NOTE developer (визит 1)

## Выяснено
- Реализация целиком в worktree (незакоммичено — коммитит пульт): orchestrator/mr_sync.py (сверка evaluate/sync_task, --confirm/_close, supervised, record_fork_point, accept_server_head, foreign_commit); проводка: artel.py (mr-sync), fsm_merge_gate (_mr_incident_stops до публикации головы, record_fork_point в _deliver_mr), fsm._approve_escalated (accept_server_head), auto._poll_mr_sync, watch (OUTCOME_CHANGED_ACTION значим), catalog/board (mr_sync_shown), retro/snapshot/cleanup (note → строка «Закрытие:» RETRO), schema (fork_point, mr_sync_outcome, mr_sync_at; CLOSED_AS_MERGED_UPSTREAM(_OTHER)), targets (mr_sync_interval_min), forge/gitlab_adapter (5 полей), подсказка без «(шаг Б2.2)» + HINT в тесте Б2.1а.
- Зелёные: все 3 долгоживущих файла задачи (mr_sync 47), test_invariants с приложением (88), модули доставки/доски/watch/надзора/схемы/RETRO/answer/zone_lock/merge_after; свой tests/test_mr_sync_units.py (4, мутации проверены).
- КОНФЛИКТ → PLAN status: escalate: tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac15_gate_with_link_talks_to_mr_only_by_undraft_and_assign (talked <= {undraft_mr, assign_mr}) против AC-13 (mr_status на approve). Предложен мандат на добавку mr_status в множество.
- Планка AC-20 читает PLAN из закоммиченной ссылки документов: до автокоммита пульта plank-run красен «нет приложения»; логика планки на дисковом PLAN проверена вручную — дифф применяется, слова есть.

## Не сработало
- Bash отклоняет `ls`, `cd`, `$x`, `for`, `{…'…}` — правки через Edit, мутации python-heredoc с бэкапом файла.
- pytest -n (xdist) в шаге — узлы падают; гонять без -n.

## Где остановился
PLAN.md сдан status: escalate (3 вопроса). После ANSWER: если мандат по вопросу 1 — правка утверждения test_ac15 по мандату, PLAN → ready.

## Чего не хватило
Где в существующих тестах Б2.1б зафиксировано «гейт не читает MR» — нашлось только прогоном (test_mr_delivery.py:1308).
