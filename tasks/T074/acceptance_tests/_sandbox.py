"""Общая песочница приёмочных тестов T074 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из `test_ac*.py`, тот же
приём, что `tasks/T070/acceptance_tests/_sandbox.py`).

## Допущения интерфейса, которые вводит этот файл

SPEC (tasks/T074/SPEC.md) называет только внешнюю форму команды
(`pause --now <id>`) и природу данных, через которые идёт адресация
(«данные lease задачи (pid, host)», требование 2 / AC-6), не имя модуля
или функции. По прецеденту `tasks/T070/acceptance_tests/_sandbox.py`
(SPEC T070 тоже не фиксировала имя `orchestrator/pause.py`) здесь принято:

- Новая функция `orchestrator.pause.cmd_pause_now(task_id: str) -> None`
  — рядом с уже существующими `cmd_pause`/`cmd_resume` (тот же модуль:
  Материалы SPEC T074 не называют новый модуль, а сама операция —
  надмножество обычной `pause`, требование 1: «ставит обычную пометку
  паузы задачи (как pause, T070)»).
- `cmd_pause_now` читает `store.lease_row(conn, task_id)` — единственный
  источник (pid, hostname), который называют и SPEC («данные lease»,
  Материалы: `orchestrator/lease.py`), и код (`lease.acquire` пишет туда
  `os.getpid()`/`socket.gethostname()` вызывающей CLI-сессии). Тест не
  проверяет, что записано в pid ЭТОЙ сессией `run`/`auto` по-настоящему
  (это делает `lease.acquire`, не эта задача) — только то, что
  `cmd_pause_now` адресуется РОВНО по этому полю: тест сам кладёт в
  таблицу `leases` управляемый pid реального (тестового) процесса и
  проверяет, что именно ЕГО не стало.
- Прерывание — сигналом ОС по этому pid (`os.kill`/эквивалент), не через
  `waitpid` (у `pause --now` нет права ждать чужого потомка — pid,
  записанный в lease, принадлежит ДРУГОМУ процессу той же машины,
  требование 2). Тест проверяет результат («процесса с этим pid больше
  нет» — тем же приёмом, что `tests/test_doctor.py::dead_pid`), не способ
  доставки сигнала.
- Чекпоинт WIP, снятие lease, учёт частичной стоимости и вся
  журнальная последовательность (требование 1, AC-3..AC-5, AC-10) —
  действие САМОЙ команды `pause --now` (её процесса), а не работа,
  которую позже заметит прерванный процесс: тот уже мёртв к моменту,
  когда `pause --now` продолжает свою последовательность (симметрично
  тому, что уже пишет `commit_timeout_checkpoint`, T041 — коммитит
  оркестратор, не роль). Стоимость шага (AC-10, требование 4) читается
  из СУЩЕСТВУЮЩЕГО на диске stream-json лога шага (`agent_log.
  last_agent_log`/`spend.stream_usage_tokens`, механика T040) — SPEC
  сам называет источник («из stream-json лога шага»), не только его
  механику начисления.
- Пометка причины чекпоинта — подстрока `pause --now` в тексте коммита
  и/или журнала (AC-3, «пометка причины «pause --now»» — SPEC называет
  сам текст пометки буквально).

Прогон ДО реализации падает `AttributeError: module 'orchestrator.pause'
has no attribute 'cmd_pause_now'` (модуль `orchestrator/pause.py` уже
существует с T070, атрибута `cmd_pause_now` в нём ещё нет) — ожидаемо
(skills/test-authoring: «падать на отсутствующей пока реализации —
нормально»), не брак теста.

## Песочница

Часть критериев (AC-3, AC-9, AC-10, AC-11, AC-13, AC-14) требует
НАСТОЯЩЕГО git worktree задачи — заглушкой `gitcmd.git` чекпоинт не
проверить (тот же довод, что в `tasks/T041/acceptance_tests/
test_checkpoint_after_timeout.py`). `InterruptSandbox` — расширение
`tests.test_git_fixation.RealPultGitTest` (реальный git, реальный
worktree, `cmd_run`/`fsm` без заглушек кроме самого агента) утилитами,
специфичными для сценария `pause --now`: реальный дочерний процесс вместо
записи в lease, чтение/запись лога шага, срез журнала.
"""
import io
import shutil
import socket
import subprocess
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (agent_log, config, fixation, fsm, pause,  # noqa: E402
                          runner, spend, store, workspace)
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

