# Записка developer — 01M5FGJW4RBN9C9P48Q8MDHJX1

## Выяснено
- Реализация (итерация 0): `cleanup.cleanup_merged_remote` + помощники в `orchestrator/cleanup.py`; `_delete_origin_branch(repo, branch, head=None)`; `fsm_merge_gate._cleanup_merged_task(..., merged_sha)`, `final_sha` из `_cmd_approve_merge_gate`; абзац `docs/retention.md`.
- Итерация 1 (R1-F1): новый сторож проводки `tests/test_fsm_merge_gate_remote_branch_cleanup.py` — тело гейта у внешнего проекта и у артели: done → ветки в origin нет + одна запись «уборка: удалена»; moved → ветка на месте, записи нет. Ветка публикуется в origin в setUp.
- Мутации проверены: вызов удалён → 2 done-теста красные; уборка до проверки исхода push → все 4 красные. Код возвращён.
- Карта регенерирована.

## Не сработало
- `cat`/`ls`/`cp` в шелле шага нет или требуют подтверждения — мутации делал через Edit.

## Где остановился
- Шаг завершён: PLAN.md (шаг 5, `ready`), реестр REVIEW R1-F1 → fixed, guard ок; suite-run №2 зелёный (6352 прошло, 0 упало, 2 пропущено). Код не закоммичен — коммитит пульт.

## Чего не хватило
- Ничего: приём сторожа взят из планки `acceptance_tests/test_merge_gate_remote_cleanup.py`.
