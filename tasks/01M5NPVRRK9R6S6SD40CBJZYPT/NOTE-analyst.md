# Записка analyst

## Выяснено
- Круг 2 (возврат из spec_gate 24.10): решения Оператора пп. 1–4 и мелочи внесены в SPEC; status: ready, guard ок; 7 AC, budget 30.
- П.1 → требование 1: plank_in_code_copy (ветка документов) только при tree.root ≠ wt_path; иначе прежний materialize_from_branch + preexisting (tests/test_pull.py:240). Причина — plank_in_code_copy (acceptance.py:2027) в finally сносит tasks/<id>/ целиком.
- П.2/п.4 → требование 2 и AC-3: AC-3 только без operator_pull; добавлен сценарий fixable=False → PLAN_APPENDIX_GATE_FAILURE_ACTION. pull.py:833–839 вне зоны — в «Не входит».
- П.3 → требование 3: suite_tree непосредственно перед acceptance.run, прежние проверки раньше.
- AC-6: «<имя главной ветки>» (source_branch).

## Не сработало
- Bash с `cd … &&` и относительным путём отклонён правилом deny — только абсолютные пути.

## Где остановился
- SPEC сдан, шаг завершён.

## Чего не хватило
- Ничего существенного.
