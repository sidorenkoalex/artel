"""Приёмочные тесты 01M1VBEHTDYPK3E4RRFHWYYYW3 — критерий без прямого
теста: AC-12 (skip). Разбор — рядом с пометкой ниже.

Зелёный с рождения: файл не содержит исполняемых тестов — только
пометку; краснеть здесь нечему.
"""

# AC-12: skip — «Существующие tests/test_doctor.py и существующие тесты
# CLI пульта остаются зелёными после изменений.» Регрессия существующего
# набора — не отдельный юнит-тест здесь: тот же класс критерия и то же
# решение, что уже применяют tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/
# acceptance_tests/test_ac_manual_and_skip_markers.py (AC-12 там) и
# tasks/01M1THKTJ7YT1K410G1KS17MK6/acceptance_tests/
# test_ac_manual_and_skip_markers.py (AC-6 там) к формулировке
# «существующие тесты остаются зелёными» — зелёность `tests/` на каждом
# коммите ветки уже обеспечивает штатный CI-джоб `python`
# (`.github/workflows/ci.yml`, `unittest discover -s tests -v`) и
# автогейт acceptance на переходе review -> verifying (ADR-0007, условие
# «в», `orchestrator/acceptance.py`, `config.FULL_SUITE_TIMEOUT_SEC`).
# Дублирующий subprocess-прогон tests/test_doctor.py здесь не даёт
# сигнала сверх штатных гейтов, только удлиняет приёмочный прогон этой
# задачи (skills/test-authoring.md, решение Оператора 05.09: «Полный
# набор tests/ в шаге не запускай»).
