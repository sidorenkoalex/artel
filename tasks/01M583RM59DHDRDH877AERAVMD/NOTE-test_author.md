## Выяснено
- Долгоживущий tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py — AC-1..5, AC-8, AC-11: дочерний процесс `artel.py canary`, подменённый Popen шлёт os.kill себе в точке окна; ведение сообщает свои SIGTERM/SIGHUP через pipe (pass_fds), ожидания по времени нет.
- Разовый acceptance_tests/test_existing_and_base.py — AC-6, 7 (AST-сверка методов с DIFF_BASE + прогон pytest), AC-9/10 (git archive DIFF_BASE orchestrator tests scripts → прогон AC-1 раннего окна, pgid из строк «наблюдение: {...}»), AC-12 (у CanaryLifecycleTest подменяется `_CHILD`: time.sleep(N)→sleep(0) + ожидание процесса; ac1–ac3 обязаны упасть).
- На базе: красны AC-1, 2, 3 (ведение живо / не создано), AC-9 (HEAD), AC-12 (ac1/ac2 зелёные с коротким ведением). Стаб (откладывающий обработчик вокруг Popen + `assertTrue(alive…)` перед os.kill в launch_signalled) — всё зелёное; стаб откачен.
- `ps` нет в PATH шага — берём через shutil.which с /bin:/usr/bin.
## Не сработало
- ls/cat в шелле шага недоступны — python3/git работают.
## Где остановился
- Готово: preflight пройдена, plank-run на базе: 3 failed / 4 passed по ожиданию.
## Чего не хватило
- —
