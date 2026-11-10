"""Команда `suite-lock` настоящим процессом: держатель замка, код выхода
команды, отказ на занятом замке, предел, `SIGTERM`, ошибка запуска, отказы
разбора до взятия замка и ожидание гейта на внешнем держателе.

Группа: долгоживущий
Красен до реализации: модуля `orchestrator/suite_hold.py` ещё нет — процесс `suite-lock` падает на импорте с трассой, команда под замком не запускается, а `suite_lock.describe` держателя вида `внешний` даёт текст `suite-run` (AC-8).

Процесс `suite-lock` — дочерний `sys.executable -c`, который переназначает
`config.LOGS` на временный каталог теста и зовёт
`suite_hold.cmd_suite_lock`; настоящий замок машины главной копии тесты не
читают и не меняют. Команда под замком — настоящий короткий процесс
Python. Каждый процесс теста — в своей группе (`start_new_session=True`),
по пределу времени группа снимается `os.killpg`; процессы, о которых
команда сообщила строкой `READY`, снимаются уборкой теста.
"""
import contextlib
import json
import os
import random
import signal
import string
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import acceptance, config, suite_lock

pytestmark = pytest.mark.size("large")

REPO = Path(__file__).resolve().parents[1]
EXTERNAL = "внешний"
LETTERS = string.ascii_letters + string.digits + "абвгдеёжзийклмнопрстуфхцчшщэюя"
ID_LETTERS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
# Страховка от зависания процесса теста — не условие проверки.
SAFETY_SEC = 40
# Срок остановки из критериев AC-4 и AC-6.
STOP_WITHIN_SEC = 15

SUITE_LOCK = (
    "import sys\n"
    "from pathlib import Path\n"
    "from orchestrator import config, suite_hold\n"
    "config.LOGS = Path(sys.argv[1])\n"
    "sys.exit(suite_hold.cmd_suite_lock(sys.argv[2:]))\n")

# Команда под замком: копирует запись замка в файл-след и выходит с кодом.
COPY_LOCK = (
    "import sys\n"
    "from pathlib import Path\n"
    "lock, trace, code = sys.argv[1:4]\n"
    "Path(trace).write_text(Path(lock).read_text(encoding='utf-8'),"
    " encoding='utf-8')\n"
    "sys.exit(int(code))\n")

# Команда под замком: порождает дочерний процесс, сообщает оба pid строкой
# READY и спит 30 с.
WITH_CHILD = (
    "import os, subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c',"
    " 'import time; time.sleep(30)'])\n"
    "print('READY', os.getpid(), child.pid, flush=True)\n"
    "time.sleep(30)\n")

# Команда под замком: создаёт файл-след.
TOUCH = "import sys\nopen(sys.argv[1], 'w').close()\n"


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
    """Список pid, которые уборка теста снимает по `SIGKILL` (группы и
    процессы)."""
    groups, pids = [], []
    yield groups, pids
    for pid in pids:
        kill_pid(pid)
    for pgid in groups:
        kill_group(pgid)


def start(logs: Path, argv: list, groups: list) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(REPO), env.get("PYTHONPATH", "")) if p)
    proc = subprocess.Popen(
        [sys.executable, "-c", SUITE_LOCK, str(logs), *argv], cwd=REPO,
        env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, start_new_session=True)
    groups.append(proc.pid)
    return proc


def finish(proc: subprocess.Popen, head: str = "") -> tuple[int | None, str]:
    """Код выхода и весь вывод (stdout и stderr) процесса `suite-lock`."""
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


def run(logs: Path, argv: list, groups: list) -> tuple[int | None, str, int]:
    proc = start(logs, argv, groups)
    code, out = finish(proc)
    return code, out, proc.pid


def describe_case(seed: int, code, out: str) -> str:
    return f"зерно {seed}: код {code}, вывод:\n{out[-2000:]}"


# --------------------------------------------------------------- AC-1

