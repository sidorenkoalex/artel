## Выяснено
- forge.py: у типов только reason; ProjectInfo без поля кода; _GitHub имеет pipeline_status → выбор ci-token по hasattr(pipeline_status) не различит хостинги, только ci_by_pipeline.
- gitlab_adapter._read_all теряет Reply.status (возвращает (None, reason)) — заполнить поле кода без правки _read_all нельзя.
- Сторож ac9 (tests/test_01m5w27…:425-442) не ловит `forge.hosting(x) == "gitlab"` (attr `hosting` не field_like).
- Имени файла CI (.gitlab-ci.yml) и поля записи под него в коде нет; ADR-0029:55 — «если запись называет файл конвейера».
- full_suite ci|both допустим только у хостинга с job_test_report (targets.py:1098-1103) — у github нет, строки 8/9 фактически gitlab-only.
- doctor/__init__ не импортирует catalog (branch_template) — обход через entry.get("branch_template")/targets.DEFAULT_BRANCH_TEMPLATE.
## Не сработало
- Bash с cd/ls/wc требует подтверждения — читать Read/grep абсолютными путями.
## Где остановился
- SPEC-AUDIT.md записан, verdict fail, status ready; guard — ок. Шаг завершён.
## Чего не хватило
- Не нашёл, что значит «с target-human» в заголовке п.1 ТЗ (merge_gate?) — в SPEC выпало.
