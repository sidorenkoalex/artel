# Записка developer — 01M5TBFCVFNN95BHH0E9C6KBKB

## Выяснено
- Дизайн в PLAN.md: таблицы `epic_drafts`/`epic_decisions` с ключом (epic_id, number); файлы ссылки — Markdown + первая строка `<!-- artel-epic-<row|draft|decisions>: JSON -->` (restore читает только JSON, `>` экранирован >).
- Ссылка пишется `epics._write_ref` → `artifact_branch.commit_files("epic-<id>", …, target=project)`; журнал отправки ключа `epic-` идёт под id эпика с target проекта (`artifact_branch._journal_identity`; для задач вызов journal без target, как прежде).
- `cmd_epic` оборачивает подкоманды в `deferred_sends()`; `epic add|remove` пишут ссылку внутри своего `lease.run_locked` — одна отправка.
- promote → `catalog.cmd_new(..., tz_text=...)`, рамка → `budget.apply_operator_frame` (ядро `apply_division_frame`).
- Фильтры `epic-` в retro_corpus, plan_appendix_ci, artifact_cleanup, snapshot, doctor; `fetch_all_from_origin` сдвигает ссылки эпиков, но не отдаёт их в исходах.
- Итог: 4 долгоживущих файла (37) + свой test_epic_drafts_units.py (2) зелёные; 40 файлов затронутых модулей зелёные.

## Не сработало
- `pytest -n` — сторож роли считает это полным прогоном; гонять с `-p no:xdist`.
- Bash heredoc с f-строками (`{…"…"}`) и `$f` в цикле отклоняются песочницей — вставка кода Edit'ом.

## Где остановился
- Готово: код, карта перегенерирована, PLAN status: ready.

## Чего не хватило
- Ничего существенного; дольше всего — выяснить, что `store.journal(target=…)` лучше не передавать для задач (форма вызова в существующих тестах).