@pytest.mark.parametrize("code", [0, 3])
def test_ac1_lock_held_by_suite_lock_pid_and_code_passed_through(
        logs, spawned, tmp_path, code):
    """Во время команды замок за pid процесса `suite-lock` с видом `внешний` и основанием; после — замка нет, код выхода — код команды.

    Сценарий: свободный замок; `suite-lock --reason <случайное основание>
    -- python <копировать запись замка в файл-след и выйти с кодом>` —
    код 0 и код 3 отдельными случаями. Запись, прочитанная командой:
    `pid` — pid процесса `suite-lock`, `kind` — `внешний`, `task_id` и
    `run` — `null`, `reason` — основание. После завершения файла замка
    нет, код выхода `suite-lock` равен коду команды.

    Ловит мутацию: замок берётся с видом по умолчанию (`kind` нет —
    держатель читается как `suite-run`); держателем записан pid команды, а
    не `suite-lock`; основание не пишется; замок не снимается после
    команды; код выхода `suite-lock` — всегда 0 или 1 вместо кода команды.
    """
    seed, rng = seeded()
    groups, _pids = spawned
    reason = phrase(rng)
    trace = tmp_path / "trace.json"
    argv = ["--reason", reason, "--", sys.executable, "-c", COPY_LOCK,
            str(suite_lock.path()), str(trace), str(code)]

    status, out, pid = run(logs, argv, groups)

    where = describe_case(seed, status, out)
    assert trace.exists(), where
    record = json.loads(trace.read_text(encoding="utf-8"))
    assert record.get("pid") == pid, f"{where}\nзапись {record}"
    assert record.get("kind") == EXTERNAL, f"{where}\nзапись {record}"
    assert "task_id" in record and record["task_id"] is None, record
    assert "run" in record and record["run"] is None, record
    assert record.get("reason") == reason, f"{where}\nзапись {record}"
    assert not suite_lock.path().exists(), where
    assert status == code, where
    assert "Traceback" not in out, where


# --------------------------------------------------------------- AC-2

@pytest.mark.parametrize("kind", ["suite-run", "гейт", "notes", EXTERNAL])
def test_ac2_busy_lock_refused_naming_holder_lock_untouched(
        logs, spawned, tmp_path, kind):
    """Замок за живым чужим процессом — отказ с `suite_lock.describe` держателя, команда не запускалась, запись замка побайтно та же.

    Сценарий: файл замка вида `kind` за процессом теста (живой, чужой для
    `suite-lock`); `suite-lock --reason <основание> -- python <создать
    файл-след>`. Код выхода не 0, вывод содержит
    `suite_lock.describe(<держатель>)`, файла-следа нет, байты файла замка
    после вызова — те же, что до.

    Ловит мутацию: на занятом замке команда всё равно запускается
    (файл-след создан); отказ без описания держателя; уходя, `suite-lock`
    снимает или переписывает чужой замок (`release` без сверки pid,
    `_write` поверх); отказ с кодом 0.
    """
    seed, rng = seeded()
    groups, _pids = spawned
    task = "".join(rng.choice(ID_LETTERS) for _ in range(26))
    holder = {"task_id": task, "pid": os.getpid(), "run": None}
    if kind == "suite-run":
        holder["run"] = rng.randint(1, 9)
    elif kind == "notes":
        holder["task_id"] = None
        holder["kind"] = kind
    elif kind == EXTERNAL:
        holder.update(task_id=None, kind=kind, reason=phrase(rng))
    else:
        holder["kind"] = kind
    lock = suite_lock.path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(holder, ensure_ascii=False), encoding="utf-8")
    before = lock.read_bytes()
    trace = tmp_path / "trace"
    argv = ["--reason", phrase(rng), "--", sys.executable, "-c", TOUCH,
            str(trace)]

    status, out, _pid = run(logs, argv, groups)

    where = describe_case(seed, status, out)
    assert status not in (0, None), where
    assert suite_lock.describe(holder) in out, where
    assert not trace.exists(), where
    assert lock.read_bytes() == before, where
    assert "Traceback" not in out, where


# --------------------------------------------------------------- AC-4

def test_ac4_limit_stops_whole_group_releases_lock_code_124(logs, spawned):
    """По пределу `--limit 1` команда и её потомок остановлены не позже 15 с от запуска, замка нет, код 124, сообщение называет предел.

    Сценарий: `suite-lock --reason <основание> --limit 1 -- python
    <породить потомка, напечатать READY с обоими pid, спать 30 с>`. Тест
    читает строку READY, ждёт конца `suite-lock` и проверяет: с запуска
    прошло не больше 15 с, команды и её потомка нет (или они зомби), файла
    замка нет, код выхода 124, вывод `suite-lock` называет предел — число
    1 отдельным словом.

    Ловит мутацию: по пределу снимается замок, а команда работает дальше
    (код 124, но процессы живы 30 с); `SIGTERM` уходит только первому
    процессу группы — `os.kill` вместо группы, потомок команды жив;
    предел не соблюдается (команда доживает до своих 30 с); код выхода по
    пределу — код убитой команды (-15/143), а не 124; сообщение о пределе
    не выводится.
    """
    seed, rng = seeded()
    groups, pids = spawned
    argv = ["--reason", phrase(rng), "--limit", "1", "--", sys.executable,
            "-c", WITH_CHILD]

    started = time.monotonic()
    proc = start(logs, argv, groups)
    found, head = wait_ready(proc, pids)
    groups.extend(found[:1])
    status, out = finish(proc, head)
    elapsed = time.monotonic() - started

    where = describe_case(seed, status, out) + f"\nпрошло {elapsed:.1f} с"
    assert len(found) == 2, where
    assert elapsed <= STOP_WITHIN_SEC, where
    assert all(gone(pid) for pid in found), f"{where}\nживы: {found}"
    assert not suite_lock.path().exists(), where
    assert status == 124, where
    rest = out.replace(head, "", 1)
    assert any(word.strip(".,:;()«»") == "1" for word in rest.split()), where


