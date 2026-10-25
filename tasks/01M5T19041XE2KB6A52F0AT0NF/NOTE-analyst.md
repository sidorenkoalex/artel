# Записка analyst — 01M5T19041XE2KB6A52F0AT0NF

## Выяснено
- Единая точка перечня защищённых путей проекта — `orchestrator/repo_context.py:106` `protected_paths(ctx)` (внешний — `ctx.no_paths`, собранный в `resolve`, `:96`). Её зовут: `advance_gates/zones.py:265`, `fsm.py:1188`, `fsm_merge_gate.py:108,272,973`, `github_adapter.py:193`, `appendix_tree.py:263`, `advance_gates/plan_appendix.py:169`, `catalog.py:236`. runner.py `no_paths` не сверяет.
- Формула сверки — `config.is_protected_path` (`orchestrator/config.py:789`): маска `**/<имя>` — только по последнему компоненту пути; `**/.claude/` (каталог на любой глубине) ею не выражается, а config.py в ТЗ — только чтение.
- `tests/test_project_protected_paths.py::ProjectPerimeterTest::test_external_perimeter_is_its_no_paths` ждёт `protected_paths(vnesh) == ("zz/",)` — краснеет, если обвязка входит в `protected_paths`; литерал-контейнер, разделом «Меняемое поведение» не оформляется.
- `tests/test_doctor.py::TargetWrapperCheckTest::test_wrapper_present_is_warn_and_names_the_markers` — warn на обвязке в клоне; по новому смыслу (клон без рабочих копий) — `'warn'` → `'ok'` (скаляр, годится для «Меняемое поведение»).
- `TARGET_WRAPPER_MARKERS` — `orchestrator/doctor/preflight.py:516`, реэкспорт `doctor/__init__.py:136`.

## Где остановился
Батч QUESTIONS.md сдан (guard ок), 3 вопроса: где объединять обвязку с no_paths; маска `**/.claude/` при config.py только для чтения; doctor у артели. SPEC.md не писался. После ANSWER — писать SPEC (зоны при дефолтах A/A/A: targets.py, workspace.py, repo_context.py, github_adapter.py, config.py, doctor/preflight.py, doctor/__init__.py, tests/; бюджет 45; секция деления обязательна — сигналы ≥5 файлов и ≥$30), удалить QUESTIONS.md.

## Чего не хватило
Поиск, поддерживает ли `is_protected_path` маски каталогов `**/<dir>/` — нет (config.py:806-814).
