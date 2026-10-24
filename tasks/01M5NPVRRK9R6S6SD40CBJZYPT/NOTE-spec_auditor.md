# Записка spec_auditor — 01M5NPVRRK9R6S6SD40CBJZYPT

## Выяснено
- Факты SPEC о коде подтвердились: pull.py:592/620/679-682/684; advance_gates/acceptance.py:34 (PLANK_NOT_RUN), :598-615; fsm_autogate.py:417; plan_appendix.py:28/:40/:233 (skip_in_base).
- `acceptance.plank_in_code_copy` (acceptance.py:2027) в finally зовёт `drop_from_code_copy` — rmtree всего `tasks/<id>/` без учёта `preexisting`; tests/test_pull.py:240 (`test_preexisting_plank_dir_is_kept_after_pull`) требует сохранить уже лежавший каталог — конфликт треб. 1 (тот же узел) и треб. 5 на пути «дерево = рабочая копия».
- pull.py:833-839: при `operator_pull=True` любой `Refused` из `_materialize_and_run_plank` эскалирует (UNVERIFIED_HEAD_REASON) — AC-3 «не становится escalated» на пути `pull-main` ложно без правки вне зоны.
- SPEC не задаёт место `suite_tree` относительно проверки «планка не найдена»/перечня долгоживущих/ComponentsPending (треб. 3 «порядок прочих проверок не меняется»); на рубеже verifying suite_tree идёт ДО проверки отсутствия планки.
- AC-3 не требует теста на ветку `fixable=False`.
- Refused после слияния: слияние остаётся в ветке, повтор видит Fresh — планка после подтяжки не перепрогоняется (поведение прежнее для прочих Refused).

## Не сработало
- Bash с `cd` и `;`-цепочками отклоняется — нужны абсолютные пути, одна команда.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Поиск обработки Refused у вызывателей (fsm.py:285, fsm_merge_gate.py:725, pull.py:833).
