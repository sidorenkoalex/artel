"""Тестовый стаб дерева процессов роли (не `test_*.py`, не участвует в
`unittest discover`) — по образцу `spawn_sleep_process` (`tests/
test_pause_now.py`) и `InterruptSandbox.spawn_sleep_process` (`tasks/
T074/acceptance_tests/_sandbox.py`), расширенному ещё на один уровень
дерева (внук процесса): SPEC этой задачи требует, чтобы group-kill снимал
ДЕРЕВО целиком, не только непосредственного потомка агентного шага —
одноуровневый стаб T074 этого не различил бы.

argv: <marker_path> [role]
  role — "leader" (по умолчанию): спавнит собственную копию с role=
  "child" (реальный внук, без `start_new_session` — наследует группу
  процессов лидера, как и настоящий `pytest`/`unittest`, запущенный
  инструментом Bash агента) и АТОМАРНО пишет `marker_path` JSON'ом
  `{"leader": pid, "child": pid}` — тесты ждут появления файла, чтобы
  узнать оба pid до того, как начнут действовать; "child" — просто ждёт
  сигнала.

Оба уровня ставят обработчик `SIGTERM`, который перед выходом создаёт
файл `<marker_path>.sigterm.<pid>` — наблюдаемое доказательство того,
что группа реально получила `SIGTERM` (а не только грубый `SIGKILL` без
грейса), прежде чем завершиться. Без своего обработчика `SIGTERM` тоже
завершил бы процесс (это default action) — маркер нужен именно чтобы
ОТЛИЧИТЬ «получил SIGTERM и штатно вышел» от «выжил после SIGTERM и был
убит только последующим SIGKILL».
"""
import json
import os
import signal
import subprocess
import sys
import time


def _install_sigterm_marker(marker_path: str) -> None:
    def handler(signum, frame):
        try:
            with open(f"{marker_path}.sigterm.{os.getpid()}", "w",
                     encoding="utf-8") as fh:
                fh.write("1")
        except OSError:
            pass
        sys.exit(0)
    signal.signal(signal.SIGTERM, handler)


def main() -> None:
    marker_path = sys.argv[1]
    role = sys.argv[2] if len(sys.argv) > 2 else "leader"
    _install_sigterm_marker(marker_path)
    if role == "leader":
        child = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), marker_path, "child"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(marker_path, "w", encoding="utf-8") as fh:
            json.dump({"leader": os.getpid(), "child": child.pid}, fh)
    time.sleep(120)


if __name__ == "__main__":
    main()
