# Записка spec_auditor — 01M6TT4FKD1JWSJFVJ7328K03Y (аудит 4, spec_sha a0856ae8)

## Выяснено
- Решения возврата 2 (1–4) перенесены: требование 1 + AC-9 (одинаковые ci_base_branch/ci_base_push_options), AC-5 без store.steps_of_action, «Не входит» — interruptible, записки — в «Материалах».
- Ссылки сходятся на cfa465d80: outcome_integrity.py:1045-1133, 1173-1187, 1465, 1493-1510, 1561, 1583-1623, 820-837; gitcmd.py:2112-2155 (`--refmap=` при tracking_refs=False); config.py:361/372; fsm_merge_gate.py:191 (мерж — fetch_ref_sha по умолчанию, ссылка отслеживания обновляется).
- Хук pre-push сейчас git не вызывает вовсе (:38-103); после задачи — `git merge-base --is-ancestor`, рекурсии нет.
- Profile (project_profile.py:136, 455-472, только чтение) поля ci_base не несёт — гейт читает поле из записи компонента (`project_profile.components(...)[i].fields`) — выполнимо без правки.
- tests/test_01m5xzskk8gzteca2kwafhe029_component_fields.py текст «(известны: …)» побайтно не сверяет — новые поля COMPONENT_FIELDS (targets.py:130) его не ломают.
- Новая находка: классификация «отказ отправки базы на verifying = проходящая негодность» есть только в записке решения 4 возврата 2; ни требование 7, ни AC-7 этот случай не несут — мутация «эскалировать сразу при отказе хука» не поймана.

## Не сработало
- Bash с `;`/`cd`/несколькими командами отклоняется; работают одиночные grep/git hash-object.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Какой «замок проекта» имеется в виду (требование 5): отдельного общего замка проекта, кроме merge_lock, нет; на мерже (требование 8) окно уже держит merge_lock.
