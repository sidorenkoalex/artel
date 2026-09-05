---
operator: Alexander Sidorenko
model: unknown
artel_sha: 96aac935c17ef2651136a60526accfa529e56fb3
---

# RETRO: 01M1SD5NZ79MWCEJDJ9JP6EPWS — R6 — `store.py`: схема и миграции отдельно, запросы по областям

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: R6 — `store.py`: схема и миграции отдельно, запросы по областям

Стоимость итого: $19.31
  analyst: $1.08, 949499 токенов
  test_author: $12.58, 26878880 токенов
  developer: $4.04, 7677442 токенов
  reviewer: $1.62, 2302940 токенов

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 1 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
планка: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1SD5NZ79MWCEJDJ9JP6EPWS/tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/acceptance_tests, cwd: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M1SD5NZ79MWCEJDJ9JP6EPWS
OK: состояние в /var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/tmpn_m4bj57/.artel/state.db
Задачи в полёте (ветки task/* без строки в БД) холодный старт не восстанавливает автоматически — пересборка по веткам остаётся ручной сверкой Оператора (SPEC T049, требование 11).
Отчёт сгенерирован: /var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/tmpzoa_c_lw/.artel/report.html
[T001] lease не заведён — снимать нечего
........F..
======================================================================
FAIL: test_ac7_report_html_matches_golden_sha256 (test_ac7_report_output_smoke.ReportOutputByteParityTest.test_ac7_report_html_matches_golden_sha256)
`report.cmd_report()` на детерминированной фикстуре (две
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/al.sidorenko/projects/artel/.artel/worktrees/01M1SD5NZ79MWCEJDJ9JP6EPWS/tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/acceptance_tests/test_ac7_report_output_smoke.py", line 98, in test_ac7_report_html_matches_golden_sha256
    self.assertEqual(
    ~~~~~~~~~~~~~~~~^
        actual_sha256, _EXPECTED_SHA256,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        "report.html отличается от золотого снимка — длина текущего "
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        f"вывода {len(html)} байт")
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: '3d45117130e12c7590a770d8897c86aa78cb019597e27c3bff46a2f105c13235' != '920f2ac5c41e17525a0845cfdf97ef5c44bf7d5093df2538d00c420af40fee68'
- 3d45117130e12c7590a770d8897c86aa78cb019597e27c3bff46a2f105c13235
+ 920f2ac5c41e17525a0845cfdf97ef5c44bf7d5093df2538d00c420af40fee68
 : report.html отличается от золотого снимка — длина текущего вывода 6336 байт

----------------------------------------------------------------------
Ran 11 tests in 0.294s

FAILED (failures=1)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
