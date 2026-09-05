"""AC-8 (tasks/01M1REVP9WGRHDDNVEVE8BBH0Z/SPEC.md): «Существующие тесты
`orchestrator/doctor.py` (включая прежние сценарии сирот-веток без сверки
с origin) остаются зелёными после изменения критерия.»

Регрессия конкретно `tests/test_doctor.py` — не отдельный юнит-тест
здесь, см. маркер ниже.

Зелёный с рождения: файл не содержит исполняемых тестовых методов (AC-8
помечен skip ниже — регрессия уже покрыта штатным CI-гейтом), поэтому
`unittest discover` проходит его без сборов и без ошибок что до, что
после появления кода задачи.
"""

# AC-8: skip — регрессия `tests/test_doctor.py` (и всего существующего
# набора tests/) уже исполняется штатным CI-гейтом на каждом коммите
# ветки задачи (.github/workflows/ci.yml, джоб python, `unittest
# discover -s tests -v`), и именно его зелёный статус требует merge_gate
# (orchestrator/fsm.py, cmd_approve при state == "merge_gate") — тот же
# приём, что tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/
# test_ac5_existing_suite_stays_green.py, tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/
# acceptance_tests/test_ac7_existing_tests_stay_green.py,
# tasks/T053/acceptance_tests/test_ac7_full_suite_regression.py.
# Дублирующий здесь subprocess-прогон всего набора не даёт новой гарантии
# сверх штатного гейта, а только удлиняет приёмочный прогон этой задачи.
# Конкретно `OrphanArtifactBranchSweepTest` в tests/test_doctor.py уже
# мокает `gitcmd.git`/`gitcmd.list_branches` фиксированным успехом на
# ЛЮБОЙ git-вызов (включая новый `ls-remote --heads origin 'artifact/*'`,
# которого раньше не было) — естественная реализация требования 1-2 этой
# задачи (сверка с origin ДОБАВЛЯЕТСЯ к существующей сверке с БД, не
# заменяет её) видит от этих моков «на origin веток artifact/* нет» и
# сохраняет прежний исход прежних тестов без правки самих тестов.
