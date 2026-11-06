# Записка spec_auditor

## Выяснено
- Второй аудит (spec_sha 2017826…): все 4 отклонения первого закрыты решением Оператора №1 (AC-7, форма отказа + позитивный контроль AC-4/AC-6, действие/причина AC-5, однократная подстановка).
- Факты сверены: targets.py:667-669 (refuse — форма `поле 'policy.X' — …`), :539-541, :424-428 DELIVERY_POLICY_FIELDS (туда же новое поле для _flatten :855-859); pull.py:939-940 цепочка replace (в решении 3 «938-939» — сдвиг на строку); store.journal(action, detail) store.py:1610.
- Все вызовы pult_message в кодовой ветке: checkpoint.py:1887 (через _commit_worktree_change), pull.py:473, :556, amend.py:806. Вне перечня ТЗ — fsm_merge_gate.py:1051 (коммит приложений PLAN), отмечен наблюдением.
- Каркас amend-tests в песочнице: tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py.
- Статический список отказов tests/test_01m6n7cykdamakenx60cbk7vqx_entry_checks.py:47-64 новое поле не ломает.

## Не сработало
- `echo $?` и пайпы в Bash отклоняются песочницей.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict pass; guard — ок. Шаг завершён.

## Чего не хватило
- Ничего существенного; перечень мест коммитов снова собирал grep'ом по `pult_message(`.
