# Записка analyst

## Выяснено
- ТЗ достаточно, SPEC.md написан (status: ready, budget_usd 25 по рамке ТЗ, 7 AC, зоны из ТЗ), guard проходит.
- `yamlmini.mapping` уже разбирает `test_profile.env` как вложенный dict строк — правка yamlmini не нужна.
- Проверка профиля: `orchestrator/targets.py` — `PROFILE_FIELDS`/`PROFILE_OPTIONAL`/`_check_profile`/`_profile_value_error`; `Profile` — `orchestrator/project_profile.py:64`.
- Места запуска: `acceptance.py` run:384, collect:512, run_repeat:649, run_plank:923, _run_full_suite_now:1313, _run_full_suite_to_log:1361, флаг `observed_full_suite`:179; `two_sided._run_side`:222.
- `secret_env_names()` — providers/base.py:256, claude.py:213, codex.py:500.

## Не сработало
- guard отказал на упоминание `orchestrator/providers/` без классификации — добавил строку в «Не входит».

## Где остановился
- SPEC готов, QUESTIONS.md не создавался.

## Чего не хватило
- Ничего существенного.
