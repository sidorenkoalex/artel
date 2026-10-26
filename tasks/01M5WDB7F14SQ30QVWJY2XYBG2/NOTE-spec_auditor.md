# Записка spec_auditor — 01M5WDB7F14SQ30QVWJY2XYBG2 (аудит 3, spec_sha 57f5bdf4)

## Выяснено
- Факты SPEC верны: catalog.py:918/844/1024, fsm.py:1016/1403 (до записей :1414/:1431/:1444), gitcmd.py:37/86/94/164/341/413/441/469; шестой subprocess.run — check_ignore gitcmd.py:549 (не push).
- Внутренние противоречия SPEC: AC-9 `push_options: [X, Y]` и AC-6 `-o X` против нормы формы `ИМЯ=значение` (AC-1); `--delete` вне белого списка флагов при разрешённом удалении refs/artifacts/<id>.
- Долгоживущий тест А0 tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:474 запрещает сравнение merge_gate с "operator" вне targets.py — предикат белого списка только в targets.py.
- Обход: общий config клона (push.pushOption, remote.origin.pushurl/push/mirror), --config-env, GIT_CONFIG_* в env, send-pack.
- artifact_cleanup.py:103 удаляет refs/heads/artifact/* артели, не refs/artifacts/<id> (ТЗ ошибался, SPEC не перенёс).
- Вердикт: concerns, 9 отклонений; guard ок.

## Не сработало
- `ls`, `cd … && git`, heredoc с `$` в Bash — отказ/подтверждение; только простые команды.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns). Шаг завершён.

## Чего не хватило
- Перечня push-мест: `grep -rn '"push"' orchestrator/`.
