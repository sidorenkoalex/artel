---
task: 01M4KG7VHHXTVTW5TTX2PGY5RY
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: suite-run доступен роли на Codex (песочница workspace-write)

## Фаза A — план
- Таблица покрытия полна: требования 1–6 → шаги 1–4. Шаги размера MR.
- «Влияние на систему» исправлено по R1-F1 и теперь совпадает с кодом.
  Через очередь в журнал проходит только `SUITE_NEAR_LIMIT_ACTION` от
  `orchestrator`, с пометкой досыла и обрезанным текстом. Остаточный риск
  назван честно: роль может подделать информационную запись «близко к
  пределу» для любой задачи. Гейты эту запись не читают (проверено:
  `grep SUITE_NEAR_LIMIT_ACTION orchestrator scripts` находит её только в
  `acceptance.py:1197/1230/1238` и в `suite_lock.deferrable`).
- В «Рисках» названа потеря алерта (R1-F3). Отказ поднимать алерт на
  досыле обоснован: иначе у роли появился бы ещё один канал из песочницы.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Замок тот же (`suite_lock.directory()/lock.json`). Отчёт и лог лежат в каталоге, доступном роли. AC-4/AC-6/AC-8 зелёные |
| 2 | OK | `--add-dir` открывает ровно `config.LOGS/suite-run`, логи перенесены туда же. Очередь `pending-journal` больше не канал произвольных записей (закрытый перечень `deferrable`) |
| 3 | OK | Сбой записи откладывается (`_journal_deferred` → `defer_journal`, только действие из перечня). Досыл `deliver_journal` пишет запись в журнал от `DEFERRED_ACTOR` с пометкой досыла. AC-5 зелёный |
| 4 | OK | Argv и окружение Claude прежние (AC-7). Отчёт называет путь лога |
| 5 | OK | Замок, пределы и `--sandbox workspace-write` не тронуты. Подделка записей, которым верят гейты, закрыта (R1-F1 принят) |
| 6 | OK | Изменено одно ожидание: `test_docs_dir_layout.py::…::test_add_dir_only_when_docs_dir_given_and_model_stays_last`. Оно объявлено в SPEC. В итерации 2 существующие утверждения `tests/` не менялись: инкрементальный diff `tests/` только добавляет три метода |

## Замечания

Блокеров и major нет.

Наблюдение, не замечание: `session_id` записи досыл по-прежнему берёт из
файла очереди (только если это строка). Журнал читает `session_id` лишь у
записей `lease взят/перехвачен` и `created` (`watch._owner_session_id`,
`watch.py:176–189`). Через очередь таких записей не провести, поэтому
`session_id` записи «близко к пределу» ни на что не влияет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/suite_lock.py: `deliver_journal`/`_deliver`, `defer_journal`, `deferrable` | Досыл писал в журнал произвольные actor/action из файла очереди | — | Принято. Перечень `deferrable` содержит только `SUITE_NEAR_LIMIT_ACTION`, его проверяют и `defer_journal`, и `_deferred_text` досыла. Автора ставит досыл (`DEFERRED_ACTOR`), текст обрезается до `DEFERRED_DETAIL_MAX`, поля проверяются на тип, выброшенная запись называется в stderr. `SUITE_DURATION_ACTION` исключено обоснованно: suite-run его не пишет, а по нему калибруется doctor. Временные мутации M1/M2/M4/M5 ловятся (см. ниже) |
| R1-F2 | accepted | orchestrator/suite_lock.py: `deliver_journal`, `finally: conn.close()` | Соединение досыла не закрывалось | — | Принято. Соединение закрывается в `finally`. `test_delivery_closes_connection` ловит мутацию M3 |
| R1-F3 | accepted | PLAN.md «Риски» | Алерт «близко к пределу» из процесса роли теряется | — | Принято. Потеря названа в рисках PLAN. Отказ поднимать алерт на досыле обоснован (иначе лишний канал из песочницы к Оператору) |

## Вердикт
approved. R1-F1..R1-F3 закрыты, новых blocker/major нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_suite_run.py tests/test_suite_run_deferred_journal.py tests/test_docs_dir_layout.py tests/test_suite_lock.py tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py tests/test_acceptance.py`:
  80 passed, 88 subtests passed (33 с).
- Временные мутации `orchestrator/suite_lock.py`, каждая с прогоном
  `tests/test_suite_run_deferred_journal.py`. Затем код возвращён,
  `git status` чистый.
  - M1: досыл берёт `actor` из файла → 1 failed.
  - M2: `defer_journal` без проверки перечня → 2 failed.
  - M3: соединение не закрывается → 1 failed.
  - M4: `_deferred_text` без проверки перечня → 1 failed.
  - M5: нет обрезки detail → 1 failed.
  Заявки «Ловит мутацию» трёх новых методов подтверждены.
- `artel.py plank-run 01M4KG7VHHXTVTW5TTX2PGY5RY`: отказ «планки нет» (в
  `refs/artifacts/…` нет `test_*.py`). Задачу держат долгоживущие файлы,
  они зелёные (см. выше). CI коммита c31a5990 зелёный.
- Карта: `git show --stat c31a5990` — `docs/codebase-map.md` обновлён в том
  же коммите, `deferrable` есть в карте (строка 1826).

## Предложения системе
- Очередь «процесс роли пишет → процесс пульта исполняет» здесь закрыта
  перечнем действий и автором, который ставит сам досыл. Тот же приём стоит
  внести в review-checklist как обязательный пункт для любого такого канала
  (повтор предложения итерации 1, класс подтверждён исправлением).
