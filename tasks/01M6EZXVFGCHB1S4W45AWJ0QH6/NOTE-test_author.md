# Записка test_author — 01M6EZXVFGCHB1S4W45AWJ0QH6

## Выяснено
- Планка: acceptance_tests/_stand.py (общий стенд) + test_clone_hooks.py (AC-1–6, 18),
  test_push_checks.py (AC-7–10), test_doctor_line.py (AC-11–14, 16), test_hosting_token.py (AC-15, 17).
  Все AC — тестами, пометок manual/skip/escalate нет. 68 тестов.
- Группа — «разовый», как в прецеденте refs/artifacts/01M5WDB7F14SQ30QVWJY2XYBG2:…/test_push_point.py:
  долгоживущему файлу guard закрывает импорт orchestrator.gitcmd и вызов git через subprocess
  (scripts/guard.py::_GIT_MODULES, SIGN_GIT_CALL).
- Стенд: фикстура real_git; scripts/git-hooks проверяемого дерева копируется в config.ROOT и коммитится
  (эталон хука — HEAD). Записи проектов — targets.local_path(), url = путь bare-origin. HOME — временный
  (в нём protocol.file.allow=always для подмодуля AC-15); запрещённые GIT_* сняты.
- Строка doctor — doctor.check_clone_hooks(), починка — doctor._fix_project_clones() (их называет треб. 8).
- AC-17 гоняет настоящий `git credential fill` в окружении (и с `-c credential…` argv) хостингового вызова.
- До реализации: 44 красных по верным причинам (нет каталога target-human, нет сверок, нет строки,
  clone без токена, помощник без сверки host); зелёные — прежнее поведение (защита main, AC-4, AC-6, AC-9…).
- Стаб корректной реализации (хуки target-human, ensure_clone, сверки gitcmd, строка doctor, helper с host)
  дал 68 passed; стаб откачен, рабочая копия чиста. preflight — все проверки пройдены.

## Не сработало
- В оболочке шага нет `ls`/`cat` в PATH; листинг — через python3 os.walk, чтение — Read.

## Где остановился
- Шаг завершён: планка готова, preflight пройден.

## Чего не хватило
- Правила долгоживущих файлов (запрет gitcmd/subprocess-git) — пришлось искать в scripts/guard.py:4111-4135.
