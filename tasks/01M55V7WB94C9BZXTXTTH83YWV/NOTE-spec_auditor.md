# Записка spec_auditor

## Выяснено
- Аудит SPEC sha 924d3943: все ссылки файл:строка SPEC (ci.py, ci_rerun.py, fsm_merge_gate.py, acceptance.py, github_adapter.py, fsm.py:166/264, gitcmd.py:44-46/133-135, pin.py:86, doctor/main_ci.py:33, targets.yaml:70, подмены в tests/) сверены — совпадают.
- Решения Оператора №1 (1-5) и №2 (1-6) перенесены полностью.
- Тестов с литералом `--repo` в tests/ нет; test_merge_gate_ci_wait.py:82 подмена «ре-ран (тест)» — повтор запущен, :163 держит «подтверждённый красный».
- Отклонения (concerns, не fail): К-1 AC-11 не ловит «флейк: … ре-ран зелёный» при незапущенном повторе (fsm_merge_gate.py:297-302); К-2 форма передачи репозитория в check_runs/failed_check_names/find_run_id/check_run_workflow_run/trigger_rerun не задана (`repo` в ci.py уже значит и URL, и путь клона) — риск «тест-навязывает-устройство» на AC-6; К-3 правило GH_REPO «два последних сегмента» не определено для scp-адреса.

## Не сработало
- `==` как разделитель в zsh-команде и `awk`/`$var` в Bash — песочница/zsh режут; использовать `--`.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns, guard прогнан.

## Чего не хватило
- Помощника «путь клона → запись targets.yaml» в коде нет (repo_context.clone_path только имя→путь).
