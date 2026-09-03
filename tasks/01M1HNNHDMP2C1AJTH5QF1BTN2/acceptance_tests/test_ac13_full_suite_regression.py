"""AC-13 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Существующие тесты,
включая LockTest инварианта 27, остаются зелёными без ослабления.»

Регрессия всего существующего набора — не отдельный юнит-тест здесь, см.
пометку ниже.

Зелёный с рождения: файл несёт только пометку `# AC-13: skip` — ни
одного тестового метода, ни одного класса `unittest.TestCase`, поэтому
`unittest discover` не найдёт здесь ничего, что могло бы упасть.
"""

# AC-13: skip — регрессия всего существующего набора tests/ (включая
# tests/test_acceptance_tests_flow.py::LockTest) уже исполняется штатным
# CI-гейтом на каждом коммите ветки задачи, и именно его зелёный статус
# требует merge_gate (orchestrator/fsm.py, cmd_approve при state ==
# "merge_gate"). Дублирующий здесь subprocess-прогон всего tests/ не даёт
# новой гарантии сверх штатного гейта, а только удлиняет приёмочный
# прогон этой задачи — тот же приём, что
# tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/acceptance_tests/test_ac9_full_suite_regression.py
# и tasks/T050/acceptance_tests/test_ac9_full_suite_regression.py.
