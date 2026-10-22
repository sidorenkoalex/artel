# Записка spec_auditor

## Выяснено
- Факты SPEC о коде подтверждены: suite_run.py:771 cmd_suite_run, :774 _db, :775 resolve_task_id, :779 deliver_journal, :780 --wait, :792 --failed, :802 _running, :812 _acquire_lock, :819 _new_log, :826-827 снятие маркера, :829 Popen, :838 run.json; _read_failed :224; role_prompt.py:413 suite_run_note (вызов только :134, ветка developer); readonly_db :60/:155/:269/:377 и пять методов — строки верны.
- store.db() (store.py:387) пишет: mkdir, WAL, migrate — поэтому разрешение id для developer только прямым sqlite3 mode=ro (как _db:171).
- _running (:705) и suite_lock.holder (:142) только читают — проверку «уже идёт» можно ставить до deliver_journal.
- Песочницы tests/ (sandbox.py:663 isolate_keychain_and_role, SuiteRunStand :175) снимают ARTEL_ROLE — тесты «процесса Оператора» в шаге developer не покраснеют.
- docs/codebase-map.md в COMMON_ZONES (config.py:814).
- Смена ROLES не теряет утверждений — guard.weakened_helpers (:1999) её не видит.

## Где остановился
- SPEC-AUDIT.md записан: verdict concerns, status ready; guard ок.
- Отклонения: О1 — тест отказа developer под подменой БД только на чтение (SPEC тр. 8) без AC; О2 — deliver_journal в случае «уже идёт» не определён; О3 — у разрешения префикса в AC-1 нет наблюдаемого признака; О4 — позитивная часть AC-5 не проверяема.

## Чего не хватило
- Bash в рабочем каталоге требует абсолютных путей и не пропускает `$VAR` — проще `git grep` из `cd <wt> &&` и Read.
