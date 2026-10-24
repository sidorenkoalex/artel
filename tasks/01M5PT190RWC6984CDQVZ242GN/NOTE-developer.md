# Записка developer

## Выяснено
- Сделано и зелёно: патчи mutation-001…026 (каждый проверен одиночным прогоном
  в копии $TMPDIR; строки падения «до» — в PLAN, раздел «Мутации»);
  tests/report_outcome_sandbox.py (ast.dump 50/50); tests/test_report_outcome_module.py
  (26 функций, 1344 строки, «26 passed in 23.58s»); переходной модуль;
  импорт test_component_report_gates.py; карта перегенерирована.
- Модуль собирается заново: из корня worktree
  `python3 <docs>/assemble_report_outcome.py <docs>/module_head.txt > tests/test_report_outcome_module.py`
  (сборка читает исходник через `git show HEAD:` — после коммита сведения
  HEAD уже переходной модуль! тогда брать базу: поправить ревизию в assemble).
- Планке нужны в PLAN строки «mutation-NNN + Класс::метод + tests/<файл>.py:<строка>»
  и для «после» — `test_report_outcome_module.py::<функция>` + строка нового файла.
- `ls`/`cat`/`ps` в Bash нет; heredoc с `{`+кавычкой Bash отклоняет —
  скрипты файлом в каталог документов.

## Не сработало
- mutation-run --ref base 1-13: три раза (№1–№3) отказ «контроль красный» —
  VitestReporterTest::test_ac9_timeout_kills_group_not_green :1249 «раннер не
  запускался» (предел компонента 1 с под xdist). PLAN — status: escalate.

## Где остановился
- Ждём ответа Оператора на эскалацию. Дальше: «до» частями 1-13, 14-26 →
  «после» (`--ref worktree --tests tests/test_report_outcome_module.py`, перед
  каждой частью вывод `git status --porcelain -- orchestrator/`) → строки
  «после» в PLAN → итог CI → status: ready.
- Адресный прогон этого шага уже потрачен на tests/test_report_outcome_module.py.

## Чего не хватило
- Способа прогнать контроль mutation-run без xdist / с повтором красного теста.
