# Записка spec_auditor

## Выяснено
- Визит 5 (spec_sha bfdc09b5): после №4.1 SPEC — только две строки doctor (треб. 14, 15), AC-1 — role_env побайтно прежний.
- Якоря верны: doctor/cli.py:221-224 (+226 check_orphans), :305-331; __init__.py:152-155; lease.py:399-416; acceptance.py:156; test_doctor_closed_ref_fix.py:152-195 (без песочницы, store.db→None); test_doctor.py:1040-1043.
- role_env (runner.py:1246-1361) не зависит от раннера; gitcmd._project_entry глотает TargetsError — AC-1 зелёный с рождения.
- Все прочие тесты cmd_doctor(fix=True)/all_checks — в песочнице без compose → skip, не ломаются.
- Опыт: os.getpgid(pid завершившегося дочернего) → ProcessLookupError.
- Вердикт concerns: Д1 getpgid по записанному pid неисполним для завершённых вызовов; Д2 по пределу снимается pid, не группа (дополнение compose — внук), предел down 10 с против 10 с stop grace; Д3 подключение строк в all_checks/cmd_doctor не покрыто AC; Д4 мелочи (docker не найден, machine.path, зависание network ls); Д5 hostname в process_alive.

## Не сработало
- docker/sh в шаге: `sh` нет в PATH шага — нужен /bin/sh; cd вне рабочих каталогов запрещён.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns), guard прогнан.

## Чего не хватило
- Опыта с Docker CLI (дочерний процесс дополнения, context inspect --format).
