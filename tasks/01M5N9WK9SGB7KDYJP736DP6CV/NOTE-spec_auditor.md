# Записка spec_auditor — 01M5N9WK9SGB7KDYJP736DP6CV (круг 2)

## Выяснено
- Решения Оператора круга 1 (пп. 1–5) в SPEC 6c39fad перенесены полностью; адреса guard.py сверены на 2b187a3d.
- Главное: литерал фикстуры не имеет роли в `_constant_roles` (guard.py:2279) → `_strictness_sign` даёт SIGN_UNRATED (:2391) → `_change_reason` относит к ослаблению (test_integrity.py:1132), объявление не снимает. Противоречит AC-10 «та же оценка строгости» и решению п. 1; роль equality — обход для границ.
- Форма (в) уровня модуля: нет функции для адреса и ключа lint_base.
- Мой Г1 круга 1 ошибочен: `tests/` в COMMON_ZONES (config.py:814), zone_lock._own_paths их выкидывает. Маски в zones гейт зон не понимает (zones.py:29 — префикс).

## Не сработало
- Составные bash с cd — работают в этом шаге, `ls` нет в окружении.

## Где остановился
- SPEC-AUDIT.md записан, вердикт concerns; guard: ок.

## Чего не хватило
- Связи `signs` → `_change_reason` (test_integrity.py:1126) в SPEC — искал grep'ом `.signs`.
