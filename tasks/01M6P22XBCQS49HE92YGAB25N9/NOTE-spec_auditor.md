# Записка spec_auditor

## Выяснено
- Визит 4: SPEC b6b16c9f…, решения 2.1–2.6 закрывают пункты 1–7 визита 3; якоря верны (cli.py:305-331, test_doctor_closed_ref_fix.py:152-195 — all_checks тоже подменён, plank_layout.py:41-47, acceptance.py:1277-1301/:2068, test_ac6 обходит только orchestrator/ и scripts/).
- Опыт: `exec sleep` под `subprocess.run(timeout=1)` — 1,0 с без сироты; дочерний sleep — 1,0 с, но внук-сирота остаётся. `git ls-files --error-unmatch`: 0 отслеживаемый / 1 нет. Деревья сторон — `git worktree add` (two_sided.py:466, outcome_integrity.py:702).
- Остаток: А1 — окружение вызовов docker в doctor и `context inspect` не задано (ТЗ треб. 5); Б1 — `compose` без `workdir` (workdir необязателен, targets.py:76-77) → планка в tasks/<id>/… вне монтирования.

## Не сработало
- `$VAR`/`for` в Bash — отказ «Contains expansion»; помогает python3 - <<'EOF'.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, 2 отклонения + к сведению; guard ок.

## Чего не хватило
- Нет.
