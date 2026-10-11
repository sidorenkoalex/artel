"""AC-7 (tasks/T066/SPEC.md): `test_invariants.ManualGatesNeedTheOperatorTest`
зелёный, его сценарии при политике manual не изменились; добавлен и
зелёный отдельный тест сценария автогейта; полный набор `tests/` зелёный.

Составной критерий — три части, три разных источника проверки:
- «добавлен и зелёный отдельный тест сценария автогейта»: этот файл
  каталога, `test_ac1_ac2_ac3_autogate_success.py`
  (`AutogatePassesAllConditionsTest`), и есть этот тест — отдельный
  regression-тест здесь был бы дублированием того же прогона.
- «`ManualGatesNeedTheOperatorTest` зелёный, сценарии не изменились» и
  «полный набор `tests/` зелёный» — регрессия существующего модуля,
  не нового поведения этой задачи; см. маркер ниже.
"""

# AC-7: skip — регрессия `tests/test_invariants.py::
# ManualGatesNeedTheOperatorTest` и полного набора `tests/` уже
# исполняется штатным CI-гейтом (`.github/workflows/ci.yml`, джоб
# `python`, `unittest discover -s tests -v`) на каждый коммит ветки
# задачи и требуется `merge_gate` (`orchestrator/fsm.py`, `cmd_approve`
# при `state == "merge_gate"`) — тот же довод, что и в
# tasks/T049/acceptance_tests/test_ac6_ac7_regression_and_protected_paths.py
# (AC-6 там), tasks/T044/acceptance_tests/test_lease_readonly_and_doctor.py
# (AC-7 там). Повторный subprocess-прогон здесь ловил бы окружение
# машины исполнителя, а не дефект этой задачи, и не даёт новой гарантии
# сверх штатного гейта; сам `ManualGatesNeedTheOperatorTest` — файл
# `PROTECTED` (docs/invariants.md) и правится только Оператором отдельным
# ADR, эта задача его не трогает.
