# Записка developer

## Выяснено
- Часть 1 уже в ветке (коммит «подтяжка main» e15c0f506): `acceptance.find_docker`, `compose_env(profile, docker)`, `COMPOSE_RUN_LABELS`, `config.COMPOSE_TEARDOWN_TIMEOUT_SEC`.
- `machine.path` попадает в `env.PATH` профиля — `project_profile.component_profiles(name)` даёт профили и для `test_profile` (компонент `default`).
- Планка ищет строку/починку в фасаде по `__module__ == orphans` и префиксам `check_`/`_fix_` — новые имена `check_compose_stands`, `_fix_compose_stands`; других `check_*`/`_fix_*` в orphans не добавлять.
- Общий вызов docker — `project_checks._docker_call` (Popen, `start_new_session`, по пределу `killpg SIGKILL`, `proc.wait()`, затем ≤ `GROUP_GONE_PROBES` проб сигналом 0).

## Не сработало
- `pytest -n 4` в шаге роли: воркеры xdist падают «node down» — гонял последовательно.

## Где остановился
- Готово: код, карта, PLAN `ready`. Планка 30/30, долгоживущие 26/26, тесты doctor 194 + 369 зелёные.

## Чего не хватило
- Имени строки/починки в SPEC (выводил из правила поиска планки).
