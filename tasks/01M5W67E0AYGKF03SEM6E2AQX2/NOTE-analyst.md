# Записка аналитика

## Выяснено
- Возврат с гейта SPEC 26.10: 11 решений Оператора применены в SPEC.md (23 AC, budget 70, части $40/$45, guard ок).
- Сняты: coldstart (зона, AC-10, test_coldstart), хук pre-push (→ Б2). Добавлены: журнал «ветка отправлена: <sha>» и `-o` push_options в gitcmd (часть 1), атомарность деления, «своя ветка» = ветка живой (не killed/done) задачи проекта из БД, отправка без refspec — отказ.
- Конфликт rebase — прежний путь: escalated + PULL_CONFLICT_ROLE_STEP_MARKER (pull.py:575,589; PULL_CONFLICT_MARKED_STATES pull.py:87 включает in_dev).
- Вызовы fsm._pull_main_or_escalate: fsm_advance.py:771 (in_dev→verifying, единственное место freshness), runner.py:643, pull_main.py:66, fsm.py:1577, fsm_merge_gate.py:727, canary.py:1384.
- ensure_head_in_origin (github_adapter.py:211, push :241) общий для всех forge; вызовы fsm_advance.py:478, pull_main.py:93, fsm_merge_gate.py:701, amend.py:826, tests_writing.py:62.
- Merge-коммит подтяжки — идентичность клона (workspace.inherit_identity, workspace.py:78); workspace.py в зоны не внесён, правка — через pull.py.

## Не сработало
- `ls` в Bash недоступен (command not found) — читать каталоги через Read/grep.

## Где остановился
- SPEC.md переписан, status: ready, guard ок. «Меняемое поведение» не заводилось — правок существующих тестов не ожидается.

## Чего не хватило
- Риск: запись журнала при каждой отправке ветки (и у артели) может задеть тесты, сверяющие журнал целиком — не проверял.
