# Записка developer — 01M52EEDEYV14658X8VFNHCW8K

## Выяснено
- `targets.py`: `runner` (вид `runner`), `workdir` (вид `dir`), `env` (новый вид `mapping`) — в `PROFILE_FIELDS` и `PROFILE_OPTIONAL`; условие «workdir/env только при pytest-own» — после проверки значений в `_check_profile`. Перечень секретов — публичная `targets.secret_env_names()` (реестр провайдеров + `FORGE_SECRET_ENV_NAMES`), импорт `providers` внутри функции (цикл providers→claude→runner→store→targets).
- `Profile`: `runner`, `workdir`, `env` (MappingProxyType, `hash=False`), умолчания из `targets.PROFILE_RUNNER_DEFAULT`.
- Требование 7 закрыто долгоживущим `..._launch_places.py`, места запуска не трогались.
- Оба долгоживущих файла + test_01m45…_test_profile, project_profile_gates, network_address_gate, targets_* , multitarget, repo_context — зелёные локально. Карта регенерирована.

## Не сработало
- suite-run №1: 4 красных подтеста `launch_places::test_ac7_full_suite_to_log_argv_cwd_env` — тест считает разницу env с os.environ, а полный прогон пульта уже несёт `PYTHONUNBUFFERED=1` (acceptance.py:1372). Воспроизводится `PYTHONUNBUFFERED=1 python3 -m pytest tests/test_01m52eed…_launch_places.py`. Код задачи ни при чём.

## Где остановился
- Код готов, PLAN `status: escalate` (вариант А — amend-tests: `os.environ.pop("PYTHONUNBUFFERED", None)` в `AcceptancePlacesTest.call`). После ответа — снять escalate, сдать ready, кода не править.

## Чего не хватило
- Предпроверка test_author не гоняет долгоживущие файлы в окружении полного прогона.
