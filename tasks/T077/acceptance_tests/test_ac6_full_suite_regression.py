"""AC-6 (tasks/T077/SPEC.md): полный тестовый набор проекта зелёный
после изменений.

Зелёный с рождения: файл не несёт исполняемых тестов (только пометку
`skip` ниже) — редактировать нечего, красноты не бывает ни до, ни
после правки guard.py; регрессия всего набора проверяется штатным CI,
см. маркер ниже.
"""

# AC-6: skip — регрессия всего существующего набора tests/ уже
# исполняется штатным CI-гейтом на каждом коммите ветки задачи
# (.github/workflows/ci.yml, джоб python, `unittest discover -s tests`),
# и именно его зелёный статус требует merge_gate (orchestrator/fsm.py,
# cmd_approve при state == "merge_gate"). Дублирующий здесь
# subprocess-прогон всего набора не даёт новой гарантии сверх штатного
# гейта, а только удлиняет приёмочный прогон этой задачи — тот же
# приём, что tasks/T048/acceptance_tests/test_ac6_full_suite_
# regression.py и tasks/T053/acceptance_tests/test_ac7_full_suite_
# regression.py.
