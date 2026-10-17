# Записка spec_auditor

## Выяснено
- Визит 3 (SPEC sha 320f31b6): решения гейта №1 и №2 (Ф-1 (б), Ф-2, П-1, О-4, Ф-3 (а), П-2) и ANSWER-1 отражены; факты о коде сверены (role_prompt.py:36,77-114; checkpoint.py:376,384,412,497,1550,1731; runner.py:1310-1346; zones.py:222,274-276,305-307; project_profile.py:106-163).
- targets.yaml:45-53 — у артели test_profile есть, значения = умолчания guard; ветка refusal артель не задевает.
- «Было» правки skills/test-authoring.md совпадает со строками 114-126.

## Не сработало
- Составные Bash-команды (`;`, `|` с grep по targets.yaml) требуют подтверждения — по одной команде или Read.

## Где остановился
- SPEC-AUDIT.md сдан: verdict pass, status ready; два наблюдения (команда прогона пункта 5 для sled, _role_may_delete при refusal/skip).

## Чего не хватило
- Ничего существенного.
