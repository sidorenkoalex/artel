# Записка spec_auditor — 01M5TBFH5VZ7GSRXX7VNKHFCCQ (визит 6, SPEC sha 0ed0ddca)

## Выяснено
- main 7f37c6dd7 не двигался с визита 5; сверка через `git show origin/main:<файл>`.
- Три отклонения визита 5 внесены (решение гейта №5): матрица «без git» → test_author_report.py:185; догон external_refs без журнала; треб. 10 — все отказы `--ref`.
- `build_model` зовёт `watch._pin_head()` — он читает файлы .git, git не запускает (watch.py:355-379): test_author_report.py:185 не сломается.
- `build_model` делает один `last_step_times` на проект (board.py:130) — AC-14 согласован.

## Не сработало
- —

## Где остановился
- SPEC-AUDIT.md: verdict pass, status ready; guard прогнан.

## Чего не хватило
- —
