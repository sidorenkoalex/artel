# Записка spec_auditor — 01M590GJAF0EDV4NBC4C99MFVH

## Выяснено
- Полный прогон гейта мержа идёт только после применённых приложений PLAN (`fsm_merge_gate.py:1038-1068`, `_full_suite_or_refuse`), без приложений — не идёт вовсе.
- Запись с несколькими компонентами отказывается на входе гейта мержа (`fsm_merge_gate.py:1253-1265` через `project_profile.decide:158`) и в `_task_own_profile` (`acceptance.py:2459`); `repo_context.profile_of` (только чтение) отдаёт `multi`. SPEC не говорит, как AC-9/AC-12 достигаются на такой записи.
- `test_profile` не может нести `report_args` (`targets.py:350-355`, `PROFILE_FIELDS`), а запись sled backend — `test_profile` с `report: junit-xml` (`targets.yaml:81-90`, только чтение): у треб. 13 нет источника `{path}`.
- Различитель SPEC «report и runner ≠ pult-pytest» не покрывает черновик ADR-0026 (компоненты без `runner`, `ADR:68-104`).
- Прогон планки на гейтах — `acceptance.run` (`advance_gates/acceptance.py:405`, `pull.py:668`, `amend.py:554`), SPEC называет только `run_plank`.
- `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py:310-311` закрепляет `skip` с `MULTI_COMPONENT_PENDING` у строки предела doctor.

## Не сработало
- —

## Где остановился
- SPEC-AUDIT.md сдан: verdict fail, status ready, guard ок. 14 отклонений; главные — Б4 (sled без report_args), Б5 (различитель), Б3 (несколько компонентов на гейтах), Б2 (прогон мержа только после приложений), А1 (`acceptance.run`).

## Чего не хватило
- Где на гейте мержа вообще идёт полный прогон (только после приложений) — искал дольше всего.
