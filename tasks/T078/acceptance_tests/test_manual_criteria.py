"""Приёмочные тесты T078 — критерий без прямого локального теста (AC-4).

Зелёный с рождения: файл не содержит исполняемых тестов — только
skip-пометку; краснеть здесь нечему.
"""

# AC-4: skip — «полный тестовый набор (tests/) зелёный» уже исполняется
# штатным CI-гейтом на каждом коммите ветки задачи (.github/workflows/
# ci.yml: `python3 -m unittest discover -s tests -v`) и требуется
# merge_gate (orchestrator/fsm.py, cmd_approve при state == "merge_gate") —
# тем же основанием, что tasks/T055/acceptance_tests/
# test_ac4_full_suite_regression.py и AC-8 в
# tasks/T072/acceptance_tests/test_manual_criteria.py. Дублирующий здесь
# subprocess-прогон всего tests/ не даёт новой гарантии сверх штатного
# гейта, только удлиняет приёмочный прогон этой задачи.
