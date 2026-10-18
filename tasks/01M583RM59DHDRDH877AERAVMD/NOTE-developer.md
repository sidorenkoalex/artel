## Выяснено
- Правка: `orchestrator/canary.py` — класс `_SignalDeferral` (обработчик-функция на SIGTERM/SIGHUP/SIGINT, кроме уже `SIG_IGN`/None; вне главного потока не ставится); в `_drive_in_clone` `release()` зовётся в обеих ветках исключения `Popen` и первой строкой защищённого `try`.
- Тест: `_CHILD` пишет `alive_before_signal`, `launch_signalled` проверяет его перед `os.kill` (AC-12, мандат ANSWER-2).
- ANSWER-3: линт `reap_observed` закрыт Оператором через `amend-tests` (ffe7c593, `sandbox.wait_processes_gone`).
## Не сработало
- `ls`/`cat` в шелле шага нет — `git ls-files`/python.
## Где остановился
- После ANSWER-3: затронутые модули 34 passed; `suite-run --failed` №2 зелёный (1/0). PLAN.md — status: ready, раздел эскалации заменён «Итогом эскалации». Код задачи не трогался.
## Чего не хватило
- —
