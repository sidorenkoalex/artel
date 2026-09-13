---
operator: Alexander Sidorenko
model: unknown
artel_sha: 01b6a33c6078e8dd071828c1e7e2e41d7f871e0d
---

# RETRO: 01M2CN465WEDCF6D77V37FJ82E — Фикс утечки тестов в настоящий пульт: WORKTREES в песочнице test_git_fixation

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: Фикс утечки тестов в настоящий пульт: WORKTREES в песочнице test_git_fixation

Стоимость итого: $15.27
  analyst: $1.63, 2420740 токенов
  test_author: $6.07, 12079889 токенов
  developer: $5.06, 11325973 токенов
  reviewer: $2.51, 4123536 токенов

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 2 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
планка: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M2CN465WEDCF6D77V37FJ82E/tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests, cwd: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M2CN465WEDCF6D77V37FJ82E
вит мутацию: разработчик правит `tests/test_invariants.py`
        напрямую в коде ветки вместо приложения диффа к PLAN.md (SPEC
        «Не входит» это явно запрещает) — файл появится в списке
        изменённых путей, и `assertNotIn` покраснеет.
        """
        changed = _util.changed_paths_since_main()
>       self.assertNotIn(
            TARGET_FILE, changed,
            f"{TARGET_FILE} не должен править код ветки задачи напрямую "
            f"— только приложением unified diff к PLAN.md (AC-4)")
E       AssertionError: 'tests/test_invariants.py' unexpectedly found in ['docs/codebase-map.md', 'docs/invariants.md', 'docs/retro/01M2CN3VV99BTAJF2JBTNADQPH.md', 'orchestrator/checkpoint.py', 'tasks/01M2CN3VV99BTAJF2JBTNADQPH/PLAN.md', 'tasks/01M2CN3VV99BTAJF2JBTNADQPH/REVIEW.md', 'tasks/01M2CN3VV99BTAJF2JBTNADQPH/SPEC.md', 'tasks/01M2CN3VV99BTAJF2JBTNADQPH/TZ.md', 'tasks/01M2CN3VV99BTAJF2JBTNADQPH/acceptance_tests/test_ac1_wip_checkpoint_shared_helper.py', 'tasks/01M2CN3VV99BTAJF2JBTNADQPH/acceptance_tests/test_ac2_commit_external_step_artifacts_split.py', 'tasks/01M2CN3VV99BTAJF2JBTNADQPH/acceptance_tests/test_ac3_full_suite_regression.py', 'tasks/01M2CN3VV99BTAJF2JBTNADQPH/acceptance_tests/test_ac4_ac5_smoke_and_plan_documentation.py', 'tasks/01M2CN3VV99BTAJF2JBTNADQPH/acceptance_tests/test_ac6_protected_code_untouched.py', 'tests/test_git_fixation.py', 'tests/test_invariants.py'] : tests/test_invariants.py не должен править код ветки задачи напрямую — только приложением unified diff к PLAN.md (AC-4)

tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/test_ac4_invariants_diff_attachment.py:84: AssertionError
=========================== short test summary info ============================
FAILED tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/test_ac4_invariants_diff_attachment.py::TaskBranchDoesNotTouchTestInvariantsTest::test_ac4_task_branch_diff_does_not_touch_test_invariants
========================= 1 failed, 7 passed in 1.12s ==========================


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
