# Записка spec_auditor — 01M5AA5TS90RDJ2AFXB882WTPD (аудит №2, spec_sha 860193ae)

## Выяснено
- Решения Оператора на гейте SPEC №1 (пп. 1–7) внесены в SPEC полностью: long_lived_template, сверка по последнему сегменту маски, AC-10 на уровне функции гейта + preflight, amend в обоих режимах, AC-15 на тексты, AC-8 расширен, AC-16 (словарь записи не меняется).
- Новая находка 1: форма «корень — часть до первого заполнителя непуста» (req 1) расходится с выводом пары «корень — часть до СЕГМЕНТА с первым заполнителем» (req 2): шаблон `test_<id>_<name>.py` (один сегмент) проходит форму, а long_lived_dir выходит пустым.
- Новая находка 2: `repo_context.profile_of` (только чтение, repo_context.py:152-174) берёт поля компонента из `targets.target()` и требует `long_lived_dir` (не в PROFILE_OPTIONAL, targets.py:64-65). Значит пару обязан производить `targets.load`/`target` в копии; вывод в `project_profile.components` даст PROFILE_UNREAD. SPEC пишет «при построении полей компонента» — двусмысленно. Ловят сквозные AC-5/AC-12 через decide.
- Факты SPEC сверены: targets.py:402-420, :493, :628-633; project_profile.py:66-146, :265-300, :453-489; guard.py:288, :590, :711, :2600-2606, :2663, :3353, :3809-3868; fsm.py:649; fsm_advance.py:535-537; preflight.py:150-214; amend.py:645, :988; role_prompt.py:179-286; runner.py:1336-1338.

## Где остановился
SPEC-AUDIT.md готов (status: ready, verdict: concerns, 3 отклонения: корень шаблона, место вывода пары, «в правке» у amend-tests), guard — ок.

## Чего не хватило
Откуда `profile_of` берёт поля компонента — из `targets.target()`, а не из `project_profile.components` (repo_context.py:152).
