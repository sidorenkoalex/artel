# Записка analyst — 01M4VC31NFCS6JZ0VE8HNJ7FYM

## Выяснено
- Итерация 4 (возврат spec_gate по аудиту Е-1, В-1): SPEC поправлен, status: ready, guard — ок. 11 AC, budget 45 (рамка ТЗ $50), монолит.
- Е-1: признак эскалации самой роли без разбора детали — запись журнала с действием `fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` (fsm.py:71) сразу за `state -> escalated`; её пишет только `fsm_advance._mark_artifact_escalation` (:67) в шести точках эскалации по артефакту роли (:180, :207, :292, :382, :556, :650). Эскалации пульта (budget.py:300, fixation.py:248, runner.py:447/:800, лимит ревью fsm_advance.py:347) маркера не несут → роль `unknown`. Правило в SPEC — для всех состояний (требование 1), AC-1..AC-3 дополнены маркером, новый AC-11 — бюджет из spec_audit и из spec_writing → `unknown`, не чистый.
- В-1: AC-1 — подменяется только процесс клона (`_drive_in_clone`/`_read_drive_result`), место вычисления ролей внутри пульта не проверяется.
- `store.task_steps` — ORDER BY id; `canary_drive.build_result` отдаёт весь журнал клона в `steps` (маркер в нём есть).

## Не сработало
- Составные bash-команды с путями вне рабочего каталога отклоняются — документы задачи читать через Read.

## Где остановился
- Шаг завершён.

## Чего не хватило
- Перечень мест `set_state(..., "escalated")` с маркером/без — нашёл grep'ом `"escalated"` по orchestrator/ и докстрингом `_mark_artifact_escalation`.
