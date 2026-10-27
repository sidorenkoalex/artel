# Записка spec_auditor — 01M5XXA2HY73D3WTXDR19Z5SWW

## Выяснено
- Перечни состояний из Факта 2 ТЗ сверены — адреса верны (fsm.py:33-38, :839, :1959, :1757; zone_lock.py:110/119/126; config.py:870/923; auto.py:70/1150/1168; board.py:19-43; watch.py:40; catalog.py:1353; merge_after.py:55/649/769).
- Не названы SPEC: report.MANUAL_GATE_STATES (report.py:42, корректно без awaiting_human), doctor/branch_freshness.py:40 (фильтр TERMINAL_STATES — awaiting_human попадёт в проверку свежести, ADR-0029 п.2 этого не хочет).
- fsm.STATES держит review ДО verifying (fsm.py:34-35), а поток in_dev→verifying→review (fsm_advance.py:885/469) — «от verifying до awaiting_human» в требовании 7 / AC-11 двусмысленно насчёт review.
- forge/gitlab_adapter: нет списка MR по ветке (gitlab_adapter.py:51-63 ALLOWED_PAIRS, QUERY_KEYS без source_branch) — «сверка открытых MR ветки» через read-only forge невыполнима.
- amend-tests (amend.py:834, без проверки состояния) отправляет голову ветки — обход «ничего не отправляет в ветку в awaiting_human»; amend.py вне зон.
- Надзор эпика (auto.py:1298-1306): состояние вне EPIC_GATE_STATES при role_step_started → _READY → перезапуск auto по кругу.
- Тесты: board_model :131-133 и test_report :255/:270 — докстринги, перечней состояний там нет.
- _refuse_if_main_red (fsm_merge_gate.py:1525) не классифицирован SPEC (ни «исполняется», ни «нет»).

## Не сработало
- Bash с `cd …;` и `sed` по относительному пути после cd — отказ песочницы; работают простые команды из cwd.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, 14 пунктов вердикта; guard — ок.

## Чего не хватило
- Нет перечня «команды, отправляющие ветку задачи» — искал вызовы ensure_head_in_origin грепом.
