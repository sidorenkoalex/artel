# Записка spec_auditor — 01M5NNDYGQ8G6VFDEEXYBB0W3D (круг 4, spec_sha 0ae9cac5)

## Выяснено
- Diff SPEC к кругу 3: `git diff d7b13c42 bf0e11dc -- tasks/<id>/SPEC.md` (ссылка refs/artifacts/<id>). Все 4 решения гейта №3 внесены дословно по смыслу (req 2, 7; AC-2, AC-7; «Не входит»).
- Код `mutation-run` только на origin/main (549e997e); ветка на 16f9ab43 его не несёт — читать `git show origin/main:orchestrator/mutation_run.py`.
- Шапка «ревизия прогона» для `worktree` — HEAD рабочей копии (`_revision`, :288-299), а копия несёт и НЕзакоммиченные файлы (`_prepare` :477-486) → `git diff <до> <после> -- orchestrator/` не видит незакоммиченную правку orchestrator/ в момент «после». Замечание, не отклонение.
- origin/main против базы ветки 16f9ab43 отличается в orchestrator/ (artel.py, mutation_run.py, pull.py): подтяжка main между «до» и «после» сделает AC-7 красным → повтор «до». Замечание.
- Числа 80/54/1728 перепроверены.

## Где остановился
- SPEC-AUDIT.md: verdict pass, status ready (замечания без отклонений по решению гейта №3).

## Чего не хватило
- Корень пульта на диске закрыт для Read — только git show origin/main.
