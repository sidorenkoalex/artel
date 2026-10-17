# Записка analyst

## Выяснено
- ANSWER-1: вариант A — runner.py (только _missing_required_artifact/_has_own_long_lived_test, :1310-1346) в зонах, потолок прежний $25.
- Возврат 1 со spec_gate 17.10: Ф-1 (б) — своя зона test_author в зонном фильтре коммита (checkpoint.py), COMMON_ZONES не трогать; Ф-2 — refusal/skip; П-1 — AC-3/AC-5.
- Возврат 2 со spec_gate 17.10: Ф-3 (а) — гейт зон не меняется; в требование 3 добавлено правило «задача внешнего проекта с долгоживущими файлами включает long_lived_dir в zones:», требование 3 — страховка коммита; признание гейтом зон — в «Не входит» (advance_gates/zones.py:222, :274-276, :305-307). П-2 — AC-7 и требование 5 (skip): проверка артефакта не засчитывает tests/test_<id>_<имя>.py.
- Источник профиля — project_profile.for_task(conn, task_id) → Decision (project_profile.py:121-163).

## Не сработало
- Ничего нового.

## Где остановился
- SPEC.md: 8 требований, 8 AC, status: ready, guard ок, budget 25.

## Чего не хватило
- Связь «коммит чекпоинта → гейт зон на in_dev» видна только чтением zones.py:_zones_gate.
