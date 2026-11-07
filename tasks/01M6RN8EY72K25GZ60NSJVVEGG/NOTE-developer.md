# Записка developer

## Выяснено
- Реализация: targets.py (поле, проверка, `render_template` — один `re.sub`),
  checkpoint.py (`task_project_entry`, `pult_subject`, применение в
  `_commit_worktree_change` — через неё идут все чекпоинты), pull.py
  (`_auto_resolve_conflict`, `_run_merge` теперь с `conn` первым
  аргументом), amend.py (`_commit_long_lived` принимает текст без `<id>: `),
  advance_gates/review.py (`_templated_pull_subject`, полное равенство темы).
- Возврат из verifying (CI: SqlOnlyInStoreTest): два прямых SQL в
  checkpoint.py (`task_project_entry`, `pult_subject`) заменены на
  `store.task_exists`/`store.task_target`/`store.get_task` — store.py не
  тронут. `tests/test_multitarget.py -k SqlOnlyInStore` зелёный.

## Не сработало
- `timeout 590` над pytest обрезал вывод без итоговой строки — длинный файл
  гонять в фоне.

## Где остановился
- Шаг завершён: долгоживущие файлы 37/37 зелёные после правки (3:46),
  tests/test_multitarget.py 51/51, карта регенерирована, guard ок, PLAN ready.

## Чего не хватило
- Сторож «SQL только в store» не гоняется в шаге developer — узнали от CI.
