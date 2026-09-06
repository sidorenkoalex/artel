---
operator: Alexander Sidorenko
model: unknown
artel_sha: 04951f18bf53c402c879c53aef17d6f572cc72a1
---

# RETRO: 01M1TKP269W9JN3NBJCR5Q6C3B — канарейка — диагностика незелёного прогона и бейзлайн только с зелёного исхода

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: канарейка — диагностика незелёного прогона и бейзлайн только с зелёного исхода

Стоимость итого: $55.51
  analyst: $2.04, 3291117 токенов
  test_author: $9.05, 19334519 токенов
  developer: $22.47, 49918666 токенов
  reviewer: $6.59, 11833073 токенов

Ревью: 2 итераций; приёмка: 0 отказ(ов)

Эскалации: 3 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
планка: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1TKP269W9JN3NBJCR5Q6C3B/tasks/01M1TKP269W9JN3NBJCR5Q6C3B/acceptance_tests, cwd: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1TKP269W9JN3NBJCR5Q6C3B
baseline_after) if baseline_after is not None else None}")
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: <sqlite3.Row object at 0x1065439a0> is not None : killed-прогон завёл бейзлайн вопреки AC-8/AC-7: {'title': 'killed-ne-dolzhen-zavodit-bazu', 'steps': 4, 'cost_usd': 0.0, 'review_iterations': 0, 'updated_at': '2026-09-06 16:09:04Z'}

======================================================================
FAIL: test_ac8_killed_run_does_not_raise_a_deviation_alert (test_ac8_killed_runs_excluded_from_baseline_and_deviation.KilledRunDoesNotRaiseDeviationAlertTest.test_ac8_killed_run_does_not_raise_a_deviation_alert)
Несмотря на заведомо огромное отклонение раздутых метрик от
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/al.sidorenko/projects/artel/.artel/worktrees/01M1TKP269W9JN3NBJCR5Q6C3B/tasks/01M1TKP269W9JN3NBJCR5Q6C3B/acceptance_tests/test_ac8_killed_runs_excluded_from_baseline_and_deviation.py", line 139, in test_ac8_killed_run_does_not_raise_a_deviation_alert
    self.assertEqual(
    ~~~~~~~~~~~~~~~~^
        canary_deviation_alerts, [],
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        f"killed-прогон завёл алерт отклонения от бейзлайна вопреки "
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        f"AC-8: {canary_deviation_alerts}")
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: Lists differ: [<sqlite3.Row object at 0x1065a0d90>, <sqlite3.Row object at 0x1065a3010>] != []

First list contains 2 additional elements.
First extra element 0:
<sqlite3.Row object at 0x1065a0d90>

- [<sqlite3.Row object at 0x1065a0d90>, <sqlite3.Row object at 0x1065a3010>]
+ [] : killed-прогон завёл алерт отклонения от бейзлайна вопреки AC-8: [<sqlite3.Row object at 0x1065a0d90>, <sqlite3.Row object at 0x1065a3010>]

----------------------------------------------------------------------
Ran 18 tests in 28.441s

FAILED (failures=6)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
