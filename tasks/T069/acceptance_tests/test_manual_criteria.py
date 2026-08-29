"""Приёмочные тесты T069 — критерий без прямого локального теста (AC-4).

О состоянии ВСЕГО существующего набора `tests/` после правки, а не о
наблюдаемом поведении нового кода этой задачи — дублирующий прогон
здесь не даёт новой гарантии сверх штатного гейта и рискует ложным
красным на другой машине (тот же приём, что
tasks/T037/acceptance_tests/test_manual_criteria.py,
tasks/T053/acceptance_tests/test_ac7_full_suite_regression.py,
tasks/T057/acceptance_tests/test_manual_criteria.py,
tasks/T058/acceptance_tests/test_manual_criteria.py).

Зелёный с рождения: файл не содержит исполняемых тестов — только
manual-пометку AC-4; краснеть здесь нечему, критерий проверяет CI
полным набором tests/ на ветке задачи.
"""

# AC-4: manual — «полный тестовый набор зелёный» проверяется тем же
# прогоном, что уже гоняет CI на каждый пуш ветки задачи
# (.github/workflows/ci.yml, джоб python: `unittest discover -s tests -v`)
# и который требует merge_gate (orchestrator/fsm.py, cmd_approve при
# state == "merge_gate") — зелёный статус и есть проверка критерия. Число
# тестов и конкретный состав мутационных проверок новых маркеров
# (isolation_smoke MCP-вектора, обвязки target'а) видит только сам этот
# прогон на ветке задачи, не зафиксированное здесь значение — они
# появятся вместе с реализацией AC-1/AC-2/AC-3 (developer, `tests/
# test_doctor.py`, `tests/test_runner.py` — по прецеденту T058, где
# `test_project_hook_setting_source_leak_is_caught` и соседние мутации
# появились там же, не в приёмочных тестах).
