# Записка spec_auditor — 01M5TBFCVFNN95BHH0E9C6KBKB

## Выяснено
- Визит 2 (SPEC be22cc78…), после возврата Оператора с гейта 26.10: пункты 1–6 прошлого аудита сняты решениями, внесены в SPEC (треб. 12, 17, AC-15…AC-21, budget.py/board.py в зонах).
- Э1 смержен в origin/main (f909b7dd9); в ветке задачи (761b646e9) epics.py нет — читать `git show origin/main:orchestrator/epics.py`.
- Главная новая находка: `send_pending` досылает только набор `_unsent` своего процесса, а пара после неудачной отправки из набора убрана (`artifact_branch.py:533-541`). Повтор отказа у ссылок задач — следующей командой или `origin_sync_refusal` (`tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py:333,450`). Поэтому формулировка треб. 12 и AC-9 «досылка (send_pending) отправляет» по коду не выполнима.
- `_journal_push_outcome`/`_send`/`_last_send_failed`/`task_repo` берут ключ из `branch_name(task_id)` и строки задачи. Для журнала под `E…` и репозитория проекта эпика нужна параметризация в artifact_branch (он в зонах).
- Существующие тесты Э1 задают рамки: AC-19 миграции `len(added) == 1` (`tests/test_01m5tbbdfs6dwqy6ms263t1kpy_migration.py:121`), фикстура снимает индексы с `epic` в SQL (`:56-60`); AC-18 команд — нет lease по id эпика; AC-30 — target всех записей эпика = проект.

## Не сработало
- `cd … && git`, подстановка процесса — отказ песочницы.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, 6 пунктов; guard ок. Главный — п.1 (AC-9/send_pending).

## Чего не хватило
- Механизм повтора недосланной ссылки между процессами — нашёл только в тесте one_push_per_command:333.
