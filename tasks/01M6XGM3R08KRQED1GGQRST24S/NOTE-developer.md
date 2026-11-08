# Записка developer

## Выяснено
- PLAN.md: шапка + разделы «## Приложение 1…5», скопированные программно из TZ.md (от «## Приложение 1» до конца), байт в байт; `guard.plan_appendices(PLAN) == plan_appendices(TZ)` — True.
- Все пять приложений проходят `git apply --check` на HEAD 79dd269f.
- `docs/codebase-map.md` регенерирован (новый файл tests/ test_author'а) — единственная правка в worktree.
- Временная копия (git archive HEAD + приложения + карта): долгоживущий файл задачи, role_templates, guard_division_section, spec_budget, template_commits — 115 passed. На дереве без приложений тот же набор + test_brief, spec_audit_flow, yaml_parsing — 204 passed.

## Не сработало
- `plank-run` краснеет «PLAN.md задачи нет в ссылке документов»: планка берёт PLAN из ссылки, попадёт туда после автокоммита шага. Ожидаемо.
- В Bash нет `cp`/`ls`, `$?` отклоняется — пользоваться python.

## Где остановился
Шаг готов: PLAN.md status: ready, guard ок.

## Чего не хватило
Ничего существенного.
