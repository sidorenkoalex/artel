---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-4: ответ Оператора

## Ответы

# ANSWER-4: ответ Оператора

## Ответы

1. Вопрос из PLAN про `_util.py` закрыт ещё ANSWER-3: файл в артефактной
   ветке с 16cffbcc (amend-tests), планка 27/28 на твоём незакоммиченном
   коде — красен только AC-7. Остаток причины AC-7 (по выводу теста,
   строка `plugins: anyio-4.13.0`): плагин `pytest-timeout` не подключён,
   потому что подпроцесс `python3 -m pytest` берёт `python3` из PATH
   (pyenv 3.13), а pytest-timeout установлен только в venv пульта
   `.artel/venv` (P0, requirements.lock). `-o timeout=…` без плагина
   ничего не делает. Нужно: подпроцессы pytest в `acceptance.run()`/
   `run_full_suite()` (и в `amend`, если там свой вызов) запускать
   интерпретатором venv — `config.ROOT / ".artel/venv/bin/python3"`, если
   существует, иначе `sys.executable` — и передавать `-p pytest_timeout`
   явно, чтобы отсутствие плагина было ошибкой, а не тихим пропуском;
   в `doctor` (`venv-packages`) — сообщение о том, каким интерпретатором
   пульт гоняет тесты.
2. Дисциплина шага (второй обрыв подряд): прогон планки НЕ запускать в
   фоне — ход роли заканчивается вместе с процессом, уведомления не
   будет. Гоняй синхронно: сначала `tasks/<id>/acceptance_tests/
   test_ac7_per_test_timeout.py` (~2,5 мин), затем всю планку. Перед
   завершением хода: `git add -u && git commit`, PLAN.md со
   `status: ready` и снятыми вопросами. Незакоммиченная правка
   `orchestrator/acceptance.py` (`-o timeout`) в worktree сохранена —
   продолжай с неё. Полный `tests/` не запускать.
