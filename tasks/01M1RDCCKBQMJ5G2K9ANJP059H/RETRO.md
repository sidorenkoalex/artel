---
operator: Alexander Sidorenko
model: unknown
artel_sha: f1010dd9dcb119ef3a014031b36e0bef77b32d4a
---

# RETRO: 01M1RDCCKBQMJ5G2K9ANJP059H — объявленный стек пульта, часть 2 — CI на объявленной версии Python

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: объявленный стек пульта, часть 2 — CI на объявленной версии Python

Стоимость итого: $14.14
  analyst: $1.31, 1805795 токенов
  test_author: $2.13, 3693144 токенов
  developer: $5.32, 10240188 токенов
  reviewer: $5.38, 8551879 токенов

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 5 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
н существовать (AC-3)",
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
AssertionError: False is not true : /private/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/scripts/stack_ci.py должен существовать (AC-3)

======================================================================
FAIL: test_ac4_dedicated_test_passes_when_manifest_and_script_agree (test_ac4_stack_ci_matches_manifest.Ac4StackCiManifestSyncTest.test_ac4_dedicated_test_passes_when_manifest_and_script_agree)
Запускает `tests/test_stack_ci.py` отдельным процессом — так
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/artel-acceptance-01M1RDCCKBQMJ5G2K9ANJP059H-mrw0ntqs/acceptance_tests/test_ac4_stack_ci_matches_manifest.py", line 37, in test_ac4_dedicated_test_passes_when_manifest_and_script_agree
    self.assertEqual(
    ~~~~~~~~~~~~~~~~^
        result.returncode, 0,
        ^^^^^^^^^^^^^^^^^^^^^
    ...<2 lines>...
        f"STDERR:\n{result.stderr}",
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
AssertionError: 1 != 0 : tests/test_stack_ci.py должен быть зелёным при согласованных манифесте и скрипте:
STDOUT:

STDERR:
tests (unittest.loader._FailedTest.tests) ... ERROR

======================================================================
ERROR: tests (unittest.loader._FailedTest.tests)
----------------------------------------------------------------------
ImportError: Failed to import test module: tests
Traceback (most recent call last):
  File "/Users/al.sidorenko/.pyenv/versions/3.13.12/lib/python3.13/unittest/loader.py", line 137, in loadTestsFromName
    module = __import__(module_name)
ModuleNotFoundError: No module named 'tests'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)


----------------------------------------------------------------------
Ran 3 tests in 0.050s

FAILED (failures=2, errors=1)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
