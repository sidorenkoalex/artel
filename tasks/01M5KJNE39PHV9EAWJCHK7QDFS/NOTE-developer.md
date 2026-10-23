# Записка developer — 01M5KJNE39PHV9EAWJCHK7QDFS

## Выяснено
- Возврат из verifying (CI 39908727505): зеркало пакета tests в test_fsm_advance_tests_writing_test_groups.py без direct_git.py → ModuleNotFoundError.
- Ограда по решению Оператора (try/except ModuleNotFoundError, exc.name != "tests.direct_git" → raise, иначе DIRECT_GIT_DIR = None) внесена в tests/__init__.py (не закоммичена — коммитит пульт).
- С оградой: все 9 файлов с зеркалом зелёные (-p no:xdist), долгоживущий файл задачи 11 passed / 43 subtests.
- НО залоченная планка acceptance_tests/test_oneoff_init_and_plan.py::Ac6InitOnlyWiringTest красная: foreign_statements считает узел Try посторонним (разрешены только Import os/ImportFrom/одно Assign DIRECT_GIT_DIR = prefer_direct_git(os.environ)/Delete). Это противоречие с AC-6 → эскалация в PLAN.md (status: escalate), вариант — amend-tests планки.

## Не сработало
- Bash: `ls`, `$?`, `$t`, heredoc с `{'` отклоняются песочницей.

## Где остановился
- PLAN.md: status escalate, раздел «Эскалация». Ждём ANSWER-3.

## Чего не хватило
- Решение возврата не учитывало планку AC-6 (AST-разбор tests/__init__.py) — нашёл, прочитав acceptance_tests/test_oneoff_init_and_plan.py.
