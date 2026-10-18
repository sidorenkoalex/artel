## Выяснено
- Места SPEC о коде сверены: canary.py:2333-2335 Popen, :2336 OSError, :2338 wait, :2344-2350 except BaseException, :2731/:2737/:2744, :2806-2819 запись «оборвана сигналом» + SystemExit(128+n); уборка suite canary.py:1236-1244; suite_run.py:801-812.
- runner.py:92 — роли стартуют в своей сессии, т.е. команда suite-run (зовёт роль) не в группе ведения: описание механизма окна suite-run в SPEC неточно (вне зон, ANSWER-1).
- artel.py:1597 `_detach_canary` — это запуск самой канарейки, SPEC пишет «не процессы канарейки».
- tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py:22-36 зовёт `_drive_in_clone` напрямую с фейковым Popen без `pid` и вне `_interrupt_on_signal` — в матрице SPEC нет.
- Пробелы способа: отложенный сигнал при OSError/исключении Popen (код 127 «как сейчас» его теряет); SIG_IGN обработчика (canary.py:2742) до fork наследуется ведением.
## Где остановился
Вердикт concerns, SPEC-AUDIT.md записан.
## Чего не хватило
—