# --------------------------------------------------------------- AC-6

def test_ac6_sigterm_stops_group_releases_lock_code_143(logs, spawned):
    """`SIGTERM` процессу `suite-lock` во время команды с потомком: оба остановлены не позже 15 с, замка нет, код 143.

    Сценарий: `suite-lock --reason <основание> -- python <породить
    потомка, напечатать READY с обоими pid, спать 30 с>`; по строке READY
    тест шлёт `SIGTERM` процессу `suite-lock` (не группе). Затем: с запуска
    прошло не больше 15 с, команды и её потомка нет (или они зомби), файла
    замка нет, код выхода 143.

    Ловит мутацию: обработчика `SIGTERM` нет — `suite-lock` умирает по
    сигналу (код -15), замок остаётся, команда в своей группе работает
    дальше; обработчик снимает замок, но группу команды не останавливает;
    останавливается только первый процесс группы (потомок жив); код
    выхода — 1 или код команды вместо `128 + 15`.
    """
    seed, rng = seeded()
    groups, pids = spawned
    argv = ["--reason", phrase(rng), "--", sys.executable, "-c", WITH_CHILD]

    started = time.monotonic()
    proc = start(logs, argv, groups)
    found, head = wait_ready(proc, pids)
    groups.extend(found[:1])
    if found:
        os.kill(proc.pid, signal.SIGTERM)
    status, out = finish(proc, head)
    elapsed = time.monotonic() - started

    where = describe_case(seed, status, out) + f"\nпрошло {elapsed:.1f} с"
    assert len(found) == 2, where
    assert elapsed <= STOP_WITHIN_SEC, where
    assert all(gone(pid) for pid in found), f"{where}\nживы: {found}"
    assert not suite_lock.path().exists(), where
    assert status == 143, where


# --------------------------------------------------------------- AC-7

@pytest.mark.parametrize("case", ["nothing_after_separator", "missing_file"])
def test_ac7_no_command_refused_and_lock_absent(logs, spawned, tmp_path,
                                                case):
    """Команды нет (`--` без продолжения, несуществующий исполняемый файл) — отказ, код не 0, файла замка нет.

    Сценарий: `suite-lock --reason <основание> --` и `suite-lock --reason
    <основание> -- <путь к несуществующему файлу во временном каталоге>`.
    Код выхода не 0, файла замка после вызова нет, вывод — текст отказа, а
    не трасса необработанного исключения.

    Ловит мутацию: ошибка запуска несуществующего файла (`OSError` из
    `Popen`) проходит мимо снятия замка — замок остаётся за мёртвым
    процессом `suite-lock` и файл лежит; исключение запуска падает
    трассой вместо отказа; пустая команда отдаётся `Popen` и роняет
    процесс `IndexError`; отказ с кодом 0.
    """
    seed, rng = seeded()
    groups, _pids = spawned
    tail = ([] if case == "nothing_after_separator"
            else [str(tmp_path / f"нет-{rng.randrange(10 ** 9)}")])
    argv = ["--reason", phrase(rng), "--", *tail]

    status, out, _pid = run(logs, argv, groups)

    where = describe_case(seed, status, out)
    assert status not in (0, None), where
    assert not suite_lock.path().exists(), where
    assert "Traceback" not in out, where


# --------------------------------------------------------------- AC-8

