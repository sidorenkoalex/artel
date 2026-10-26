# Записка developer — 01M5TBBDFS6DWQY6MS263T1KPY

## Выяснено
- Возврат из verifying: CI-линт формата id ловит `TASK_ID = re.compile(...)` в tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py:37. Это единственное попадание линта по ветке; код задачи чист.
- Файл — долгоживущий, под замком сумм (acceptance_tests/long_lived.sha256.txt, строка 5) — разработчику править нельзя.
- Готов патч amend-views-task-id.diff (каталог документов): помощник `carries_id` (id из store.all_tasks + epics) вместо регулярного выражения. `git apply --check` ок; применённый временно — 7 passed, линт пуст; файл возвращён `git checkout --`.
- Реализация Э1 прежняя (см. PLAN.md «Подход»): epics.py, board.py, SQL в store.py, schema._migrate_epics, catalog._status_line.

## Не сработало
- Первая версия диффа: неверный счётчик хунка (-77,6 вместо -77,4) — поймал `git apply --check`.

## Где остановился
- PLAN.md status: escalate (вопрос: amend-tests патчем — дефолт, либо мандат на правку). guard ок. Код не менялся, дерево чистое.
- После amend-tests новый шаг разработчика, скорее всего, не нужен: задача может идти в verifying.

## Чего не хватило
- Причина возврата требовала править тест, замок его запрещает — противоречие видно только при сверке с long_lived.sha256.txt.
