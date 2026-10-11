"""AC-7 (tasks/T053/SPEC.md): существующие тесты (включая
`test_invariants.py` и тесты T050/T051/T052) остаются зелёными без
ослабления существующих тестов, гейтов, лимитов, guard-проверок и
инвариантов (ADR-0002).

Регрессия всего существующего набора — не отдельный юнит-тест здесь, см.
маркер ниже.
"""

# AC-7: skip — регрессия всего существующего набора tests/ уже
# исполняется штатным CI-гейтом на каждом коммите ветки задачи
# (.github/workflows/ci.yml, джоб python, `unittest discover -s tests -v`),
# и именно его зелёный статус требует merge_gate (orchestrator/fsm.py,
# cmd_approve при state == "merge_gate"). Дублирующий здесь
# subprocess-прогон всего набора не даёт новой гарантии сверх штатного
# гейта, а только удлиняет приёмочный прогон этой задачи — тот же приём,
# что tasks/T050/acceptance_tests/test_ac9_full_suite_regression.py /
# tasks/T048/acceptance_tests/test_ac6_full_suite_regression.py.
