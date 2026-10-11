---
task: T032
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: doctor: check_base_branch — догфуд-skip и тесты

Мелкий фикс в doctor по minor-замечанию ревью T022 (строка беклога P3
«doctor: check_base_branch»): проверка check_base_branch в
orchestrator/doctor.py — единственная из «только для внешнего target»
проверок требования 9 задачи T022, которая не исключает догфуд
(config.DEFAULT_TARGET), в отличие от соседних check_remote_empty
и recovery_check; и сама функция не покрыта тестами.

Хочу: (1) check_base_branch для догфуд-target ведёт себя как соседние
проверки — честный skip с причиной «догфуд — особый случай», не попытка
сверки; (2) функция покрыта тестами по образцу соседних в test_doctor.py
(skip на догфуде, сверка/расхождение/недоступный gh на внешнем target —
что из этого уже покрываемо в песочнице, реши по месту); (3) поведение
для внешних target не меняется. Класс — мелкий фикс, $15.
