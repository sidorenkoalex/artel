# Записка developer

## Выяснено
- Реализация: runner.spawn_agent(nproc_limit=) → preexec_fn с setrlimit; runner._read_maxprocperuid/role_nproc_limit/_user_process_count/_step_nproc_limit; вызов _step_nproc_limit в _run_developer_step после _refuse_before_start, до подтяжки и _run_attempts; предел протянут _run_attempts → run_agent_once → _spawn_and_wait (kwarg nproc_limit).
- Снятие группы на обычном исходе — ветка else у proc.wait в _spawn_and_wait, до close_pump; запись action "agent process group terminated".
- doctor: orchestrator/doctor/role_nproc.py, строка role-nproc, регистрация в cli.all_checks после machine-load.
- plank-run: 27 passed; долгоживущий файл: 3 passed.

## Не сработало
- Bash: ls/awk недоступны; cd + git отклоняется.

- Свой тест tests/test_role_nproc_limit.py (7 тестов), сторожа проверены мутацией; затронутые модули — 624 passed.
- Приложение skills/test-authoring.md: git apply --check проходит (диф из ТЗ, закрывающий ``` вынесен на свою строку).
- guard.py на файле tests/ ругается «нет frontmatter» — это не артефакт, применим только к tasks/; заявки мутаций проверены guard.test_functions_without_mutation_claim.

## Где остановился
- Готово: код, тесты, docs/stack.md, карта, PLAN.md status: ready.

## Чего не хватило
- Как прогнать линт заявок мутаций/детерминизма для своего теста — пришлось звать функции guard/test_lint вручную.
