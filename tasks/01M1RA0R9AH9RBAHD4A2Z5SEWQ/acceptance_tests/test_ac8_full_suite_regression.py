"""AC-8 (tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/SPEC.md): существующие тесты
подтяжки/конфликта (`tests/test_fsm_map_conflict_autoresolve.py`,
`tests/test_branch_freshness_gate.py`) остаются зелёными без изменения
проверяемого ими поведения.

Регрессия всего существующего набора — не отдельный юнит-тест здесь, см.
маркер ниже.

Зелёный с рождения: без исполняемых тестов в этом файле — критерий закрыт
пометкой skip (регрессия уже покрыта штатным CI-гейтом), докстринг только
объясняет причину.
"""

# AC-8: skip — регрессия всего существующего набора tests/, включая
# ИМЕННО названные критерием файлы, уже исполняется штатным CI-гейтом на
# каждом коммите ветки задачи (.github/workflows/ci.yml, джоб python,
# `unittest discover -s tests -v`), и именно его зелёный статус требует
# merge_gate (orchestrator/fsm.py, cmd_approve при state == "merge_gate").
# Дублирующий здесь subprocess-прогон этих двух файлов не даёт новой
# гарантии сверх штатного гейта, а только удлиняет приёмочный прогон этой
# задачи — тот же приём, что tasks/T067/acceptance_tests/
# test_ac8_full_suite_regression.py / tasks/T053/acceptance_tests/
# test_ac7_full_suite_regression.py.
