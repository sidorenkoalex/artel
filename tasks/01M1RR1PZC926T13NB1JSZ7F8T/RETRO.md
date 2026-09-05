---
operator: Alexander Sidorenko
model: unknown
artel_sha: c0097a4e35f363a5afeb1ba42ea7a70fb98dbca4
---

# RETRO: 01M1RR1PZC926T13NB1JSZ7F8T — Занятость зоны только по старту developer (регрессия 01M1REVJ8AJ)

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: Занятость зоны только по старту developer (регрессия 01M1REVJ8AJ)

Стоимость итого: $10.25
  analyst: $1.60, 114234 токенов
  test_author: $2.40, 4412359 токенов
  developer: $5.20, 10278707 токенов
  reviewer: $1.06, 1742818 токенов

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 2 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
", line 53, in <module>
    from . import store
  File "/Users/al.sidorenko/projects/artel/.artel/worktrees/01M1RR1PZC926T13NB1JSZ7F8T/orchestrator/store.py", line 18, in <module>
    from . import config, session
  File "/Users/al.sidorenko/projects/artel/.artel/worktrees/01M1RR1PZC926T13NB1JSZ7F8T/orchestrator/session.py", line 19, in <module>
    def resolve_session_id(session_id: str | None = None) -> str:
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'


======================================================================
FAIL: test_ac6_test_zone_lock_suite_stays_green (test_ac6_zone_lock_suites_stay_green.ZoneLockAndZonesGateSuitesStayGreenTest)
`python3 -m unittest tests.test_zone_lock` (реальное дерево
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/artel-acceptance-01M1RR1PZC926T13NB1JSZ7F8T-i1ys87qj/acceptance_tests/test_ac6_zone_lock_suites_stay_green.py", line 43, in test_ac6_test_zone_lock_suite_stays_green
    self.assertTrue((_REPO_ROOT / "tests/test_zone_lock.py").is_file())
AssertionError: False is not true

======================================================================
FAIL: test_ac6_test_zones_gate_suite_stays_green (test_ac6_zone_lock_suites_stay_green.ZoneLockAndZonesGateSuitesStayGreenTest)
`python3 -m unittest tests.test_zones_gate` (реальное дерево
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/artel-acceptance-01M1RR1PZC926T13NB1JSZ7F8T-i1ys87qj/acceptance_tests/test_ac6_zone_lock_suites_stay_green.py", line 60, in test_ac6_test_zones_gate_suite_stays_green
    self.assertTrue((_REPO_ROOT / "tests/test_zones_gate.py").is_file())
AssertionError: False is not true

----------------------------------------------------------------------
Ran 4 tests in 0.000s

FAILED (failures=2, errors=2)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
