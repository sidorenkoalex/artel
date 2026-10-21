# Записка test_author — 01M5FGJW4RBN9C9P48Q8MDHJX1

## Выяснено
- Планка: долгоживущий `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py` (свойства `cleanup.cleanup_merged_remote(conn, task_id, branch, merged_sha)` — AC-1…AC-8, артель и внешний проект, зерно `random`); разовые `acceptance_tests/test_merge_gate_remote_cleanup.py` (тело гейта `_cmd_approve_merge_gate`: AC-1, 4, 6г, 7, 8 — набор `GateCases` у артели и у проекта) и `acceptance_tests/test_retention_doc.py` (AC-9).
- Валидация стабом (cleanup_merged_remote + `_delete_origin_branch(..., lease)` с разбором `None` + вызов из `_cleanup_merged_task(…, final_sha)` + абзац retention.md): все тесты зелёные; стаб откатан `git checkout`, дерево чистое кроме долгоживущего файла.
- Без кода: красные все, кроме AC-7 гейта, AC-8 гейта (gh) и kill артели — они держат прежнее поведение.
- Guard долгоживущих: импорт `orchestrator.gitcmd` — признак «git-модуль»; шпион ставится `mock.patch("orchestrator.gitcmd.in_repo", …)`, оригинал — `cleanup.gitcmd.in_repo`. `subprocess.CompletedProcess(["git"], …)` — признак «git-вызов».
- Трассируемость требует имя `test_ac6_…` — `test_ac6a_…` не считается.
- Предпроверка `preflight` пройдена целиком.

## Не сработало
- Составные bash-команды и `ls`/`rm` требуют подтверждения — по одной команде, удаление через python.

## Где остановился
- Шаг завершён: планка сдана.

## Чего не хватило
- Нет сводки, какие тесты гоняют тело гейта мержа до конца (нашёл grep'ом `_cmd_approve_merge_gate` по tests/).
- Записка прошлого запуска не упомянула уже написанный разовый файл гейта — чуть не появился дубль.
