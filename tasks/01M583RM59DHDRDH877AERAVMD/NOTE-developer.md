## Выяснено
- Правка: `orchestrator/canary.py` — класс `_SignalDeferral` (обработчик-функция на SIGTERM/SIGHUP/SIGINT, кроме уже `SIG_IGN`/None; вне главного потока не ставится); в `_drive_in_clone` `release()` зовётся в обеих ветках исключения `Popen` и первой строкой защищённого `try` — отложенный сигнал поднимается `signal.raise_signal` прежним обработчиком.
- Тест: `_CHILD` пишет `alive_before_signal` (poll suite/ведения), `launch_signalled` проверяет его и `self.alive(...)` перед `os.kill(child.pid, …)` (AC-12, мандат ANSWER-2).
- Затронутые модули 34 passed; plank-run 5 passed.
## Не сработало
- `ls` в шелле шага нет — `git ls-files`/python.
## Где остановился
- suite-run №1: 5885 passed, 1 failed — линт `test_invariants.py::DeterministicTestsLintTest::test_tests_tree_has_no_wall_clock_waits_or_live_file_reads` ругается на `reap_observed` долгоживущего файла test_author (цикл по time.monotonic + sleep). Файл залочен, `_EXCEPTIONS` в защищённом пути — PLAN.md status: escalate (дефолт: запись в `_EXCEPTIONS` по образцу `CanaryLifecycleTest::launch_signalled`, :2183). Код задачи после ответа не трогать — только `suite-run --failed`, снять escalate → ready.
## Чего не хватило
- —
