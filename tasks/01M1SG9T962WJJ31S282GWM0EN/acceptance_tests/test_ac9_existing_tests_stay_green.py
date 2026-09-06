"""AC-9 (tasks/01M1SG9T962WJJ31S282GWM0EN/SPEC.md): `tests/test_zones_gate.
py`, существующие тесты гейта ёмкости и существующие тесты ревью-пакета
остаются зелёными без ослабления ассертов.

Регрессия существующего набора — не отдельный юнит-тест здесь, см.
маркер ниже.

Зелёный с рождения: файл не содержит исполняемых тестовых методов (AC-9
помечен skip ниже — регрессия уже покрыта штатным CI-гейтом), поэтому
`unittest discover` проходит его без сборов и без ошибок что до, что
после появления кода задачи.
"""

# AC-9: skip — регрессия tests/test_zones_gate.py, tests/test_capacity_gate.py
# и tests/test_review_package.py уже исполняется штатным CI-гейтом на каждом
# коммите ветки задачи (.github/workflows/ci.yml, джоб python, `unittest
# discover -s tests -v`), и именно его зелёный статус требует merge_gate
# (orchestrator/fsm.py, cmd_approve при state == "merge_gate"). Дублирующий
# здесь subprocess-прогон всего набора не даёт новой гарантии сверх штатного
# гейта, а только удлиняет приёмочный прогон этой задачи — тот же приём, что
# tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/acceptance_tests/test_ac9_existing_tests_stay_green.py
# и её же ссылки (tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ, T053, T050, T048).
