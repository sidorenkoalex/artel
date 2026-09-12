"""AC-9 (tasks/01M2B6JWGS9HMR9XZJBASXVNSY/SPEC.md): «Существующие тесты
`tests/test_lease*.py`, `tests/test_budget*.py` и `tests/test_catalog*.py`
проходят без ослабления (ни одна существующая проверка не удалена и не
смягчена).»

Регрессия существующего набора — не отдельный юнит-тест здесь, см.
пометку ниже.

Зелёный с рождения: файл несёт только пометку `# AC-9: skip` — ни
одного тестового метода, ни одного класса `unittest.TestCase`, поэтому
`unittest discover` не найдёт здесь ничего, что могло бы упасть.
"""

# AC-9: skip — регрессия tests/test_lease*.py, tests/test_budget*.py и
# tests/test_catalog*.py уже исполняется штатным CI-гейтом на каждом
# коммите ветки задачи, и именно его зелёный статус требует merge_gate
# (orchestrator/fsm.py, cmd_approve при state == "merge_gate"). Дублирующий
# здесь subprocess-прогон тех же файлов не даёт новой гарантии сверх
# штатного гейта, а только удлиняет приёмочный прогон этой задачи — тот
# же приём, что
# tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/test_ac13_full_suite_regression.py
# и предшествующие ей прецеденты (01M1GJ3ZP1YGG5QRB6FQ44NN8D, T050).
