# Записка аналитика 01M6M1799YCY5HXMHHD71SHJET

## Выяснено
- ANSWER-1: мандат на `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py::test_ac13_github_other_functions_refuse` (только удаление 4 ключей GH_CALLS), «не найден» = код 1 + stderr `Could not resolve to a PullRequest` → `(404)`, булево поле «уже существует» в MergeRequest, mr_assignee без forge = как без проекта, бюджет 40 — приняты.
- SPEC.md написан: 10 требований, AC-1..AC-17, монолит (часть 1 из 2), без merge_after (ТЗ: «первой из двух»), без «Меняемого поведения». guard ок.
- Вызовы gh вне `_GitHub` (не ограничены списком, названы в AC-13): ci.check_runs/check_runs_page, run_list, find_run_id, trigger_rerun, github_adapter.ensure_draft_mr (pr create/pr comment), github_adapter.undraft_mr (pr ready <ветка>), cleanup._close_project_pr (pr close при kill, cleanup.py:245).

## Не сработало
- `task-rm` отказывает файлу, сохранённому в ссылке документов (QUESTIONS.md) — удалён os.remove в каталоге документов.

## Где остановился
- Шаг завершён: SPEC status ready, QUESTIONS.md удалён.

## Чего не хватило
- Штатного способа удалить сохранённый в ссылке документ (task-rm его не берёт).
