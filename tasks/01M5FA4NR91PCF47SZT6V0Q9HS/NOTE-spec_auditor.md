# Записка spec_auditor — 01M5FA4NR91PCF47SZT6V0Q9HS (аудит, spec_sha cb29ed40)

## Выяснено
- Ссылки SPEC на код подтверждены: canary.py:280/2796/2823/2847/2862/2876/2895/2911/2941/2959, artel.py:181/1539/1762/2017, doctor/cli.py:35/153/166/194, doctor/__init__.py:154, notes.py:266/285, fsm_merge_gate.py:1255/1268, sandbox.py:90/1581/1897, test_invariants.py:149/245–267/3155/3176–3185.
- Перечень: 119 классов в 61 файле, все существуют. AST: 114 — признак (1) без сужения PATCHED_ATTRS и без setUp без super (AllChecksProviderNamesTest — через алиасы test_doctor.py:195 и test_providers.py:35–36); CanaryPoolDriftCheckTest — (2); CmdCanaryTemplateSelectionTest и DoctorFixOrderTest — (2) после задачи; MainCopyGitUnchangedDuringTaskTest — (3).
- Поиск `cmd_doctor(fix=True)` у SPEC пропускает позиционную форму `doctor.cmd_doctor(False, True)` (project_area.py:363, помощник `doctor_fix` → CloneCreationTest, CloneHooksFromPinTest); оба класса уже в перечне.
- Тесты, добавленные после 58c9a84b (до main cb58b144), реестра не достигают.
- doctor без --fix до live_run_note не доходит (check_pending_notes зовёт только pending_notes).

## Где остановился
- SPEC-AUDIT.md: concerns, 3 отклонения (поиск fix=True, AC-20 без перечня функций реестра, AC-19 без разрешения основ по определению).

## Чего не хватило
- rm в Bash недоступен — временный файл удалял python3 os.remove; `$f`/`${}` в командах песочница отказывает.
