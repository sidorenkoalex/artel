# Записка spec_auditor

## Выяснено
- `_whitelist_refusal` (orchestrator/gitcmd.py:1012-1017) отказывает `--delete` любой ссылки, кроме `refs/artifacts/<id>`: без `-c` удаление ветки задачи всё равно отказано («--delete task/x — удаление только refs/artifacts/<id> задачи проекта») — проверено вызовом функции. Форма `:ref` — тоже отказ (:1012). Требования 1 и 3 SPEC несовместимы.
- `tests/test_01m6n7cykdamakenx60cbk7vqx_people_flow.py:904` (`test_ac9_kill_before_send_keeps_pr_notes_branch_outcome`) закрепляет обратное AC-1: ветка в origin цела после kill target-human до отправки; сейчас зелёный (прогон ac9/ac10 — 6 passed).
- `gitcmd.git` без срока (:1440); `gitcmd.read(timeout=)` проходит `_push_plan`, но без токена хостинга (`_hosting_project` только в `git`).

## Где остановился
SPEC-AUDIT.md: verdict fail, status escalate.

## Чего не хватило
Знания, что белый список запрещает удаление веток (`--delete`) — ТЗ это упустил.
