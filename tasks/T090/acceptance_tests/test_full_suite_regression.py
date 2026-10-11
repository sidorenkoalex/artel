"""AC-2 (tasks/T090/SPEC.md): полный прогон тестового набора `tests/`
проходит с тем же результатом, что и до изменения (все тесты зелёные,
включая `tests/test_cas_set_state.py` и тесты, покрывающие
`store.enable_wal`/WAL-режим) — наблюдаемое поведение команд CLI,
CAS/транзакций и WAL не меняется.

Поимённое упоминание `test_cas_set_state.py` и WAL-тестов в критерии не
выделяет их в отдельный контур проверки: оба файла — обычные модули под
`tests/`, которые штатный CI-джоб `python` (`.github/workflows/ci.yml`,
`unittest discover -s tests -v`) гоняет вместе со всеми остальными на
каждом коммите ветки задачи, и именно его зелёный статус требует
`merge_gate` (orchestrator/fsm.py, `cmd_approve` при `state ==
"merge_gate"`). Если выбранный разработчиком приём закрытия соединений
сломает CAS (T050) или WAL-режим, эти же существующие тесты покраснеют
на том же гейте — дублирующий здесь subprocess-прогон всего набора не
даёт новой гарантии сверх штатного гейта, а только удлиняет приёмочный
прогон этой задачи (сверх уже тяжёлого AC-1, см.
tasks/T090/acceptance_tests/test_no_unclosed_connections.py). Тот же
приём, что tasks/T053/acceptance_tests/test_ac7_full_suite_regression.py
/ tasks/T067/acceptance_tests/test_ac8_full_suite_regression.py /
tasks/T077/acceptance_tests/test_ac6_full_suite_regression.py.

Зелёный с рождения: без исполняемых тестов в этом файле — критерий
закрыт пометкой skip (регрессия уже покрыта штатным CI-гейтом),
докстринг только объясняет причину.
"""

# AC-2: skip — регрессия всего существующего набора tests/ (включая
# test_cas_set_state.py и тесты WAL/enable_wal) уже исполняется штатным
# CI-гейтом на каждом коммите ветки задачи (.github/workflows/ci.yml,
# джоб python, `unittest discover -s tests -v`), и именно его зелёный
# статус требует merge_gate (orchestrator/fsm.py, cmd_approve при
# state == "merge_gate"). Дублирующий здесь subprocess-прогон всего
# набора не даёт новой гарантии сверх штатного гейта, а только удлиняет
# и без того тяжёлый приёмочный прогон (AC-1 уже гоняет весь набор один
# раз) — тот же приём, что tasks/T053/acceptance_tests/
# test_ac7_full_suite_regression.py.
