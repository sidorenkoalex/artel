# Записка test_author — 01M57PM7NBFX34319TR0F9CB4F

## Выяснено
- Прошлый визит не оставил ни одного файла планки (отказ трассируемости по всем AC-1…AC-17).
- Раскладка:
  - долгоживущий `tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py` — AC-1…AC-11, AC-16, AC-17;
  - долгоживущий `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py` — AC-13 (через `notes.cmd_note`
    на RealGitSandbox, как tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py), AC-14 (`doctor.check_merge_lock`);
  - разовый `acceptance_tests/test_one_off_helpers_and_diff.py` — AC-12 (закрытые имена `merge_queue._head_task_id`
    и пр. в долгоживущем файле запрещены), AC-15 (`_pult.changed_paths`).
- Вторая строка `merge_locks` сеется прямым `INSERT INTO merge_locks`: прежний `set_merge_lock` стирает таблицу.
- Живой держатель без subprocess — чужой host со свежим heartbeat; мёртвый — протухший heartbeat или `_dead_pid()` на этом host.
- Новая сигнатура в тестах: `merge_lock.touch_heartbeat(conn, task_id, session_id)` позиционно (AC-6, AC-7).
- До правки: первый файл 26 подтестов красны (AC-1, 2, 4б, 6, 7, 8, 9, 10 при двух проектах, 11); зелены AC-3, 4а, 5,
  10 при одном проекте, 16, 17. Второй — красен порядок «нужная строка не первая».
- Проверка стабом сделана (store: строки по проекту через task_target; acquire/touch/очередь/тексты по проекту;
  notes и doctor по всем строкам): все три файла плюс tests/test_merge_lock.py, test_merge_queue.py,
  note_window_project, test_doctor -k MergeLock зелёные; стаб откатан `git checkout`, дерево чистое кроме двух новых файлов.
- `preflight` — все проверки пройдены.

## Не сработало
- Bash: `ls` и `$VAR` в команде требуют подтверждения — каталоги читать через Read/grep.

## Где остановился
- Шаг завершён: планка и два долгоживущих файла готовы, plank-run 2 passed (со стабом), preflight зелёный.

## Чего не хватило
- Карта кода `docs/codebase-map.md` не регенерирована: правка вне tests/ для test_author откатывается пультом.
