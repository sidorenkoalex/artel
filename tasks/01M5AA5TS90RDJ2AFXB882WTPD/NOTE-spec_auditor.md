# Записка spec_auditor — 01M5AA5TS90RDJ2AFXB882WTPD (аудит №3, spec_sha 9118350e)

## Выяснено
- Решения гейта SPEC №2 (пп. 1–3) внесены: корень «до сегмента с первым заполнителем» (req 1, AC-2), пара выводится в targets.load/target копией (req 2, AC-16), «в правке» у amend — снимок до ИЛИ после (req 8, AC-11).
- targets.load (targets.py:149-170) зовёт check и отдаёт те же словари; target() — через load. Внешних вызовов targets.check на выходе load/target нет (grep) — вывод пары после check безопасен.
- Все пути профиля идут через project_profile.with_tools → _with_component_fields (decide :176, acceptance.py:3543, suite_run.py:296) — long_lived_template туда доходит.
- Фикстуры G1а с long_lived (tests/test_01m58fnwbv25…:54, :69) без поля tests — сверка с масками их не задевает; форму проходят.
- component_profiles у записи из нескольких компонентов получит производную пару (fsm_merge_gate.py:895) — в рамке границы ТЗ, через decide недостижимо (MULTI_COMPONENT_PENDING).
- Косметика: req 8 «текстом текстом».

## Где остановился
SPEC-AUDIT.md: verdict pass, status ready.

## Чего не хватило
Ничего существенного; сверка мест — по записке аудита №2.
