"""Снятие оставшейся группы процессов шага после обычного исхода.

Группа: разовый
Красен до реализации: группа шага после обычного исхода не снимается — оставленный ролью процесс жив, перекачка ждёт его до предела `PUMP_JOIN_TIMEOUT_SEC` и пишет «agent log INCOMPLETE», записи о снятии группы нет.

Файл разовый не по предмету, а по песочнице: шаг идёт через
`runner.cmd_run` в `_step.step_sandbox` с git-заглушкой
(`gitcmd.git`), а долгоживущим файлам `tests/` обращение к `gitcmd`
запрещено.

Связка: «`runner.cmd_run` — настоящий процесс агента — журнал шага».
`runner.spawn_agent` подменён обёрткой, которая зовёт НАСТОЯЩИЙ
`spawn_agent` с теми же аргументами (в том числе `nproc_limit`), но с
командой-сценарием на `python` вместо CLI роли.

Безопасность (решение Оператора, возврат 4, п. 5): оставленный ролью
процесс — `sleep 30`, живёт не дольше 30 с; тест сам снимает группу
агента (`os.killpg`) и оставленный процесс в завершении, в том числе в
красной фазе.

Провалидировано временным стабом реализации (снятие группы до
`close_pump` с записью `group_kill_detail` при непустой группе; удалён,
не закоммичен): оба метода зелёные.
"""
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _step import journal, journal_text, step_sandbox  # noqa: E402
from orchestrator import config, liveness, runner  # noqa: E402

SLEEP = shutil.which("sleep", path=os.pathsep.join(
    [os.environ.get("PATH", ""), "/bin", "/usr/bin"])) or "/bin/sleep"
PS = shutil.which("ps", path=os.pathsep.join(
    [os.environ.get("PATH", ""), "/bin", "/usr/bin"])) or "/bin/ps"

LEAVES_PROCESS = """
import subprocess
leftover = subprocess.Popen([{sleep!r}, "30"])
open({pidfile!r}, "w").write(str(leftover.pid))
print("шаг роли: оставил процесс", flush=True)
"""

LEAVES_NOTHING = """
print("шаг роли: ничего не оставил", flush=True)
"""


def kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def alive(pid: int) -> bool:
    """Процесс жив и не зомби (зомби без родителя-жнеца — уже не процесс шага)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    res = subprocess.run([PS, "-o", "stat=", "-p", str(pid)],
                         capture_output=True, text=True, timeout=10)
    stat = res.stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def run_step_with_agent(box, task: str, script: str) -> tuple:
    """`runner.cmd_run` с настоящим процессом агента; (pid агентов, секунды)."""
    real_spawn = runner.spawn_agent
    pids = []

    def spawn(cmd, **kwargs):
        # git-заглушка песочницы не выписывает рабочую копию — каталог
        # роли для настоящего процесса заводится здесь же.
        Path(kwargs["cwd"]).mkdir(parents=True, exist_ok=True)
        proc = real_spawn([sys.executable, "-c", script], **kwargs)
        pids.append(proc.pid)
        return proc

    started = time.monotonic()
    try:
        with mock.patch.object(runner, "spawn_agent", spawn):
            box.capture(runner.cmd_run, task)
    finally:
        for pid in pids:
            kill_group(pid)
    return pids, time.monotonic() - started


def group_rows(rows, pgid: int, counts) -> list:
    marks = [liveness.group_kill_detail(pgid, n) for n in counts]
    return [row for row in rows
            if any(mark in (row["detail"] or "") for mark in marks)]


def test_ac6_leftover_process_removed_after_ordinary_step():
    """Процесс, оставленный ролью в группе шага, снят после обычного исхода, запись о снятии есть.

    Сценарий: агент шага — настоящий процесс (`python`), который
    запускает `sleep 30` в своей группе (тот держит stdout агента —
    пайп перекачки), пишет его pid в файл и выходит с rc=0. Предел
    ожидания перекачки поднят до 15 с, чтобы его исчерпание отличалось от
    штатного завершения. После `runner.cmd_run`: оставленный процесс не
    жив; в журнале задачи есть запись с текстом
    `liveness.group_kill_detail` для pgid агента; шаг вернулся быстрее
    предела ожидания перекачки и без записи «agent log INCOMPLETE»;
    запись «agent run finished» есть.

    Ловит мутацию: снятие группы стоит ПОСЛЕ `close_pump` (или только в
    ветке таймаута) — перекачка ждёт все 15 с, в журнале «agent log
    INCOMPLETE», а `sleep` переживает шаг; либо снятие есть, но запись в
    журнал о нём не делается — записи `group_kill_detail` нет.
    """
    join_limit = 15
    with step_sandbox() as (box, task):
        pidfile = box.root / "leftover.pid"
        script = LEAVES_PROCESS.format(sleep=SLEEP, pidfile=str(pidfile))
        with mock.patch.object(config, "PUMP_JOIN_TIMEOUT_SEC", join_limit):
            pids, elapsed = run_step_with_agent(box, task, script)
        rows = journal(task)
        leftover = int(pidfile.read_text(encoding="utf-8")) \
            if pidfile.exists() else None
    try:
        note = f"pid агента {pids}, {elapsed:.1f} с\n{journal_text(rows)}"
        assert len(pids) == 1 and leftover is not None, note
        actions = [row["action"] for row in rows]
        assert "agent run finished" in actions, note
        assert "agent log INCOMPLETE" not in actions, note
        assert elapsed < join_limit, note
        assert not alive(leftover), f"оставленный ролью процесс {leftover} жив\n{note}"
        assert group_rows(rows, pids[0], range(1, 100)), note
    finally:
        if leftover is not None:
            try:
                os.kill(leftover, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def test_ac6_no_record_when_group_is_empty():
    """Агент ничего не оставил в группе — записи о снятии группы в журнале нет.

    Сценарий: агент шага — настоящий процесс, который печатает строку и
    выходит с rc=0, не порождая потомков. После `runner.cmd_run`: шаг
    завершён («agent run finished»), записи с текстом
    `liveness.group_kill_detail` для pgid агента нет.

    Ловит мутацию: запись о снятии пишется безусловно после каждого
    шага (число снятых 0 или выдуманная единица `max(count, 1)`) — в
    журнале появляется «группа процессов (pgid=…) снята».
    """
    with step_sandbox() as (box, task):
        pids, _ = run_step_with_agent(box, task, LEAVES_NOTHING)
        rows = journal(task)
    note = f"pid агента {pids}\n{journal_text(rows)}"
    assert len(pids) == 1, note
    assert "agent run finished" in [row["action"] for row in rows], note
    assert not group_rows(rows, pids[0], range(0, 100)), note
