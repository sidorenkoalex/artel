---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-7: ответ Оператора

## Ответы

---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-7: ответ Оператора

## Ответы

Правка по ANSWER-6 (коммит 14bbdd53) закрыла 8 из 9 красных. Остался
один: `test_ac5_amend_journal.py::test_ac5_journal_entry_names_pytest_
style_green_summary`, та же ошибка `Error importing plugin "timeout"` из
pyenv. Воспроизведено Оператором прогоном планки голым `python3` из PATH
против worktree, как это делает пульт (28 тестов, 1 красный).

Причина: AC-5 строит песочницу `RealGitSandbox` (`tests/sandbox.py`),
которая подменяет `config.ROOT` на временный git-репозиторий в
`/private/var/folders/…`. `stack._main_copy_root()` делает
`git rev-parse --git-common-dir` с `cwd=config.ROOT`, получает `.git`
временного репозитория, и venv там нет ни у «worktree», ни у «главной
копии» — запасной `sys.executable` снова pyenv. Остальные тесты планки
гоняют раннер против настоящего worktree, поэтому у них поиск через git
доходит до venv главной копии.

Требование: venv принадлежит той установке пульта, чей КОД исполняется,
а не подменяемому тестами `config.ROOT`. В `_main_copy_root()` отправной
точкой для `git rev-parse --git-common-dir` бери расположение самого
модуля: `Path(__file__).resolve().parent.parent` (`orchestrator/stack.py`
→ корень копии кода, worktree или главная). В рабочем пульте это тот же
путь, что `config.ROOT`; в песочнице с подменённым `ROOT` — настоящий
worktree, откуда git ведёт к главной копии и её venv. Порядок поиска из
ANSWER-6 сохраняется: `config.VENV_DIR` → venv главной копии по
расположению кода → `sys.executable` с предупреждением.

Тест в `tests/test_stack.py`: `config.ROOT` подменён на временный
каталог без venv, функция всё равно возвращает venv по расположению
модуля (venv-заглушку положи в главную копию временного репозитория,
куда ведёт `git rev-parse` от каталога с копией `stack.py`, либо
замокай `subprocess.run` и проверь, что `cwd` — каталог модуля, а не
`config.ROOT`); мутация «отправная точка снова `config.ROOT`» — красный.
Планку не трогай — она залочена и права.

Проверка перед сдачей ровно как у пульта: из worktree
`python3 -m unittest discover -s tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/acceptance_tests`
с `python3` из PATH (pyenv). 28 из 28 — коммит до конца хода, PLAN.md —
раздел «## Возврат — venv по расположению кода», status: ready.
