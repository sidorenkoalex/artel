# Записка spec_auditor

## Выяснено
- Ссылки SPEC на код подтверждены (targets.py:29-31, ci.py:57-59, github_adapter.py:103-139, claude.py:45/165, runner.py:964, brief.py:519-550, gitcmd.py:22, role_prompt.py:238-245/323, knowledge_cards.py:953-956).
- Хостинговые git-вызовы пульта разбросаны по artifact_branch.py:346/521/558, snapshot.py:294/325, fsm_merge_gate.py:697/1142, github_adapter.py:160/234, notes.py, artifact_cleanup.py, workspace.py:111 (clone), doctor/*; все сходятся в gitcmd.git (через in_repo `-C <путь>`), но gitcmd.git не знает проекта, а его сигнатуру `(*args)` подменяют заглушки тестов (gitcmd.py:235-241). Токен в зоне gitcmd возможен только определением проекта по пути `-C`.
- Роль может звать `artel.py doctor` (artel.py:1883, без --fix) — новые проверки 8.1/8.2 с токеном пойдут из процесса роли.
- «Токен артели» для 8.5 не определён: targets.yaml:28 artel-token, roles.yaml:46 token_fallback тот же слот, а хостинг артели идёт через gh/osxkeychain Оператора.
- AC-3: у origin в виде локального репозитория помощник учётных данных не вызывается, поэтому push проходит и без токена.

## Где остановился
SPEC-AUDIT.md написан, verdict concerns.

## Чего не хватило
Карты вызовов «хостинговая git-операция → вызывающий модуль»; собирал её grep по "push"/"fetch".
