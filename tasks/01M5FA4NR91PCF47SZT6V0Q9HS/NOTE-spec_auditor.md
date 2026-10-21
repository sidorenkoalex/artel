# Записка spec_auditor — 01M5FA4NR91PCF47SZT6V0Q9HS (аудит круга 3, spec_sha dd452684)

## Выяснено
- Ссылки SPEC на код подтверждены: canary.py:2796–2959, artel.py:181/1539/1762/2003–2032, doctor/cli.py:153/194, notes.py:266/285, fsm_merge_gate.py:1255/1268, sandbox.py:90/1581/1897, test_invariants.py:149/245–267/3155/3176–3185, project_area.py:138/1244, test_doctor_canary_pool.py:249.
- Разбор AST перечня (116 классов, 58 файлов): у 113 есть признак (1) без сужения PATCHED_ATTRS и без setUp без super; CmdCanaryTemplateSelectionTest и CanaryPoolDriftCheckTest — признак (2); MainCopyGitUnchangedDuringTaskTest — признак (3) (один тестовый метод).
- Пробел: tests/test_doctor_closed_ref_fix.py:150 `DoctorFixOrderTest` (unittest.TestCase, без подмены ROOT) зовёт `cmd_doctor(fix=True)` (:183) с подменёнными all_checks и починками — новая починка реестра под --fix (требование 4) дойдёт до настоящего реестра; в перечне его нет (перечень снят шпионом на main, где этого пути не было).
- Признак (1) не проверяет фактическую подмену ROOT: TmpRootTest.PATCHED_ATTRS сужаем (прецедент tests/test_doctor.py:2088 без ROOT).

## Где остановился
- SPEC-AUDIT.md записан (concerns), guard прогнан.

## Чего не хватило
- Bash-песочница отказывает в awk/redirect в /tmp; разбор делал python3 heredoc.
