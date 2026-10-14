---
task: 01M4XVM49PP5WHSXT5S8JW85WN
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

# Ответ Оператора от 14.10.2026

Вопрос 1: A, адресная миграция по ADR-0024. Вопрос 2: B, существующий process/lease-контекст с сохранением всех описанных границ. Решение Оператора явно получено в текущем чате. Аналитику: оформить непротиворечивый SPEC с пятиколоночной матрицей и обязательными AC сохранения защитных свойств; не расширять мандат на helpers/весь файл. Если понадобится правка общего helper, эскалировать с точным носителем.

Ослабление тестов разрешено: tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir
Основание: ADR-0024, решение Оператора 14.10.2026; только смена прежнего разрешения developer на запрет нового полного запуска при сохранении всех защитных проверок разрешённых маршрутов. Удаление, переименование, skip/xfail, retries, увеличение лимитов и смягчение assertions не разрешены.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| Новый полный запуск developer | Прежнее разрешение, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:303,341,407,435,473 | Нет: заменяется ранним отказом | Новые проверки cmd_suite_run: отказ до открытия БД с записью/создания БД, deliver_journal, файлов, замка и запуска; чтение существующей БД для проверки process/lease допустимо без побочных эффектов | Адресная миграция по решению Оператора |
| Отчёт green/red в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report | Прежние исходы и отчёты :303 | Да, для разрешённых запусков | Тот же метод и assertions на операторе/прочих ролях; отдельный отказ developer | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Досыл журнала в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record | Отложенная запись и досыл :341 | Да, для разрешённых запусков | Тот же метод/assertions; новый запрет не создаёт запись | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Общий замок в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file | Одна блокировка роли/гейта :407 | Да, для разрешённых запусков | Тот же метод/assertions обоих направлений; отказ developer до lock | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Предел и timeout в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome | Предел профиля и точный timeout :435 | Да, для разрешённых запусков | Тот же метод/assertions, прежние пределы | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Логи в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir | Логи ветки/базы в suite-run :473 | Да, для разрешённых запусков | Тот же метод/assertions; отказ developer без файлов | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Контекст вызывающего шага | runner.py:74–92,1570–1583; ARTEL_ROLE/TASK не удостоверяют процесс | Да; проверка усиливается | Новые проверки process/lease для Codex/Claude, неполного контекста и отделённого разрешённого фона | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Разрешённые маршруты | --failed, статус, --wait; tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py:579–601 | Да | Прежние проверки плюс подтверждённый developer; HOME/случайная роль не считаются developer | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Обязательные гейты/CI | Полный набор, таймауты, метрики, reuse | Да | Прежние тесты и обязательные гейты/CI | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |

Независимая проверка: pass после адресной правки строки о БД; developer_suite_tz_audit подтвердил пять методов, сохранение защитных свойств и границы 1A+2B. Чтение существующей БД для проверки process/lease разрешено; создание/запись и остальные побочные эффекты отказа запрещены.

## Принятое ADR-0024

Публикация docs/adr/0024-developer-full-suite-contract.md удержана штатным окном тишины пульта; решение уже принято Оператором. Полный текст для аналитика:

# ADR-0024: Новый полный suite-run из шага developer запрещён

Статус: принят, не исполнен. Дата: 14.10.2026. Решение Оператора: «оформляй ADR и ANSWER: запрещаем новый полный прогон developer, сохраняем проверки на разрешённых маршрутах, роль определяем по процессу/lease». Исполнение — задача 01M4XVM49PP5WHSXT5S8JW85WN. Дополняет ADR-0002; не меняет общую песочницу ADR-0023.

## Контекст

coding-standards запрещает developer полный tests/, но suite-run и пять старых сценариев readonly_db разрешают его. Нужна явная миграция этого разрешения, а не удаление защитных проверок ради зелени.

## Решение

1. Новый полный suite-run из подтверждённого шага developer получает именованный отказ до открытия БД с записью/создания БД, deliver_journal, файлов, лога, замка, PID и запуска. Не изменять уже идущий прогон.
2. Developer сохраняет адресные тесты, планку, --failed, чтение статуса и --wait. Полные операторские прогоны, прочие роли, обязательные полные гейты и CI сохраняются.
3. Вариант 2B: принадлежность вызывающего процесса живому шагу и точная роль подтверждаются существующими сведениями process/lease. Один HOME, переменная ARTEL_ROLE или состояние запрошенной задачи не удостоверяют developer. Подтверждённый developer не получает разрешение лишь из-за потери ARTEL_ROLE. Проверить Codex/Claude и отделённый разрешённый фон. Когда принадлежность не доказана, сохранить прежний маршрут; при невозможности переносимого подтверждения — эскалация, без новой песочницы и ослабления guard'ов.
4. Вариант 1A: адресно разрешена смена области сценария developer только в пяти методах ниже. Имена методов, виды и строгость assertions и защитные свойства отчётов, журнала, общего замка, пределов/timeout и логов сохраняются для разрешённых запусков. Простое исключение developer без новых проверок раннего отказа и разрешённых путей не допускается. Мандат не разрешает удалить/переименовать тест, skip/xfail, retry, поднять предел или сменить ожидаемый исход разрешённого запуска.
5. SPEC обязан перенести каждое свойство матрицы в проверяемые AC. Рамка $50 не увеличивается. Реализация и исполнение ADR подтверждаются обычными гейтами, а не этим документом.

## Адресные носители миграции

- `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report`
- `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record`
- `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file`
- `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome`
- `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir`

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| Новый полный запуск developer | Прежнее разрешение, tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:303,341,407,435,473 | Нет: заменяется ранним отказом | Новые проверки cmd_suite_run: отказ до открытия БД с записью/создания БД, deliver_journal, файлов, замка и запуска; чтение существующей БД для проверки process/lease допустимо без побочных эффектов | Адресная миграция по решению Оператора |
| Отчёт green/red в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report | Прежние исходы и отчёты :303 | Да, для разрешённых запусков | Тот же метод и assertions на операторе/прочих ролях; отдельный отказ developer | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Досыл журнала в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record | Отложенная запись и досыл :341 | Да, для разрешённых запусков | Тот же метод/assertions; новый запрет не создаёт запись | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Общий замок в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file | Одна блокировка роли/гейта :407 | Да, для разрешённых запусков | Тот же метод/assertions обоих направлений; отказ developer до lock | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Предел и timeout в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome | Предел профиля и точный timeout :435 | Да, для разрешённых запусков | Тот же метод/assertions, прежние пределы | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Логи в tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py::LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir | Логи ветки/базы в suite-run :473 | Да, для разрешённых запусков | Тот же метод/assertions; отказ developer без файлов | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Контекст вызывающего шага | runner.py:74–92,1570–1583; ARTEL_ROLE/TASK не удостоверяют процесс | Да; проверка усиливается | Новые проверки process/lease для Codex/Claude, неполного контекста и отделённого разрешённого фона | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Разрешённые маршруты | --failed, статус, --wait; tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py:579–601 | Да | Прежние проверки плюс подтверждённый developer; HOME/случайная роль не считаются developer | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
| Обязательные гейты/CI | Полный набор, таймауты, метрики, reuse | Да | Прежние тесты и обязательные гейты/CI | ок при условии: сохранить названные прежние проверки и добавить обязательные проверки-замены из столбца покрытия |
