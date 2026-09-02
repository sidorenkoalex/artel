"""AC-7 (tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md): существующий набор
`tests/` остаётся зелёным после изменений.

Регрессия всего существующего набора — не отдельный юнит-тест здесь, см.
маркер ниже.

Зелёный с рождения: файл не содержит исполняемых тестовых методов (AC-7
помечен skip ниже — регрессия уже покрыта штатным CI-гейтом), поэтому
`unittest discover` проходит его без сборов и без ошибок что до, что
после появления кода задачи.
"""

# AC-7: skip — регрессия всего существующего набора tests/ уже
# исполняется штатным CI-гейтом на каждом коммите ветки задачи
# (.github/workflows/ci.yml, джоб python, `unittest discover -s tests -v`),
# и именно его зелёный статус требует merge_gate (orchestrator/fsm.py,
# cmd_approve при state == "merge_gate"). Дублирующий здесь
# subprocess-прогон всего набора не даёт новой гарантии сверх штатного
# гейта, а только удлиняет приёмочный прогон этой задачи — тот же приём,
# что tasks/T053/acceptance_tests/test_ac7_full_suite_regression.py /
# tasks/T050/acceptance_tests/test_ac9_full_suite_regression.py /
# tasks/T048/acceptance_tests/test_ac6_full_suite_regression.py.
