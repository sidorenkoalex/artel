# Записка test_author 01M4VC31NFCS6JZ0VE8HNJ7FYM

## Выяснено
- Долгоживущий файл: tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py
  (AC-1 функция, AC-2, AC-3, AC-5..AC-11) — только публичное: canary.escalation_roles,
  models.unclean_reason/clean_run/pair_admission, store.insert_canary_run(escalation_roles=[...]),
  store.all_canary_runs, fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER. До реализации 23 красных.
- Разовый acceptance_tests/test_run_one_task_escalation_roles.py: AC-1 (строка
  через _run_one_task, подменены только _ephemeral_clone/_drive_in_clone, разбор
  _read_drive_result настоящий), AC-4 (metrics ровно поля main), AC-10 пороги
  литералами (3, 2, «средний»). До реализации: нет колонки escalation_roles.
- Стаб-валидация: временная реализация в canary/models/store — оба файла
  зелёные (12+3), стаб откачен `git checkout` трёх файлов. preflight — все пройдены.
- Карту docs/codebase-map.md не регенерировал: правку вне новых tests/ пульт
  откатывает у test_author; регенерация — дело developer.

## Не сработало
- `cd … && grep`/циклы в Bash просят подтверждения — абсолютные пути, по одной команде.

## Где остановился
- Шаг завершён.

## Чего не хватило
- —
