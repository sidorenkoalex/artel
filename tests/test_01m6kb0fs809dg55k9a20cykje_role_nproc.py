"""Предел числа процессов, который `runner.spawn_agent` ставит процессу шага роли.

Группа: долгоживущий
Красен до реализации: у `runner.spawn_agent` нет аргумента `nproc_limit` и нет `runner.role_nproc_limit` — вызовы падают TypeError/AttributeError.

Связка, которую держит файл: «`runner.spawn_agent` — настоящий дочерний
процесс ОС»: ребёнок сам читает свой `RLIMIT_NPROC` и сам упирается в
него на порождении (AC-1, AC-2).

Безопасность (требование 9 SPEC): ни один тест не порождает больше 100
процессов; каждое порождение — в своей группе (`spawn_agent`), с
пределом времени, и тест сам снимает группу (`os.killpg`) в завершении;
опыт с порождением (AC-2) идёт только под ограничением «текущее число
процессов пользователя + 10».

Провалидировано временным стабом реализации (`preexec_fn` с
`setrlimit`, `role_nproc_limit`; удалён, не закоммичен): все методы
зелёные.
"""
import os
import resource
import shutil
import signal
import subprocess
import sys

import pytest

from orchestrator import runner

CHILD_TIMEOUT_SEC = 60
SLEEP = shutil.which("sleep", path=os.pathsep.join(
    [os.environ.get("PATH", ""), "/bin", "/usr/bin"])) or "/bin/sleep"
PS = shutil.which("ps", path=os.pathsep.join(
    [os.environ.get("PATH", ""), "/bin", "/usr/bin"])) or "/bin/ps"


