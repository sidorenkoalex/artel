# Записка analyst

## Выяснено
- ТЗ достаточно, пишу SPEC (рамка $35, зоны из ТЗ — 6 элементов → сигнал деления, даю обоснование монолита).
- ci.py без репозитория проекта: check_runs (:143), _commit_workflow_runs (:371), _no_checks_by_branch→run_list(branch) (:678), _inherited_from_main→failed_check_names (:481), failed_check_names (:732), find_run_id (:1136), check_run_workflow_run (:1211), trigger_rerun (:1235; там же head_sha(branch) без repo — читает клон артели). check_runs_page/run_list уже берут repo, но gh api с --repo не работает.
- Вызывающие без repo: ci_rerun.py :224, :232, :267, :279, :298; fsm_merge_gate.py :290 (trigger_rerun). С repo уже: fsm_advance :453, fsm_autogate :287, acceptance :2069/:2087/:2184, ci_rerun :123/:158/:244, fsm_merge_gate :293/:341, :579/:618 (main_line_status — только артель, is_artel-ранний выход).
- accepted_full_suite для внешнего возвращается до gh (:829). advance_gates/ ci не зовёт.
- Тестов, утверждающих `--repo` у `gh api`, в tests/ нет (grep) — «Меняемое поведение» не нужно.

## Не сработало
- `cd … && wc` в Bash отказан правилом Read deny — пользоваться абсолютными путями / grep.

## Где остановился
- SPEC.md написан, status: ready, 7 AC, budget_usd 35 (рамка ТЗ), обоснование монолита; guard ок.
- Guard требует классифицировать каждый упомянутый путь (fsm_advance.py, fsm_autogate.py внесены в «Не входит»).

## Чего не хватило
- Ничего существенного; перечень вызывающих собран grep'ом по `ci\.<fn>(`.
