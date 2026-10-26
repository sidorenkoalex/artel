# Записка spec_auditor — 01M5TBFH5VZ7GSRXX7VNKHFCCQ (визит 3, SPEC sha 183c611b)

## Выяснено
- Ветка задачи не содержит Э1; сверка по `git -C <wt> show origin/main:<файл>` и `git -C <wt> grep -n -A<n> <шаблон> origin/main -- <файл>`.
- Требование 3 (пакетное чтение steps для waiting_on): queue_wait (zone_lock.py:850) → _waiting/_occupies/_stay_since_id/_occupier/_waiting_dependency/queue_order — пакетирование требует правки zone_lock.py (нет в зонах) или копии логики в board.py; плитка report waiting_on не показывает.
- E1-тест board_model.py:222 (ac23) подменяет zone_lock.queue_wait(conn, task_id, t=None) и ждёт dependency; :202 (ac22) — на None. В матрице SPEC строки нет, мандат только на test_report.py.
- test_report.py:1018 и command_report:524/:550 доску не покрывают.
- store.db() открывает новое соединение на каждый вызов (store.py:403) — AC-3 по total_changes «уже открытого» соединения не ловит запись своим соединением.
- Строки: catalog.py:694 _ensure_task_worktree, board.py:130 last_step_times (один запрос steps на проект), artel.py:2233 белый список ролей закрыт по умолчанию.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready, guard ок.

## Чего не хватило
- Знания «какие тесты держат zone_lock.queue_wait как источник waiting_on» — нашёл чтением E1-теста целиком.
