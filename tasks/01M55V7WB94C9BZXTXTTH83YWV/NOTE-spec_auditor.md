# Записка spec_auditor

## Выяснено
- Аудит SPEC sha 3b934eca (четвёртый визит): решения гейта №1–№3 (включая К-1..К-4) перенесены; все ссылки файл:строка SPEC сверены по коду — совпадают (ci.py, ci_rerun.py, fsm_merge_gate.py, acceptance.py, github_adapter.py, fsm.py:166, подмены в tests/).
- Полный перечень вызывающих `ci.<функция>(` (git grep по orchestrator/ и scripts/) совпадает с перечнем требования 3.
- workspace.task_repo(id) == repo_context.clone_path(target) — путь клона, сопоставление путь→запись работает для всех вызывающих.
- `_repo_kwargs(config.ROOT)` возвращает {"repo": ROOT} (is_artel(путь) истинен только для клона артели) — ловушка для check_runs под main_line_status(repo=config.ROOT); ловит существующий tests/test_main_ci_fetched_repo.py:64.
- tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:165-229 — образец проверки «признак артели подменён» (строки 18/19); для нового пути gh api (GH_REPO) такого AC в SPEC нет — К-4 без критерия.
- refs/remotes/origin/<base> клона обновляют подтяжка/вход в verifying/push (github_adapter.py:33-39) — решение Оператора, не отклонение.

## Не сработало
- `sed ...; sed ...` цепочкой — песочница требует подтверждения; читать через python3 heredoc или Read.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns (Н-1..Н-4), guard прогнан.

## Чего не хватило
- Помощника «путь клона → имя записи» в repo_context нет; есть закрытый gitcmd._project_of_path (gitcmd.py:62-68).
