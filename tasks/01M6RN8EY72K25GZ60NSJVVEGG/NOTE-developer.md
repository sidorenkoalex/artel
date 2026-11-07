# Записка developer

## Выяснено
- Реализация: targets.py (поле, проверка, `render_template` — один `re.sub`),
  checkpoint.py (`task_project_entry`, `pult_subject`, применение в
  `_commit_worktree_change` — через неё идут все чекпоинты), pull.py
  (`_auto_resolve_conflict`, `_run_merge` теперь с `conn` первым
  аргументом), amend.py (`_commit_long_lived` принимает текст без `<id>: `),
  advance_gates/review.py (`_templated_pull_subject`, полное равенство темы).
- Долгоживущие файлы задачи: 37/37 зелёные (commits-файл идёт ~20 минут
  последовательно; `-n` xdist падает «node down»).

## Не сработало
- `timeout 590` над pytest обрезал вывод без итоговой строки — длинный файл
  гонять в фоне.

## Где остановился
- Прогон тестов затронутых модулей, карта, guard, PLAN ready.

## Чего не хватило
- Время прогона commits-файла (13 мин на AC-7/AC-8) нигде не указано.
