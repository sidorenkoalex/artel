# Записка spec_auditor

## Выяснено
- Факты SPEC о местах запуска acceptance.py:448/556/665/932/1324/1345/1373, :1172, :1176, :35-65, :69-89 подтверждены; targets.py:41-53 подтверждён; yamlmini даёт 'off' строкой.
- Фикстуры tests/sandbox.py:1057-1065, :1097 (artel_target_entry), :1117 без `sandbox` -> станут `required`, без `image` -> targets.load (проверяет все записи) откажет. Опрокидываются tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:107-121, test_01m484rnv3qbdy3b0m16j916zp_external_flow.py:45-61. В SPEC нет ни «Меняемого поведения», ни решения о фикстурах.
- Автогейт зовёт acceptance.acceptance_suite (fsm_autogate.py:323), full_suite без command — acceptance.py:1847-1848; гейт мержа fsm_merge_gate.py:962-967 тоже потребитель профиля, в п.6 не назван.
- project_profile.Profile (project_profile.py:63-74) — носитель профиля, вне зон; вызывающие run/collect/run_plank (plank_run.py:187 и др.) вне зон, а сигнатуры мест запуска не несут проекта/задачи.
- Пробелы AC: AC-7 (-e NAME без значения / env docker CLI), AC-5 (флаги сверх перечня), AC-3 (realpath только в targets.check).

## Где остановился
- SPEC-AUDIT.md сдан: verdict fail, status ready; guard ок.

## Чего не хватило
- Как места запуска узнают проект/задачу (сигнатуры без них) — искал по вызывающим grep'ом `acceptance\.(run|collect|run_plank)(`.
