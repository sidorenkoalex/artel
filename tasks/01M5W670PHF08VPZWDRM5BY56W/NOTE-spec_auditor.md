# Записка spec_auditor — 01M5W670PHF08VPZWDRM5BY56W

## Выяснено
- Рабочий каталог (HEAD 58d9b72) позади origin/main: А0 (`targets.SUPPORTED_FORGES`, `unsupported_reason`, строка doctor `project-support-*`) есть только в origin/main (5705cfd) — сверять А0-факты через `git show origin/main:…`.
- Белый список требования 3 не содержит чтения проекта (`GET /projects/:id` — default_branch, права) и конвейеров по ref; «участники» прямо запрещены. А требование 7 (сверка base) и 8 (роль пользователя, последний конвейер базы) без них не исполнимы; часть 2 деления не имеет зон forge.py/gitlab_adapter.py.
- `ci.head_sha` (ci.py:204) — локальный `git rev-parse`, к хостингу не ходит; AC-13 требует вызова транспорта и для него.
- ADR-0029 п.8 (стр. 62): «Неполный статус — не зелёный» — в SPEC нет (пагинация заданий, canceled, неизвестные статусы).
- `trigger_rerun`→`rerun_started` (ci.py:1679) читает подстроку «не запущен»; отказ gitlab без неё читается как запущенный повтор.
- origin/main tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:62 — запись gitlab с `url: https://localhost/team/<имя>`, `doctor.all_checks` — после А1 doctor пойдёт в живой транспорт.

## Где остановился
- Вердикт fail, SPEC-AUDIT.md записан.

## Чего не хватило
- Долго искал, где А0: не в рабочем каталоге, а в origin/main.
