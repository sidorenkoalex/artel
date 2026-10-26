# Записка developer — 01M5WDB7F14SQ30QVWJY2XYBG2

## Выяснено
- Возврат из verifying (CI 40384230945): `test_git_hooks.py::...test_repo_context_git_reaches_a_real_child_with_the_marker`
  падал — `-c alias.probe=!echo` во временном репо (не проект) отказывался «псевдоним git в команде».
- Уточнение гейта: отказ `-c alias.*`/`--config-env alias.*` при любой подкоманде, но только для клона под белым списком.
- Исправлено (шаг 8 PLAN): в `gitcmd._push_plan` отказ псевдонима после `targets.load()`, через новую
  `_alias_guarded_project` (клон вызова или слово после подкоманды — путь/`file://`/url записи;
  отказ при внешнем проекте под белым списком или с неизвестным гейтом).
- Тесты: `test_alias_defined_in_command_refused` — у `operator` теперь проходит; новый
  `test_alias_in_command_into_whitelisted_clone_from_pult_root_refused`. Мутации красные (6 и 2).
- Прогоны: 163 passed (push_point, git_hooks, multitarget, файлы задачи, А0, store), 20 passed соседние, планка 75 passed.

## Не сработало
- heredoc/`cp` в Bash роли требуют подтверждения — мутации только через Edit.

## Где остановился
- Шаг завершён: PLAN.md status: ready, карта регенерирована.

## Чего не хватило
- Ничего существенного.