__all__ = ["pause", "config", "fixation", "fsm", "runner", "spend", "store",
          "workspace", "agent_log", "socket", "InterruptSandbox", "invoke"]


def invoke(call) -> tuple:
    """(стдаут, код выхода). Отказ команды пульта уходит `sys.exit`
    (`orchestrator/runner.py::_cmd_run`, отказ по паузе) — тот же приём,
    что `tasks/T070/acceptance_tests/_sandbox.py::invoke`."""
    buf = io.StringIO()
    code = None
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        code = exc.code
    return buf.getvalue(), code


class InterruptSandbox(RealPultGitTest):
    """`RealPultGitTest` (T001, git настоящий, worktree настоящий) +
    утилиты сценария «шаг бежит в другом процессе той же машины»."""

    OTHER_SESSION = "other-cli-session"

    def spawn_sleep_process(self) -> subprocess.Popen:
        """Реальный дочерний процесс, живущий достаточно долго, чтобы
        `pause --now` успел его найти и прервать; `SIGTERM` без
        собственного обработчика завершает процесс Python сразу же
        (никакой особой обработки не требуется, чтобы проверить факт
        прерывания)."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self._reap, proc)
        return proc

    @staticmethod
    def _reap(proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            proc.kill()
        proc.wait()

    @staticmethod
    def dead_pid() -> int:
        """pid реального процесса, уже завершённого и убранного —
        тот же приём, что `tests/test_doctor.py::dead_pid`."""
        proc = subprocess.Popen([sys.executable, "-c", "pass"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        proc.wait()
        return proc.pid

    def install_lease(self, pid: int, hostname: str | None = None,
                      session_id: str | None = None) -> None:
        """Кладёт строку `leases` НАПРЯМУЮ (не через `lease.acquire`):
        приёмочный тест не про то, кто взял lease, а про то, что
        `pause --now` адресуется РОВНО по её (pid, hostname) — требование
        2 / AC-6."""
        conn = store.db()
        store.insert_lease(conn, self.TASK, session_id or self.OTHER_SESSION,
                           pid, hostname or socket.gethostname(), store.now())

    def lease_row(self):
        return store.lease_row(store.db(), self.TASK)

    def write_dirty_wip(self, name: str = "wip_from_agent.md") -> Path:
        """Незакоммиченный файл — то, что оставляет бегущий шаг в
        рабочем дереве worktree задачи (тот же приём и адрес, что
        `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py::
        write_wip`)."""
        path = workspace.path(self.TASK) / "tasks" / self.TASK / name
        path.write_text("работа агента, ещё не закоммичена\n",
                        encoding="utf-8")
        return path

    def write_step_log(self, role: str, lines: list) -> Path:
        """Stream-json лог текущего шага — источник частичной стоимости
        прерванного шага (AC-10, требование 4: «из stream-json лога
        шага»); имя файла — соглашение `agent_log.new_agent_log`."""
        path = agent_log.new_agent_log(self.TASK, role)
        path.write_text("".join(lines), encoding="utf-8")
        return path

    def journal(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def journal_text(self) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in self.journal())

    def orchestrator_journal(self) -> list:
        return [r for r in self.journal() if r["actor"] == "orchestrator"]

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def unknown_cost_alerts(self) -> list:
        return store.db().execute(
            "SELECT * FROM alerts WHERE kind='incident' AND "
            "source LIKE 'spend.unknown_cost%'").fetchall()
