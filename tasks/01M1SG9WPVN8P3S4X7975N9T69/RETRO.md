---
operator: Alexander Sidorenko
model: unknown
artel_sha: 20dd4c0c74c66cb897bb0026a64aed2d8f3348c9
---

# RETRO: 01M1SG9WPVN8P3S4X7975N9T69 — сторож Bash роли: возврат запрета полного прогона tests/ до таймаута на тест

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: сторож Bash роли: возврат запрета полного прогона tests/ до таймаута на тест

Стоимость итого: $9.84
  analyst: $1.14, 1464817 токенов
  test_author: $2.75, 5133368 токенов
  developer: $4.61, 9260445 токенов
  reviewer: $1.34, 2470111 токенов

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 2 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
планка: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1SG9WPVN8P3S4X7975N9T69/tasks/01M1SG9WPVN8P3S4X7975N9T69/acceptance_tests, cwd: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1SG9WPVN8P3S4X7975N9T69
.pyenv/versions/3.13.12/lib/python3.13/pathlib/_local.py", line 546, in read_text
    return PathBase.read_text(self, encoding, errors, newline)
           ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/pathlib/_abc.py", line 632, in read_text
    with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
         ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/pathlib/_local.py", line 537, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: '/Users/al.sidorenko/projects/artel/.artel/worktrees/01M1SG9WPVN8P3S4X7975N9T69/tasks/01M1SG9WPVN8P3S4X7975N9T69/SPEC.md'

======================================================================
FAIL: test_ac6_hook_docstring_states_removal_condition (test_ac6_removal_condition_documented.HookDocstringStatesRemovalConditionTest.test_ac6_hook_docstring_states_removal_condition)
Докстринг хука называет `pytest-timeout` как условие снятия и
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/al.sidorenko/projects/artel/.artel/worktrees/01M1SG9WPVN8P3S4X7975N9T69/tasks/01M1SG9WPVN8P3S4X7975N9T69/acceptance_tests/test_ac6_removal_condition_documented.py", line 68, in test_ac6_hook_docstring_states_removal_condition
    self.assertTrue(has_negation,
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
                    "докстринг не отрицает явно ручное снятие Оператором")
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : докстринг не отрицает явно ручное снятие Оператором

----------------------------------------------------------------------
Ran 17 tests in 0.169s

FAILED (failures=1, errors=2)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
