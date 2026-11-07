# NOTE spec_auditor 01M6TRKY1A41QSZMCXY9TKYXG7

## Выяснено
- appendix_tree.suite_tree с branch=… (fsm.py:1673, fsm_autogate.py:417) кладёт временное дерево на голову ветки БЕЗ незакоммиченных правок (appendix_tree.py:189 переносит их только при branch=None). Значит при приложениях PLAN дерево приёмки правок рабочей копии не содержит; AC-5 «с приложением PLAN» противоречит требованию 2а.
- PLAN для дерева приёмки читается из ЛОКАЛЬНОЙ refs/artifacts/<id> (appendix_tree.read_plan -> artifact_branch.show), CI — из origin (plan_appendix_ci.py:173-193). push ссылки best-effort (artifact_branch.py:489), отложенные досылки (:560). Условие 2б не сверяет локальный PLAN с origin.
- «сдвиг ссылки после начала CI» — git не хранит время пуша; наблюдаемый канал SPEC не назван.
- Мандатные тесты: 01m4begq…::test_ac4 подслучай stale; 01m5xzsk…::test_ac9_unmet_condition (stale_base), test_ac10 (stale_base); стенд 01m5xzsk — merge_gate: operator (строка 125).
- test_ac9_fresh_against_base_without_main_is_green теряет ловимую мутацию (база vs main) — для target-human покрытия нет.

## Не сработало
- ls/sed в Bash отклоняются — пользоваться Read и grep.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, 7 отклонений; guard ок. Опыт git (дата коммита ≠ момент пуша, у голого origin нет reflog) — в /tmp/audit01m6-*.

## Чего не хватило
- Где пульт журналирует время пуша refs/artifacts (artifact_branch.push журналирует исходы) — не проверял глубоко.
