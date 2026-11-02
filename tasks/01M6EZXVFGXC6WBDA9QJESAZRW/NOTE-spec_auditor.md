# Записка spec_auditor — 01M6EZXVFGXC6WBDA9QJESAZRW

## Выяснено
- Аудит 3 (spec_sha f6ff8ac1…): решения Оператора №1 и №2 перенесены в SPEC полностью; отклонения аудитов 1–2 сняты.
- Новое: у people_entry второй вызывающий — github_adapter.ensure_forge_draft_mr (:431), зовётся из advance_gates/tests_writing.py:82 на in_dev->verifying для любой задачи, включая артель. Требование 1 (people_entry бросает) его не учитывает.
- Пример шва «side_effect начиная с N-го вызова» конфликтует с «только» для AC-18 (путь артели продолжается); github_adapter.targets — общий модуль, подмена там глобальна.

## Не сработало
- Пайпы с awk в Bash требуют подтверждения — читать через Read.

## Где остановился
- SPEC-AUDIT.md записан: verdict concerns, status ready, 2 отклонения.

## Чего не хватило
- Перечня вызывающих people_entry в SPEC — нашёл grep'ом по orchestrator/.
