# Записка spec_auditor

## Выяснено
- Круг 2: SPEC sha cfe072cc… совпадает с `git hash-object`. Все 7 решений Оператора круга 1 перенесены (AC-8, AC-9, строка матрицы, требование 4, имя константы, AC-2, SigintTest в «Не входит»).
- Факты о коде подтверждены (canary.py:3423, 3461, 3505, 3702, 3759-3767; liveness.py:50; protection :260, :281, :335-340, :499-501, :652; parallel :382-384; pyproject timeout=120).
- Вердикт concerns: AC-8 не ловит «store.db() в цикле, но вне try» — шпион store.db в AC-3 не бросает; предложено: первый вызов store.db бросает OperationalError.
- Тестов на код выхода 1 нет (test_canary_run_task.py:328, :361 — 128+signum).

## Не сработало
- Bash с `; echo rc=$?` отклоняется (simple_expansion) — запускать guard одиночной командой.

## Где остановился
- SPEC-AUDIT.md написан (status: ready, verdict: concerns), guard ок.

## Чего не хватило
- Ничего существенного.
