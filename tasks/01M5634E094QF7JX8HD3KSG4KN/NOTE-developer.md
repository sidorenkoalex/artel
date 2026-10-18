# Записка developer

## Выяснено
- Развилка — `brief.is_artel_task(conn, task_id)` (repo_context.is_artel по target задачи);
  ветка артели в четырёх сборщиках брифа исполняет прежний код в прежнем порядке (AC-1 зелёный).
- Конвенции внешнего проекта: `brief._project_conventions_parts` → `_read_project_conventions`:
  `reference_cache.branch_commit` → `git ls-tree <sha>` (состав корня) → `git show <sha>:<файл>`
  байтами через `_clone_git` (не gitcmd.show — тот не различает «нет файла» и сбой).
- Миссии: `role_prompt.mission_brief_package` — `artel` по той же развилке; тексты артели те же строки.
- Долгоживущий файл задачи: 13 passed; планка: 2 passed.

## Не сработало
- `ls`/`grep -A` в Bash требуют подтверждения — читал файлы Read.

## Где остановился
- Код готов; тесты затронутых модулей зелёные (~200 passed, 23 файла); карта регенерирована;
  PLAN.md status: ready, guard ок. Полный suite-run №1 зелёный: 5638 прошло, 0 упало, 2 пропущено.
  Шаг завершён.
- В Bash нет `sleep` (command not found) — ожидание через `python3 -c "import time; time.sleep(30)"`.

## Чего не хватило
- Ничего существенного.
