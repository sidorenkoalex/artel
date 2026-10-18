# Записка spec_auditor

## Выяснено
- Падение doctor на записи с 2 компонентами — cli.py:94 `full_suite_timeout_check` → `project_profile.full_suite_limit` (project_profile.py:186-188) поднимает TargetsError на PROFILE_UNREAD multi; `targets.load` (cli.py:88-92) уже перехвачен.
- `repo_context.profile_of` (только чтение) отдаёт в values лишь `targets.PROFILE_FIELDS` (repo_context.py:171-172) — `tools` туда не входит; запись с >1 компонентом — UNREAD, Profile нет вовсе.
- Долгоживущий тест tests/test_01m58fnwbv25ff26e7az9q9912_components.py:657-694 требует равенства Profile единственного компонента и test_profile — признак «из components:» в Profile нельзя добавить без поломки равенства; требование 7 против AC-8 неразличимо.
- Ключ базы: acceptance.py:2319 пишет, suite_run.py:523 читает — SPEC не говорит, входят ли суммы блокировок в base-ключ.

## Где остановился
- Вердикт fail, SPEC-AUDIT.md записан, status: ready, guard.py — ок. Шаг завершён.

## Чего не хватило
- CI-файл sled (.artel/projects/sled/repo/.github/workflows/ci.yml) недоступен на чтение — формат переменной BACKEND_RE не сверен.
