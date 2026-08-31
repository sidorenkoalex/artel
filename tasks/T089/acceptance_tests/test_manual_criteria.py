"""Приёмочные тесты T089 — критерии без прямого локального теста (AC-6).

Зелёный с рождения: файл не содержит исполняемых тестов — только
manual-пометку; краснеть здесь нечему.
"""

# AC-6: manual — «полный набор tests/ проходит зелёным после сведения
# хелперов» уже гоняется штатным CI-джобом «python»
# (`.github/workflows/ci.yml`: `unittest discover -s tests -v` на каждый
# пуш) и требуется отдельным автогейтом оркестратора
# (`orchestrator/acceptance.py::run_full_suite`, условие acceptance-гейта
# ADR-0007). Повтор полного прогона tests/ ещё и отсюда, подпроцессом
# внутри собственного acceptance_tests/ этой же задачи, — риск ложного
# красного от окружения машины (тот же довод и прецедент, что
# `tasks/T037/acceptance_tests/test_manual_criteria.py` AC-5,
# `tasks/T079/acceptance_tests/test_manual_criteria.py` AC-13), а не
# проверка дефекта именно T089.
