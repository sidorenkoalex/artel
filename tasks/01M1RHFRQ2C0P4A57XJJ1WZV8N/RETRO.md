---
operator: Alexander Sidorenko
model: unknown
artel_sha: 368f3db47d694da6bf9475b9fe3c32549e91caef
---

# RETRO: 01M1RHFRQ2C0P4A57XJJ1WZV8N — регрессия №13 — после замечаний ревью `auto` запускает разработчика, а не переход

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: регрессия №13 — после замечаний ревью `auto` запускает разработчика, а не переход

Стоимость итого: $39.50
  analyst: $3.30, 4733711 токенов
  test_author: $12.72, 29415704 токенов
  developer: $17.07, 35586661 токенов
  reviewer: $6.41, 12908158 токенов

Ревью: 0 итераций; приёмка: 1 отказ(ов)

Эскалации: 3 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
eview_git_gate.py", line 149, in test_ac7_manual_advance_on_unchanged_code_refuses_named_not_transitions
    self.assertEqual(self.state(), "in_dev")
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'review' != 'in_dev'
- review
+ in_dev


======================================================================
FAIL: test_ac5_review_remarks_scenario_runs_developer_not_ready_plan_advance (test_ac5_review_remarks_runs_developer_step.ReviewRemarksScenarioRunsDeveloperBeforeAnyPreAdvanceSkipTest.test_ac5_review_remarks_scenario_runs_developer_not_ready_plan_advance)
Ловит мутацию: пред-advance пропускает шаг developer ТОЛЬКО
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/private/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/artel-acceptance-01M1RHFRQ2C0P4A57XJJ1WZV8N-ha07o7tg/acceptance_tests/test_ac5_review_remarks_runs_developer_step.py", line 57, in test_ac5_review_remarks_scenario_runs_developer_not_ready_plan_advance
    self.assertEqual(
    ~~~~~~~~~~~~~~~~^
        agent_run_finished_actors(conn, self.TASK), ["developer"],
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        "developer не отработал шаг ровно один раз — сценарий "
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        "«замечания ревью -> auto» продвинул задачу по готовому "
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        "PLAN.md, минуя developer (или отдал шаг другой роли)")
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: Lists differ: ['reviewer'] != ['developer']

First differing element 0:
'reviewer'
'developer'

- ['reviewer']
+ ['developer'] : developer не отработал шаг ровно один раз — сценарий «замечания ревью -> auto» продвинул задачу по готовому PLAN.md, минуя developer (или отдал шаг другой роли)

----------------------------------------------------------------------
Ran 10 tests in 3.792s

FAILED (failures=8)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
