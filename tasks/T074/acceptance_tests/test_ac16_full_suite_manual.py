"""Приёмочные тесты T074 — AC-16.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-16. Полный тестовый набор зелёный; новые тесты `pause --now` и
расширенного чекпоинта аварийного шага — в общей песочнице
(tests/sandbox.py).

Критерий смешивает два разных адресата:

- «полный тестовый набор зелёный» — уже проверяет CI на каждый пуш
  (`.github/workflows/ci.yml`, `python3 -m unittest discover -s tests`)
  и автогейт acceptance (`orchestrator/acceptance.py::run_full_suite`);
  повторный прогон подпроцессом внутри самих `acceptance_tests/` того же
  смысла не добавляет и рискует ложным красным из-за окружения этой
  машины — тот же довод, что уже применён в `tasks/T037/acceptance_tests`
  (AC-5), `tasks/T040/acceptance_tests` (AC-4) и `tasks/T041/
  acceptance_tests` (AC-5).
- «новые тесты... — в общей песочнице (tests/sandbox.py)» — это
  указание РАЗРАБОТЧИКУ, где положить его СОБСТВЕННЫЕ юнит-тесты
  (`tests/test_pause_now.py` и т.п., по образцу `tests/test_pause.py`
  для T070 и `tests/test_timeout_checkpoint.py` для T041), не
  наблюдаемое поведение системы, которое можно закрыть тестом из
  `tasks/T074/acceptance_tests/`.

# AC-16: manual — Оператор/ревьювер на приёмке проверяет: (1) CI зелёный
# на ветке задачи; (2) в tests/ появились юнит-тесты pause --now и
# расширенного чекпоинта, использующие tests/sandbox.py (TmpRootTest/
# capture/FakeProc), а не только приёмочные тесты этого каталога. Число
# тестов «до этой задачи» в tests/ — сверяется на приёмке командой
# `python3 -c "import unittest; print(unittest.TestLoader().discover(
# 'tests').countTestCases())"` от свежего main той же веткой, что и
# прочие AC «manual: CI» этого репозитория (T037/T040/T041) — планка для
# сверки, что набор не уменьшился и не покраснел.

Зелёный с рождения: файл не исполняет код задачи — только несёт пометку
`manual` для критерия, который проверяется на приёмке Оператором/CI, а
не unittest'ом этого каталога.
"""
import unittest

if __name__ == "__main__":
    unittest.main()
