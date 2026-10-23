# Записка developer — 01M5KJNE39PHV9EAWJCHK7QDFS

## Выяснено
- Реализовано и закоммичено (73fc60c4): tests/direct_git.py (prefer_direct_git), tests/__init__.py (import os; from .direct_git import prefer_direct_git; DIRECT_GIT_DIR = prefer_direct_git(os.environ)), карта регенерирована.
- Долгоживущий файл: 11 passed, AC-7 не пропущен на этой машине; own_run_path и pult_pytest_unchanged зелёные.
- Мутации платформа / exists без X_OK / без normpath — красные.
- Планка: AC-6 зелёный только после коммита (branch_diff берёт закоммиченное); AC-9 красен, пока PLAN.md не перенесён автокоммитом в ссылку документов.
- AC-10: 261 запуск git и в базе, и в ветке (хук аудита); в ветке +1 xcode-select.

## Не сработало
- Bash: нет cat/ls; `for` с `$t` и heredoc с `{'` отклоняются песочницей.

## Где остановился
- PLAN.md status: ready, замеры внесены. Шаг завершён.

## Чего не хватило
- Что plank-run AC-6 видит только закоммиченный дифф — узнал по красному прогону.
