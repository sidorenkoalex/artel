# Записка аналитика 01M5TBFH5VZ7GSRXX7VNKHFCCQ (Э4), шаг 4 — возврат со spec_gate (аудит 3), 26.10

## Выяснено
- Причина возврата — решения Оператора (1)–(5) аудита 3; мандат ANSWER-1 в силе (6 методов tests/test_report.py).
- board.py на origin/main: waiting_on :21 (queue_wait :34), _card :39, build_model(conn, project) :123, last_step_times :130.

## Где остановился
- SPEC правлен, status: ready, 15 AC (число не выросло), guard ок. Решения → SPEC:
  (1) треб. 3 — флаг `with_waiting` в build_model, report выключает, zone_lock.py не трогается; AC-14 + «Не входит»;
  (2) строка матрицы по board_model.py:202/:222 — без правки, мандат не нужен;
  (3) AC-3 — подмена store.db() измеряемым соединением;
  (4) строка матрицы «число запросов к steps» — покрывает только AC-14;
  (5) «без сети» — в AC-3; порядок ref до _ensure_task_worktree — AC-9; пустая система — AC-12; чередование id — AC-5; одно множество проектов и один last_step_times на проект — AC-14.

## Не сработало
- Составная bash-команда (`D=…; ls; cat`) требует подтверждения — читать файлы через Read.

## Чего не хватило
- Ветка задачи без Э1 — сверка только `git show origin/main:<файл>`.
