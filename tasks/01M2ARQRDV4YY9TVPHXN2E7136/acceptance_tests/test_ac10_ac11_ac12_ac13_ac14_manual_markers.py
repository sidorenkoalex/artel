"""AC-10, AC-11, AC-12, AC-13, AC-14 (tasks/01M2ARQRDV4YY9TVPHXN2E7136/SPEC.md):
все пять — о МЕСТЕ/ФОРМЕ артефактов вне `acceptance_tests/` этой планки
(unified diff приложением к PLAN.md; постоянные regression-тесты именно в
`tests/test_acceptance_*.py`/`tests/test_fsm_advance_*.py`; факт «существующие
тесты не ослаблены диффом разработчика»), не о поведении, которое можно
испытать этой планкой напрямую.

Зелёный с рождения: файл не содержит исполняемых тестовых методов — все
пять критериев ниже размечены пометками, ни один автоматический тест не
испытывается.

- AC-10 — унифицированный дифф к защищённому `skills/test-authoring.md`
  прикладывается к PLAN.md и применяется Оператором при мерже (та же
  конвенция, что и во всех прочих приложениях диффа в истории репозитория).
  Код-ветка задачи (то единственное, что видят acceptance_tests) никогда не
  понесёт финальный `skills/test-authoring.md`; формат приложения диффа к
  PLAN.md не зафиксирован машинно ни SPEC, ни шаблоном `templates/PLAN.md`.
- AC-11 — критерий требует ПОСТОЯННЫХ unit-тестов именно в
  `tests/test_acceptance_*.py` (регрессионный набор пульта, не эта планка).
  Поведение всех трёх сценариев критерия (зелёная планка, ModuleNotFoundError,
  планка без единого теста, включая мутацию «collect всегда True») уже
  покрыто ЗДЕСЬ: test_ac1_ac2_ac3_collect.py::CollectTest —
  test_ac1_green_plank_collects_successfully,
  test_ac2_module_not_found_error_is_red_with_module_name_in_tail,
  test_ac3_plank_without_a_single_test_is_named_explicitly. Присутствие
  ОТДЕЛЬНЫХ, ПОСТОЯННЫХ unit-тестов именно в `tests/` — предмет ревью кода
  разработчика (та же логика, что и у прочих правок диффа: автоматическая
  проверка «файл содержит нужные слова» была бы гейминг-уязвимой имитацией,
  не проверкой критерия по существу — тот же довод, что применён прецедентом
  tasks/01M1THKWFXFYNW28HDJGYHQWH6/acceptance_tests/test_ac8_ac9_manual_markers.py).
- AC-12 — тот же класс, для `tests/test_fsm_advance_*.py`: поведение гейта
  `tests_writing` по AC-4/AC-5 уже покрыто ЗДЕСЬ,
  test_ac4_ac5_tests_writing_dry_collect.py.
- AC-13 — тот же класс: сценарий AC-8 (отброшенные файлы — последняя
  запись визита) уже покрыт ЗДЕСЬ, test_ac8_stray_files_last_journal_entry.py.
- AC-14 — «существующие тесты `tests_writing`/`checkpoint`/`acceptance` не
  ослаблены этой задачей» — свойство ДИФФА разработчика (файлы
  `tests/test_fsm_advance_gate_*.py`, `tests/test_checkpoint_*.py`,
  `tests/test_acceptance.py`, `tests/test_acceptance_tests_flow.py` и
  подобные не удалены/не смягчены/не помечены skip/xfail), не поведение,
  которое можно испытать отдельной планкой изнутри неё самой — Оператор/
  ревьювер проверяет по факту `git diff` ветки задачи против этих файлов
  (ADR-0002, принцип целостности — ослабление тестов допускает только
  Оператор отдельным ADR).
"""

# AC-10: manual — unified diff к защищённому skills/test-authoring.md
# прикладывается к PLAN.md и применяется Оператором при мерже; код-ветка
# задачи не несёт финального содержимого файла, формат приложения диффа к
# PLAN.md не зафиксирован машинно.

# AC-11: manual — критерий требует постоянных unit-тестов в
# tests/test_acceptance_*.py; поведение всех трёх сценариев (зелёная
# планка/ModuleNotFoundError/планка без тестов) уже покрыто здесь,
# test_ac1_ac2_ac3_collect.py::CollectTest — присутствие постоянных тестов
# именно в tests/ проверяет ревью кода.

# AC-12: manual — тот же класс, для tests/test_fsm_advance_*.py; поведение
# гейта tests_writing по AC-4/AC-5 уже покрыто здесь,
# test_ac4_ac5_tests_writing_dry_collect.py.

# AC-13: manual — тот же класс; сценарий AC-8 уже покрыт здесь,
# test_ac8_stray_files_last_journal_entry.py.

# AC-14: manual — «существующие тесты не ослаблены» — свойство диффа
# разработчика (tests/test_fsm_advance_gate_*.py, tests/test_checkpoint_*.py,
# tests/test_acceptance.py и подобные не тронуты/не смягчены/не помечены
# skip/xfail), проверяется Оператором/ревьювером по git diff, не отдельным
# автотестом планки (ADR-0002).
