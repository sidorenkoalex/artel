# Записка аналитика

## Выяснено
- Возврат с spec_gate: 4 решения Оператора внесены в SPEC. Факты сверены по коду: `pull.py:926-939` (commit_title — первая ссылка системы, порядок {id}→{ref}→{text}), `targets.py:667-669` (форма отказа `поле 'policy.<имя>'`), `projects.py:986-996` (копия в config.LOGS/targets-<время>.yaml), `github_adapter.py:140-186` (условия входа и push), `tests/test_draft_mr_commits.py:55-67` (образец голого origin).
- Требование 3: первая ссылка в порядке записи, ссылки читаются только при `{ref}` в шаблоне, порядок подстановки {id}, {ref}, {title}.
- AC-1 — транспорт GitLab с сервером-дублёром, без подмены forge.open_mr; AC-3/4/5/8 — текст `поле 'policy.mr_title_template'`; AC-7 — копия в config.LOGS; AC-9 — RealGitSandbox + init_bare_origin + подмена ci.gh, две ссылки, `{ref}` в названии.
- 9 AC, budget_usd 28, status ready, guard ок.

## Не сработало
- guard: `orchestrator/pull.py` упомянут без классификации — добавлен в «Не входит» как образец.

## Где остановился
- SPEC.md исправлен, guard ок. Шаг завершён.

## Чего не хватило
- —
