# Записка developer (итерация 2)

## Выяснено
- R1-F1: `project_checks._drop_group(proc)` теперь `killpg SIGKILL` → `proc.wait()` → пробы; без сбора зомби-лидера группа на macOS отвечает `PermissionError` на каждую пробу. Опыт после правки — `{'gone': 1}`.
- R1-F2: сторож `tests/test_doctor_compose_stands.py` (4 теста, фасад `doctor.check_compose_stands`/`_fix_compose_stands`); 5 мутаций orphans.py проверены — все красят.
- Часть 1 в ветке: `acceptance.find_docker`, `compose_env(profile, docker)`, `COMPOSE_RUN_LABELS`, `config.COMPOSE_TEARDOWN_TIMEOUT_SEC`.

## Не сработало
- `pytest -n 4` в шаге роли падает «node down» — гонять последовательно.
- Shell-функции и `{...}` в heredoc отклоняются песочницей — сценарий мутаций писал файлом и убирал `task-rm`.

## Где остановился
- Готово: код, сторож, карта, PLAN `ready`, реестр REVIEW размечен `fixed`. Планка 30/30, затронутые 149 + карта 34.

## Чего не хватило
- Ничего существенного.
