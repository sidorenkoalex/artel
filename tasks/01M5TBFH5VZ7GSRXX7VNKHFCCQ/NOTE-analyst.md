# Записка аналитика 01M5TBFH5VZ7GSRXX7VNKHFCCQ (Э4), шаг 6 — возврат со spec_gate (аудит 5), 26.10

## Выяснено
- Причина возврата — три решения Оператора аудита 5; мандат ANSWER-1 в силе (6 методов tests/test_report.py).
- tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py:185 — AuthorReportTest::test_ac12_… гоняет cmd_report, проверяет «ни одного git» (Popen + gitcmd). Подтверждено по origin/main.
- tests/test_epics_board_units.py:9 — после migrate старой БД ровно одна запись steps (миграция эпиков).

## Где остановился
- SPEC правлен, status: ready, 15 AC, guard ок. Решения → SPEC:
  (1) строка матрицы: «report не зовёт git» — test_author_report.py:185; «не меняет БД» снято;
  (2) треб. 5: догон external_refs записей журнала не пишет; новая строка матрицы test_epics_board_units.py:9 «тот же тест без правки»;
  (3) треб. 10: любой отказ new по --ref (без «:», пустая система/ключ, ref_systems, ref_required) до catalog.py:738; AC-9 и AC-12 — «ссылки refs/artifacts/<id> нет».

## Не сработало
- Составная bash-команда может требовать подтверждения — читать через Read / `git show origin/main:<файл>`.

## Чего не хватило
- Ветка задачи без Э1 — сверка только `git show origin/main:<файл>`.
