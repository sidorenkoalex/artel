---
operator: Alexander Sidorenko
model: unknown
artel_sha: f0ac767db971451ee2a947f8611d4a19e73b2492
---

# RETRO: 01M1TKP6AAY4W8GDGZNA9R0JZT — P1a — раннер pytest в пульте: acceptance, dry_run, amend и их тесты

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: P1a — раннер pytest в пульте: acceptance, dry_run, amend и их тесты

Стоимость итого: $47.47
  analyst: $5.37, 8583108 токенов
  test_author: $13.00, 29798793 токенов
  developer: $25.63, 54466487 токенов
  reviewer: $3.47, 5693169 токенов

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: 7 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
планка: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1TKP6AAY4W8GDGZNA9R0JZT/tasks/01M1TKP6AAY4W8GDGZNA9R0JZT/acceptance_tests, cwd: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1TKP6AAY4W8GDGZNA9R0JZT
sers/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1232, in pytest_cmdline_parse
    self.parse(args)
    ~~~~~~~~~~^^^^^^
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1576, in parse
    self.pluginmanager.consider_preparse(args, exclude_only=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/site-packages/_pytest/config/__init__.py", line 835, in consider_preparse
    self.consider_pluginarg(parg)
    ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/site-packages/_pytest/config/__init__.py", line 864, in consider_pluginarg
    self.import_plugin(arg, consider_entry_points=True)
    ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/site-packages/_pytest/config/__init__.py", line 920, in import_plugin
    raise ImportError(
        f'Error importing plugin "{modname}": {e.args[0]}'
    ).with_traceback(e.__traceback__) from e
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/site-packages/_pytest/config/__init__.py", line 913, in import_plugin
    mod = importlib.import_module(importspec)
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1324, in _find_and_load_unlocked
ImportError: Error importing plugin "timeout": No module named 'timeout'

----------------------------------------------------------------------
Ran 28 tests in 126.290s

FAILED (failures=1)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
