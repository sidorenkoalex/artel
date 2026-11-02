## Выяснено
- Возврат аудита 1 из 2 (12 отклонений). Решаю SPEC-ом, не батчем: почти всё закрывается кодом.
- А-1 «с target-human»: предикат `targets.merged_by_project_people(entry)` (targets.py:566-570) — без литерала. Новые строки 8–10 — только для таких записей; строки защит/workflow — для forge-пути (`forge.ci_by_pipeline`) по п.2 ТЗ.
- Б-2: `_GitHub` имеет `pipeline_status`, но нет `protections`/`project_info`/`branch_pipeline`; развилка — `forge.ci_by_pipeline`.
- Б-3: проба подмодуля — `doctor.gitcmd.in_repo(clone, "ls-remote", url)`: `gitcmd._hosting_project` по `-C clone` даёт токен слота записи (gitcmd.py:98-122, 1005-1011). В роли `hosting_token` отказывает.
- Б-4: шаблон ветки — `entry.get("branch_template") or doctor.targets.DEFAULT_BRANCH_TEMPLATE` (targets.py:364).
- Поле кода: назвал `http_status: int | None`; права = {401,403,404} как `_GhProbe.denied` (project_checks.py:269-272).
- Код ответа теряется в `_read_all` (gitlab_adapter.py:282-308) — проведение кода разрешено в SPEC явно.

## Не сработало
- Bash с `;`/`cd &&` иногда требует подтверждения — Read/grep с абсолютными путями.

## Где остановился
- SPEC.md переписан под все 12 отклонений аудита (15 AC, budget 40 = рамка, status: ready), guard ок. Шаг завершён.
- Выбор, который может оспорить Оператор: строки 8–10 только у `target-human` (буква ТЗ:24); строка workflow оценивает только push-конвейер (MR-события — в «Не входит»); ok при заполненном слоте `project-token`.

## Чего не хватило
- Семантики оценки `workflow:rules` в ТЗ нет — задал по правилам GitLab (push-конвейер, правила с 1, первое сработавшее решает).
