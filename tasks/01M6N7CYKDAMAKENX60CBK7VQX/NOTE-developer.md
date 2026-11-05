# Записка developer

## Выяснено
- Код: targets.py (пара + `_check_ci_required_jobs` в `check`), gitlab_adapter.py (`READS_CI_REQUIRED_JOBS = True`), ci.py (`people_rerun_refusal`, вызов в `trigger_rerun` после отказа GitLab), ci_rerun.py (отказ после проверок `--reason`, до `verifying_status`), cleanup.py (`PR_LEFT_TO_PROJECT_PEOPLE`, признак `forge.ci_by_pipeline` вместо литерала, `_forge_of` убран), doctor/project_checks.py (`check_workflows_dir_no_paths` — проба именем по формуле записки SPEC).
- Три файла мандата правлены: github+target-human убран из UNSUPPORTED, тексты — новый перечень, константы GHTH_REASON/TARGET_HUMAN_REASON удалены (не используются), test_ac2_github_target_human_* утверждают поддержку (имена сохранены).
- Планка AC-13 читает HEAD (`git show HEAD:`), а не рабочее дерево — перед plank-run нужен коммит.

## Не сработало
- `pytest -n 4` на пачке файлов — узлы xdist падают; гонял последовательно.
- Bash с несколькими операциями через `;`/`$()` требует подтверждения — дробить.

## Где остановился
- Задачные tests/test_01m6n7cyk* — 54+ зелёные; мандатные три файла — 29 зелёные; карта регенерирована.
- 31 смежный файл tests/ (kill, ci-rerun, ci status, gitlab forge/doctor, mr-sync, push hook, github mr gate) — 802 passed.
- Код закоммичен be0277fb5; plank-run — 10 passed; guard PLAN.md — ок; PLAN status: ready.

## Чего не хватило
- Что AC-13 сверяет HEAD, а не дерево — видно только в теле планки.
