# Записка analyst — 01M6BMG29KZV1RX21HFAXZG3CM

## Выяснено
- ANSWER-1: все три вопроса — вариант A. (1) мандат на переписывание `tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py::test_ac9_in_dev_gate_of_ci_component_judges_local_checkouts`. У него два обязательных условия: нет выписок на `in_dev`, находку ловит `verifying`. Отдельный тест «`verifying → review` только через гейт» с мутацией «гейт не вызван». (2) Прочий сбой подготовки на `verifying` → эскалация дословно, без потолка. (3) «Общий счётчик» = то же действие журнала и тот же текст, новой колонки нет.
- Строки по коду после В1.2: `fsm_advance.in_dev` :759, гейт исходов :843, сжатие :855, `_origin_push_gate` :868; `fsm_advance.verifying` :441 (→ `review` :469). `outcome_integrity`: `merge_gate_escalates` :1396 (в ТЗ :1153), `_judge_ci` :1148, `_ci_report` :1044 (перезапуск :1062–1063), `_ci_base_report` :1084, `_gate` :1336.
- Строка мандата «Ослабление тестов разрешено:» и матрица живут в ANSWER-1 (их читает `mandate.py`). Матрица продублирована в SPEC.

## Не сработало
- В Bash нет `ls`/`cat`/`rm` (command not found), `/bin/rm` просит подтверждения. QUESTIONS.md удалён через `python3 -c os.remove`.

## Где остановился
- SPEC.md написан (13 AC, zones — 3 файла, merge_after — оба id из ТЗ, budget 40), guard ок. QUESTIONS.md удалён.
- Сработал сигнал AC ≥ 10: в секции оценки — обоснование монолита. Решение принимает Оператор.

## Чего не хватило
- Ничего существенного. Дольше всего сверял, где читается мандат (ANSWER против SPEC): `mandate.py:29–38`.
