# Записка spec_auditor — 01M4VBTTH9TT5R74W2ZGKKYZK2

## Выяснено
- Диагноз SPEC верен: test_ac7 строки 162-175 — 9 записей w1, затем 4.0 w2 (1-я новой серии) + range(k)=8 → 9 записей при «ровно k».
- Гейт неослабления (orchestrator/advance_gates/test_integrity.py, scripts/guard.py:1094 `_helper_calls`, :1258 `changed_test_assertions`) считает утверждения помощников первого уровня по каждому статическому вызову: test_ac7 несёт 5 копий `assertTrue(rows, …)` из measured_run (строки 158,162,167,173,177). Перевод test_ac7 на контролируемые измерения без measured_run теряет их → находка «утверждение удалено»; раздела «Меняемое поведение» в SPEC нет.
- Реальные прогоны test_ac7 сейчас косвенно держат `acceptance._workers` (xdist_workers=2) и нормализацию `_suite_metrics` (acceptance.py:278-299); test_ac1 suite_observation проверяет только workers==1 и per_test>0 (строки 95,109).
- AC-1 не ловит мутацию doctor `len(series) <= k` → `< k` (suite_duration.py:54), если 8-я запись нормальная.
- Матрица SPEC — 4 столбца, не форма docs/operator-gates.md:61 (5 столбцов, файл:строка).
- ANSWER-n нет. Вердикт: fail.

## Не сработало
- `ls` в каталоге документов требует подтверждения — проверял Read конкретных файлов.

## Где остановился
- SPEC-AUDIT.md написан (verdict: fail, status: ready, 6 отклонений), guard: ок. Шаг завершён.

## Чего не хватило
- Где «зарегистрированный перечень» долгоживущего файла чужой задачи: нашёл только long_lived.sha256.txt в acceptance_tests задачи-владельца (guard.py:2945).
