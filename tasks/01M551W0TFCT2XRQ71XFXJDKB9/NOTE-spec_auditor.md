# Записка spec_auditor

## Выяснено
- Ссылки SPEC на код сходятся: role_prompt.py:36/78-80/94/114, checkpoint.py:376/384/412/497, runner.py:1310-1346.
- Находка: коммит test_author идёт через `_commit_worktree_change` с зонным фильтром `_stray_staged_paths(_zone_paths)` (checkpoint.py:1731, 1550): COMMON_ZONES несёт `tests/` артели, `backend/tests/` внешнего проекта вне зон задачи снимается со стейджа — SPEC это место не называет.
- SPEC не говорит, что делать при Decision без профиля (refusal/skip, project_profile.py:140-159) в задании/чекпоинте/проверке артефакта.

## Не сработало
- sed после cd в Bash отклоняется — читать через Read.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок. Отклонения: Ф-1 (зонный фильтр), Ф-2 (Decision без профиля), П-1 (части требований 2-3 без AC: checkpoint.py:384/412/497, runner.py:1319).

## Чего не хватило
- Связь чекпоинта test_author с зонным фильтром нашёл только чтением `_commit_worktree_change`.
