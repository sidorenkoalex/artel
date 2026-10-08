---
task: 01M4C954HBJWEGD3AZS7Q3EHA4
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Дозор: позиции, просмотр, подтверждение, уведомление

## Соответствие SPEC

Фаза A (гейт плана): покрытие требований полное, шаги имеют проверяемый размер и соответствуют архитектуре. План корректно описывает миграцию, обратимость и отсутствие влияния на lease/состояния задач.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Схема, миграция и явный `INSERT` добавлены. |
| 2 | OK | `steps` читаются одним запросом по наблюдаемому набору и упорядочены по id. |
| 3 | OK | Есть `events`/`acknowledge`, границы, монотонность и проверка сессии. |
| 4 | OK | `alerts` включён по умолчанию для наблюдения; роль допускается только к `events`. |
| 5 | OK | Вывод обезврежен, уведомления передаются отдельным аргументом и не прерывают цикл. |
| 6 | Не полностью | Реализация PID-владения есть, но обязательный помощник `force_stop` неработоспособен в окружении роли (R1-F1). |
| 7 | OK | `run`/`auto` отказывают в песочнице; смена pin выдаёт предупреждение. |
| 8 | OK | `doctor` проверяет обе точки hooks и называет `hook-migrate`. |
| 9 | OK | Документация обновлена для независимого дозора и перезапуска. |
| 10 | OK | Повторный запуск, мёртвый/свой PID и `--takeover` обработаны. |
| 11 | OK | Набор без задач и терминальные задачи не завершают цикл сами. |
| 12 | OK | Позиция сдвигается и для строк, не прошедших фильтр. |
| 13 | OK | `--events` и `--from` разделяют перечень классов и возвращают `POSITION`. |
| 14 | OK | Метаданные подтверждения и сообщение о запоздалом повторе реализованы. |
| 15 | OK | В документации явно зафиксирована общая для чатов позиция. |

## Замечания

- major — tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py:239-243 — `WatchProgressSandbox.force_stop` теперь вызывает `artel.main()` с `observe stop`, но оставляет `ARTEL_ROLE=reviewer`. Штатное ограничение роли закономерно завершает вызов `SystemExit: artel.py observe stop: команда недоступна процессу роли reviewer`; из-за этого при запуске модуля в окружении роли не завершаются 12 тестов. Дополнительно точечно прочитаны ограничитель роли в `orchestrator/artel.py` и помощник теста именно для проверки причины отказа. Предложение: в тестовом контексте временно очистить `config.ARTEL_ROLE_ENV`, сохранив вызов через публичную команду и подстановку `ARTEL_SESSION_ID`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py:239-243 | `force_stop` вызывает запрещённый для роли `observe stop`, не снимая признак роли. | 12 тестов этого долгоживущего модуля падают в штатном окружении роли и не очищают дозор. | В тестовом вызове временно очистить `config.ARTEL_ROLE_ENV`, оставив публичный `observe stop` и проверку сессии. |

## Вердикт

changes_requested: исправить R1-F1 и повторить адресный прогон `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py` в обычном окружении роли.

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4C954HBJWEGD3AZS7Q3EHA4` — 1 passed.
- Адресные контрактные тесты позиций/дозора и новые регрессии — 23 passed; совместный запуск с `test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py` выявил 12 падений на запрете `observe stop` для `ARTEL_ROLE=reviewer`.
- `ARTEL_ROLE= python3 -m pytest tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py -x` — 13 passed, что подтверждает зависимость дефекта от неснятого окружения роли.
- `ARTEL_ROLE= python3 -m pytest tests/test_watch.py tests/test_observation_edges.py tests/test_artel_role_restricted_commands.py tests/test_doctor.py tests/test_store_schema_migration_parity.py tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py tests/test_01m4c954hbjwegd3azs7q3eha4_documentation.py` — 145 passed.
- `git diff --check 0dc0b7b56111352d99cec017fda9d71092e41cf9...HEAD` — без замечаний.
