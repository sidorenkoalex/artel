# Записка analyst

## Выяснено

- ТЗ достаточно для исправленного SPEC: меняются только три тестовых файла из заявленных зон; продуктовый алгоритм `orchestrator/doctor/suite_duration.py` остаётся только для чтения.
- Причина падения подтверждена кодом: после первой записи с `workers=2` цикл `range(k)` создаёт девять записей, а doctor корректно сравнивает девятую с первыми восемью.
- `test_ac7_duration_calibrates_and_ignores_worker_changes` несёт 15 учитываемых утверждений, включая пять `assertTrue(rows, ...)` из `measured_run` (вызовы 158, 162, 167, 173, 177); SPEC требует сохранить метод, формы и число, поэтому мандат на ослабление не нужен.
- Для реальной интеграции `test_ac1_gate_writes_each_outcome_with_metrics` недостаточен: он держит `workers == 1` и только `seconds_per_test > 0`. SPEC требует минимальный реальный сценарий workers=2 и точное равенство нормализации.
- Реестр долгоживущего файла принадлежит задаче `01M4ARAXF7VSS5XZ8C99BX8DE2`: `tasks/01M4ARAXF7VSS5XZ8C99BX8DE2/acceptance_tests/long_lived.sha256.txt`; его пересчитывает только `amend-tests`.

## Не сработало

- Первый прогон `guard.py` отказал: после явного включения пути штатного обновления долгоживущего реестра сработал сигнал «затронут инвариантный механизм», а секция оценки объёма была пуста. Добавлено обоснование монолита.

## Где остановился

- SPEC дополнен по шести замечаниям аудита и обоснованием монолита; `python3 scripts/guard.py …/SPEC.md` завершился `GUARD: ок (1 файлов)`.

## Чего не хватило

- Для установления границы понадобились `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac7_duration_calibrates_and_ignores_worker_changes`, `orchestrator/doctor/suite_duration.py::check_suite_duration` и `orchestrator/amend.py::_amend_with_long_lived`.
