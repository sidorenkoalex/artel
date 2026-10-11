"""AC-3 (tasks/T055/SPEC.md): `cmd_new` работает как прежде — задача
заводится, TZ/SPEC рождаются в worktree, main не тронут (существующие
тесты T048 зелёные).
"""

# AC-3: skip — буквально то же наблюдаемое поведение уже залочено
# существующими тестами, которые гоняет штатный CI-гейт на каждом
# коммите этой ветки: tests/test_workspace.py::EnsureTest
# .test_creates_worktree_on_a_fresh_branch_from_main и
# .test_fresh_branch_forks_from_main_not_from_head_of_something_else
# (ensure() заводит worktree свежей ветки от main) и
# tasks/T048/acceptance_tests/test_ac1_ac2_new_creates_branch.py (cmd_new:
# main не тронут, TZ.md/SPEC.md рождаются в ветке задачи). Дублирующий
# независимый прогон здесь не даёт новой гарантии сверх этих уже
# существующих локов, только удлиняет приёмочный прогон — тот же приём,
# что AC-6 в tasks/T048/acceptance_tests/test_ac6_full_suite_regression.py.
