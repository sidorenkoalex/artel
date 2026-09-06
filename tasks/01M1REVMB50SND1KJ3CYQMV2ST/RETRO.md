---
operator: Alexander Sidorenko
model: unknown
artel_sha: c41d403d5e4b748e6956f39564a1070c0915a5df
---

# RETRO: 01M1REVMB50SND1KJ3CYQMV2ST — эскалация «конфликт подтяжки main» называет конфликтные файлы

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: эскалация «конфликт подтяжки main» называет конфликтные файлы

Стоимость итого: $9.09
  analyst: $1.29, 1956360 токенов
  test_author: $2.04, 3477256 токенов
  developer: $3.27, 5836573 токенов
  reviewer: $2.50, 4332399 токенов

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: 2 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
планка: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1REVMB50SND1KJ3CYQMV2ST/tasks/01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests, cwd: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1REVMB50SND1KJ3CYQMV2ST
.......F
======================================================================
FAIL: test_ac5_map_only_conflict_still_autoresolves_without_escalation (test_pull_conflict_detail.PullConflictDetailTest.test_ac5_map_only_conflict_still_autoresolves_without_escalation)
Единственный конфликтующий файл — ровно `docs/codebase-map.md`
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/al.sidorenko/projects/artel/.artel/worktrees/01M1REVMB50SND1KJ3CYQMV2ST/tasks/01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests/test_pull_conflict_detail.py", line 466, in test_ac5_map_only_conflict_still_autoresolves_without_escalation
    acc_run.assert_called_once_with(self.wt_path / "tasks" / self.TASK)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/unittest/mock.py", line 991, in assert_called_once_with
    return self.assert_called_with(*args, **kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/unittest/mock.py", line 979, in assert_called_with
    raise AssertionError(_error_message()) from cause
AssertionError: expected call not found.
Expected: run(PosixPath('/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/tmplj7z_tet/wt/tasks/01M1THKBEQ1E2MV2T4H0VRWCXH'))
  Actual: run(PosixPath('/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/tmplj7z_tet/wt/tasks/01M1THKBEQ1E2MV2T4H0VRWCXH'), code_root=PosixPath('/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/tmplj7z_tet/wt'))

----------------------------------------------------------------------
Ran 8 tests in 0.104s

FAILED (failures=1)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
