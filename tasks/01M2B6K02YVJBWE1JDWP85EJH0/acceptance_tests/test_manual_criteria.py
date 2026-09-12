"""Приёмочные пометки 01M2B6K02YVJBWE1JDWP85EJH0 — критерии без прямого
локального теста (AC-9).

Зелёный с рождения: файл не содержит исполняемых тестов — только
skip-пометку; краснеть здесь нечему.
"""

# AC-9: skip — регрессия всего существующего набора tests/test_canary.py,
# tests/test_pin.py, tests/test_doctor*.py уже исполняется штатным
# CI-гейтом на каждом коммите ветки задачи (.github/workflows/ci.yml)
# и требуется merge_gate (orchestrator/fsm.py, cmd_approve при
# state == "merge_gate") — тем же основанием, что tasks/T072/
# acceptance_tests/test_manual_criteria.py (AC-8) и tasks/
# 01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/_sandbox.py (AC-8).
# Дублирующий здесь subprocess-прогон этих файлов не даёт новой
# гарантии сверх штатного гейта, только удлиняет приёмочный прогон этой
# задачи; changes к источнику sha в canary.py/pin.py/doctor/, требуемые
# этой же задачей, УЖЕ гоняются целевым набором AC-1..AC-8 выше на
# наблюдаемое поведение, а не только "существующие тесты не тронуты".