def kill_group(pgid: int) -> None:
    """Снимает группу `pgid` целиком; пустая или чужая группа — тихо."""
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def group_empty(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def user_process_count() -> int:
    """Число процессов пользователя теста — своим `ps`, не кодом пульта."""
    res = subprocess.run([PS, "-U", str(os.getuid()), "-o", "pid="],
                         capture_output=True, text=True, timeout=30)
    return len([line for line in res.stdout.splitlines() if line.strip()])


def spawn_and_collect(script: str, **kwargs) -> str:
    """Ребёнок `runner.spawn_agent` со сценарием `script`; его stdout."""
    proc = runner.spawn_agent([sys.executable, "-c", script],
                              stdout=subprocess.PIPE, text=True, **kwargs)
    try:
        out, _ = proc.communicate(timeout=CHILD_TIMEOUT_SEC)
    finally:
        kill_group(proc.pid)
        proc.wait(timeout=CHILD_TIMEOUT_SEC)
    return out


READ_LIMIT = ("import resource\n"
              "print(*resource.getrlimit(resource.RLIMIT_NPROC))\n")


def child_nproc(**kwargs) -> tuple:
    return tuple(int(v) for v in spawn_and_collect(READ_LIMIT, **kwargs).split())


def test_ac1_child_carries_role_limit_and_pult_keeps_own():
    """Ребёнок `spawn_agent(nproc_limit=role_nproc_limit())` несёт (N, N), пульт — прежние пределы.

    Сценарий: тест вычисляет N функцией `runner.role_nproc_limit()`,
    запускает через `runner.spawn_agent(..., nproc_limit=N)` ребёнка,
    который печатает свой `resource.getrlimit(RLIMIT_NPROC)`. Ребёнок
    видит мягкий и жёсткий пределы, равные N; N не выше конечных мягкого
    и жёсткого пределов процесса теста; пределы процесса теста после
    запуска те же, что до.

    Ловит мутацию: `preexec_fn` ставит только мягкий предел
    (`(N, hard)`) — ребёнок печатает прежний жёсткий предел вместо N;
    либо `setrlimit` исполняется в процессе пульта до `Popen`, а не в
    ребёнке — `getrlimit` теста после запуска равен (N, N), а не
    прежнему; либо min формулы забывает текущий мягкий предел пульта —
    N выше мягкого предела процесса теста.
    """
    before = resource.getrlimit(resource.RLIMIT_NPROC)
    limit = runner.role_nproc_limit()
    assert isinstance(limit, int) and limit > 0, limit

    child = child_nproc(nproc_limit=limit)

    assert child == (limit, limit), (child, limit)
    assert resource.getrlimit(resource.RLIMIT_NPROC) == before
    for own in before:
        if own != resource.RLIM_INFINITY:
            assert limit <= own, (limit, before)


def test_ac1_without_limit_child_inherits_pult_limits():
    """Ребёнок `spawn_agent` без `nproc_limit` несёт те же `RLIMIT_NPROC`, что процесс теста.

    Сценарий: тот же печатающий ребёнок, запущенный без аргумента
    `nproc_limit`, и сравнение с `resource.getrlimit` процесса теста.

    Ловит мутацию: `spawn_agent` ставит `preexec_fn` безусловно (зовёт
    `role_nproc_limit()` сам при отсутствии аргумента) — ребёнок без
    аргумента печатает (N, N) вместо пределов процесса теста.
    """
    own = resource.getrlimit(resource.RLIMIT_NPROC)
    limit = runner.role_nproc_limit()

    child = child_nproc()

    assert child == own, (child, own, limit)


RUNAWAY = """
import errno, subprocess
procs = []
result = "exhausted"
for _ in range(90):
    try:
        procs.append(subprocess.Popen([{sleep!r}, "20"]))
    except OSError as exc:
        result = "EAGAIN" if exc.errno == errno.EAGAIN else "errno %s" % exc.errno
        break
for proc in procs:
    proc.kill()
for proc in procs:
    proc.wait()
print(result, len(procs), flush=True)
"""


@pytest.mark.skipif(os.geteuid() == 0,
                    reason="RLIMIT_NPROC не действует на root — опыт не о чем")
def test_ac2_runaway_child_hits_eagain_and_pult_still_spawns():
    """Ребёнок под пределом «процессы пользователя + 10» получает EAGAIN до 90 порождений.

    Сценарий: тест считает процессы своего пользователя (`ps -U`),
    запускает через `runner.spawn_agent(nproc_limit=счёт + 10)` ребёнка,
    который пытается породить до 90 процессов `sleep` и печатает исход:
    `EAGAIN k` — отказ после k успешных порождений, `exhausted 90` —
    отказа не было. Ожидание: исход `EAGAIN`, k < 90 (ноль допустим);
    процесс теста, у которого предела нет, после этого запускает
    процесс; группа ребёнка пуста — все порождённые процессы завершились
    в пределах теста.

    Ловит мутацию: `spawn_agent` принимает `nproc_limit`, но не ставит
    `preexec_fn` (или ставит предел только на сам `exec`, не на ребёнка)
    — ребёнок порождает все 90 `sleep` и печатает `exhausted 90`; либо
    предел ставится процессу пульта — следующий запуск процесса тестом
    падает EAGAIN.
    """
    limit = user_process_count() + 10
    script = RUNAWAY.format(sleep=SLEEP)

    proc = runner.spawn_agent([sys.executable, "-c", script],
                              stdout=subprocess.PIPE, text=True,
                              nproc_limit=limit)
    try:
        out, _ = proc.communicate(timeout=CHILD_TIMEOUT_SEC)
        group_was_empty = group_empty(proc.pid)
    finally:
        kill_group(proc.pid)
        proc.wait(timeout=CHILD_TIMEOUT_SEC)

    outcome = out.split()
    assert outcome and outcome[0] == "EAGAIN", (out, limit)
    assert int(outcome[1]) < 90, (out, limit)
    after = subprocess.run([sys.executable, "-c", "pass"], timeout=CHILD_TIMEOUT_SEC)
    assert after.returncode == 0
    assert group_was_empty, "порождённые ребёнком процессы пережили его"
