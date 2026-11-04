# Записка developer

## Выяснено
- Механизм: `orchestrator/role_bin/git` (sh, 0755) → `python3 -I -S orchestrator/role_git.py <каталог обёртки> "$@"`; role_git.py — только stdlib (AC-14 копирует role_bin и role_git.py в дублёр без пакета).
- Свои/чужие рабочие копии выводятся без БД: `<корень>/.artel/projects/*/worktrees/<ARTEL_TASK>` — своя, прочие — чужие; клон проекта своей копии разрешён.
- Пульт зовёт git через `gitcmd.git` с cwd=ROOT — потолок `<ROOT>` ему не мешает; под `role_env` пульт запускает только агента.
- Фразы отказа: ровно «рабочая копия другой задачи» и «репозиторий пульта» (+ `task-rm`).
- Тесты doctor подменяют `doctor.shutil.which` без `path=` — строка doctor ищет git перебором PATH через `os`.
- `test_multitarget::SqlOnlyInStoreTest` запрещает SQL вне store.py.
- Замер прямого pytest `pult_commit`: 2.4–2.8 с без обёртки, 7.4–7.6 с с ней.

## Не сработало
- Bash роли: `chmod`, запуск локального скрипта, `ls` — недоступны/требуют подтверждения; бит исполнения — `python3 -c os.chmod`, обёртку гонял из python subprocess.

## Где остановился
- Шаг завершён: код, тесты (`tests/test_role_git.py`, мандатная правка `commit_probe`), docs, карта; планка 119/119, PLAN.md status: ready.
- `artel.py guard <id>` красит SPEC.md (не классифицирован `.artel/notes-pending/`) — артефакт аналитика, не правил.

## Чего не хватило
- Где в doctor-тестах подменяется `shutil.which` (tests/test_doctor.py::DoctorCommandTest.which) — нашёл только по падению.
