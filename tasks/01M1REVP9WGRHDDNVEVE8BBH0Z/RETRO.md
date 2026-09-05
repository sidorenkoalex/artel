---
operator: Alexander Sidorenko
model: unknown
artel_sha: 1aed801cf5a71355d7e298c62647f7c099064d2c
---

# RETRO: 01M1REVP9WGRHDDNVEVE8BBH0Z — критерий сироты для `doctor --fix` и предпросмотр кандидатов

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: критерий сироты для `doctor --fix` и предпросмотр кандидатов

Стоимость итого: $20.42
  analyst: $0.95, 1108268 токенов
  test_author: $6.82, 15214242 токенов
  developer: $8.78, 18382281 токенов
  reviewer: $3.87, 7534421 токенов

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: 3 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
t found in 'Осиротевшие артефактные ветки удалены:\n  artifact/t777\nУборка игнорируемых файлов артефактных веток живых задач:\n\nDOCTOR: ок\n'

======================================================================
FAIL: test_ac6_unreachable_origin_blocks_deletion_with_a_distinct_fail (test_ac6_origin_unavailable_blocks_fix.Ac6OriginUnavailableBlocksFixTest.test_ac6_unreachable_origin_blocks_deletion_with_a_distinct_fail)
origin недоступен: ни одна ветка не удалена, вывод содержит
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/artel-acceptance-01M1REVP9WGRHDDNVEVE8BBH0Z-t0l31zeh/acceptance_tests/test_ac6_origin_unavailable_blocks_fix.py", line 54, in test_ac6_unreachable_origin_blocks_deletion_with_a_distinct_fail
    with self.assertRaises(SystemExit) as cm:
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: SystemExit not raised

======================================================================
FAIL: test_ac7_preview_reports_uncomputable_criterion_instead_of_a_list (test_ac7_origin_unavailable_preview_message.Ac7OriginUnavailablePreviewMessageTest.test_ac7_preview_reports_uncomputable_criterion_instead_of_a_list)
origin недоступен, `doctor` без `--fix`: вместо числа/имён
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/artel-acceptance-01M1REVP9WGRHDDNVEVE8BBH0Z-t0l31zeh/acceptance_tests/test_ac7_origin_unavailable_preview_message.py", line 48, in test_ac7_preview_reports_uncomputable_criterion_instead_of_a_list
    self.assertIn("критерий не вычислим без origin", out)
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'критерий не вычислим без origin' not found in '\nDOCTOR: ок\n'

----------------------------------------------------------------------
Ran 11 tests in 4.085s

FAILED (failures=8, errors=1)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
