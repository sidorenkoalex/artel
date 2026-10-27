# Записка spec_auditor — 01M5XZ9Z68XE2EKPDHYCAK25KF

## Выяснено
- Адреса SPEC в fsm_merge_gate.py (1442, 1513, 1525, 1541, 1545, 1581, 1650), forge.py (218/223/227), gitlab_adapter.py:211, targets.py:29-30, gitcmd.py:176, amend.py:834, test_invariants.py:646 — подтверждены.
- github_adapter.py:166 — это `git push`, а `gh pr create` стоит на :174.
- Подтяжка на гейте мержа (`_sync_main_or_wait` -> `fsm._pull_main_or_escalate`, merge_main=True) всегда делает merge, `policy.freshness` там не читается; rebase есть только на in_dev->verifying (pull.py:875). «Тем же методом freshness ... без изменений» в требовании 1 этому противоречит.
- Для `operator` после подтяжки цикл (`fsm_merge_gate.py:1655-1674`) ждёт CI, заходит в тело снова и мержит новую голову в том же approve — на гейт не возвращается. Формулировка AC-6 «тем же путём, что для operator (... возврат на гейт)» по коду не подтверждается.
- `confirm_fixation` (fsm.py:852, вызов :1802) уже отказывает, если sha не совпал с фиксацией, — AC-5 проходит и без новой сверки.
- Единая точка отправки — `gitcmd._push_plan` (:730); запись «ветка отправлена» пишет `_PushPlan.after` (:541-556); `_last_sent_sha` читает и устаревшую форму записи (:177, :225).

## Не сработало
- Скрипты на несколько команд через `;`/`&&` в Bash требуют подтверждения; используй одиночные `git grep`/Read.

## Где остановился
- SPEC-AUDIT.md написан: status ready, verdict concerns, 9 пунктов вердикта. `scripts/guard.py` по файлу — ок; поле signals yamlmini читает дословно.

## Чего не хватило
- Пришлось искать, проходит ли подтяжка на гейте через freshness: читать pull.evaluate (pull.py:782-900).
