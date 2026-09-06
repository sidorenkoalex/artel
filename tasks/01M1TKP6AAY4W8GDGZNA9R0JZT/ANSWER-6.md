---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-6: ответ Оператора

## Ответы

---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-6: ответ Оператора

## Ответы

Эскалация «приёмочные тесты красные после подтяжки main» (9 из 28,
17:38Z). Слияние с main ни при чём и сохранено — красна среда, в которой
пульт гоняет планку задачи. Диагноз по трассировке из журнала:

```
File ".../.pyenv/versions/3.13.12/lib/python3.13/site-packages/_pytest/config/__init__.py"
ImportError: Error importing plugin "timeout": No module named 'timeout'
```

Pytest поднялся из интерпретатора pyenv, а не из venv пульта. Причина в
`stack.pytest_python_executable()`: она ищет venv по `config.VENV_DIR =
ROOT / ".artel" / "venv"`, где `ROOT` — корень той копии кода, откуда
импортирован модуль. Планку пульт гоняет против worktree задачи
(`acceptance.run(tdir, code_root=<worktree>)`), в worktree каталога
`.artel/venv` нет (там только `.artel/projects`), функция уходит в
запасной `sys.executable`, а процесс планки пульт главной копии запускает
голым `python3` из PATH — это pyenv 3.13 без `pytest-timeout`. Явная
загрузка `-p timeout` честно падает. Локально у тебя всё зелёное, потому
что ты запускал из venv.

Требование: `pytest_python_executable()` не должна зависеть от того, что
venv лежит рядом с импортированным кодом. Venv пульта живёт в главной
копии репозитория, из которой созданы worktree. Порядок поиска:

1. `config.VENV_DIR`, если каталог есть (главная копия — как сейчас);
2. иначе venv главной копии, найденный через git: корень общего
   `.git` (`git rev-parse --git-common-dir` из `ROOT`, worktree указывает
   на `<главная копия>/.git`) → `<главная копия>/.artel/venv/bin/python3`;
3. иначе `sys.executable` с предупреждением в stderr, что venv не найден
   (как WARN `_venv_exists_check`).

Тест на п.2 в `tests/test_stack.py`: временный репозиторий с worktree,
venv-заглушка только в главной копии (пустой файл `bin/python3`) — функция
возвращает путь главной копии; мутация «п.2 убран» — красный. Ни один
существующий assert не ослабляется.

Проверка перед сдачей — ровно как у пульта, не из venv: из главной копии
`python3 -c "from orchestrator import acceptance; ..."` либо просто
`python3 -m unittest discover -s tasks/<id>/acceptance_tests` в worktree с
`python3` из PATH (pyenv). 28 из 28 — сдавай, коммит до конца хода,
PLAN.md — раздел «## Возврат — интерпретатор venv из worktree», status:
ready.
