# NOTE developer

## Выяснено
- Реализация в коммите 19cc91aff: `targets.SUBMODULE_TOKENS_FIELD` (+ `_submodule_tokens_error`,
  отказ в `check` при `local=False`); `gitcmd.submodule_credentials`,
  `HOSTING_PATH_CREDENTIAL_HELPER`, `hosting_path_env` (запись без поля — прежний `hosting_env`);
  разбор `.gitmodules`/относительных адресов переехал в `gitcmd.gitmodules_entries`/
  `resolve_submodule_url`, doctor делегирует; `workspace._clone_submodules(clone, entry, target)`;
  `doctor` `_field_submodule_problem`.
- Долгоживущий файл 61 passed, AC-9 129 passed, plank-run 6 passed, guard PLAN ок.

## Не сработало
- `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py::EnsureCloneSurvivesFetchFailureTest`
  висит 120 с и на коде базы — среда машины, не задача.

## Где остановился
- PLAN status: ready, код закоммичен.

## Чего не хватило
- Команды «прогнать тест на базе» — сравнивал через `git checkout HEAD~1 -- orchestrator/`.
