# Записка spec_auditor — 01M5AA5TS90RDJ2AFXB882WTPD

## Выяснено
- Адреса SPEC сверены с кодом: targets.py:411-415 (отказ G2б), :493 `_template_path_error`, project_profile.py:66/134/138/144, guard.py:288/590/711/2620/2663/3353/3809/3820/3857, fsm.py:649, fsm_advance.py:537, preflight.py:168, runner.py:1338, role_prompt.py:196-286 — совпадают.
- Места «только чтение» (checkpoint, zones, advance_gates/acceptance, plank_run) действительно идут через `Profile.is_long_lived` и `ls_tree_files(-r)` — без правки работают.
- `targets.py` не может импортировать ни guard (guard→zone_lock→store→targets), ни project_profile: сверку маски в п.1 придётся писать заново; правило планки сверяет ПОСЛЕДНИЙ СЕГМЕНТ масок (`guard.PlankComponent._patterns`), SPEC этого не говорит.
- Сторож предпроверки (tests/test_01m4p4zp...:235) смотрит только три тела, не их помощников.
- В tests/ есть компоненты с парой и `.test.js` (test_01m590gj...:571, test_01m59z0f...:262, test_01m59kmp...:178) — п.5 (отказ «не метка и не Python») задевает и пару: противоречит «Границе».
- ANSWER-n нет.

## Вердикт
concerns (см. SPEC-AUDIT.md, отклонения 1-7): граница vs п.5; сверка маски не определена; AC-10 недостижим и без preflight; amend --from-branch; п.4 без AC; AC-8 уже п.6; место дописывания пары.

## Где остановился
SPEC-AUDIT.md написан (status: ready, verdict: concerns), guard — ок.

## Чего не хватило
Дольше всего искал, сравнивает ли правило планки полную маску или её последний сегмент (guard.py:2600 `_patterns`).
