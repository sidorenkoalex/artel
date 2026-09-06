"""Приёмочная пометка 01M1NGFK3N6MRMYGCC09H975V3, не выражаемая
собственным тестом в этом каталоге — AC-8.

AC-1..AC-7 — в остальных файлах этого каталога (`test_ac1_ac2_
pin_update_canary_gate.py`, `test_ac3_ac4_doctor_canary_trigger.py`,
`test_ac5_ac6_ac7_pin_to_rollback.py`), по одному файлу на связанную
пару/тройку критериев.

Зелёный с рождения: файл не содержит исполняемых тестов — только
пометку AC-8; краснеть здесь нечему.
"""

# AC-8: skip — регрессия всего существующего набора tests/ уже исполняется
# штатным CI-гейтом на каждом коммите ветки задачи (.github/workflows/
# ci.yml, джоб «Синтаксис и тесты оркестратора», `unittest discover -s
# tests -v` на чистом раннере), и именно его зелёный статус требует
# merge_gate (orchestrator/fsm.py::cmd_approve при state == "merge_gate").
# Дублирующий здесь subprocess-прогон всего набора не даёт новой гарантии
# сверх штатного гейта, а только удлиняет приёмочный прогон этой задачи —
# тот же приём, что tasks/01M1P9QAG65GVF69YJEV0V18D9/acceptance_tests/
# test_scope_markers.py (AC-10 там) и tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/
# acceptance_tests/test_ac7_existing_tests_stay_green.py.


if __name__ == "__main__":
    import unittest
    unittest.main()
