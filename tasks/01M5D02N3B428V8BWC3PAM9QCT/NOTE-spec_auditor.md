# Записка spec_auditor — 01M5D02N3B428V8BWC3PAM9QCT

## Выяснено
- Все ссылки файл:строка из «Материалов» SPEC совпадают с кодом (mandate.py, answer.py, spec_audit.py, outcome_integrity.py, test_integrity.py, zones.py, project_profile.py, pult_vitest_reporter.js).
- Гейт исходов действует только при `in_outcome_bounds` (advance_gates/acceptance.py:213): компонент записи `components:` с `report`, запись из одного компонента; `test_profile` с `report` (pytest-own) и записи из нескольких компонентов — вне. Проверка при записи из требования 2 SPEC («компонент есть в записи проекта и имеет `report`») шире.
- Прежние тесты не патчат `_answer_mandate` и не закрепляют текст `_mandate_hint` — своя подсказка гейта исходов (AC-13) их не ломает. `matrix_refusals` прежние тесты зовут плоским списком строк.
- Вердикт: concerns (пробелы AC у требования 4, неоднозначность нормализации остатка строки, граница «компонент с report»).

## Не сработало
- Bash с `cd …; sed` отклоняется правилом чтения — читать файлы инструментом Read по абсолютному пути.

## Где остановился
- SPEC-AUDIT.md записан (verdict: concerns, О-1…О-4), guard: ок. Шаг завершён.

## Чего не хватило
- Где граница гейта исходов: `in_outcome_bounds` в advance_gates/acceptance.py, а не в outcome_integrity.py.
