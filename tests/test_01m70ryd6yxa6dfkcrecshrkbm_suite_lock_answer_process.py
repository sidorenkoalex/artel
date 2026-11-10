"""Команда `suite-lock` настоящим процессом по ANSWER-1: `SIGINT` самой
команды (п. 2) и успех по явному `--limit`, равному границе подменённых
констант (п. 3).

Группа: долгоживущий
Красен до реализации: модуля `orchestrator/suite_hold.py` на базе ещё нет — процесс `suite-lock` падает на импорте с трассой, команда под замком не запускается.

Процесс `suite-lock` — дочерний `sys.executable -c`, который переназначает
`config.LOGS` на временный каталог теста (и, где нужно, константы предела)
и зовёт `suite_hold.cmd_suite_lock`; настоящий замок машины главной копии
тесты не читают и не меняют. Команда под замком — настоящий короткий
процесс Python. Каждый процесс теста — в своей группе
(`start_new_session=True`), уборка теста снимает группы `os.killpg`.
"""
import contextlib
import os
import random
import signal
import string
import subprocess
import sys
import time
from pathlib import Path

import pytest

from orchestrator import config, suite_lock

pytestmark = pytest.mark.size("large")

REPO = Path(__file__).resolve().parents[1]
LETTERS = string.ascii_letters + string.digits + "абвгдеёжзийклмнопрстуфхцчшщэюя"
# Страховка от зависания процесса теста — не условие проверки.
SAFETY_SEC = 40
# Срок остановки из ANSWER-1 п. 2 (та же форма, что AC-6).
STOP_WITHIN_SEC = 15

# argv: каталог логов, ожидание замка, предел полного прогона, аргументы.
SUITE_LOCK = (
    "import sys\n"
    "from pathlib import Path\n"
    "from orchestrator import config, suite_hold\n"
    "config.LOGS = Path(sys.argv[1])\n"
    "if sys.argv[2]:\n"
    "    config.FULL_SUITE_LOCK_WAIT_SEC = int(sys.argv[2])\n"
    "    config.FULL_SUITE_TIMEOUT_SEC = int(sys.argv[3])\n"
    "sys.exit(suite_hold.cmd_suite_lock(sys.argv[4:]))\n")

WITH_CHILD = (
    "import os, subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c',"
    " 'import time; time.sleep(30)'])\n"
    "print('READY', os.getpid(), child.pid, flush=True)\n"
    "time.sleep(30)\n")

# Команда под замком: создаёт файл-след и выходит с кодом.
TOUCH = ("import sys\nopen(sys.argv[1], 'w').close()\n"
         "sys.exit(int(sys.argv[2]))\n")


def seeded() -> tuple[int, random.Random]:
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def phrase(rng: random.Random) -> str:
    return " ".join("".join(rng.choice(LETTERS)
                            for _ in range(rng.randint(1, 8)))
                    for _ in range(rng.randint(1, 4)))


def kill_group(pgid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, signal.SIGKILL)


