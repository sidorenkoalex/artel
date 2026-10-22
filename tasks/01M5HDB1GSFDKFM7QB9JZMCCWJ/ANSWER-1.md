---
task: 01M5HDB1GSFDKFM7QB9JZMCCWJ
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Мандат Оператора (решение 22.10.2026, «ок по рекомендациям»): из выбора роли стенда (ROLES, строка 60) исключается developer; методы и утверждения не меняются. Основание — ADR-0024 п. 4 и поправка 22.10.2026 п. 1 (коммит 3aacbd39).

Ослабление тестов разрешено: tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| ROLES без developer в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report | итог и отчёт прогона при БД только на чтение (tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:303) | остаётся для test_author и reviewer; у developer полный прогон исчезает вместе с разрешением | tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:303 (тот же метод и утверждения); новый тест отказа developer под БД только на чтение (AC-1 SPEC) | ок |
| ROLES без developer в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record | отложенная запись журнала и её досыл (tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:341) | остаётся | tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:341; новый тест: отказ developer не создаёт отложенной записи и не досылает журнал (AC-3 SPEC) | ок |
| ROLES без developer в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file | один файл замка у роли и гейта (tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:407, :377) | остаётся | tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:407; новый тест: developer --failed под БД только на чтение берёт общий замок, при замке гейта отказ называет задачу гейта (AC SPEC) | ок при условии этого теста |
| ROLES без developer в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome | предел профиля и исход «не уложился» (tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:435) | остаётся | tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:435 | ок |
| ROLES без developer в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir | логи ветки и базы под suite-run/ (tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:473) | остаётся | tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:473; новый тест: отказ developer не создаёт лог (AC-3 SPEC) | ок |
| ROLES без developer в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report (wait_report) | --wait у developer под БД только на чтение (косвенно, при выпадении developer) | остаётся | новый тест --wait 0 developer под той же подменой БД (AC SPEC) | ок при условии этого теста |

Независимая проверка: ок при условии двух новых тестов (developer --failed с общим замком и --wait 0 под БД только на чтение) — матрицу составил независимый проверяющий ТЗ без контекста сессии, 22.10.2026.
