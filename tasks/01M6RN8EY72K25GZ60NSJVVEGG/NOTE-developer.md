# Записка developer

## Выяснено
- Реализация: targets.py (поле, проверка, `render_template` — один `re.sub`),
  checkpoint.py (`task_project_entry`, `pult_subject`, применение в
  `_commit_worktree_change`), pull.py, amend.py, advance_gates/review.py
  (`_templated_pull_subject`).
- Итерация ревью 1, R1-F1 закрыт: отказ шаблону с `\n`/`\r` в
  `_check_delivery`; `_git_subject` в review.py нормализует ожидаемую тему как
  git (`%s`), тема лога сравнивается после `rstrip()`. Новый тест
  `tests/test_commit_message_template_subject.py` (9 тестов, 3 мутации красят).
- `target-set` уже сам отказывает многострочному значению («в одну строку»),
  yamlmini не раскрывает `\n` в кавычках — поэтому отказ загрузчика
  тестируется прямо через `targets._check_delivery`.
- Тест-модуль, импортирующий `orchestrator.checkpoint` первым, ловит цикл
  импорта — сначала `from orchestrator import artel`.

## Не сработало
- Составные Bash-команды с `cp`/`;`/редиректом отклоняются — мутации делал
  одним python-скриптом с восстановлением файла в `finally`.

## Где остановился
- Код, тест, карта, PLAN/REVIEW-реестр обновлены; см. итог прогона в PLAN.

## Чего не хватило
- Ничего существенного.