def test_ac8_gate_wait_names_external_holder(tmp_root, capsys, monkeypatch):
    """Гейт на замке вида `внешний` у живого чужого процесса ждёт и пишет запись об ожидании «внешней команды «<основание>» (pid N)».

    Связка: ожидание замка прогоном гейта (`acceptance.run_full_suite` →
    `_machine_lock` → `suite_lock.wait_acquire`) над файлом замка
    песочницы `tmp_root`. Сценарий: замок вида `внешний` за родительским
    процессом теста (живой, чужой), предел ожидания
    `config.FULL_SUITE_LOCK_WAIT_SEC` — 0; прогон набора не начат (pytest
    не позван), вывод несёт запись об ожидании с текстом держателя ровно
    «внешней команды «<основание>» (pid N)», файл замка не тронут.

    Ловит мутацию: `describe` не знает вида `внешний` — запись об ожидании
    называет «suite-run задачи None»; держатель вида `внешний` читается
    как брошенный — гейт снимает чужой замок и запускает прогон поверх
    внешней команды.
    """
    seed, rng = seeded()
    reason = phrase(rng)
    pid = os.getppid()
    holder = {"task_id": None, "pid": pid, "run": None, "kind": EXTERNAL,
              "reason": reason}
    lock = suite_lock.path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(holder, ensure_ascii=False), encoding="utf-8")
    before = lock.read_bytes()
    work = tmp_root.root / "work"
    (work / "tests").mkdir(parents=True)
    monkeypatch.setattr(config, "FULL_SUITE_LOCK_WAIT_SEC", 0)
    done = subprocess.CompletedProcess([], 0, "1 passed in 0.01s\n", "")

    with mock.patch.object(acceptance.subprocess, "run",
                           return_value=done) as pytest_run:
        green, note = acceptance.run_full_suite(work)

    out = capsys.readouterr().out
    expected = f"внешней команды «{reason}» (pid {pid})"
    where = f"зерно {seed}: вывод:\n{out}\nисход: {green} {note}"
    assert expected in out, where
    assert not green, where
    assert not [c for c in pytest_run.call_args_list
                if "pytest" in " ".join(map(str, c.args[0] if c.args else ()))
                ], where
    assert lock.read_bytes() == before, where


# --------------------------------------------------------------- AC-12

@pytest.mark.parametrize("case", [
    "limit_over", "limit_zero", "limit_negative", "limit_nonnumeric",
    "no_separator", "nothing_after_separator", "empty_reason",
    "reason_without_value", "no_reason",
])
def test_ac12_refusals_before_lock_reach_the_process(logs, spawned, tmp_path,
                                                      case):
    """Отказ разбора до взятия замка доходит до процесса `suite-lock`: код не 0, вывод несёт `suite_hold.refusal` на том же входе, замка и следа команды нет.

    Сценарий: входы AC-5 и AC-10, дающие отказ (предел больше разности
    настоящих `config.FULL_SUITE_LOCK_WAIT_SEC` и
    `config.FULL_SUITE_TIMEOUT_SEC`, `0`, `-5`, `x`; нет `--`, ничего после
    `--`, пустое основание, `--reason` без значения, нет `--reason`);
    команда, где она есть, — python, создающий файл-след. Текст отказа
    считается в тесте `suite_hold.refusal(argv)` и должен быть в выводе
    процесса.

    Ловит мутацию: `cmd_suite_lock` проверяет аргументы своим кодом, не
    `refusal`, и пропускает вход, на котором `refusal` отказывает
    (команда запускается — файл-след создан, код 0); разбор идёт после
    `acquire` — замок взят и (при сбое снятия) остаётся; отказ печатается
    без текста `refusal` или с кодом 0.
    """
    from orchestrator import suite_hold

    seed, rng = seeded()
    groups, _pids = spawned
    trace = tmp_path / "trace"
    command = [sys.executable, "-c", TOUCH, str(trace)]
    reason = phrase(rng)
    bound = config.FULL_SUITE_LOCK_WAIT_SEC - config.FULL_SUITE_TIMEOUT_SEC
    limit = {"limit_over": str(bound + 1), "limit_zero": "0",
             "limit_negative": "-5", "limit_nonnumeric": "x"}
    if case in limit:
        argv = ["--reason", reason, "--limit", limit[case], "--", *command]
    else:
        argv = {
            "no_separator": ["--reason", reason, *command],
            "nothing_after_separator": ["--reason", reason, "--"],
            "empty_reason": ["--reason", "", "--", *command],
            "reason_without_value": ["--reason", "--", *command],
            "no_reason": ["--", *command],
        }[case]
    text = suite_hold.refusal(argv)
    assert isinstance(text, str) and text, f"зерно {seed}: {argv} → {text!r}"

    status, out, _pid = run(logs, argv, groups)

    where = describe_case(seed, status, out) + f"\nотказ: {text!r}"
    assert status not in (0, None), where
    assert text in out, where
    assert not suite_lock.path().exists(), where
    assert not trace.exists(), where