def kill_pid(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.kill(pid, signal.SIGKILL)


def gone(pid: int) -> bool:
    """Процесса нет либо он уже зомби (завершён, не забран родителем)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                          capture_output=True, text=True, timeout=10,
                          start_new_session=True).stdout.strip()
    return stat == "" or stat.startswith("Z")


@pytest.fixture
def logs(tmp_path, monkeypatch):
    """`config.LOGS` — временный каталог теста (в нём же замок)."""
    path = tmp_path / "logs"
    path.mkdir()
    monkeypatch.setattr(config, "LOGS", path)
    return path


@pytest.fixture
def spawned():
    groups, pids = [], []
    yield groups, pids
    for pid in pids:
        kill_pid(pid)
    for pgid in groups:
        kill_group(pgid)


def start(logs: Path, argv: list, groups: list,
          constants: tuple[str, str] = ("", "")) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(REPO), env.get("PYTHONPATH", "")) if p)
    proc = subprocess.Popen(
        [sys.executable, "-c", SUITE_LOCK, str(logs), *constants, *argv],
        cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, start_new_session=True)
    groups.append(proc.pid)
    return proc


def finish(proc: subprocess.Popen, head: str = "") -> tuple[int | None, str]:
    try:
        rest, _ = proc.communicate(timeout=SAFETY_SEC)
    except subprocess.TimeoutExpired:
        kill_group(proc.pid)
        rest, _ = proc.communicate()
    return proc.returncode, head + (rest or "")


def wait_ready(proc: subprocess.Popen, pids: list) -> tuple[list, str]:
    """Читает вывод до строки `READY <pid команды> <pid её потомка>`;
    `[]` — вывод кончился раньше. Чтение блокирующее, без опроса."""
    seen = ""
    while True:
        line = proc.stdout.readline()
        if not line:
            return [], seen
        seen += line
        if line.startswith("READY "):
            found = [int(x) for x in line.split()[1:3]]
            pids.extend(found)
            return found, seen


def test_sigint_stops_group_releases_lock_code_130(logs, spawned):
    """`SIGINT` процессу `suite-lock` во время команды с потомком: оба остановлены не позже 15 с, замка нет, код 130.

    Сценарий: `suite-lock --reason <основание> -- python <породить
    потомка, напечатать READY с обоими pid, спать 30 с>`; по строке READY
    тест шлёт `SIGINT` процессу `suite-lock` (не группе). Затем: с запуска
    прошло не больше 15 с, команды и её потомка нет (или они зомби), файла
    замка нет, код выхода 130.

    Ловит мутацию: перехвачен только `SIGTERM` — по `SIGINT` `suite-lock`
    падает `KeyboardInterrupt` мимо остановки группы (команда и потомок
    живы, код 1) либо умирает по сигналу с замком на диске; код выхода —
    не `128 + 2`.
    """
    seed, rng = seeded()
    groups, pids = spawned
    argv = ["--reason", phrase(rng), "--", sys.executable, "-c", WITH_CHILD]

    started = time.monotonic()
    proc = start(logs, argv, groups)
    found, head = wait_ready(proc, pids)
    groups.extend(found[:1])
    if found:
        os.kill(proc.pid, signal.SIGINT)
    status, out = finish(proc, head)
    elapsed = time.monotonic() - started

    where = (f"зерно {seed}: код {status}, прошло {elapsed:.1f} с, "
             f"вывод:\n{out[-2000:]}")
    assert len(found) == 2, where
    assert elapsed <= STOP_WITHIN_SEC, where
    assert all(gone(pid) for pid in found), f"{where}\nживы: {found}"
    assert not suite_lock.path().exists(), where
    assert status == 130, where


def test_explicit_limit_at_bound_runs_command(logs, spawned, tmp_path):
    """`--limit`, равный разности подменённых в процессе `suite-lock` констант, — команда запущена, код выхода — её код, замка после выхода нет.

    Сценарий: в дочернем процессе `suite-lock` подменены
    `config.FULL_SUITE_LOCK_WAIT_SEC` и `config.FULL_SUITE_TIMEOUT_SEC`
    случайными значениями (разность ≠ 900); `--limit <их разность> --
    python <создать файл-след, выйти со случайным кодом>`. Файл-след есть,
    код выхода — код команды, файла замка нет, в выводе нет трассы.

    Ловит мутацию: команда сверяет `--limit` своим сравнением,
    расходящимся с `suite_hold.refusal` — строгим `<` вместо `<=` или
    литералом 900 вместо констант в момент вызова: граница отклоняется,
    команда не запускается.
    """
    seed, rng = seeded()
    groups, _pids = spawned
    timeout = rng.randint(50, 500)
    wait = timeout + rng.choice([d for d in range(5, 2000) if d != 900])
    bound = wait - timeout
    code = rng.randint(0, 9)
    trace = tmp_path / "trace"
    argv = ["--reason", phrase(rng), "--limit", str(bound), "--",
            sys.executable, "-c", TOUCH, str(trace), str(code)]

    proc = start(logs, argv, groups, (str(wait), str(timeout)))
    status, out = finish(proc)

    where = (f"зерно {seed}: граница {bound}, код {status}, "
             f"вывод:\n{out[-2000:]}")
    assert trace.exists(), where
    assert status == code, where
    assert not suite_lock.path().exists(), where
    assert "Traceback" not in out, where
